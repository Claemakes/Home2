// AI Room Manipulation for GlassRain Elevate
const API_ENDPOINT = '/api/ai/design-room';

// Function to handle room design changes
async function processDesignRequest(roomImage, designRequest) {
    try {
        // Create form data for sending the image and request
        const formData = new FormData();
        formData.append('room_image', roomImage);
        formData.append('design_request', designRequest);
        
        // Show loading state
        showLoadingState('Processing your design request...');
        
        // Send the request to the backend
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Failed to process design request');
        }
        
        const result = await response.json();
        
        // Hide loading state
        hideLoadingState();
        
        if (result.success) {
            // Update the room display with the new image
            updateRoomDisplay(result.modified_image_url);
            
            // Return the AI description of changes
            return result.ai_description;
        } else {
            throw new Error(result.error || 'Unknown error occurred');
        }
    } catch (error) {
        console.error('Error processing design request:', error);
        hideLoadingState();
        return 'I encountered an error trying to process your design request. Please try again.';
    }
}

// Function to capture room from camera or file upload
function captureRoomImage(source) {
    return new Promise((resolve, reject) => {
        if (source === 'camera') {
            // For demo purposes, we'll use a placeholder
            // In production, this would access the device camera
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Failed to load camera image'));
            img.src = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
                '<rect width="100%" height="100%" fill="#2a2a2a"/>' +
                '<rect x="100" y="250" width="600" height="300" fill="#333"/>' +
                '<rect x="150" y="50" width="500" height="200" fill="#444"/>' +
                '<circle cx="400" cy="300" r="50" fill="#555"/>' +
                '<text x="400" y="300" font-family="Arial" font-size="20" fill="#999" text-anchor="middle">Camera Room Image</text>' +
                '</svg>'
            );
        } else if (source === 'upload') {
            // Create file input and trigger click
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        const img = new Image();
                        img.onload = () => resolve(img);
                        img.onerror = () => reject(new Error('Failed to load uploaded image'));
                        img.src = event.target.result;
                    };
                    reader.onerror = () => reject(new Error('Failed to read file'));
                    reader.readAsDataURL(file);
                } else {
                    reject(new Error('No file selected'));
                }
            };
            fileInput.click();
        } else {
            reject(new Error('Invalid source'));
        }
    });
}

// Helper function to update room display
function updateRoomDisplay(imageUrl) {
    const roomDisplay = document.querySelector('.room-image-large');
    roomDisplay.innerHTML = '';
    
    const img = document.createElement('img');
    img.src = imageUrl;
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.objectFit = 'contain';
    
    roomDisplay.appendChild(img);
}

// Loading state functions
function showLoadingState(message) {
    const loadingEl = document.createElement('div');
    loadingEl.id = 'ai-loading-overlay';
    loadingEl.style.position = 'absolute';
    loadingEl.style.top = '0';
    loadingEl.style.left = '0';
    loadingEl.style.right = '0';
    loadingEl.style.bottom = '0';
    loadingEl.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
    loadingEl.style.display = 'flex';
    loadingEl.style.flexDirection = 'column';
    loadingEl.style.alignItems = 'center';
    loadingEl.style.justifyContent = 'center';
    loadingEl.style.zIndex = '1000';
    loadingEl.style.borderRadius = '12px';
    
    const spinner = document.createElement('div');
    spinner.style.width = '50px';
    spinner.style.height = '50px';
    spinner.style.border = '3px solid rgba(194, 158, 73, 0.3)';
    spinner.style.borderRadius = '50%';
    spinner.style.borderTopColor = '#C29E49';
    spinner.style.animation = 'aiSpin 1s linear infinite';
    
    const messageEl = document.createElement('p');
    messageEl.textContent = message || 'Processing...';
    messageEl.style.color = '#fff';
    messageEl.style.marginTop = '20px';
    
    loadingEl.appendChild(spinner);
    loadingEl.appendChild(messageEl);
    
    // Add the animation if it doesn't exist
    if (!document.getElementById('ai-spin-animation')) {
        const style = document.createElement('style');
        style.id = 'ai-spin-animation';
        style.textContent = '@keyframes aiSpin { to { transform: rotate(360deg); } }';
        document.head.appendChild(style);
    }
    
    document.querySelector('.room-display').appendChild(loadingEl);
}

function hideLoadingState() {
    const loadingEl = document.getElementById('ai-loading-overlay');
    if (loadingEl) {
        loadingEl.remove();
    }
}

// Export functions for use in elevate.html
window.ElevateAI = {
    processDesignRequest,
    captureRoomImage,
    updateRoomDisplay
};