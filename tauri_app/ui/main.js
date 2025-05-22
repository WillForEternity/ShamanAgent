// Shaman Agent UI JavaScript will go here
console.log("Shaman Agent UI loaded");

const screenshotImg = document.getElementById('screenshot-thumbnail');
const screenshotApiUrl = 'http://127.0.0.1:8000/screenshot';

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

// Update screenshot when the page loads
updateScreenshot();

// Update screenshot every 2 seconds (2000 milliseconds)
setInterval(updateScreenshot, 2000);
