import { listen } from '@tauri-apps/api/event'; 

// Shaman Agent UI JavaScript will go here
console.log("Shaman Agent UI loaded");

const screenshotImg = document.getElementById('screenshot-thumbnail');
const screenshotApiUrl = 'http://127.0.0.1:8000/screenshot';
const predictApiUrl = 'http://127.0.0.1:8000/predict'; 

async function updateScreenshot() {
    console.log('Fetching screenshot for display...');
    try {
        const response = await fetch(screenshotApiUrl);
        if (!response.ok) {
            console.error('Failed to fetch screenshot for display:', response.status, response.statusText);
            return;
        }
        const imageBlob = await response.blob();
        const imageUrl = URL.createObjectURL(imageBlob);
        screenshotImg.src = imageUrl;
    } catch (error) {
        console.error('Error fetching screenshot for display:', error);
    }
}

async function getScreenshotBlob() {
    console.log('Fetching screenshot blob for analysis...');
    try {
        const response = await fetch(screenshotApiUrl);
        if (!response.ok) {
            console.error('Failed to fetch screenshot blob:', response.status, response.statusText);
            return null;
        }
        const imageBlob = await response.blob();
        console.log('Screenshot blob fetched successfully.');
        return imageBlob;
    } catch (error) {
        console.error('Error fetching screenshot blob:', error);
        return null;
    }
}

async function handleScreenAnalysis() {
    console.log('Hotkey triggered! Initiating screen analysis...');
    try {
        const imageBlob = await getScreenshotBlob();
        if (!imageBlob) {
            console.error('Could not get screenshot blob for analysis. Aborting.');
            return;
        }

        const formData = new FormData();
        formData.append('image', imageBlob, 'screenshot.png');

        console.log('Sending screenshot to /predict endpoint...');
        const response = await fetch(predictApiUrl, {
            method: 'POST',
            body: formData, 
        });

        if (!response.ok) {
            const errorText = await response.text(); 
            console.error('Failed to send image for prediction:', response.status, response.statusText, errorText);
            return;
        }

        const predictionResult = await response.json();
        console.log('Prediction Result:', predictionResult);
        // TODO: Update UI with the prediction result (overall description, grid, actionable items)

    } catch (error) {
        console.error('Error during screen analysis process:', error);
    }
}

async function initializeApp() {
    updateScreenshot();

    setInterval(updateScreenshot, 2000);

    try {
        await listen('trigger_screen_analysis', handleScreenAnalysis);
        console.log('Successfully listening for "trigger_screen_analysis" hotkey event.');
    } catch (e) {
        console.error('Failed to set up listener for trigger_screen_analysis:', e);
    }
}

initializeApp();
