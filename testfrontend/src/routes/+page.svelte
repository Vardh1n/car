<script>
    import { onMount } from 'svelte';
    import "./style.css";
    
    // API Configuration
    let apiUrl = 'http://192.168.196.140:8000';
    let proxyUrl = 'http://localhost:8001'; // Client proxy server
    let connectionStatus = 'disconnected';
    
    // Pin data
    let pins = {};
    let availablePins = {};
    let predefinedPins = {};
    let allGpioPins = [13, 18, 22, 23, 24, 27];
    
    // Motor control state
    let motorStatus = {};
    let tankLeftSpeed = 0;
    let tankRightSpeed = 0;
    let directionalSpeed = 50;
    
    // Auto-refresh interval
    let refreshInterval;
    
    // Camera stream
    let ws;
    let imgUrl = '';
    let detectionInfo = [];
    let objectDetected = false;
    let findObject = '';
    let foundTarget = false;
    let cameraConnected = false;
    
    // Load initial data
    onMount(async () => {
        await checkConnection();
        await loadAllPins();
        await loadPredefinedPins();
        await loadMotorStatus();
        startCamera();
        
        // Auto-refresh every 2 seconds
        refreshInterval = setInterval(async () => {
            if (connectionStatus === 'connected') {
                await loadAllPins();
                await loadMotorStatus();
            }
        }, 2000);
        
        return () => {
            if (refreshInterval) clearInterval(refreshInterval);
            if (ws) ws.close();
        };
    });
    
    // Check API connection
    async function checkConnection() {
        try {
            const response = await fetch(`${apiUrl}/`);
            if (response.ok) {
                connectionStatus = 'connected';
                return true;
            }
        } catch (error) {
            connectionStatus = 'error';
            console.error('Connection failed:', error);
        }
        return false;
    }
    
    // API Functions
    async function makeRequest(endpoint, method = 'GET', body = null) {
        try {
            const config = {
                method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (body) {
                config.body = JSON.stringify(body);
            }
            
            const response = await fetch(`${apiUrl}${endpoint}`, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: 'Request failed' }));
                throw new Error(error.detail || 'Request failed');
            }
            
            connectionStatus = 'connected';
            return await response.json();
        } catch (error) {
            connectionStatus = 'error';
            console.error('API Error:', error);
            throw error;
        }
    }
    
    async function loadAllPins() {
        try {
            const data = await makeRequest('/pins/all');
            if (data) {
                pins = data.pins || {};
                availablePins = data.available_pins || {};
            }
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }
    
    async function loadPredefinedPins() {
        try {
            const data = await makeRequest('/pins/predefined');
            if (data) {
                predefinedPins = data.predefined_pins || {};
            }
        } catch (error) {
            console.error('Failed to load predefined pins:', error);
        }
    }
    
    async function loadMotorStatus() {
        try {
            const data = await makeRequest('/motor/status');
            if (data) {
                motorStatus = data.motor_status || {};
            }
        } catch (error) {
            console.error('Failed to load motor status:', error);
        }
    }
    
    async function quickConfigurePin(pin, mode) {
        try {
            const config = {
                pin: pin,
                mode: mode,
                initial_state: mode === 'output' ? false : null,
                pull_up_down: mode === 'input' ? 'floating' : null
            };
            
            await makeRequest('/pin/configure', 'POST', config);
            await loadAllPins();
        } catch (error) {
            console.error('Failed to configure pin:', error);
            alert(`Failed to configure pin: ${error.message}`);
        }
    }
    
    async function togglePin(pin) {
        try {
            const currentState = pins[pin]?.state || false;
            
            const data = {
                pin: pin,
                state: !currentState
            };
            
            await makeRequest('/digital/write', 'POST', data);
            await loadAllPins();
        } catch (error) {
            console.error('Failed to toggle pin:', error);
            alert(`Failed to toggle pin: ${error.message}`);
        }
    }
    
    // High/Low control functions
    async function setPinHigh(pin) {
        try {
            await makeRequest(`/digital/high/${pin}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to set pin high:', error);
            alert(`Failed to set pin high: ${error.message}`);
        }
    }
    
    async function setPinLow(pin) {
        try {
            await makeRequest(`/digital/low/${pin}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to set pin low:', error);
            alert(`Failed to set pin low: ${error.message}`);
        }
    }
    
    async function setPredefinedPinHigh(pinName) {
        try {
            await makeRequest(`/pins/predefined/${pinName}/high`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to set predefined pin high:', error);
            alert(`Failed to set ${pinName} high: ${error.message}`);
        }
    }
    
    async function setPredefinedPinLow(pinName) {
        try {
            await makeRequest(`/pins/predefined/${pinName}/low`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to set predefined pin low:', error);
            alert(`Failed to set ${pinName} low: ${error.message}`);
        }
    }
    
    // Motor control functions
    async function tankDrive(leftSpeed, rightSpeed) {
        try {
            const data = {
                left_speed: leftSpeed,
                right_speed: rightSpeed
            };
            
            await makeRequest('/motor/tank', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to execute tank drive:', error);
            alert(`Tank drive failed: ${error.message}`);
        }
    }
    
    let moving = false; // Prevent concurrent calls
    
    async function moveForward(speed = directionalSpeed) {
        if (moving) return;
        moving = true;
        try {
            // Check for object detection and target matching
            if (detectionInfo.length > 0 && findObject.trim()) {
                const match = detectionInfo.find(det =>
                    det.class.toLowerCase().includes(findObject.trim().toLowerCase())
                );
                if (!match) {
                    alert("Object detected! Cannot move forward unless target object is found.");
                    return;
                }
            }
            
            const data = { speed: speed };
            await makeRequest('/motor/forward', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to move forward:', error);
            alert(`Move forward failed: ${error.message}`);
        } finally {
            moving = false;
        }
    }
    
    async function moveBackward(speed = directionalSpeed) {
        try {
            const data = { speed: speed };
            await makeRequest('/motor/backward', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to move backward:', error);
            alert(`Move backward failed: ${error.message}`);
        }
    }
    
    async function turnLeft(speed = directionalSpeed) {
        try {
            const data = { speed: speed };
            await makeRequest('/motor/left', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to turn left:', error);
            alert(`Turn left failed: ${error.message}`);
        }
    }
    
    async function turnRight(speed = directionalSpeed) {
        try {
            const data = { speed: speed };
            await makeRequest('/motor/right', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to turn right:', error);
            alert(`Turn right failed: ${error.message}`);
        }
    }
    
    async function spinLeft(speed = directionalSpeed) {
        try {
            const data = { speed: speed };
            await makeRequest('/motor/spin-left', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to spin left:', error);
            alert(`Spin left failed: ${error.message}`);
        }
    }
    
    async function spinRight(speed = directionalSpeed) {
        try {
            const data = { speed: speed };
            await makeRequest('/motor/spin-right', 'POST', data);
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to spin right:', error);
            alert(`Spin right failed: ${error.message}`);
        }
    }
    
    async function stopMotors() {
        try {
            await makeRequest('/motor/stop', 'POST');
            await loadMotorStatus();
            tankLeftSpeed = 0;
            tankRightSpeed = 0;
        } catch (error) {
            console.error('Failed to stop motors:', error);
            alert(`Stop motors failed: ${error.message}`);
        }
    }
    
    async function setPWM(pin, dutyCycle) {
        try {
            if (!pins[pin]?.pwm) {
                // Start PWM with default frequency
                await makeRequest('/pwm/start', 'POST', {
                    pin: pin,
                    frequency: 1000,
                    duty_cycle: parseFloat(dutyCycle)
                });
            } else {
                // Update existing PWM
                await makeRequest('/pwm/update', 'PUT', {
                    pin: pin,
                    duty_cycle: parseFloat(dutyCycle)
                });
            }
            await loadAllPins();
        } catch (error) {
            console.error('Failed to set PWM:', error);
            alert(`PWM control failed: ${error.message}`);
        }
    }
    
    async function stopPWM(pin) {
        try {
            await makeRequest(`/pwm/stop/${pin}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to stop PWM:', error);
            alert(`Stop PWM failed: ${error.message}`);
        }
    }
    
    async function cleanupAllPins() {
        try {
            await makeRequest('/pins/cleanup', 'POST');
            await loadAllPins();
            await loadMotorStatus();
        } catch (error) {
            console.error('Failed to cleanup pins:', error);
            alert(`Cleanup failed: ${error.message}`);
        }
    }
    
    function getPinStatus(pin) {
        return pins[pin] || { mode: 'unconfigured', state: false };
    }
    
    function isPinConfigured(pin) {
        return pins.hasOwnProperty(pin);
    }
    
    function getPinName(pin) {
        for (let [name, pinNum] of Object.entries(predefinedPins)) {
            if (pinNum === pin) return name;
        }
        return `GPIO ${pin}`;
    }
    
    function checkAndMoveForward() {
        if (!objectDetected || !findObject.trim()) return;
        
        // Check if any detected object matches the target
        const match = detectionInfo.find(det => 
            det.class.toLowerCase().includes(findObject.trim().toLowerCase())
        );
        
        if (match) {
            foundTarget = true;
            // Optionally auto-move forward when target is found
            // moveForward();
        } else {
            foundTarget = false;
        }
    }
    
    function startCamera() {
        try {
            // Connect to the proxy camera WebSocket
            ws = new WebSocket(`ws://${proxyUrl.replace('http://', '').replace('https://', '')}/ws/proxy_camera`);
            ws.binaryType = 'arraybuffer';
            
            ws.onopen = () => {
                console.log('Camera WebSocket connected');
                cameraConnected = true;
            };
            
            ws.onmessage = (event) => {
                try {
                    // If it's a string, it's detection info
                    if (typeof event.data === "string") {
                        const info = JSON.parse(event.data);
                        detectionInfo = info.detections || [];
                        objectDetected = detectionInfo.length > 0;
                        checkAndMoveForward();
                    } else if (event.data instanceof ArrayBuffer) {
                        // It's the processed image with bounding boxes
                        const blob = new Blob([event.data], { type: 'image/jpeg' });
                        if (imgUrl) {
                            URL.revokeObjectURL(imgUrl); // Clean up previous URL
                        }
                        imgUrl = URL.createObjectURL(blob);
                    }
                } catch (error) {
                    console.error('Error processing camera data:', error);
                }
            };
            
            ws.onerror = (error) => {
                console.error('Camera WebSocket error:', error);
                cameraConnected = false;
            };
            
            ws.onclose = () => {
                console.log('Camera WebSocket closed');
                cameraConnected = false;
                // Attempt to reconnect after 3 seconds
                setTimeout(() => {
                    if (!cameraConnected) {
                        startCamera();
                    }
                }, 3000);
            };
        } catch (error) {
            console.error('Failed to start camera:', error);
            cameraConnected = false;
        }
    }
    
    // Keyboard controls
    function handleKeydown(event) {
        if (event.target.tagName === 'INPUT') return; // Don't interfere with input fields
        
        switch(event.key.toLowerCase()) {
            case 'w':
            case 'arrowup':
                event.preventDefault();
                moveForward();
                break;
            case 's':
            case 'arrowdown':
                event.preventDefault();
                moveBackward();
                break;
            case 'a':
            case 'arrowleft':
                event.preventDefault();
                turnLeft();
                break;
            case 'd':
            case 'arrowright':
                event.preventDefault();
                turnRight();
                break;
            case 'q':
                event.preventDefault();
                spinLeft();
                break;
            case 'e':
                event.preventDefault();
                spinRight();
                break;
            case ' ':
                event.preventDefault();
                stopMotors();
                break;
        }
    }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="container">
    <!-- Header -->
    <header>
        <h1>🔌 GPIO Controller</h1>
        <div class="connection-status {connectionStatus}">
            <div class="status-dot"></div>
            {connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'error' ? 'Disconnected' : 'Connecting...'}
        </div>
        
        <div class="api-config">
            <input type="text" bind:value={apiUrl} placeholder="http://192.168.196.140:8000" />
            <input type="text" bind:value={proxyUrl} placeholder="http://localhost:8001" />
            <button on:click={checkConnection} class="refresh-btn">🔄 Refresh</button>
            <button on:click={cleanupAllPins} class="cleanup-btn">🧹 Cleanup All</button>
        </div>
    </header>

    <main>
        <!-- Camera and Object Detection Section -->
        <section class="card camera-section">
            <h2>📹 Camera & Object Detection</h2>
            <div class="camera-controls">
                <div class="camera-stream">
                    <div class="video-container">
                        {#if imgUrl}
                            <img src={imgUrl} alt="Live Camera with YOLO Detection" />
                        {:else}
                            <div class="no-video">
                                <span>📷 No video feed</span>
                                <div class="camera-status {cameraConnected ? 'connected' : 'disconnected'}">
                                    {cameraConnected ? '🟢 Connected' : '🔴 Disconnected'}
                                </div>
                            </div>
                        {/if}
                        <button on:click={startCamera} class="camera-btn">
                            📹 {cameraConnected ? 'Restart' : 'Start'} Camera
                        </button>
                    </div>
                </div>
                
                <div class="detection-panel">
                    <div class="object-search">
                        <label>🎯 Target Object:</label>
                        <input 
                            type="text" 
                            bind:value={findObject} 
                            placeholder="e.g. person, car, bottle" 
                            on:input={checkAndMoveForward}
                        />
                        {#if foundTarget}
                            <div class="target-found">✅ Target found!</div>
                        {/if}
                    </div>
                    
                    <div class="detection-info">
                        <h4>Detected Objects:</h4>
                        {#if detectionInfo.length > 0}
                            <div class="detection-list">
                                {#each detectionInfo as detection}
                                    <div class="detection-item">
                                        <span class="object-name">{detection.class}</span>
                                        <span class="confidence">{Math.round(detection.confidence * 100)}%</span>
                                    </div>
                                {/each}
                            </div>
                        {:else}
                            <div class="no-detections">No objects detected</div>
                        {/if}
                    </div>
                </div>
            </div>
        </section>

        <!-- Motor Control Section -->
        <section class="card motor-section">
            <h2>🚗 Motor Control</h2>
            
            <div class="keyboard-hint">
                💡 Use keyboard: W/A/S/D or Arrow keys to control, Q/E for spin, Space to stop
            </div>
            
            <!-- Tank Drive Control -->
            <div class="motor-control-grid">
                <div class="tank-drive">
                    <h3>Tank Drive</h3>
                    <div class="tank-controls">
                        <div class="tank-slider">
                            <label>Left Motor: {tankLeftSpeed}%</label>
                            <input 
                                type="range" 
                                min="-100" 
                                max="100" 
                                bind:value={tankLeftSpeed}
                                on:input={() => tankDrive(tankLeftSpeed, tankRightSpeed)}
                                class="tank-range"
                            />
                        </div>
                        <div class="tank-slider">
                            <label>Right Motor: {tankRightSpeed}%</label>
                            <input 
                                type="range" 
                                min="-100" 
                                max="100" 
                                bind:value={tankRightSpeed}
                                on:input={() => tankDrive(tankLeftSpeed, tankRightSpeed)}
                                class="tank-range"
                            />
                        </div>
                    </div>
                </div>
                
                <!-- Directional Controls -->
                <div class="directional-controls">
                    <h3>Directional Control</h3>
                    <div class="speed-control">
                        <label>Speed: {directionalSpeed}%</label>
                        <input 
                            type="range" 
                            min="0" 
                            max="100" 
                            bind:value={directionalSpeed}
                            class="speed-slider"
                        />
                    </div>
                    
                    <div class="direction-grid">
                        <div></div>
                        <button 
                            on:click={() => moveForward()} 
                            class="direction-btn forward"
                            class:disabled={objectDetected && !foundTarget}
                        >
                            ⬆️ Forward
                        </button>
                        <div></div>
                        
                        <button on:click={() => turnLeft()} class="direction-btn left">⬅️ Left</button>
                        <button on:click={stopMotors} class="direction-btn stop">⏹️ Stop</button>
                        <button on:click={() => turnRight()} class="direction-btn right">➡️ Right</button>
                        
                        <button on:click={() => spinLeft()} class="direction-btn spin-left">↺ Spin L</button>
                        <button on:click={() => moveBackward()} class="direction-btn backward">⬇️ Backward</button>
                        <button on:click={() => spinRight()} class="direction-btn spin-right">↻ Spin R</button>
                    </div>
                </div>
            </div>
            
            <!-- Motor Status Display -->
            {#if Object.keys(motorStatus).length > 0}
                <div class="motor-status">
                    <h3>Motor Status</h3>
                    <div class="motor-status-grid">
                        {#each Object.entries(motorStatus) as [name, status]}
                            <div class="motor-pin-status">
                                <span class="motor-pin-name">{name}</span>
                                <span class="motor-pin-value {status.current_value ? 'high' : 'low'}">
                                    {status.current_value ? 'HIGH' : 'LOW'}
                                </span>
                                {#if status.pwm}
                                    <span class="motor-pwm">PWM: {status.pwm.duty_cycle}%</span>
                                {/if}
                            </div>
                        {/each}
                    </div>
                </div>
            {/if}
        </section>

        <!-- Predefined Pins (Quick Access) -->
        {#if Object.keys(predefinedPins).length > 0}
            <section class="card predefined-section">
                <h2>🎯 Quick Controls</h2>
                <div class="predefined-grid">
                    {#each Object.entries(predefinedPins) as [name, pin]}
                        {@const pinStatus = getPinStatus(pin)}
                        <div class="predefined-card {pinStatus.mode}">
                            <h3>{name}</h3>
                            <p class="pin-number">GPIO {pin}</p>
                            
                            {#if !isPinConfigured(pin)}
                                <div class="config-buttons">
                                    <button on:click={() => quickConfigurePin(pin, 'output')} class="config-btn output">
                                        ⚡ Output
                                    </button>
                                    <button on:click={() => quickConfigurePin(pin, 'input')} class="config-btn input">
                                        📥 Input
                                    </button>
                                </div>
                            {:else if pinStatus.mode === 'output'}
                                <div class="output-controls">
                                    <div class="high-low-buttons">
                                        <button 
                                            class="hl-btn high {pinStatus.state ? 'active' : ''}"
                                            on:click={() => setPredefinedPinHigh(name)}
                                        >
                                            🟢 HIGH
                                        </button>
                                        <button 
                                            class="hl-btn low {!pinStatus.state ? 'active' : ''}"
                                            on:click={() => setPredefinedPinLow(name)}
                                        >
                                            🔴 LOW
                                        </button>
                                    </div>
                                    
                                    <button 
                                        class="power-btn {pinStatus.state ? 'on' : 'off'}"
                                        on:click={() => togglePin(pin)}
                                    >
                                        {pinStatus.state ? '🟢 ON' : '🔴 OFF'}
                                    </button>
                                    
                                    <div class="pwm-section">
                                        <label>PWM Power: {pinStatus.pwm?.duty_cycle || 0}%</label>
                                        <input 
                                            type="range" 
                                            min="0" 
                                            max="100" 
                                            value={pinStatus.pwm?.duty_cycle || 0}
                                            on:input={(e) => setPWM(pin, e.target.value)}
                                            class="power-slider"
                                        />
                                        {#if pinStatus.pwm}
                                            <button on:click={() => stopPWM(pin)} class="stop-pwm">Stop PWM</button>
                                        {/if}
                                    </div>
                                </div>
                            {:else}
                                <div class="input-display">
                                    <div class="input-value {pinStatus.current_value ? 'high' : 'low'}">
                                        {pinStatus.current_value ? 'HIGH' : 'LOW'}
                                    </div>
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            </section>
        {/if}
    </main>
</div>

<style>
    /* Add these new styles for the camera section */
    .camera-section {
        margin-bottom: 2rem;
    }
    
    .camera-controls {
        display: flex;
        gap: 2rem;
        align-items: flex-start;
    }
    
    .video-container {
        width: 500px;
        height: 375px;
        background: #222;
        border-radius: 12px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 2px solid #444;
        position: relative;
    }
    
    .video-container img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    
    .no-video {
        text-align: center;
        color: #888;
    }
    
    .camera-status {
        margin-top: 1rem;
        font-size: 0.9rem;
        padding: 0.3rem 0.6rem;
        border-radius: 5px;
    }
    
    .camera-status.connected {
        background: #1a5f1a;
        color: #4caf50;
    }
    
    .camera-status.disconnected {
        background: #5f1a1a;
        color: #f44336;
    }
    
    .camera-btn {
        position: absolute;
        top: 10px;
        right: 10px;
        background: #333;
        color: #fff;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        cursor: pointer;
        font-size: 0.8rem;
    }
    
    .camera-btn:hover {
        background: #555;
    }
    
    .detection-panel {
        flex: 1;
        min-width: 300px;
    }
    
    .object-search {
        margin-bottom: 1.5rem;
    }
    
    .object-search label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    
    .object-search input {
        width: 100%;
        padding: 0.5rem;
        border: 1px solid #ddd;
        border-radius: 5px;
        font-size: 1rem;
    }
    
    .target-found {
        color: #4caf50;
        font-weight: bold;
        margin-top: 0.5rem;
        padding: 0.5rem;
        background: #e8f5e8;
        border-radius: 5px;
    }
    
    .detection-info h4 {
        margin-bottom: 1rem;
    }
    
    .detection-list {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    
    .detection-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem;
        background: #f5f5f5;
        border-radius: 5px;
        border-left: 4px solid #ff6b35;
    }
    
    .object-name {
        font-weight: bold;
        text-transform: capitalize;
    }
    
    .confidence {
        background: #ff6b35;
        color: white;
        padding: 0.2rem 0.4rem;
        border-radius: 3px;
        font-size: 0.8rem;
    }
    
    .no-detections {
        color: #888;
        font-style: italic;
        padding: 1rem;
        text-align: center;
        background: #f9f9f9;
        border-radius: 5px;
    }
    
    .keyboard-hint {
        background: #e3f2fd;
        padding: 0.8rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        font-size: 0.9rem;
        color: #1976d2;
        border-left: 4px solid #2196f3;
    }
    
    .direction-btn.disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    
    /* Existing styles remain the same */
    /* ... rest of your existing CSS ... */
</style>
