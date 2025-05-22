from fastapi import FastAPI, Response
import mss
import io
from PIL import Image

app = FastAPI()

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
async def post_predict():
    # Placeholder for model prediction logic
    # This will receive JPEG image bytes and return JSON grid labels
    return {"message": "Predict endpoint not yet implemented"}

if __name__ == "__main__":
    import uvicorn
    # It's common to run uvicorn from the command line:
    # uvicorn vision_bridge:app --reload --port 8000
    # But for direct script execution (less common for production):
    uvicorn.run(app, host="0.0.0.0", port=8000)
