<script>
    import { onMount } from 'svelte';
    import "./style.css";
    // API Configuration
    let apiUrl = 'http://192.168.196.140:8000';
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
    
    // Load initial data
    onMount(async () => {
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
        };
    });
    
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
                const error = await response.json();
                throw new Error(error.detail || 'Request failed');
            }
            
            connectionStatus = 'connected';
            return await response.json();
        } catch (error) {
            connectionStatus = 'error';
            console.error('API Error:', error);
            return null;
        }
    }
    
    async function loadAllPins() {
        try {
            const data = await makeRequest('/pins/all');
            if (data) {
                pins = data.pins;
                availablePins = data.available_pins;
            }
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }
    
    async function loadPredefinedPins() {
        try {
            const data = await makeRequest('/pins/predefined');
            if (data) {
                predefinedPins = data.predefined_pins;
            }
        } catch (error) {
            console.error('Failed to load predefined pins:', error);
        }
    }
    
    async function loadMotorStatus() {
        try {
            const data = await makeRequest('/motor/status');
            if (data) {
                motorStatus = data.motor_status;
            }
        } catch (error) {
            console.error('Failed to load motor status:', error);
        }
    }
    
    async function quickConfigurePin(pin, mode) {
        const config = {
            pin: pin,
            mode: mode,
            initial_state: mode === 'output' ? false : null,
            pull_up_down: mode === 'input' ? 'floating' : null
        };
        
        await makeRequest('/pin/configure', 'POST', config);
        await loadAllPins();
    }
    
    async function togglePin(pin) {
        const currentState = pins[pin]?.state || false;
        
        const data = {
            pin: pin,
            state: !currentState
        };
        
        await makeRequest('/digital/write', 'POST', data);
        await loadAllPins();
    }
    
    // New high/low control functions
    async function setPinHigh(pin) {
        await makeRequest(`/digital/high/${pin}`, 'POST');
        await loadAllPins();
    }
    
    async function setPinLow(pin) {
        await makeRequest(`/digital/low/${pin}`, 'POST');
        await loadAllPins();
    }
    
    async function setPredefinedPinHigh(pinName) {
        await makeRequest(`/pins/predefined/${pinName}/high`, 'POST');
        await loadAllPins();
    }
    
    async function setPredefinedPinLow(pinName) {
        await makeRequest(`/pins/predefined/${pinName}/low`, 'POST');
        await loadAllPins();
    }
    
    // Motor control functions
    async function tankDrive(leftSpeed, rightSpeed) {
        const data = {
            left_speed: leftSpeed,
            right_speed: rightSpeed
        };
        
        await makeRequest('/motor/tank', 'POST', data);
        await loadMotorStatus();
    }
    
    async function moveForward(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/forward', 'POST', data);
        await loadMotorStatus();
    }
    
    async function moveBackward(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/backward', 'POST', data);
        await loadMotorStatus();
    }
    
    async function turnLeft(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/left', 'POST', data);
        await loadMotorStatus();
    }
    
    async function turnRight(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/right', 'POST', data);
        await loadMotorStatus();
    }
    
    async function spinLeft(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/spin-left', 'POST', data);
        await loadMotorStatus();
    }
    
    async function spinRight(speed = directionalSpeed) {
        const data = { speed: speed };
        await makeRequest('/motor/spin-right', 'POST', data);
        await loadMotorStatus();
    }
    
    async function stopMotors() {
        await makeRequest('/motor/stop', 'POST');
        await loadMotorStatus();
        tankLeftSpeed = 0;
        tankRightSpeed = 0;
    }
    
    async function setPWM(pin, dutyCycle) {
        if (!pins[pin]?.pwm) {
            // Start PWM with default frequency
            await makeRequest('/pwm/start', 'POST', {
                pin: pin,
                frequency: 1000,
                duty_cycle: dutyCycle
            });
        } else {
            // Update existing PWM
            await makeRequest('/pwm/update', 'PUT', {
                pin: pin,
                duty_cycle: dutyCycle
            });
        }
        await loadAllPins();
    }
    
    async function stopPWM(pin) {
        await makeRequest(`/pwm/stop/${pin}`, 'POST');
        await loadAllPins();
    }
    
    async function cleanupAllPins() {
        await makeRequest('/pins/cleanup', 'POST');
        await loadAllPins();
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
    
    function startCamera() {
        ws = new WebSocket('ws://localhost:8000/ws/proxy_camera');
        ws.binaryType = 'arraybuffer';
        ws.onmessage = (event) => {
            const blob = new Blob([event.data], { type: 'image/jpeg' });
            imgUrl = URL.createObjectURL(blob);
        };
        ws.onclose = () => {
            // Optionally handle reconnect
        };
    }
</script>

<div class="container">
    <!-- Header -->
    <header>
        <h1>🔌 GPIO Controller</h1>
        <div class="connection-status {connectionStatus}">
            <div class="status-dot"></div>
            {connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'error' ? 'Disconnected' : 'Connecting...'}
        </div>
        
        <div class="api-config">
            <input type="text" bind:value={apiUrl} placeholder="http://192.168.1.100:8000" />
            <button on:click={loadAllPins} class="refresh-btn">🔄 Refresh</button>
            <button on:click={cleanupAllPins} class="cleanup-btn">🧹 Cleanup All</button>
        </div>
    </header>

    <main>
        <!-- Motor Control Section -->
        <section class="card motor-section">
            <h2>🚗 Motor Control</h2>
            
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
                        <button on:click={() => moveForward()} class="direction-btn forward">⬆️ Forward</button>
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

<button on:click={startCamera}>Start Camera</button>
{#if imgUrl}
    <img src={imgUrl} alt="Live Camera" />
{/if}
    </main>
</div>
