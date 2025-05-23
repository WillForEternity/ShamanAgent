from fastapi import FastAPI, Response, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import mss
import io
from PIL import Image
import asyncio
import tempfile
import os
import json
import uuid
import traceback # Added for more detailed error logging

app = FastAPI()

# CORS configuration
origins = [
    "http://localhost:1420",    # Common Tauri dev server port
    "http://127.0.0.1:1420",   # Alternative for localhost
    "http://localhost:1430",    # Port from user's error log
    "http://127.0.0.1:1430",   # Alternative for localhost from error log
    "tauri://localhost",        # For production Tauri builds
    "http://localhost:8000",    # For local testing of the API itself
    "http://127.0.0.1:8000"   # For local testing of the API itself
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"]   # Allows all headers
)

# Configuration for llama.cpp
# Assuming vision_bridge.py is in the project root where a 'models' directory exists
MODEL_PATH = "models/smolvlm2-q4km.gguf"
MMPROJ_PATH = "models/smolvlm2-mmproj-f16.gguf"
# Assumes 'llama-mtmd-cli' is in the system PATH
# If not, you might need to provide a full path or ensure llama.cpp/build/bin is in PATH
LLAMA_MTMD_CLI_PATH = "llama-mtmd-cli"

# MODIFIED PROMPT_TEMPLATE:
# Removed the non-standard "<|end|>" token.
# This provides a clear instruction after the image placeholder.
PROMPT_TEMPLATE = "<image>\nDescribe the content of the screen."

# In-memory store for task statuses and results
tasks = {}

async def _run_model_inference_task(task_id: str, image_path: str):
    """Helper function to run the model inference in the background."""
    try:
        # Ensure model and projector files exist (already checked in main endpoint but good for standalone task)
        if not os.path.exists(MODEL_PATH) or not os.path.exists(MMPROJ_PATH):
            tasks[task_id] = {"status": "failed", "error": "Model or MMProj file not found during task execution."}
            return

        cmd = [
            LLAMA_MTMD_CLI_PATH,
            "-m", MODEL_PATH,
            "--mmproj", MMPROJ_PATH,
            "-p", PROMPT_TEMPLATE,
            "--image", image_path,
            "-ngl", "35", # Number of layers to offload to GPU
            "--temp", "0.1",
            "-e", # Process escaped sequences in prompt
            "-t", "4", # Number of threads (CPU)
            # "-c", "2048", # Optionally set context size if default is problematic
            # "--no-warmup" # Consider adding this if warmup is causing issues, though it's generally good.
        ]

        print(f"Task {task_id}: Not using JSON schema for output.")

        print(f"Task {task_id}: Running async command: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await process.communicate()

        stdout_str = stdout_bytes.decode('utf-8', errors='ignore').strip()
        stderr_str = stderr_bytes.decode('utf-8', errors='ignore').strip()

        if process.returncode != 0:
            error_details = (
                f"llama-mtmd-cli failed with exit code {process.returncode}.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stderr: {stderr_str}\n"
                f"Stdout: {stdout_str}"
            )
            print(f"Task {task_id}: {error_details}")
            tasks[task_id] = {"status": "failed", "error": "Model inference failed", "details": error_details}
            return

        # Parse output: expect plain text description
        if stdout_str:
             tasks[task_id] = {"status": "completed", "result": {"description": stdout_str.strip()}}
             print(f"Task {task_id}: Model output (plain text): {stdout_str.strip()}")
        else:
            error_details = f"Model produced no output. Stderr: {stderr_str}"
            print(f"Task {task_id}: {error_details}")
            tasks[task_id] = {"status": "failed", "error": "No output from model", "details": error_details}

    except Exception as e_task:
        print(f"Task {task_id}: Error during model inference task: {e_task}")
        traceback.print_exc()
        tasks[task_id] = {"status": "failed", "error": "An unexpected error occurred during task execution", "details": str(e_task)}
    finally:
        if image_path and os.path.exists(image_path):
            print(f"Task {task_id}: Cleaning up temporary image: {image_path}")
            try:
                os.remove(image_path)
            except Exception as e_remove:
                print(f"Task {task_id}: Error cleaning up temp file {image_path}: {e_remove}")

@app.post("/predict")
async def post_predict_start_task(image: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    # Ensure model and projector files exist (quick check before starting task)
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model file not found at {MODEL_PATH}")
        raise HTTPException(status_code=500, detail="Model file not found")
    if not os.path.exists(MMPROJ_PATH):
        print(f"Error: MMProj file not found at {MMPROJ_PATH}")
        raise HTTPException(status_code=500, detail="MMProj file not found")

    tmp_image_path = None
    try:
        # Save uploaded image to a temporary file that the background task can access
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_image_file:
            content = await image.read()
            tmp_image_file.write(content)
            tmp_image_path = tmp_image_file.name
        
        task_id = str(uuid.uuid4())
        tasks[task_id] = {"status": "processing"} # Initial status

        print(f"Scheduling background task {task_id} with image {tmp_image_path}")
        background_tasks.add_task(_run_model_inference_task, task_id, tmp_image_path)
        
        return {"task_id": task_id, "status": "processing"}

    except Exception as e_main:
        print(f"Error in /predict (start_task) endpoint: {e_main}")
        traceback.print_exc()
        # Clean up temp file if created and an error occurs before task scheduling
        if tmp_image_path and os.path.exists(tmp_image_path):
            try:
                os.remove(tmp_image_path)
            except Exception as e_remove_main:
                print(f"Error cleaning up temp file {tmp_image_path} in main predict endpoint: {e_remove_main}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e_main)}")

@app.get("/predict/result/{task_id}")
async def get_predict_result(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] == "completed":
        return {"task_id": task_id, "status": "completed", "result": task.get("result")}
    elif task["status"] == "failed":
        return {"task_id": task_id, "status": "failed", "error": task.get("error"), "details": task.get("details")}
    else: # processing
        return {"task_id": task_id, "status": "processing"}

@app.get("/screenshot")
async def get_screenshot():
    try:
        with mss.mss() as sct:
            monitor_number = 1 # Primary monitor
            if len(sct.monitors) <= monitor_number:
                monitor_to_grab = sct.monitors[0] if sct.monitors else None
            else:
                monitor_to_grab = sct.monitors[monitor_number]

            if not monitor_to_grab:
                print("Error: No monitors found to capture.")
                raise HTTPException(status_code=500, detail="No monitors found to capture.")

            sct_img = sct.grab(monitor_to_grab)

            img_byte_arr = io.BytesIO()
            pil_image = Image.frombytes("RGBA", sct_img.size, sct_img.bgra, "raw", "BGRA")
            pil_image.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)

            return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error capturing screenshot: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # To run: uvicorn vision_bridge:app --reload --port 8000
    print("Starting Uvicorn server on http://0.0.0.0:8000")
    print(f"Model Path: {MODEL_PATH}")
    print(f"MMProj Path: {MMPROJ_PATH}")
    print(f"Llama CLI Path: {LLAMA_MTMD_CLI_PATH}")
    print(f"Prompt Template: {PROMPT_TEMPLATE}")
    uvicorn.run(app, host="0.0.0.0", port=8000)