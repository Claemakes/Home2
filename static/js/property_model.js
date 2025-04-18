/**
 * GlassRain 3D Property Visualization
 * 
 * This module creates and manages interactive 3D property models based on address data.
 * It uses Three.js to render realistic buildings with proper lighting, materials, and camera controls.
 */

// Global variables
let scene, camera, renderer, controls;
let propertyModel = { group: null, components: {} };
let lights = {};
let isInitialized = false;
let modelData = null;
let containerEl = null;

// Configuration
const config = {
  cameraDistance: 15,
  cameraHeight: 8,
  groundSize: 50,
  shadows: true,
  ambientIntensity: 0.4,
  directionalIntensity: 0.8,
  enableFog: true,
  fogDensity: 0.01,
  skyColor: 0x87ceeb,
  groundColor: 0x3a7e4d,
  loadingMinTime: 1000, // minimum time to show loading screen in ms
  materialQuality: 'auto', // 'low', 'medium', 'high', 'auto'
  geometryDetail: 'auto', // 'low', 'medium', 'high', 'auto'
  maxTextureSize: 1024,  // maximum texture size in pixels
  textureCompression: true, // use compressed textures when available
};

// Detect device capabilities and set appropriate quality settings
function detectDeviceCapabilities() {
  // Check if WebGL is available
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  
  if (!gl) {
    config.materialQuality = 'low';
    config.geometryDetail = 'low';
    config.shadows = false;
    config.enableFog = false;
    return;
  }
  
  // Get GPU info if available
  const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
  const renderer = debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : '';
  const vendor = debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : '';
  console.log('GPU Info:', vendor, renderer);
  
  // Check if we're on a mobile device
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  
  // Check extension support for capabilities
  const hasAnisotropic = gl.getExtension('EXT_texture_filter_anisotropic');
  const hasCompressedTextures = gl.getExtension('WEBGL_compressed_texture_s3tc');
  
  // Determine available VRAM and capabilities (rough estimate)
  const maxTextureSize = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  const maxRenderbufferSize = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
  
  if (isMobile) {
    // Mobile specific settings
    config.materialQuality = 'medium';
    config.geometryDetail = 'low';
    config.shadows = false; // Disable shadows on mobile
    config.maxTextureSize = Math.min(1024, maxTextureSize);
    config.enableFog = false; // Disable fog on mobile
  } else if (renderer.match(/nvidia|radeon|geforce|rtx|gtx|rx|vega/i)) {
    // Dedicated GPU
    config.materialQuality = 'high';
    config.geometryDetail = 'high';
    config.maxTextureSize = Math.min(2048, maxTextureSize);
  } else {
    // Integrated GPU or unknown
    config.materialQuality = 'medium';
    config.geometryDetail = 'medium';
    config.maxTextureSize = Math.min(1024, maxTextureSize);
  }
  
  // Override with specific optimizations for known low-end GPUs
  if (renderer.match(/intel hd|intel uhd|mali-|adreno|powervr/i)) {
    config.materialQuality = 'medium';
    config.geometryDetail = 'low';
    config.shadows = false;
  }
  
  // Support for texture compression
  config.textureCompression = !!hasCompressedTextures;
  
  console.log('Device capabilities configured:', config.materialQuality, config.geometryDetail);
}

/**
 * Initialize the 3D scene, camera, renderer, and lighting
 * @param {string} containerId - ID of the HTML element to contain the 3D view
 */
function initializeScene(containerId) {
  if (isInitialized) return;
  
  // Get container element
  containerEl = document.getElementById(containerId);
  if (!containerEl) {
    console.error('Container element not found:', containerId);
    return;
  }
  
  // Detect device capabilities and adjust settings accordingly
  detectDeviceCapabilities();
  
  // Create scene
  scene = new THREE.Scene();
  
  // Add fog for atmospheric effect
  if (config.enableFog) {
    scene.fog = new THREE.FogExp2(0xffffff, config.fogDensity);
  }
  
  // Create camera
  const aspect = containerEl.clientWidth / containerEl.clientHeight;
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
  camera.position.set(0, config.cameraHeight, config.cameraDistance);
  camera.lookAt(0, 0, 0);
  
  // Create renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(containerEl.clientWidth, containerEl.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = config.shadows;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  
  // Handle Three.js version compatibility
  if (THREE.sRGBEncoding !== undefined) {
    // For older Three.js versions
    renderer.outputEncoding = THREE.sRGBEncoding;
  } else if (renderer.outputColorSpace !== undefined) {
    // For newer Three.js versions
    renderer.outputColorSpace = THREE.SRGBColorSpace;
  }
  
  // Apply tone mapping if available
  if (THREE.ACESFilmicToneMapping !== undefined) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
  }
  
  // Add renderer to container
  containerEl.appendChild(renderer.domElement);
  
  // Setup lights
  setupLighting();
  
  // Add orbit controls for camera
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.25;
  controls.screenSpacePanning = false;
  controls.maxPolarAngle = Math.PI / 2;
  controls.minDistance = 5;
  controls.maxDistance = 50;
  
  // Add ground 
  addGround();
  
  // Add skybox
  addSkybox();
  
  // Set up window resize handler
  window.addEventListener('resize', onWindowResize);
  
  // Start animation loop
  animate();
  
  isInitialized = true;
  console.log('3D scene initialized');
}

/**
 * Set up scene lighting
 */
function setupLighting() {
  // Ambient light for general illumination
  lights.ambient = new THREE.AmbientLight(0xffffff, config.ambientIntensity);
  scene.add(lights.ambient);
  
  // Main directional light (sun)
  lights.directional = new THREE.DirectionalLight(0xffffff, config.directionalIntensity);
  lights.directional.position.set(10, 20, 15);
  lights.directional.castShadow = config.shadows;
  
  // Configure shadow properties
  if (config.shadows) {
    lights.directional.shadow.mapSize.width = 2048;
    lights.directional.shadow.mapSize.height = 2048;
    lights.directional.shadow.camera.near = 0.5;
    lights.directional.shadow.camera.far = 50;
    lights.directional.shadow.camera.left = -25;
    lights.directional.shadow.camera.right = 25;
    lights.directional.shadow.camera.top = 25;
    lights.directional.shadow.camera.bottom = -25;
    lights.directional.shadow.bias = -0.0005;
  }
  
  scene.add(lights.directional);
  
  // Hemisphere light to simulate sky and ground reflection
  lights.hemisphere = new THREE.HemisphereLight(
    config.skyColor,    // Sky color
    config.groundColor, // Ground color
    0.3                 // Intensity
  );
  scene.add(lights.hemisphere);
}

/**
 * Add ground plane
 */
function addGround() {
  const groundGeometry = new THREE.PlaneGeometry(config.groundSize, config.groundSize);
  
  // Use a texture for the ground
  const textureLoader = new THREE.TextureLoader();
  const groundMaterial = new THREE.MeshStandardMaterial({
    color: 0x3a7e4d,
    roughness: 0.8,
    metalness: 0.1
  });
  
  const ground = new THREE.Mesh(groundGeometry, groundMaterial);
  ground.rotation.x = -Math.PI / 2; // Rotate to be horizontal
  ground.position.y = -0.01; // Slightly below 0 to avoid z-fighting
  ground.receiveShadow = config.shadows;
  
  scene.add(ground);
  propertyModel.components.ground = ground;
}

/**
 * Add skybox to scene
 */
function addSkybox() {
  const skyGeometry = new THREE.SphereGeometry(400, 32, 32);
  // Invert the geometry so that we see the inside
  skyGeometry.scale(-1, 1, 1);
  
  const skyMaterial = new THREE.MeshBasicMaterial({
    color: 0x87ceeb, // Light blue sky
    side: THREE.BackSide
  });
  
  const sky = new THREE.Mesh(skyGeometry, skyMaterial);
  scene.add(sky);
}

/**
 * Handle window resize
 */
function onWindowResize() {
  if (!containerEl || !camera || !renderer) return;
  
  camera.aspect = containerEl.clientWidth / containerEl.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(containerEl.clientWidth, containerEl.clientHeight);
}

/**
 * Animation loop
 */
function animate() {
  requestAnimationFrame(animate);
  if (controls) controls.update();
  if (renderer && scene && camera) renderer.render(scene, camera);
}

/**
 * Create a custom material based on property data
 * @param {string} type - Type of material: 'siding', 'roof', 'trim', 'window', 'door'
 * @param {object} propertyData - Property data with style information
 * @returns {THREE.Material} Material instance
 */
function createMaterial(type, propertyData) {
  // Default colors
  const defaultColors = {
    siding: 0xe8e8e8,  // Neutral light color
    roof: 0x606060,     // Medium gray
    trim: 0xffffff,     // White
    window: 0x88bbcc,   // Light blue glass
    door: 0x8b4513      // Brown wood
  };
  
  // Extract colors from property data if available
  let color = defaultColors[type];
  let roughness = 0.7;
  let metalness = 0.1;
  
  if (propertyData && propertyData.style) {
    if (propertyData.style[type + '_color']) {
      color = new THREE.Color(propertyData.style[type + '_color']);
    }
    
    if (propertyData.style[type + '_material']) {
      // Adjust material properties based on material type
      const materialType = propertyData.style[type + '_material'];
      
      if (materialType === 'brick') {
        roughness = 0.9;
        metalness = 0;
      } else if (materialType === 'vinyl') {
        roughness = 0.6;
        metalness = 0.05;
      } else if (materialType === 'metal') {
        roughness = 0.4;
        metalness = 0.7;
      } else if (materialType === 'glass') {
        roughness = 0.1;
        metalness = 0.9;
        // Additional glass properties
        return new THREE.MeshPhysicalMaterial({
          color: color,
          roughness: 0.1,
          metalness: 0.1,
          transparent: true,
          opacity: 0.8,
          clearcoat: 1.0,
          clearcoatRoughness: 0.1,
          envMapIntensity: 1.5
        });
      }
    }
  }
  
  // Apply quality settings based on device capabilities
  const materialOptions = {
    color: color,
    roughness: roughness, 
    metalness: metalness
  };
  
  // Adjust material quality based on device capabilities
  if (config.materialQuality === 'low') {
    // Simplify material for low-end devices
    return new THREE.MeshLambertMaterial({
      color: color
    });
  } else if (config.materialQuality === 'medium') {
    // Standard material with moderate settings
    return new THREE.MeshStandardMaterial(materialOptions);
  } else {
    // High quality with enhanced settings
    return new THREE.MeshStandardMaterial({
      ...materialOptions,
      envMapIntensity: 0.5,
      flatShading: false
    });
  }
}

/**
 * Load and create a 3D property model based on address data
 * @param {object} data - Property data from the server
 */
function loadPropertyModel(data) {
  if (!isInitialized) {
    console.error('Scene not initialized');
    toggleLoadingOverlay(false);
    showErrorMessage('3D engine initialization failed. Please refresh the page.');
    return;
  }
  
  if (!data || typeof data !== 'object') {
    console.error('Invalid property data provided:', data);
    toggleLoadingOverlay(false);
    showErrorMessage('Could not load property data. Please try again.');
    return;
  }
  
  try {
    // Start loading timer to ensure minimum display time for loading screen
    loadStartTime = Date.now();
    
    // Store model data
    modelData = data;
    
    // Create a group to hold all building components
    if (propertyModel.group) {
      // Remove old model if it exists
      scene.remove(propertyModel.group);
    }
    
    propertyModel.group = new THREE.Group();
    propertyModel.components = {};
    
    // Set up progressive loading to improve performance and user experience
    progressivelyLoadModel(0);
    
    console.log('3D property model loading started');
  } catch (error) {
    console.error('Error starting 3D model load:', error);
    toggleLoadingOverlay(false);
    showErrorMessage('Error rendering property model. Please try again.');
  }
}

/**
 * Progressively load model components to prevent UI blocking
 * @param {number} stage - The current loading stage
 */
function progressivelyLoadModel(stage) {
  try {
    // Update loading message if possible
    const loadingText = document.getElementById('loading-status-text');
    const loadingBar = document.getElementById('loading-progress-bar');
    
    // Progress bar update
    if (loadingBar) {
      loadingBar.style.width = `${Math.min(100, stage * 20)}%`;
    }
    
    // Handle each stage of loading
    switch (stage) {
      case 0: // Base structure
        if (loadingText) loadingText.textContent = 'Building structure...';
        createBuildingBase();
        setTimeout(() => progressivelyLoadModel(1), 10);
        break;
        
      case 1: // Roof
        if (loadingText) loadingText.textContent = 'Adding roof...';
        createRoof();
        setTimeout(() => progressivelyLoadModel(2), 10);
        break;
        
      case 2: // Windows and doors
        if (loadingText) loadingText.textContent = 'Adding details...';
        createWindows();
        createDoors();
        setTimeout(() => progressivelyLoadModel(3), 10);
        break;
        
      case 3: // Driveway
        if (loadingText) loadingText.textContent = 'Adding surroundings...';
        createDriveway();
        setTimeout(() => progressivelyLoadModel(4), 10);
        break;
        
      case 4: // Landscaping
        if (loadingText) loadingText.textContent = 'Adding landscaping...';
        createLandscaping();
        setTimeout(() => progressivelyLoadModel(5), 10);
        break;
        
      case 5: // Finalize
        if (loadingText) loadingText.textContent = 'Finalizing...';
        
        // Add model to scene if not already added
        if (propertyModel.group && propertyModel.group.parent !== scene) {
          scene.add(propertyModel.group);
        }
        
        // Position camera to focus on the property
        centerCameraOnProperty();
        
        // Complete loading after minimum time
        const loadTime = Date.now() - loadStartTime;
        const remainingTime = Math.max(0, config.loadingMinTime - loadTime);
        
        setTimeout(() => {
          toggleLoadingOverlay(false);
          if (loadingText) loadingText.textContent = 'Complete';
          console.log('3D property model loaded successfully');
          
          // Dispatch a custom event when loading is complete
          const event = new CustomEvent('modelLoadComplete', { 
            detail: { success: true } 
          });
          window.dispatchEvent(event);
        }, remainingTime);
        break;
    }
  } catch (error) {
    console.error('Error during progressive loading stage ' + stage + ':', error);
    toggleLoadingOverlay(false);
    showErrorMessage('Error rendering property model. Please try again.');
    
    // Dispatch a custom event for the error
    const event = new CustomEvent('modelLoadComplete', { 
      detail: { success: false, error: error.message } 
    });
    window.dispatchEvent(event);
  }
}

// Track loading start time globally
let loadStartTime = 0;

/**
 * Create the main structure of the building
 */
function createBuildingBase() {
  // Default dimensions if not provided in model data
  const width = modelData?.dimensions?.width || 10;
  const depth = modelData?.dimensions?.depth || 15;
  const height = modelData?.dimensions?.height || 6;
  
  // Main house body
  const geometry = new THREE.BoxGeometry(width, height, depth);
  const material = createMaterial('siding', modelData);
  
  const mainHouse = new THREE.Mesh(geometry, material);
  mainHouse.position.y = height / 2;
  mainHouse.castShadow = true;
  mainHouse.receiveShadow = true;
  
  propertyModel.group.add(mainHouse);
  propertyModel.components.mainHouse = mainHouse;
  
  // Add trim if specified
  if (modelData?.features?.includes('trim')) {
    createTrim(width, depth, height);
  }
}

/**
 * Create architectural trim
 */
function createTrim(width, depth, height) {
  const trimMaterial = createMaterial('trim', modelData);
  const trimThickness = 0.25;
  
  // Bottom trim
  const bottomTrimGeometry = new THREE.BoxGeometry(
    width + trimThickness, 
    trimThickness, 
    depth + trimThickness
  );
  const bottomTrim = new THREE.Mesh(bottomTrimGeometry, trimMaterial);
  bottomTrim.position.y = 0;
  bottomTrim.castShadow = true;
  bottomTrim.receiveShadow = true;
  propertyModel.group.add(bottomTrim);
  
  // Top trim
  const topTrimGeometry = new THREE.BoxGeometry(
    width + trimThickness, 
    trimThickness, 
    depth + trimThickness
  );
  const topTrim = new THREE.Mesh(topTrimGeometry, trimMaterial);
  topTrim.position.y = height;
  topTrim.castShadow = true;
  topTrim.receiveShadow = true;
  propertyModel.group.add(topTrim);
}

/**
 * Create roof based on property type
 */
function createRoof() {
  const width = modelData?.dimensions?.width || 10;
  const depth = modelData?.dimensions?.depth || 15;
  const height = modelData?.dimensions?.height || 6;
  
  const roofType = modelData?.style?.roof_type || 'gable';
  const roofMaterial = createMaterial('roof', modelData);
  
  let roof;
  
  // Create different roof types
  if (roofType === 'flat') {
    // Flat roof
    const roofGeometry = new THREE.BoxGeometry(width, 0.5, depth);
    roof = new THREE.Mesh(roofGeometry, roofMaterial);
    roof.position.y = height + 0.25;
    
  } else if (roofType === 'gable') {
    // Gable roof
    const roofHeight = modelData?.dimensions?.roof_height || 3;
    
    const roofGeometry = new THREE.BufferGeometry();
    const vertices = new Float32Array([
      // Left side
      -width/2, height, -depth/2,
      -width/2, height, depth/2,
      0, height + roofHeight, depth/2,
      
      -width/2, height, -depth/2,
      0, height + roofHeight, depth/2,
      0, height + roofHeight, -depth/2,
      
      // Right side
      width/2, height, -depth/2,
      0, height + roofHeight, -depth/2,
      0, height + roofHeight, depth/2,
      
      width/2, height, -depth/2,
      0, height + roofHeight, depth/2,
      width/2, height, depth/2
    ]);
    
    roofGeometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    roofGeometry.computeVertexNormals();
    
    roof = new THREE.Mesh(roofGeometry, roofMaterial);
    
  } else if (roofType === 'hip') {
    // Hip roof
    const roofHeight = modelData?.dimensions?.roof_height || 2;
    
    const shape = new THREE.Shape();
    shape.moveTo(-width/2, -depth/2);
    shape.lineTo(width/2, -depth/2);
    shape.lineTo(width/2, depth/2);
    shape.lineTo(-width/2, depth/2);
    shape.lineTo(-width/2, -depth/2);
    
    // Adjust geometry detail based on device capabilities
    let bevelSegments = 1; // Low quality default
    
    if (config.geometryDetail === 'medium') {
      bevelSegments = 2;
    } else if (config.geometryDetail === 'high') {
      bevelSegments = 4;
    }
    
    const extrudeSettings = {
      steps: 1,
      depth: 0,
      bevelEnabled: true,
      bevelThickness: roofHeight,
      bevelSize: width/4,
      bevelOffset: 0,
      bevelSegments: bevelSegments
    };
    
    const roofGeometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    roof = new THREE.Mesh(roofGeometry, roofMaterial);
    roof.position.y = height;
    roof.rotation.x = Math.PI/2;
  }
  
  if (roof) {
    roof.castShadow = true;
    roof.receiveShadow = true;
    propertyModel.group.add(roof);
    propertyModel.components.roof = roof;
  }
}

/**
 * Create windows
 */
function createWindows() {
  const width = modelData?.dimensions?.width || 10;
  const depth = modelData?.dimensions?.depth || 15;
  const height = modelData?.dimensions?.height || 6;
  
  const windowMaterial = createMaterial('window', modelData);
  const windowWidth = 1.2;
  const windowHeight = 1.5;
  const windowDepth = 0.1;
  
  // Window positions based on house size
  const positions = [
    // Front windows
    { x: -width/4, y: height/2, z: depth/2 + 0.01 },
    { x: width/4, y: height/2, z: depth/2 + 0.01 },
    
    // Side windows
    { x: -width/2 - 0.01, y: height/2, z: 0 },
    { x: width/2 + 0.01, y: height/2, z: 0 },
    
    // Back windows
    { x: -width/4, y: height/2, z: -depth/2 - 0.01 },
    { x: width/4, y: height/2, z: -depth/2 - 0.01 }
  ];
  
  const windowsGroup = new THREE.Group();
  
  // Create windows
  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i];
    const windowGeometry = new THREE.BoxGeometry(windowWidth, windowHeight, windowDepth);
    const window = new THREE.Mesh(windowGeometry, windowMaterial);
    
    window.position.set(pos.x, pos.y, pos.z);
    
    // Rotate side windows
    if (pos.x < -width/2 || pos.x > width/2) {
      window.rotation.y = Math.PI/2;
    }
    
    window.castShadow = true;
    window.receiveShadow = true;
    windowsGroup.add(window);
  }
  
  propertyModel.group.add(windowsGroup);
  propertyModel.components.windows = windowsGroup;
}

/**
 * Create doors
 */
function createDoors() {
  const depth = modelData?.dimensions?.depth || 15;
  const doorMaterial = createMaterial('door', modelData);
  
  // Front door dimensions
  const doorWidth = 1.0;
  const doorHeight = 2.0;
  const doorDepth = 0.1;
  
  const doorGeometry = new THREE.BoxGeometry(doorWidth, doorHeight, doorDepth);
  const door = new THREE.Mesh(doorGeometry, doorMaterial);
  
  // Position door on front of house
  door.position.set(0, doorHeight/2, depth/2 + 0.02);
  door.castShadow = true;
  door.receiveShadow = true;
  
  propertyModel.group.add(door);
  propertyModel.components.door = door;
}

/**
 * Create driveway
 */
function createDriveway() {
  if (!modelData?.features?.includes('driveway')) return;
  
  const depth = modelData?.dimensions?.depth || 15;
  const width = modelData?.dimensions?.width || 10;
  
  // Driveway dimensions
  const drivewayWidth = width * 0.6;
  const drivewayLength = depth * 0.8;
  
  const drivewayGeometry = new THREE.PlaneGeometry(drivewayWidth, drivewayLength);
  const drivewayMaterial = new THREE.MeshStandardMaterial({
    color: 0x888888,
    roughness: 0.9,
    metalness: 0
  });
  
  const driveway = new THREE.Mesh(drivewayGeometry, drivewayMaterial);
  driveway.rotation.x = -Math.PI/2;
  driveway.position.set(width * 0.6, 0.02, depth * 0.1);
  driveway.receiveShadow = true;
  
  propertyModel.group.add(driveway);
  propertyModel.components.driveway = driveway;
}

/**
 * Create landscaping elements
 */
function createLandscaping() {
  if (!modelData?.features?.includes('landscaping')) return;
  
  const width = modelData?.dimensions?.width || 10;
  const depth = modelData?.dimensions?.depth || 15;
  
  // Create trees
  createTrees(width, depth);
  
  // Create shrubs
  createShrubs(width, depth);
}

/**
 * Create trees
 */
function createTrees(houseWidth, houseDepth) {
  const treesGroup = new THREE.Group();
  
  // Tree material
  const trunkMaterial = new THREE.MeshStandardMaterial({
    color: 0x8B4513,
    roughness: 0.9,
    metalness: 0
  });
  
  const leavesMaterial = new THREE.MeshStandardMaterial({
    color: 0x2E8B57,
    roughness: 0.8,
    metalness: 0
  });
  
  // Tree positions
  const positions = [
    { x: -houseWidth, y: 0, z: houseDepth/2 },
    { x: houseWidth, y: 0, z: -houseDepth/2 }
  ];
  
  // Create trees
  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i];
    
    // Tree trunk
    const trunkGeometry = new THREE.CylinderGeometry(0.2, 0.3, 2, 8);
    const trunk = new THREE.Mesh(trunkGeometry, trunkMaterial);
    trunk.position.set(pos.x, 1, pos.z);
    trunk.castShadow = true;
    trunk.receiveShadow = true;
    
    // Tree leaves
    const leavesGeometry = new THREE.ConeGeometry(1.5, 3, 8);
    const leaves = new THREE.Mesh(leavesGeometry, leavesMaterial);
    leaves.position.set(pos.x, 3, pos.z);
    leaves.castShadow = true;
    leaves.receiveShadow = true;
    
    treesGroup.add(trunk);
    treesGroup.add(leaves);
  }
  
  propertyModel.group.add(treesGroup);
  propertyModel.components.trees = treesGroup;
}

/**
 * Create shrubs
 */
function createShrubs(houseWidth, houseDepth) {
  const shrubsGroup = new THREE.Group();
  
  // Shrub material
  const shrubMaterial = new THREE.MeshStandardMaterial({
    color: 0x228B22,
    roughness: 0.8,
    metalness: 0
  });
  
  // Shrub positions - along front of house
  const positions = [];
  for (let x = -houseWidth/2 + 1; x <= houseWidth/2 - 1; x += 1.5) {
    if (Math.abs(x) > 1) { // Skip area near the door
      positions.push({ x: x, y: 0, z: houseDepth/2 + 1 });
    }
  }
  
  // Create shrubs
  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i];
    
    // Shrub shape - slightly random
    const shrubGeometry = new THREE.SphereGeometry(
      0.5 + Math.random() * 0.2,
      8, 6
    );
    
    const shrub = new THREE.Mesh(shrubGeometry, shrubMaterial);
    shrub.position.set(pos.x, 0.5, pos.z);
    shrub.castShadow = true;
    shrub.receiveShadow = true;
    
    // Add some random variation to shape
    shrub.scale.y = 0.8 + Math.random() * 0.4;
    
    shrubsGroup.add(shrub);
  }
  
  propertyModel.group.add(shrubsGroup);
  propertyModel.components.shrubs = shrubsGroup;
}

/**
 * Center camera on property model
 */
function centerCameraOnProperty() {
  if (!propertyModel.group) return;
  
  // Reset camera position
  camera.position.set(0, config.cameraHeight, config.cameraDistance);
  camera.lookAt(0, 0, 0);
  
  // Reset controls target
  if (controls) {
    controls.target.set(0, 2, 0);
    controls.update();
  }
}

/**
 * Toggle loading overlay
 * @param {boolean} show - Whether to show or hide the overlay
 */
function toggleLoadingOverlay(show) {
  const overlay = document.getElementById('map-loading');
  if (!overlay) return;
  
  if (show) {
    overlay.style.display = 'flex';
  } else {
    // Use a timeout to ensure minimum display time
    setTimeout(() => {
      overlay.style.display = 'none';
    }, config.loadingMinTime);
  }
}

/**
 * Rotate the building view
 * @param {number} degrees - Degrees to rotate (positive = right, negative = left)
 */
function rotateBuildingView(degrees) {
  if (!controls) return;
  
  const radians = THREE.MathUtils.degToRad(degrees);
  
  // Get current camera position
  const currentPos = camera.position.clone();
  
  // Rotate position around y-axis
  const newX = currentPos.x * Math.cos(radians) + currentPos.z * Math.sin(radians);
  const newZ = -currentPos.x * Math.sin(radians) + currentPos.z * Math.cos(radians);
  
  // Update camera position
  camera.position.x = newX;
  camera.position.z = newZ;
  camera.lookAt(controls.target);
}

/**
 * Zoom the building view
 * @param {number} amount - Amount to zoom (positive = in, negative = out)
 */
function zoomBuildingView(amount) {
  if (!camera) return;
  
  // Get current direction vector from camera to target
  const target = controls ? controls.target : new THREE.Vector3(0, 0, 0);
  const direction = new THREE.Vector3().subVectors(camera.position, target).normalize();
  
  // Adjust position
  camera.position.addScaledVector(direction, -amount * 2);
  
  // Update controls
  if (controls) controls.update();
}

/**
 * Adjust time of day by changing light positions and intensities
 * @param {number} hour - Hour of day (0-23)
 */
function setTimeOfDay(hour) {
  if (!lights.directional || !lights.ambient || !lights.hemisphere) return;
  
  // Calculate sun position based on time
  const sunAngle = ((hour - 6) / 12) * Math.PI; // noon = 0 radians
  
  // Position sun
  const radius = 20;
  const sunX = radius * Math.sin(sunAngle);
  const sunY = radius * Math.abs(Math.sin(sunAngle)) + 5;
  const sunZ = radius * Math.cos(sunAngle);
  
  lights.directional.position.set(sunX, sunY, sunZ);
  
  // Adjust light intensities
  let ambientIntensity = 0.3;
  let directionalIntensity = 0.8;
  
  // Early morning
  if (hour < 7 || hour > 19) {
    ambientIntensity = 0.15;
    directionalIntensity = 0.3;
    scene.fog.color.set(0x7080a0); // Bluish fog color
  } 
  // Midday
  else if (hour >= 10 && hour <= 16) {
    ambientIntensity = 0.5;
    directionalIntensity = 1.0;
    scene.fog.color.set(0xeeeef0); // White fog color
  }
  // Morning/Evening
  else {
    ambientIntensity = 0.3;
    directionalIntensity = 0.7;
    
    // Golden hour colors
    if (hour > 16) {
      lights.directional.color.set(0xffc080); // Orange-ish sunset
      scene.fog.color.set(0xffc080); // Matching fog
    } else {
      lights.directional.color.set(0xfffbf0); // Slight morning warmth
      scene.fog.color.set(0xeeeef0); // Light fog
    }
  }
  
  lights.ambient.intensity = ambientIntensity;
  lights.directional.intensity = directionalIntensity;
}

/**
 * Display an error message to the user
 * @param {string} message - Error message to display
 */
function showErrorMessage(message) {
  // Look for existing error container
  let errorContainer = document.getElementById('model-error-container');
  
  // Create container if it doesn't exist
  if (!errorContainer) {
    errorContainer = document.createElement('div');
    errorContainer.id = 'model-error-container';
    errorContainer.style.position = 'absolute';
    errorContainer.style.bottom = '20px';
    errorContainer.style.left = '50%';
    errorContainer.style.transform = 'translateX(-50%)';
    errorContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.75)';
    errorContainer.style.color = '#fff';
    errorContainer.style.padding = '10px 20px';
    errorContainer.style.borderRadius = '5px';
    errorContainer.style.zIndex = '1000';
    errorContainer.style.maxWidth = '80%';
    errorContainer.style.textAlign = 'center';
    errorContainer.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.2)';
    errorContainer.style.fontFamily = 'Arial, sans-serif';
    
    if (containerEl) {
      containerEl.appendChild(errorContainer);
    } else {
      document.body.appendChild(errorContainer);
    }
  }
  
  // Set message and show
  errorContainer.textContent = message;
  errorContainer.style.display = 'block';
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    errorContainer.style.display = 'none';
  }, 5000);
}

// Export public functions
window.PropertyModel = {
  initialize: initializeScene,
  loadModel: loadPropertyModel,
  setTimeOfDay: setTimeOfDay,
  rotate: rotateBuildingView,
  zoom: zoomBuildingView
};

// Global rotation and zoom functions for direct HTML access
window.rotateBuildingView = rotateBuildingView;
window.zoomBuildingView = zoomBuildingView;