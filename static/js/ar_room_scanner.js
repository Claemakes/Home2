/**
 * GlassRain AR Room Scanner 
 * Advanced room scanning and AI-powered design recommendations
 */

document.addEventListener('DOMContentLoaded', function() {
    initARScanInterface();
    setupRoomTabs();
    setupChatInterface();
});

/**
 * Initialize the AR Scan Interface
 */
function initARScanInterface() {
    console.log("Initializing AR Room Scanner...");
    
    // Set up 3D house model (floor plan view)
    setupFloorPlanModel();
    
    // Initialize scan markers
    initializeScanMarkers();
    
    // Setup AI design assistant
    setupAIDesignAssistant();
    
    // Setup chat interface
    setupChatInterface();
}

/**
 * Setup the room tabs at the top of the interface
 */
function setupRoomTabs() {
    // Room tabs selection
    const roomTabs = document.querySelectorAll('.room-tab');
    
    roomTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Remove active class from all tabs
            roomTabs.forEach(t => t.classList.remove('active'));
            
            // Add active class to clicked tab
            this.classList.add('active');
            
            // Handle tab switching logic
            const tabText = this.textContent.trim();
            console.log(`Switching to ${tabText} tab`);
            
            // Change visualization content based on selected tab
            if (tabText === 'AR SCAN ROOM') {
                document.getElementById('scan-view').style.display = 'block';
                document.getElementById('saved-rooms').style.display = 'none';
                document.getElementById('saved-carts').style.display = 'none';
            } else if (tabText === 'CREATED ROOMS') {
                document.getElementById('scan-view').style.display = 'none';
                document.getElementById('saved-rooms').style.display = 'block';
                document.getElementById('saved-carts').style.display = 'none';
            } else if (tabText === 'SAVED CARTS') {
                document.getElementById('scan-view').style.display = 'none';
                document.getElementById('saved-rooms').style.display = 'none';
                document.getElementById('saved-carts').style.display = 'block';
            }
        });
    });
}

/**
 * Initialize the 3D floor plan model
 */
function setupFloorPlanModel() {
    // Initialize Three.js scene
    const container = document.getElementById('room-visualization');
    if (!container) return;
    
    // Scene setup code would go here in production
    console.log('3D floor plan initialized');
    
    // For demo purposes, we'll just make sure the container is visible
    container.style.display = 'block';
}

/**
 * Initialize the interactive SCAN markers on the floor plan
 */
function initializeScanMarkers() {
    // Set up interactive SCAN markers on the floor plan
    const scanMarkers = document.querySelectorAll('.scan-marker');
    const roomScanImage = document.getElementById('roomScanImage');
    const scanPlaceholder = document.getElementById('scanPlaceholder');
    
    scanMarkers.forEach((marker, index) => {
        marker.addEventListener('click', function() {
            // Visual feedback during scanning
            const originalText = marker.textContent;
            marker.textContent = 'SCANNING...';
            marker.style.backgroundColor = 'var(--gold)';
            marker.style.color = '#000';
            
            // Simulate scanning process
            setTimeout(() => {
                marker.textContent = 'SCANNED';
                
                // Show scanned room preview
                if (roomScanImage && scanPlaceholder) {
                    roomScanImage.style.display = 'block';
                    // Use a data URI for placeholder image
                    roomScanImage.src = createRoomScanPlaceholder(index);
                    scanPlaceholder.style.display = 'none';
                }
                
                // Dispatch room scanned event
                const event = new CustomEvent('roomScanned', {
                    detail: {
                        roomArea: `Room Area ${index + 1}`,
                        position: { x: marker.style.left, y: marker.style.top }
                    }
                });
                document.dispatchEvent(event);
            }, 1500);
        });
    });
    
    // Setup scan button
    const scanRoomBtn = document.getElementById('scanRoomBtn');
    if (scanRoomBtn) {
        scanRoomBtn.addEventListener('click', analyzeRoomPhoto);
    }
}

/**
 * Generate different room placeholder images based on index
 */
function createRoomScanPlaceholder(index) {
    const roomTypes = ['Living Room', 'Kitchen', 'Bedroom', 'Bathroom'];
    const roomType = roomTypes[index % roomTypes.length];
    
    return 'data:image/svg+xml;charset=UTF-8,' + 
        encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200" viewBox="0 0 300 200">
            <rect width="100%" height="100%" fill="#333"/>
            <text x="50%" y="50%" font-family="Arial" font-size="20" fill="#999" text-anchor="middle">${roomType} Scan</text>
        </svg>`);
}

/**
 * Analyze the room photo and generate AI suggestions
 */
function analyzeRoomPhoto() {
    const roomScanImage = document.getElementById('roomScanImage');
    const scanRoomBtn = document.getElementById('scanRoomBtn');
    const designSuggestions = document.getElementById('designSuggestions');
    
    if (!roomScanImage || roomScanImage.style.display === 'none') {
        alert('Please scan a room first');
        return;
    }
    
    // Visual feedback during analysis
    scanRoomBtn.disabled = true;
    scanRoomBtn.innerHTML = '<span>Analyzing...</span>';
    
    // Get the selected room type
    const roomType = document.getElementById('roomType').value;
    
    // Get the design request text
    const designRequest = document.getElementById('designRequest').value;
    
    // In production, this would call the OpenAI API with the scan image
    // Here we simulate the API call with a timeout
    setTimeout(() => {
        generateDesignSuggestions(roomType, designRequest, designSuggestions);
        
        // Reset button state
        scanRoomBtn.disabled = false;
        scanRoomBtn.innerHTML = '<span>Analyze Room Photo</span>';
    }, 2000);
}

/**
 * Generate design suggestions based on room type and design request
 */
function generateDesignSuggestions(roomType, designRequest, container) {
    const suggestions = [];
    
    // Basic suggestions based on room type
    if (roomType === 'living_room') {
        suggestions.push({
            title: 'Update Lighting Fixtures',
            description: 'Replace outdated ceiling light with modern pendant light to increase brightness and add style.',
            price: 'Estimated cost: $150-$300'
        });
        suggestions.push({
            title: 'Wall Refresh',
            description: 'Paint walls in a lighter neutral tone to make the space feel larger and more modern.',
            price: 'Estimated cost: $200-$450'
        });
        suggestions.push({
            title: 'Smart Home Integration',
            description: 'Install smart lighting and thermostat controls for improved energy efficiency.',
            price: 'Estimated cost: $350-$600'
        });
    } else if (roomType === 'kitchen') {
        suggestions.push({
            title: 'Cabinet Hardware Update',
            description: 'Replace dated cabinet knobs and pulls with modern alternatives for an instant refresh.',
            price: 'Estimated cost: $100-$250'
        });
        suggestions.push({
            title: 'Backsplash Installation',
            description: 'Add a subway tile backsplash in a classic white or light gray tone.',
            price: 'Estimated cost: $400-$800'
        });
        suggestions.push({
            title: 'Under-Cabinet Lighting',
            description: 'Install LED lighting under cabinets to improve task lighting and ambiance.',
            price: 'Estimated cost: $200-$350'
        });
    } else if (roomType === 'bedroom') {
        suggestions.push({
            title: 'Accent Wall',
            description: 'Create a focal point with an accent wall using paint or removable wallpaper.',
            price: 'Estimated cost: $150-$300'
        });
        suggestions.push({
            title: 'Lighting Upgrade',
            description: 'Add bedside pendant lights to free up nightstand space and add designer style.',
            price: 'Estimated cost: $200-$400'
        });
        suggestions.push({
            title: 'Window Treatment',
            description: 'Install blackout curtains with decorative panels for better sleep and aesthetics.',
            price: 'Estimated cost: $250-$500'
        });
    } else {
        suggestions.push({
            title: 'General Improvement',
            description: 'Based on your scan, we recommend updating fixtures and paint for a modern refresh.',
            price: 'Estimated cost: $300-$600'
        });
    }
    
    // Render suggestions
    let suggestionsHTML = '';
    suggestions.forEach(suggestion => {
        suggestionsHTML += `
            <div class="suggestion-card">
                <div class="suggestion-title">${suggestion.title}</div>
                <div class="suggestion-description">${suggestion.description}</div>
                <div class="suggestion-price">${suggestion.price}</div>
            </div>
        `;
    });
    
    container.innerHTML = suggestionsHTML;
    
    // Make cards interactive
    document.querySelectorAll('.suggestion-card').forEach(card => {
        card.addEventListener('click', function() {
            document.querySelectorAll('.suggestion-card').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

/**
 * Setup the AI design assistant panel
 */
function setupAIDesignAssistant() {
    // Set up event listeners for the AI panel controls
    const roomTypeSelect = document.getElementById('roomType');
    const designRequest = document.getElementById('designRequest');
    
    if (roomTypeSelect) {
        roomTypeSelect.addEventListener('change', function() {
            console.log('Room type changed to:', this.value);
        });
    }
    
    // Set up event listeners for suggestions
    document.addEventListener('roomScanned', function(e) {
        const designSuggestions = document.getElementById('designSuggestions');
        if (designSuggestions) {
            designSuggestions.innerHTML = '';
        }
    });
}

/**
 * Setup chat interface for the AI design assistant
 */
function setupChatInterface() {
    // Setup chat interface toggle
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatContainer = document.getElementById('ai-chat');
    const chatCloseBtn = document.getElementById('chat-close-btn');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatToggleBtn || !chatContainer) return;
    
    // Toggle chat interface
    chatToggleBtn.addEventListener('click', function() {
        chatContainer.style.display = chatContainer.style.display === 'none' ? 'flex' : 'none';
        chatToggleBtn.style.display = chatContainer.style.display === 'flex' ? 'none' : 'flex';
        if (chatContainer.style.display === 'flex') {
            chatInput.focus();
        }
    });
    
    if (chatCloseBtn) {
        chatCloseBtn.addEventListener('click', function() {
            chatContainer.style.display = 'none';
            chatToggleBtn.style.display = 'flex';
        });
    }
    
    // Send message functionality
    function sendChatMessage() {
        if (!chatInput || !chatMessages) return;
        
        const message = chatInput.value.trim();
        if (message) {
            // Add user message
            const userMessageEl = document.createElement('div');
            userMessageEl.classList.add('chat-message', 'user-message');
            userMessageEl.textContent = message;
            chatMessages.appendChild(userMessageEl);
            
            // Clear input
            chatInput.value = '';
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Simulate AI response after a short delay
            setTimeout(function() {
                const aiResponse = getAIResponse(message);
                const aiMessageEl = document.createElement('div');
                aiMessageEl.classList.add('chat-message', 'ai-message');
                aiMessageEl.textContent = aiResponse;
                chatMessages.appendChild(aiMessageEl);
                
                // Scroll to bottom again
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 1000);
        }
    }
    
    if (chatSendBtn) {
        chatSendBtn.addEventListener('click', sendChatMessage);
    }
    
    if (chatInput) {
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                sendChatMessage();
                e.preventDefault();
            }
        });
    }
}

/**
 * Get an AI response for the chat interface
 */
function getAIResponse(message) {
    // In production, this would call the OpenAI API
    // Here we return preset responses
    const responses = [
        "Based on your room scan, I recommend updating the lighting fixtures to brighten the space.",
        "I notice your walls could use a fresh coat of paint. Consider a light neutral tone to make the space feel larger.",
        "You might want to consider rearranging your furniture to improve flow in the room.",
        "Have you thought about adding some indoor plants? They can improve air quality and add visual interest.",
        "Based on the room layout, a different flooring option could make a big difference.",
        "I recommend installing smart lighting controls to enhance your space's functionality and energy efficiency.",
        "Your current color scheme could be modernized with these complementary tones...",
        "I'd suggest some artwork or wall decor to add personality to this space."
    ];
    
    return responses[Math.floor(Math.random() * responses.length)];
}