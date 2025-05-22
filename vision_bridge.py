from fastapi import FastAPI, Response, UploadFile, File
import mss
import io
from PIL import Image
import subprocess
import tempfile
import os
import json

app = FastAPI()

# Configuration for llama.cpp
# Assuming vision_bridge.py is in the project root where a 'models' directory exists
MODEL_PATH = "models/smolvlm2-q4km.gguf"
MMPROJ_PATH = "models/smolvlm2-mmproj-f16.gguf"
JSON_SCHEMA_PATH = "schemas/grid.json" # Added JSON schema path
# Assumes 'llama-mtmd-cli' is in the system PATH
# If not, you might need to provide a full path or ensure llama.cpp/build/bin is in PATH
LLAMA_MTMD_CLI_PATH = "llama-mtmd-cli"
PROMPT_TEMPLATE = "<image>\n<|end|>\nDescribe screen using 16x9 grid."


@app.get("/screenshot")
async def get_screenshot():
    try:
        with mss.mss() as sct:
            # Get a screenshot of the primary monitor
            # sct.monitors[0] is all monitors together, [1] is the primary, [2] is secondary, etc.
            # Adjust if you want a different monitor or all monitors combined.
            monitor_number = 1 # Primary monitor
            if len(sct.monitors) <= monitor_number:
                # Fallback if primary monitor (index 1) isn't found (e.g., only one virtual display like sct.monitors[0])
                # or handle more gracefully based on desired behavior.
                # For now, grab the first available monitor details if primary isn't explicitly [1]
                monitor_to_grab = sct.monitors[0] if sct.monitors else None
            else:
                monitor_to_grab = sct.monitors[monitor_number]

            if not monitor_to_grab:
                return Response(content="No monitors found to capture.", status_code=500)

            sct_img = sct.grab(monitor_to_grab)

            # Create a BytesIO object and save the image to it in PNG format
            img_byte_arr = io.BytesIO()
            # Create a PIL Image from the BGRA data captured by mss
            # Use sct_img.bgra and specify the raw decoder for BGRA format
            pil_image = Image.frombytes("RGBA", sct_img.size, sct_img.bgra, "raw", "BGRA")
            # Save the PIL Image to the BytesIO object in PNG format
            pil_image.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0) # Go to the beginning of the BytesIO buffer

            return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        return Response(content=f"Error capturing screenshot: {e}", status_code=500)

@app.post("/predict")
async def post_predict(image: UploadFile = File(...)):
    tmp_image_path = None  # Ensure tmp_image_path is defined for the finally block
    try:
        # Check if model, projector, and schema files exist
        if not os.path.exists(MODEL_PATH):
            return {"error": f"Model file not found: {MODEL_PATH}"}, 500
        if not os.path.exists(MMPROJ_PATH):
            return {"error": f"Projector file not found: {MMPROJ_PATH}"}, 500
        if not os.path.exists(JSON_SCHEMA_PATH):
            return {"error": f"JSON schema file not found: {JSON_SCHEMA_PATH}"}, 500

        # Read JSON schema content
        try:
            with open(JSON_SCHEMA_PATH, 'r') as f_schema:
                json_schema_content = f_schema.read()
            # Validate if it's proper JSON, as llama-mtmd-cli is sensitive
            json.loads(json_schema_content) 
        except FileNotFoundError:
            return {"error": f"JSON schema file not found during read: {JSON_SCHEMA_PATH}"}, 500
        except json.JSONDecodeError as e_schema_json:
            return {"error": f"Invalid JSON in schema file {JSON_SCHEMA_PATH}: {e_schema_json}"}, 500
        except Exception as e_schema_read:
            return {"error": f"Error reading JSON schema file {JSON_SCHEMA_PATH}: {e_schema_read}"}, 500

        # Save uploaded image to a temporary file
        # The CLI expects a file path, and the image will be JPEG as per ProjectGuide.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_image_file:
            content = await image.read()
            tmp_image_file.write(content)
            tmp_image_path = tmp_image_file.name
        
        cmd = [
            LLAMA_MTMD_CLI_PATH,
            "-m", MODEL_PATH,
            "--mmproj", MMPROJ_PATH,
            "-p", PROMPT_TEMPLATE,
            "--image", tmp_image_path,
            "-ngl", "35",      # Number of GPU layers, from previous test
            "--temp", "0.1",   # Temperature, from previous test
            "-e",             # Escape prompt, from previous test
            "--json-schema", json_schema_content # Pass schema content as string
        ]

        # Run the command
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if process.returncode != 0:
            error_message = (
                f"llama-mtmd-cli failed with exit code {process.returncode}.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Stderr: {process.stderr}\n"
                f"Stdout: {process.stdout}"
            )
            print(error_message)
            return {"error": "Model inference failed", "details": error_message}, 500

        # Extract JSON from stdout (it might be embedded in logs)
        output_content = process.stdout.strip()
        json_start_index = output_content.find('{')
        json_end_index = output_content.rfind('}')

        if json_start_index != -1 and json_end_index != -1 and json_start_index < json_end_index:
            json_string = output_content[json_start_index : json_end_index+1]
            try:
                result_json = json.loads(json_string)
            except json.JSONDecodeError as e_json:
                error_message = (
                    f"Failed to decode JSON from extracted string.\nError: {e_json}\n"
                    f"Extracted string: {json_string}\nFull stdout: {process.stdout}"
                )
                print(error_message)
                return {"error": "Failed to parse model output", "details": error_message}, 500
        else:
            error_message = (
                f"Could not find JSON object in llama-mtmd-cli output.\n"
                f"Stdout: {process.stdout}"
            )
            print(error_message)
            return {"error": "No JSON output from model", "details": error_message}, 500
            
        return result_json

    except Exception as e_main:
        print(f"Error in /predict endpoint: {e_main}")
        return {"error": f"An unexpected error occurred: {str(e_main)}"}, 500
    finally:
        if tmp_image_path and os.path.exists(tmp_image_path):
            os.remove(tmp_image_path)

if __name__ == "__main__":
    import uvicorn
    # It's common to run uvicorn from the command line:
    # uvicorn vision_bridge:app --reload --port 8000
    # But for direct script execution (less common for production):
    uvicorn.run(app, host="0.0.0.0", port=8000)
