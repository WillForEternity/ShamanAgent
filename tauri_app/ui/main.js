// Shaman Agent UI JavaScript will go here
console.log("Shaman Agent UI loaded");

const screenshotImg = document.getElementById('screenshot-thumbnail');
const predictButton = document.getElementById('predict-button');
const descriptionArea = document.getElementById('description-area');

const screenshotApiUrl = 'http://127.0.0.1:8000/screenshot';
const predictApiUrl = 'http://127.0.0.1:8000/predict';

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

        // 2. Send this blob to the /predict endpoint
        const formData = new FormData();
        formData.append('image', imageBlob, 'screenshot.png'); // Changed 'file' to 'image'

        const predictResponse = await fetch(predictApiUrl, {
            method: 'POST',
            body: formData,
        });

        if (!predictResponse.ok) {
            const errorText = await predictResponse.text();
            throw new Error(`Prediction request failed: ${predictResponse.status} ${predictResponse.statusText} - ${errorText}`);
        }

        const result = await predictResponse.json();
        console.log('Prediction result:', result);

        // 3. Display the description
        if (result && result.description) {
            // Sanitize and format the description if needed. For now, direct display.
            // Replace newlines with <br> for HTML display
            const formattedDescription = result.description.replace(/\n/g, '<br>');
            descriptionArea.innerHTML = `<p>${formattedDescription}</p>`;
        } else {
            descriptionArea.innerHTML = '<p>No description received from the model.</p>';
        }

    } catch (error) {
        console.error('Error during prediction:', error);
        descriptionArea.innerHTML = `<p style="color: #ffdddd;">Error: ${error.message}</p>`;
    } finally {
        predictButton.disabled = false;
    }
}

// Event listener for the predict button
if (predictButton) {
    predictButton.addEventListener('click', handlePrediction);
} else {
    console.error('Predict button not found on page load.');
}

// Update screenshot when the page loads
updateScreenshot();

// Update screenshot every 2 seconds (2000 milliseconds)
setInterval(updateScreenshot, 2000);
