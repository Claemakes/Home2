/**
 * GlassRain Elevate - Room Scanning and Design Interface
 * 
 * This script provides the functionality for the Elevate tab including:
 * - Room scanning with 3D processing
 * - AI-powered design assistant
 * - Room measurements and visualization
 * - Design saving and management
 */

// Global state management
const STATE = {
    currentTab: 'scan',
    scanActive: false,
    scanComplete: false,
    currentRoom: null,
    roomScans: [],
    savedDesigns: [],
    chatHistory: [],
    measurements: {},
    scene: null,
    camera: null,
    renderer: null,
    controls: null,
    roomModel: null
};

// DOM elements
let elements = {};

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', init);

/**
 * Initialize the application
 */
function init() {
    // Store DOM elements
    cacheElements();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up tab switching
    setupTabs();
    
    // Load user data (scanned rooms and saved designs)
    loadUserData();
}

/**
 * Cache DOM elements for faster access
 */
function cacheElements() {
    elements = {
        // Tab navigation
        tabs: document.querySelectorAll('.elevate-tab'),
        tabContents: document.querySelectorAll('.tab-content'),
        
        // Scan tab
        scanButton: document.getElementById('start-scan'),
        cameraFeed: document.getElementById('camera-feed'),
        cameraPlaceholder: document.getElementById('camera-placeholder'),
        cameraInstruction: document.querySelector('.camera-instruction'),
        loadingOverlay: document.getElementById('loading-overlay'),
        
        // Design tab
        room3DContainer: document.getElementById('room-3d-container'),
        measurementsPanel: document.getElementById('measurements-panel'),
        toggleMeasurements: document.getElementById('toggle-measurements'),
        rotateLeft: document.getElementById('rotate-left'),
        rotateRight: document.getElementById('rotate-right'),
        saveDesign: document.getElementById('save-design'),
        
        // Chat interface
        chatMessages: document.getElementById('chat-messages'),
        chatInput: document.getElementById('chat-input'),
        chatSend: document.getElementById('chat-send'),
        
        // Room and design grids
        roomsGrid: document.getElementById('rooms-grid'),
        designsGrid: document.getElementById('designs-grid')
    };
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Scan button
    if (elements.scanButton) {
        elements.scanButton.addEventListener('click', toggleScan);
    }
    
    // Design controls
    if (elements.toggleMeasurements) {
        elements.toggleMeasurements.addEventListener('click', toggleMeasurementsPanel);
    }
    
    if (elements.rotateLeft) {
        elements.rotateLeft.addEventListener('click', () => rotateRoom(-Math.PI/8));
    }
    
    if (elements.rotateRight) {
        elements.rotateRight.addEventListener('click', () => rotateRoom(Math.PI/8));
    }
    
    if (elements.saveDesign) {
        elements.saveDesign.addEventListener('click', saveCurrentDesign);
    }
    
    // Chat interface
    if (elements.chatSend) {
        elements.chatSend.addEventListener('click', sendChatMessage);
    }
    
    if (elements.chatInput) {
        elements.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendChatMessage();
            }
        });
    }
    
    // Setup suggestion pill click events
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('suggestion-pill')) {
            elements.chatInput.value = e.target.textContent;
            sendChatMessage();
        }
    });
    
    // Close measurements panel button
    const closePanel = document.querySelector('.close-panel');
    if (closePanel) {
        closePanel.addEventListener('click', () => {
            elements.measurementsPanel.style.display = 'none';
        });
    }
}

/**
 * Set up tab switching
 */
function setupTabs() {
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Get the tab ID
            const tabId = tab.dataset.tab;
            
            // Remove active class from all tabs
            elements.tabs.forEach(t => t.classList.remove('active'));
            
            // Add active class to clicked tab
            tab.classList.add('active');
            
            // Hide all tab contents
            elements.tabContents.forEach(content => content.classList.remove('active'));
            
            // Show the corresponding tab content
            const tabContent = document.getElementById(`${tabId}-tab`);
            if (tabContent) {
                tabContent.classList.add('active');
            }
            
            // Update current tab
            STATE.currentTab = tabId;
            
            // Special handling for different tabs
            handleTabChange(tabId);
        });
    });
}

/**
 * Handle specific actions when changing tabs
 * @param {string} tabId - The ID of the tab being switched to
 */
function handleTabChange(tabId) {
    if (tabId === 'design' && !STATE.scene) {
        // Initialize 3D scene if going to design tab
        initializeThreeJS();
        
        // If scan is complete, load the room model
        if (STATE.scanComplete && STATE.currentRoom) {
            loadRoomModel(STATE.currentRoom);
        }
    } else if (tabId === 'scanned-rooms') {
        // Refresh rooms list
        populateRoomsGrid();
    } else if (tabId === 'saved-designs') {
        // Refresh designs list
        populateDesignsGrid();
    }
}

/**
 * Load user data from the server
 */
function loadUserData() {
    // Load scanned rooms
    fetch('/api/rooms')
        .then(response => response.json())
        .then(data => {
            STATE.roomScans = data.rooms || [];
            populateRoomsGrid();
        })
        .catch(error => {
            console.error('Error loading rooms:', error);
        });
    
    // Load saved designs
    fetch('/api/designs')
        .then(response => response.json())
        .then(data => {
            STATE.savedDesigns = data.designs || [];
            populateDesignsGrid();
        })
        .catch(error => {
            console.error('Error loading designs:', error);
        });
}

/**
 * Populate the rooms grid with scanned rooms
 */
function populateRoomsGrid() {
    if (!elements.roomsGrid) return;
    
    // Clear existing rooms
    elements.roomsGrid.innerHTML = '';
    
    if (STATE.roomScans.length === 0) {
        // Show empty state
        elements.roomsGrid.innerHTML = `
            <div class="empty-state">
                <p>You haven't scanned any rooms yet. Go to the Scan tab to get started.</p>
            </div>
        `;
        return;
    }
    
    // Add rooms to grid
    STATE.roomScans.forEach(room => {
        const roomCard = document.createElement('div');
        roomCard.className = 'room-card';
        roomCard.innerHTML = `
            <div class="room-image">
                <span class="room-type-badge">${room.room_type || 'Room'}</span>
                <img src="${room.thumbnail_url || '/static/images/room_placeholder.jpg'}" alt="${room.name}" onerror="this.style.display='none';this.parentNode.innerHTML += '<div style=\\'height:100%;display:flex;align-items:center;justify-content:center;\\'>No Image</div>'">
            </div>
            <div class="room-details">
                <h3 class="room-name">${room.name || 'Unnamed Room'}</h3>
                <div class="room-date">${formatDate(room.scanned_at || new Date())}</div>
                <div class="room-stats">
                    <span class="room-stat">${room.width || 0}' x ${room.length || 0}'</span>
                    <span class="room-stat">${room.area || 0} sq ft</span>
                </div>
                <div class="room-actions">
                    <button class="room-action-btn design-room" data-room-id="${room.id}">Design</button>
                    <button class="room-action-btn room-details" data-room-id="${room.id}">Details</button>
                    <button class="room-action-btn delete-room" data-room-id="${room.id}">Delete</button>
                </div>
            </div>
        `;
        
        // Add event listeners for room actions
        roomCard.querySelector('.design-room').addEventListener('click', (e) => {
            e.stopPropagation();
            const roomId = e.target.dataset.roomId;
            selectRoomForDesign(roomId);
        });
        
        roomCard.querySelector('.room-details').addEventListener('click', (e) => {
            e.stopPropagation();
            const roomId = e.target.dataset.roomId;
            showRoomDetails(roomId);
        });
        
        roomCard.querySelector('.delete-room').addEventListener('click', (e) => {
            e.stopPropagation();
            const roomId = e.target.dataset.roomId;
            deleteRoom(roomId);
        });
        
        // Add click event to the whole card to go to design
        roomCard.addEventListener('click', () => {
            selectRoomForDesign(room.id);
        });
        
        elements.roomsGrid.appendChild(roomCard);
    });
}

/**
 * Populate the designs grid with saved designs
 */
function populateDesignsGrid() {
    if (!elements.designsGrid) return;
    
    // Clear existing designs
    elements.designsGrid.innerHTML = '';
    
    if (STATE.savedDesigns.length === 0) {
        // Show empty state
        elements.designsGrid.innerHTML = `
            <div class="empty-state">
                <p>You haven't saved any designs yet. Go to the Design tab to create and save designs.</p>
            </div>
        `;
        return;
    }
    
    // Add designs to grid
    STATE.savedDesigns.forEach(design => {
        const designCard = document.createElement('div');
        designCard.className = 'design-card';
        designCard.innerHTML = `
            <div class="design-image">
                <span class="design-room-badge">${design.room_type || 'Room'}</span>
                <img src="${design.thumbnail_url || '/static/images/design_placeholder.jpg'}" alt="${design.name}" onerror="this.style.display='none';this.parentNode.innerHTML += '<div style=\\'height:100%;display:flex;align-items:center;justify-content:center;\\'>No Image</div>'">
            </div>
            <div class="design-details">
                <h3 class="design-name">${design.name || 'Unnamed Design'}</h3>
                <p class="design-description">${design.description || 'No description'}</p>
                <div class="design-date">${formatDate(design.created_at || new Date())}</div>
                <div class="design-tags">
                    ${(design.tags || []).map(tag => `<span class="design-tag">${tag}</span>`).join('')}
                </div>
                <div class="design-actions">
                    <button class="design-action-btn edit-design" data-design-id="${design.id}">Edit</button>
                    <button class="design-action-btn design-details" data-design-id="${design.id}">Details</button>
                    <button class="design-action-btn delete-design" data-design-id="${design.id}">Delete</button>
                </div>
            </div>
        `;
        
        // Add event listeners for design actions
        designCard.querySelector('.edit-design').addEventListener('click', (e) => {
            e.stopPropagation();
            const designId = e.target.dataset.designId;
            editDesign(designId);
        });
        
        designCard.querySelector('.design-details').addEventListener('click', (e) => {
            e.stopPropagation();
            const designId = e.target.dataset.designId;
            showDesignDetails(designId);
        });
        
        designCard.querySelector('.delete-design').addEventListener('click', (e) => {
            e.stopPropagation();
            const designId = e.target.dataset.designId;
            deleteDesign(designId);
        });
        
        // Add click event to the whole card to edit design
        designCard.addEventListener('click', () => {
            editDesign(design.id);
        });
        
        elements.designsGrid.appendChild(designCard);
    });
}

/**
 * Toggle room scanning
 */
function toggleScan() {
    if (STATE.scanActive) {
        // Stop scanning
        stopScan();
    } else {
        // Start scanning
        startScan();
    }
}

/**
 * Start room scanning
 */
function startScan() {
    // Update UI
    elements.scanButton.textContent = 'STOP';
    elements.scanButton.style.backgroundColor = '#ff5252';
    elements.cameraPlaceholder.style.display = 'none';
    elements.cameraInstruction.style.display = 'block';
    
    // Set state
    STATE.scanActive = true;
    
    // Initialize camera if available
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            .then(stream => {
                elements.cameraFeed.srcObject = stream;
                elements.cameraFeed.style.display = 'block';
                elements.cameraFeed.play();
                
                // Start analyzing the room (would be done with AR libraries in production)
                startRoomAnalysis();
            })
            .catch(error => {
                console.error('Error accessing camera:', error);
                // Fallback for testing: simulate a scan
                simulateScan();
            });
    } else {
        // Fallback for testing: simulate a scan
        simulateScan();
    }
}

/**
 * Start analyzing the room during scanning
 */
function startRoomAnalysis() {
    // In a real implementation, this would use AR libraries to analyze the room
    // For demo purposes, we're just setting a timeout
    
    // Sample code for AR room analysis would be here
    // This would track surfaces, measure dimensions, etc.
    
    // For demo, simulate completion after 10 seconds
    setTimeout(() => {
        completeScan();
    }, 10000);
}

/**
 * Simulate a scan for testing without camera access
 */
function simulateScan() {
    // Show a message that we're using simulation mode
    const simulationMessage = document.createElement('div');
    simulationMessage.className = 'simulation-message';
    simulationMessage.textContent = 'Camera simulation mode active';
    simulationMessage.style.position = 'absolute';
    simulationMessage.style.top = '50%';
    simulationMessage.style.left = '0';
    simulationMessage.style.right = '0';
    simulationMessage.style.textAlign = 'center';
    simulationMessage.style.color = 'var(--gold)';
    simulationMessage.style.zIndex = '10';
    
    elements.cameraFeed.parentNode.appendChild(simulationMessage);
    
    // Set a timeout to complete the scan
    setTimeout(() => {
        completeScan();
    }, 5000);
}

/**
 * Stop the active scan
 */
function stopScan() {
    // Update UI
    elements.scanButton.textContent = 'SCAN';
    elements.scanButton.style.backgroundColor = 'var(--gold)';
    elements.cameraInstruction.style.display = 'none';
    
    // Stop camera feed if active
    if (elements.cameraFeed.srcObject) {
        const tracks = elements.cameraFeed.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        elements.cameraFeed.srcObject = null;
    }
    
    elements.cameraFeed.style.display = 'none';
    elements.cameraPlaceholder.style.display = 'flex';
    
    // Set state
    STATE.scanActive = false;
}

/**
 * Complete the scanning process
 */
function completeScan() {
    // Stop the active scan
    stopScan();
    
    // Show loading overlay
    elements.loadingOverlay.style.display = 'flex';
    elements.loadingOverlay.querySelector('.loading-text').textContent = 'Processing your room scan...';
    
    // Set scan complete state
    STATE.scanComplete = true;
    
    // In a real implementation, we would process the captured data here
    // For demo, simulate a processing delay and then proceed
    setTimeout(() => {
        // Hide loading overlay
        elements.loadingOverlay.style.display = 'none';
        
        // Create new room data with sample measurements
        const newRoom = {
            id: generateId(),
            name: `Room ${STATE.roomScans.length + 1}`,
            room_type: 'Living Room',
            scanned_at: new Date(),
            width: 12,
            length: 14,
            height: 9,
            area: 168,
            volume: 1512,
            walls_area: 468,
            windows: 2,
            doors: 1,
            thumbnail_url: '/static/images/room_placeholder.jpg',
            model_url: '/static/models/room.glb'
        };
        
        // Add to state
        STATE.roomScans.push(newRoom);
        STATE.currentRoom = newRoom;
        
        // Save to server (in a real implementation)
        saveRoomToServer(newRoom);
        
        // Ask the user to name and categorize the room
        promptRoomDetails(newRoom);
        
        // Automatically switch to design tab
        const designTab = document.querySelector('.elevate-tab[data-tab="design"]');
        if (designTab) {
            designTab.click();
        }
    }, 3000);
}

/**
 * Prompt the user to enter room details
 * @param {Object} room - The room object
 */
function promptRoomDetails(room) {
    // In a real implementation, show a modal to collect room name and type
    // For demo, we're using predefined values
    
    // Load the room model in the design view
    loadRoomModel(room);
    
    // Initialize chat for this room
    initializeChat(room);
}

/**
 * Save room to server
 * @param {Object} room - The room object to save
 */
function saveRoomToServer(room) {
    // In a real implementation, this would save to the server
    fetch('/api/rooms', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(room)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Room saved:', data);
    })
    .catch(error => {
        console.error('Error saving room:', error);
    });
}

/**
 * Select a room for design
 * @param {string} roomId - The ID of the room to design
 */
function selectRoomForDesign(roomId) {
    // Find the room in state
    const room = STATE.roomScans.find(r => r.id === roomId);
    
    if (!room) {
        console.error('Room not found:', roomId);
        return;
    }
    
    // Set as current room
    STATE.currentRoom = room;
    
    // Switch to design tab
    const designTab = document.querySelector('.elevate-tab[data-tab="design"]');
    if (designTab) {
        designTab.click();
    }
    
    // Load the room model
    loadRoomModel(room);
    
    // Initialize chat for this room
    initializeChat(room);
}

/**
 * Show room details
 * @param {string} roomId - The ID of the room to show details for
 */
function showRoomDetails(roomId) {
    // Find the room in state
    const room = STATE.roomScans.find(r => r.id === roomId);
    
    if (!room) {
        console.error('Room not found:', roomId);
        return;
    }
    
    // In a real implementation, this would show a modal with room details
    console.log('Room details:', room);
    
    // For demo, we'll just alert some basic info
    alert(`Room Details:
Name: ${room.name}
Type: ${room.room_type}
Dimensions: ${room.width}' x ${room.length}' x ${room.height}'
Area: ${room.area} sq ft
Volume: ${room.volume} cu ft
`);
}

/**
 * Delete a room
 * @param {string} roomId - The ID of the room to delete
 */
function deleteRoom(roomId) {
    if (!confirm('Are you sure you want to delete this room?')) {
        return;
    }
    
    // Remove from state
    STATE.roomScans = STATE.roomScans.filter(r => r.id !== roomId);
    
    // If this is the current room, clear it
    if (STATE.currentRoom && STATE.currentRoom.id === roomId) {
        STATE.currentRoom = null;
    }
    
    // Update the UI
    populateRoomsGrid();
    
    // Delete from server (in a real implementation)
    fetch(`/api/rooms/${roomId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Room deleted:', data);
    })
    .catch(error => {
        console.error('Error deleting room:', error);
    });
}

/**
 * Initialize Three.js for 3D visualization
 */
function initializeThreeJS() {
    if (!elements.room3DContainer) return;
    
    // Create scene
    STATE.scene = new THREE.Scene();
    STATE.scene.background = new THREE.Color(0x1a1a1a);
    
    // Create camera
    STATE.camera = new THREE.PerspectiveCamera(75, elements.room3DContainer.clientWidth / elements.room3DContainer.clientHeight, 0.1, 1000);
    STATE.camera.position.set(0, 1.6, 3);
    
    // Create renderer
    STATE.renderer = new THREE.WebGLRenderer({ antialias: true });
    STATE.renderer.setSize(elements.room3DContainer.clientWidth, elements.room3DContainer.clientHeight);
    STATE.renderer.shadowMap.enabled = true;
    elements.room3DContainer.appendChild(STATE.renderer.domElement);
    
    // Create controls
    STATE.controls = new THREE.OrbitControls(STATE.camera, STATE.renderer.domElement);
    STATE.controls.target.set(0, 1, 0);
    STATE.controls.update();
    
    // Add lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    STATE.scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    directionalLight.castShadow = true;
    STATE.scene.add(directionalLight);
    
    // Start animation loop
    animate();
    
    // Handle window resize
    window.addEventListener('resize', onWindowResize);
}

/**
 * Animation loop for Three.js
 */
function animate() {
    requestAnimationFrame(animate);
    
    if (STATE.controls) {
        STATE.controls.update();
    }
    
    if (STATE.renderer && STATE.scene && STATE.camera) {
        STATE.renderer.render(STATE.scene, STATE.camera);
    }
}

/**
 * Handle window resize
 */
function onWindowResize() {
    if (!elements.room3DContainer || !STATE.camera || !STATE.renderer) return;
    
    STATE.camera.aspect = elements.room3DContainer.clientWidth / elements.room3DContainer.clientHeight;
    STATE.camera.updateProjectionMatrix();
    STATE.renderer.setSize(elements.room3DContainer.clientWidth, elements.room3DContainer.clientHeight);
}

/**
 * Load a room model into the 3D scene
 * @param {Object} room - The room object
 */
function loadRoomModel(room) {
    if (!STATE.scene) {
        initializeThreeJS();
    }
    
    // Clear existing model if any
    if (STATE.roomModel) {
        STATE.scene.remove(STATE.roomModel);
        STATE.roomModel = null;
    }
    
    // For demo, create a simple room model
    // In a real implementation, we would load a 3D model from the server
    createDemoRoom(room);
    
    // Set measurements
    updateMeasurements(room);
}

/**
 * Create a simple demo room
 * @param {Object} room - The room object
 */
function createDemoRoom(room) {
    // Create a group for the entire room
    const roomGroup = new THREE.Group();
    
    // Floor
    const floorGeometry = new THREE.PlaneGeometry(room.width, room.length);
    const floorMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x8B4513,
        roughness: 0.8,
        metalness: 0.2
    });
    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    roomGroup.add(floor);
    
    // Walls
    const wallHeight = room.height || 8;
    const wallMaterial = new THREE.MeshStandardMaterial({ 
        color: 0xeeeeee,
        roughness: 0.9,
        metalness: 0.1
    });
    
    // Wall 1 (back)
    const wall1Geometry = new THREE.PlaneGeometry(room.width, wallHeight);
    const wall1 = new THREE.Mesh(wall1Geometry, wallMaterial);
    wall1.position.z = -room.length / 2;
    wall1.position.y = wallHeight / 2;
    wall1.receiveShadow = true;
    roomGroup.add(wall1);
    
    // Wall 2 (front)
    const wall2Geometry = new THREE.PlaneGeometry(room.width, wallHeight);
    const wall2 = new THREE.Mesh(wall2Geometry, wallMaterial);
    wall2.position.z = room.length / 2;
    wall2.position.y = wallHeight / 2;
    wall2.rotation.y = Math.PI;
    wall2.receiveShadow = true;
    roomGroup.add(wall2);
    
    // Wall 3 (left)
    const wall3Geometry = new THREE.PlaneGeometry(room.length, wallHeight);
    const wall3 = new THREE.Mesh(wall3Geometry, wallMaterial);
    wall3.position.x = -room.width / 2;
    wall3.position.y = wallHeight / 2;
    wall3.rotation.y = Math.PI / 2;
    wall3.receiveShadow = true;
    roomGroup.add(wall3);
    
    // Wall 4 (right)
    const wall4Geometry = new THREE.PlaneGeometry(room.length, wallHeight);
    const wall4 = new THREE.Mesh(wall4Geometry, wallMaterial);
    wall4.position.x = room.width / 2;
    wall4.position.y = wallHeight / 2;
    wall4.rotation.y = -Math.PI / 2;
    wall4.receiveShadow = true;
    roomGroup.add(wall4);
    
    // Add a window (sample)
    const windowGeometry = new THREE.PlaneGeometry(3, 2);
    const windowMaterial = new THREE.MeshStandardMaterial({ 
        color: 0x87CEEB,
        transparent: true,
        opacity: 0.7,
        roughness: 0.1,
        metalness: 0.8
    });
    const window1 = new THREE.Mesh(windowGeometry, windowMaterial);
    window1.position.set(0, wallHeight / 2, -room.length / 2 + 0.05);
    roomGroup.add(window1);
    
    // Add the room to the scene
    STATE.scene.add(roomGroup);
    STATE.roomModel = roomGroup;
    
    // Position camera
    STATE.camera.position.set(0, wallHeight / 2, room.length / 2 + 5);
    STATE.controls.target.set(0, wallHeight / 2, 0);
    STATE.controls.update();
}

/**
 * Update the measurements panel with room data
 * @param {Object} room - The room object
 */
function updateMeasurements(room) {
    if (!elements.measurementsPanel) return;
    
    // Store measurements
    STATE.measurements = {
        width: room.width,
        length: room.length,
        height: room.height || 8,
        area: room.area,
        volume: room.volume,
        wallsArea: room.walls_area
    };
    
    // Update UI
    const content = elements.measurementsPanel.querySelector('.measurements-content');
    if (content) {
        content.innerHTML = `
            <div class="measurement-item">
                <span class="measurement-label">Room Size:</span>
                <span class="measurement-value">${room.width}' x ${room.length}'</span>
            </div>
            <div class="measurement-item">
                <span class="measurement-label">Ceiling Height:</span>
                <span class="measurement-value">${room.height || 8}'</span>
            </div>
            <div class="measurement-item">
                <span class="measurement-label">Wall Area:</span>
                <span class="measurement-value">${room.walls_area || calculateWallArea(room)} sq ft</span>
            </div>
            <div class="measurement-item">
                <span class="measurement-label">Floor Area:</span>
                <span class="measurement-value">${room.area} sq ft</span>
            </div>
            <div class="measurement-item">
                <span class="measurement-label">Window Count:</span>
                <span class="measurement-value">${room.windows || 1}</span>
            </div>
            <div class="measurement-item">
                <span class="measurement-label">Door Count:</span>
                <span class="measurement-value">${room.doors || 1}</span>
            </div>
        `;
    }
}

/**
 * Calculate wall area if not provided
 * @param {Object} room - The room object
 * @returns {number} - The calculated wall area
 */
function calculateWallArea(room) {
    const perimeter = 2 * (room.width + room.length);
    const height = room.height || 8;
    return perimeter * height;
}

/**
 * Toggle the measurements panel
 */
function toggleMeasurementsPanel() {
    if (elements.measurementsPanel) {
        if (elements.measurementsPanel.style.display === 'none') {
            elements.measurementsPanel.style.display = 'flex';
        } else {
            elements.measurementsPanel.style.display = 'none';
        }
    }
}

/**
 * Rotate the room model
 * @param {number} angle - The angle to rotate by in radians
 */
function rotateRoom(angle) {
    if (STATE.roomModel) {
        STATE.roomModel.rotation.y += angle;
    }
}

/**
 * Initialize the chat interface for a room
 * @param {Object} room - The room object
 */
function initializeChat(room) {
    if (!elements.chatMessages) return;
    
    // Clear existing messages
    elements.chatMessages.innerHTML = '';
    
    // Add initial greeting and suggestions
    const welcomeMessage = document.createElement('div');
    welcomeMessage.className = 'chat-message ai-message';
    welcomeMessage.innerHTML = `
        Welcome to the design space for your ${room.room_type || 'room'}! I can help you redesign this space based on the measurements I've detected. What would you like to change?
        <div class="suggestion-pills">
            <span class="suggestion-pill">Change wall color</span>
            <span class="suggestion-pill">Update flooring</span>
            <span class="suggestion-pill">Add new lighting</span>
            <span class="suggestion-pill">Estimate renovation cost</span>
        </div>
    `;
    
    elements.chatMessages.appendChild(welcomeMessage);
    
    // Reset chat history
    STATE.chatHistory = [{
        role: 'assistant',
        content: `Welcome to the design space for your ${room.room_type || 'room'}! I can help you redesign this space based on the measurements I've detected. What would you like to change?`
    }];
}

/**
 * Send a message to the AI chat assistant
 */
function sendChatMessage() {
    if (!elements.chatInput || !elements.chatMessages) return;
    
    const message = elements.chatInput.value.trim();
    if (!message) return;
    
    // Add user message to UI
    const userMessage = document.createElement('div');
    userMessage.className = 'chat-message user-message';
    userMessage.textContent = message;
    elements.chatMessages.appendChild(userMessage);
    
    // Clear input
    elements.chatInput.value = '';
    
    // Scroll to bottom
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    
    // Add to chat history
    STATE.chatHistory.push({
        role: 'user',
        content: message
    });
    
    // Show typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'chat-message ai-message typing-indicator';
    typingIndicator.innerHTML = 'Thinking<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>';
    elements.chatMessages.appendChild(typingIndicator);
    
    // Scroll to bottom
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    
    // Process the message and get AI response
    processAIResponse(message)
        .then(response => {
            // Remove typing indicator
            elements.chatMessages.removeChild(typingIndicator);
            
            // Add AI response to UI
            const aiMessage = document.createElement('div');
            aiMessage.className = 'chat-message ai-message';
            
            // Parse response for suggestions
            const { text, suggestions } = parseResponseForSuggestions(response);
            
            // Set message text
            aiMessage.innerHTML = text;
            
            // Add suggestion pills if any
            if (suggestions.length > 0) {
                const suggestionPills = document.createElement('div');
                suggestionPills.className = 'suggestion-pills';
                
                suggestions.forEach(suggestion => {
                    const pill = document.createElement('span');
                    pill.className = 'suggestion-pill';
                    pill.textContent = suggestion;
                    suggestionPills.appendChild(pill);
                });
                
                aiMessage.appendChild(suggestionPills);
            }
            
            elements.chatMessages.appendChild(aiMessage);
            
            // Add to chat history
            STATE.chatHistory.push({
                role: 'assistant',
                content: response
            });
            
            // Scroll to bottom
            elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
            
            // Apply changes to the 3D model if requested
            applyChangesToModel(message, response);
        })
        .catch(error => {
            console.error('Error getting AI response:', error);
            
            // Remove typing indicator
            elements.chatMessages.removeChild(typingIndicator);
            
            // Add error message
            const errorMessage = document.createElement('div');
            errorMessage.className = 'chat-message ai-message error';
            errorMessage.textContent = 'Sorry, I encountered an error processing your request. Please try again.';
            elements.chatMessages.appendChild(errorMessage);
            
            // Scroll to bottom
            elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
        });
}

/**
 * Parse AI response for embedded suggestions
 * @param {string} response - The AI response
 * @returns {Object} - Object containing text and suggestions
 */
function parseResponseForSuggestions(response) {
    // Look for suggestion markers in the response
    const suggestionRegex = /\[suggestion: ([^\]]+)\]/g;
    const suggestions = [];
    let match;
    
    while ((match = suggestionRegex.exec(response)) !== null) {
        suggestions.push(match[1]);
    }
    
    // Remove suggestion markers from the text
    const text = response.replace(suggestionRegex, '');
    
    return { text, suggestions };
}

/**
 * Process message and get AI response
 * @param {string} message - The user message
 * @returns {Promise<string>} - The AI response
 */
function processAIResponse(message) {
    // In a real implementation, this would call the OpenAI API
    // For demo, we'll simulate responses based on keywords
    
    return new Promise((resolve) => {
        setTimeout(() => {
            // Get room measurements for context
            const room = STATE.currentRoom || { 
                width: 12, 
                length: 14, 
                height: 8, 
                area: 168,
                room_type: 'living room'
            };
            
            let response = '';
            
            // Check for keywords and generate appropriate responses
            if (message.toLowerCase().includes('wall color') || message.toLowerCase().includes('paint')) {
                response = `I'd recommend a few colors that would work well in this ${room.room_type}:\n\n1. Soft Sage - A calming green that creates a peaceful atmosphere\n2. Warm Taupe - A neutral that adds warmth and pairs well with gold accents\n3. Slate Blue - A sophisticated color that adds depth\n\nBased on your room size (${room.width}' x ${room.length}'), you would need about ${Math.ceil(room.walls_area / 400)} gallons of paint. For a professional job, it would cost approximately $${(room.walls_area * 3).toFixed(2)} for materials and labor.\n\n[suggestion: Change to Soft Sage]\n[suggestion: Change to Warm Taupe]\n[suggestion: Change to Slate Blue]`;
            } else if (message.toLowerCase().includes('floor') || message.toLowerCase().includes('flooring')) {
                response = `For this ${room.room_type} (${room.area} sq ft), I recommend these flooring options:\n\n1. Engineered Hardwood - Durable and beautiful, costs around $${(room.area * 8).toFixed(2)} installed\n2. Luxury Vinyl Plank - Waterproof and low maintenance, costs around $${(room.area * 5).toFixed(2)} installed\n3. Porcelain Tile - Elegant and extremely durable, costs around $${(room.area * 12).toFixed(2)} installed\n\nWould you like more specific recommendations for any of these options?\n\n[suggestion: Show hardwood samples]\n[suggestion: Show vinyl options]\n[suggestion: Calculate installation time]`;
            } else if (message.toLowerCase().includes('light') || message.toLowerCase().includes('lighting')) {
                response = `For optimal lighting in your ${room.room_type}, I recommend a layered approach:\n\n1. Ambient lighting: Recessed ceiling lights or a central fixture\n2. Task lighting: Floor or table lamps for reading/working areas\n3. Accent lighting: Wall sconces or LED strips to highlight features\n\nFor your room size, you'd need approximately 3-4 recessed lights plus supplementary fixtures. A complete lighting update would cost around $${(room.area * 15).toFixed(2)} including installation.\n\n[suggestion: Show lighting fixtures]\n[suggestion: Find LED options]\n[suggestion: Calculate energy savings]`;
            } else if (message.toLowerCase().includes('cost') || message.toLowerCase().includes('estimate') || message.toLowerCase().includes('budget')) {
                response = `Based on the measurements of your ${room.room_type} (${room.width}' x ${room.length}', ${room.area} sq ft), here's a renovation cost breakdown:\n\n• Basic refresh (paint, lighting): $${(room.area * 15).toFixed(2)}\n• Mid-range update (paint, flooring, lighting): $${(room.area * 45).toFixed(2)}\n• Full renovation (all surfaces, fixtures): $${(room.area * 125).toFixed(2)}\n\nThese estimates include materials and labor. Would you like a more detailed breakdown for a specific renovation type?\n\n[suggestion: Basic refresh details]\n[suggestion: Mid-range update details]\n[suggestion: Full renovation details]`;
            } else if (message.toLowerCase().includes('furniture') || message.toLowerCase().includes('sofa') || message.toLowerCase().includes('table')) {
                response = `For your ${room.room_type} (${room.width}' x ${room.length}'), I recommend these furniture arrangements:\n\n1. Conversation area with 3-seat sofa, two armchairs, and coffee table\n2. Entertainment setup with media console (up to ${Math.min(room.width - 2, 8)}' wide)\n3. Reading nook in the corner with a comfortable chair and floor lamp\n\nBased on your dimensions, you have enough space for a sectional sofa if preferred. Would you like specific recommendations for any furniture pieces?\n\n[suggestion: Show sofa options]\n[suggestion: Optimal furniture layout]\n[suggestion: Find space-saving ideas]`;
            } else if (message.toLowerCase().includes('contractor') || message.toLowerCase().includes('professional')) {
                response = `I can connect you with verified contractors in your area for your ${room.room_type} project. Based on the scope of work, here are the types of professionals you might need:\n\n1. Painter - For wall color changes (~$${(room.walls_area * 3).toFixed(2)})\n2. Flooring specialist - For new floors (~$${(room.area * 7).toFixed(2)} plus materials)\n3. Electrician - For lighting updates (~$${(room.area * 6).toFixed(2)})\n\nWould you like me to find available contractors in your area?\n\n[suggestion: Find painters]\n[suggestion: Find flooring experts]\n[suggestion: Get project quotes]`;
            } else {
                response = `I'd be happy to help you redesign your ${room.room_type}. Based on the measurements (${room.width}' x ${room.length}', ${room.area} sq ft), there are many possibilities. Would you like suggestions for:\n\n1. Wall colors and paint options\n2. Flooring materials and styles\n3. Lighting improvements\n4. Furniture arrangements\n5. Cost estimates for renovations\n\nWhat aspect would you like to explore first?\n\n[suggestion: Wall color ideas]\n[suggestion: Flooring options]\n[suggestion: Lighting design]\n[suggestion: Renovation costs]`;
            }
            
            resolve(response);
        }, 1500); // Simulate API delay
    });
}

/**
 * Apply changes to the 3D model based on user request and AI response
 * @param {string} userMessage - The user's request
 * @param {string} aiResponse - The AI's response
 */
function applyChangesToModel(userMessage, aiResponse) {
    if (!STATE.roomModel) return;
    
    // Check for color change requests
    if (userMessage.toLowerCase().includes('change to soft sage') || 
        (userMessage.toLowerCase().includes('sage') && userMessage.toLowerCase().includes('color'))) {
        // Change wall color to sage
        const sageColor = new THREE.Color(0xb2beb5);
        STATE.roomModel.children.forEach(child => {
            if (child.material && child.material.color && !child.material.transparent) {
                child.material.color.set(sageColor);
            }
        });
    } else if (userMessage.toLowerCase().includes('change to warm taupe') || 
              (userMessage.toLowerCase().includes('taupe') && userMessage.toLowerCase().includes('color'))) {
        // Change wall color to taupe
        const taupeColor = new THREE.Color(0xc2b280);
        STATE.roomModel.children.forEach(child => {
            if (child.material && child.material.color && !child.material.transparent) {
                child.material.color.set(taupeColor);
            }
        });
    } else if (userMessage.toLowerCase().includes('change to slate blue') || 
              (userMessage.toLowerCase().includes('blue') && userMessage.toLowerCase().includes('color'))) {
        // Change wall color to slate blue
        const blueColor = new THREE.Color(0x6a5acd);
        STATE.roomModel.children.forEach(child => {
            if (child.material && child.material.color && !child.material.transparent) {
                child.material.color.set(blueColor);
            }
        });
    } else if (userMessage.toLowerCase().includes('hardwood') && userMessage.toLowerCase().includes('floor')) {
        // Change floor to hardwood
        const floor = STATE.roomModel.children.find(child => child.rotation.x === -Math.PI / 2);
        if (floor) {
            floor.material.color.set(new THREE.Color(0x8B4513));
            floor.material.roughness = 0.3;
        }
    } else if (userMessage.toLowerCase().includes('vinyl') && userMessage.toLowerCase().includes('floor')) {
        // Change floor to vinyl
        const floor = STATE.roomModel.children.find(child => child.rotation.x === -Math.PI / 2);
        if (floor) {
            floor.material.color.set(new THREE.Color(0xa79d8c));
            floor.material.roughness = 0.5;
        }
    } else if (userMessage.toLowerCase().includes('tile') && userMessage.toLowerCase().includes('floor')) {
        // Change floor to tile
        const floor = STATE.roomModel.children.find(child => child.rotation.x === -Math.PI / 2);
        if (floor) {
            floor.material.color.set(new THREE.Color(0xe5e5e5));
            floor.material.roughness = 0.2;
        }
    }
    
    // Note: In a real implementation, we would use a more sophisticated approach
    // to modify the 3D model, possibly loading new textures or models
}

/**
 * Save the current design
 */
function saveCurrentDesign() {
    if (!STATE.currentRoom) {
        alert('No room selected for design');
        return;
    }
    
    // Prompt for design name
    const designName = prompt('Enter a name for this design:');
    if (!designName) return;
    
    // Take a screenshot of the current view
    const screenshot = STATE.renderer.domElement.toDataURL('image/png');
    
    // Create design object
    const newDesign = {
        id: generateId(),
        name: designName,
        room_id: STATE.currentRoom.id,
        room_type: STATE.currentRoom.room_type,
        description: `Design for ${STATE.currentRoom.room_type || 'room'} with custom colors and materials`,
        created_at: new Date(),
        thumbnail_url: screenshot,
        chat_history: STATE.chatHistory,
        measurements: STATE.measurements,
        tags: ['custom', 'design']
    };
    
    // Add to state
    STATE.savedDesigns.push(newDesign);
    
    // Save to server (in a real implementation)
    saveDesignToServer(newDesign);
    
    // Show success message
    alert('Design saved successfully!');
}

/**
 * Save design to server
 * @param {Object} design - The design object
 */
function saveDesignToServer(design) {
    // In a real implementation, this would save to the server
    fetch('/api/designs', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(design)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Design saved:', data);
    })
    .catch(error => {
        console.error('Error saving design:', error);
    });
}

/**
 * Edit a saved design
 * @param {string} designId - The ID of the design to edit
 */
function editDesign(designId) {
    // Find the design in state
    const design = STATE.savedDesigns.find(d => d.id === designId);
    
    if (!design) {
        console.error('Design not found:', designId);
        return;
    }
    
    // Find the associated room
    const room = STATE.roomScans.find(r => r.id === design.room_id);
    
    if (!room) {
        console.error('Associated room not found for design:', designId);
        return;
    }
    
    // Set as current room
    STATE.currentRoom = room;
    
    // Switch to design tab
    const designTab = document.querySelector('.elevate-tab[data-tab="design"]');
    if (designTab) {
        designTab.click();
    }
    
    // Load the room model
    loadRoomModel(room);
    
    // Restore chat history
    if (design.chat_history) {
        STATE.chatHistory = design.chat_history;
        
        // Update chat UI
        updateChatUI();
    } else {
        // Initialize chat for this room
        initializeChat(room);
    }
}

/**
 * Update chat UI with current chat history
 */
function updateChatUI() {
    if (!elements.chatMessages) return;
    
    // Clear existing messages
    elements.chatMessages.innerHTML = '';
    
    // Add messages from history
    STATE.chatHistory.forEach(message => {
        const messageDiv = document.createElement('div');
        messageDiv.className = message.role === 'user' ? 'chat-message user-message' : 'chat-message ai-message';
        
        if (message.role === 'user') {
            messageDiv.textContent = message.content;
        } else {
            // Parse response for suggestions
            const { text, suggestions } = parseResponseForSuggestions(message.content);
            
            // Set message text
            messageDiv.innerHTML = text;
            
            // Add suggestion pills if any
            if (suggestions.length > 0) {
                const suggestionPills = document.createElement('div');
                suggestionPills.className = 'suggestion-pills';
                
                suggestions.forEach(suggestion => {
                    const pill = document.createElement('span');
                    pill.className = 'suggestion-pill';
                    pill.textContent = suggestion;
                    suggestionPills.appendChild(pill);
                });
                
                messageDiv.appendChild(suggestionPills);
            }
        }
        
        elements.chatMessages.appendChild(messageDiv);
    });
    
    // Scroll to bottom
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

/**
 * Show design details
 * @param {string} designId - The ID of the design to show details for
 */
function showDesignDetails(designId) {
    // Find the design in state
    const design = STATE.savedDesigns.find(d => d.id === designId);
    
    if (!design) {
        console.error('Design not found:', designId);
        return;
    }
    
    // In a real implementation, this would show a modal with design details
    console.log('Design details:', design);
    
    // For demo, we'll just alert some basic info
    alert(`Design Details:
Name: ${design.name}
Room Type: ${design.room_type || 'Unknown'}
Description: ${design.description || 'No description'}
Created: ${formatDate(design.created_at)}
`);
}

/**
 * Delete a design
 * @param {string} designId - The ID of the design to delete
 */
function deleteDesign(designId) {
    if (!confirm('Are you sure you want to delete this design?')) {
        return;
    }
    
    // Remove from state
    STATE.savedDesigns = STATE.savedDesigns.filter(d => d.id !== designId);
    
    // Update the UI
    populateDesignsGrid();
    
    // Delete from server (in a real implementation)
    fetch(`/api/designs/${designId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Design deleted:', data);
    })
    .catch(error => {
        console.error('Error deleting design:', error);
    });
}

/**
 * Format a date for display
 * @param {Date|string} date - The date to format
 * @returns {string} - The formatted date string
 */
function formatDate(date) {
    const d = new Date(date);
    return d.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Generate a random ID
 * @returns {string} - A random ID
 */
function generateId() {
    return Math.random().toString(36).substring(2, 15) + 
           Math.random().toString(36).substring(2, 15);
}