// Shaman Agent UI JavaScript will go here
console.log("Shaman Agent UI loaded");

const screenshotImg = document.getElementById('screenshot-thumbnail');
const predictButton = document.getElementById('predict-button');
const descriptionArea = document.getElementById('description-area');

const screenshotApiUrl = 'http://localhost:8000/screenshot';
const predictApiUrl = 'http://localhost:8000/predict'; // This will now start the task
const predictResultApiUrlBase = 'http://localhost:8000/predict/result/'; // For polling

let pollingIntervalId = null; // To store the interval ID for polling

document.addEventListener('DOMContentLoaded', () => {
    // Initial screenshot load
    updateScreenshot();

    // Set interval to refresh screenshot (e.g., every 5 seconds)
    setInterval(updateScreenshot, 5000);

    if (predictButton) {
        predictButton.addEventListener('click', () => {
            // Clear any previous polling
            if (pollingIntervalId) {
                clearInterval(pollingIntervalId);
                pollingIntervalId = null;
            }
            handlePrediction();
        });
    }
});

async function updateScreenshot() {
    console.log('Fetching screenshot...');
    try {
        const response = await fetch(screenshotApiUrl);
        if (!response.ok) {
            console.error('Failed to fetch screenshot:', response.status, response.statusText);
            // Optionally, display a placeholder or error image
            // screenshotImg.src = 'path/to/error-image.png'; 
            return;
        }
        const imageBlob = await response.blob();
        const imageUrl = URL.createObjectURL(imageBlob);
        screenshotImg.src = imageUrl;
        console.log('Screenshot updated.');
    } catch (error) {
        console.error('Error fetching screenshot:', error);
        // Optionally, display a placeholder or error image
        // screenshotImg.src = 'path/to/error-image.png'; 
    }
}

async function handlePrediction() {
    if (!predictButton || !descriptionArea) {
        console.error('Prediction UI elements not found.');
        return;
    }

    console.log('Starting prediction...');
    descriptionArea.innerHTML = '<p>Analyzing screen...</p>'; // Use innerHTML to clear previous content with a paragraph
    predictButton.disabled = true;

    try {
        // 1. Fetch the current screenshot as a blob
        const screenshotResponse = await fetch(screenshotApiUrl);
        if (!screenshotResponse.ok) {
            throw new Error(`Failed to fetch screenshot: ${screenshotResponse.status} ${screenshotResponse.statusText}`);
        }
        const imageBlob = await screenshotResponse.blob();

        // 2. Send this blob to the /predict endpoint to start the task
        const formData = new FormData();
        formData.append('image', imageBlob, 'screenshot.png'); // 'image' is the expected field name by FastAPI

        const initialPredictResponse = await fetch(predictApiUrl, {
            method: 'POST',
            body: formData,
        });

        if (!initialPredictResponse.ok) {
            const errorText = await initialPredictResponse.text();
            throw new Error(`Failed to start prediction task: ${initialPredictResponse.status} ${initialPredictResponse.statusText} - ${errorText}`);
        }

        const taskData = await initialPredictResponse.json();

        if (taskData.task_id && taskData.status === 'processing') {
            descriptionArea.innerHTML = `Processing analysis (Task ID: ${taskData.task_id})...`;
            // Start polling for the result
            pollingIntervalId = setInterval(() => {
                pollForResult(taskData.task_id, descriptionArea, predictButton);
            }, 3000); // Poll every 3 seconds
        } else {
            throw new Error('Failed to get a valid task ID from the server.');
        }

    } catch (error) {
        console.error('Error starting prediction:', error);
        descriptionArea.innerHTML = `<p style="color: #ffdddd;">Error: ${error.message}</p>`;
        predictButton.disabled = false;
    }
}

async function pollForResult(taskId, descriptionArea, predictButton) {
    try {
        const resultResponse = await fetch(`${predictResultApiUrlBase}${taskId}`);
        if (!resultResponse.ok) {
            // Stop polling on server error for the result endpoint
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
            throw new Error(`Polling failed: ${resultResponse.status} ${resultResponse.statusText}`);
        }

        const data = await resultResponse.json();

        if (data.status === 'completed') {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
            displayPredictionResult(data.result, descriptionArea);
            predictButton.disabled = false;
        } else if (data.status === 'failed') {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
            let errorMsg = `<p style="color: #ffdddd;">Analysis failed: ${data.error || 'Unknown error'}</p>`;
            if (data.details) {
                errorMsg += `<p style="color: #ffdddd;">Details: ${data.details}</p>`;
            }
            descriptionArea.innerHTML = errorMsg;
            predictButton.disabled = false;
        } else if (data.status === 'processing') {
            // Still processing, continue polling. Update UI if desired.
            descriptionArea.innerHTML = `Processing analysis (Task ID: ${taskId})... (Status: ${data.status})`;
        } else {
            // Unknown status, stop polling
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
            throw new Error(`Unknown task status: ${data.status}`);
        }
    } catch (error) {
        console.error('Error polling for result:', error);
        // Stop polling on any error during polling itself
        if (pollingIntervalId) {
            clearInterval(pollingIntervalId);
            pollingIntervalId = null;
        }
        descriptionArea.innerHTML = `<p style="color: #ffdddd;">Error polling for results: ${error.message}</p>`;
        predictButton.disabled = false;
    }
}

function displayPredictionResult(data, descriptionArea) {
    if (!data) {
        descriptionArea.innerHTML = `<p class="error">Error: No result data received.</p>`;
        return;
    }
    if (data.error) {
        descriptionArea.innerHTML = `<p class="error">Error from model: ${data.error}</p>`;
        if (data.details) {
            descriptionArea.innerHTML += `<p class="error-details">Details: ${data.details}</p>`;
        }
    } else if (data.description) {
        // Sanitize and format the description if needed. For now, direct display.
        // Replace newlines with <br> for HTML display if desired, or use <pre> for preformatted text.
        const formattedDescription = data.description.replace(/\n/g, '<br>');
        descriptionArea.innerHTML = `<h3>Description:</h3><p>${formattedDescription}</p>`;
    } else {
        descriptionArea.innerHTML = `<p class="error">No description provided by the model.</p>`;
    }
}

// Helper to update UI elements consistently
