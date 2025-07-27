<script>
    import { onMount } from 'svelte';
    
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
    
    // Load initial data
    onMount(async () => {
        await loadAllPins();
        await loadPredefinedPins();
        await loadMotorStatus();
        
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

        <!-- All GPIO Pins Grid -->
        <section class="card">
            <h2>📍 All GPIO Pins</h2>
            <div class="gpio-grid">
                {#each allGpioPins as pin}
                    {@const pinStatus = getPinStatus(pin)}
                    {@const pinName = getPinName(pin)}
                    <div class="gpio-pin {pinStatus.mode} {pinStatus.state ? 'active' : ''}">
                        <div class="pin-header">
                            <span class="pin-name">{pinName}</span>
                            <span class="pin-number">#{pin}</span>
                        </div>
                        
                        <div class="pin-status-indicator {pinStatus.mode}">
                            {#if pinStatus.mode === 'unconfigured'}
                                ⚪
                            {:else if pinStatus.mode === 'output'}
                                {pinStatus.state ? '🟢' : '🔴'}
                            {:else}
                                📥
                            {/if}
                        </div>
                        
                        {#if !isPinConfigured(pin)}
                            <div class="quick-config">
                                <button on:click={() => quickConfigurePin(pin, 'output')} class="mini-btn output">⚡</button>
                                <button on:click={() => quickConfigurePin(pin, 'input')} class="mini-btn input">📥</button>
                            </div>
                        {:else if pinStatus.mode === 'output'}
                            <div class="pin-controls">
                                <div class="mini-hl-buttons">
                                    <button 
                                        class="mini-hl-btn high {pinStatus.state ? 'active' : ''}"
                                        on:click={() => setPinHigh(pin)}
                                        title="Set HIGH"
                                    >
                                        H
                                    </button>
                                    <button 
                                        class="mini-hl-btn low {!pinStatus.state ? 'active' : ''}"
                                        on:click={() => setPinLow(pin)}
                                        title="Set LOW"
                                    >
                                        L
                                    </button>
                                </div>
                                
                                <button 
                                    class="toggle-btn {pinStatus.state ? 'on' : 'off'}"
                                    on:click={() => togglePin(pin)}
                                >
                                    {pinStatus.state ? 'ON' : 'OFF'}
                                </button>
                                
                                <div class="pwm-mini">
                                    <input 
                                        type="range" 
                                        min="0" 
                                        max="100" 
                                        value={pinStatus.pwm?.duty_cycle || 0}
                                        on:input={(e) => setPWM(pin, e.target.value)}
                                        class="mini-slider"
                                    />
                                    <span class="pwm-value">{pinStatus.pwm?.duty_cycle || 0}%</span>
                                </div>
                            </div>
                        {:else}
                            <div class="input-mini">
                                <span class="input-state {pinStatus.current_value ? 'high' : 'low'}">
                                    {pinStatus.current_value ? 'HIGH' : 'LOW'}
                                </span>
                            </div>
                        {/if}
                    </div>
                {/each}
            </div>
        </section>

        <!-- System Info -->
        <section class="card system-info">
            <h2>📊 System Status</h2>
            <div class="stats">
                <div class="stat">
                    <span class="stat-label">Total Pins:</span>
                    <span class="stat-value">{allGpioPins.length}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Configured:</span>
                    <span class="stat-value">{Object.keys(pins).length}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Output Pins:</span>
                    <span class="stat-value">{Object.values(pins).filter(p => p.mode === 'output').length}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">PWM Active:</span>
                    <span class="stat-value">{Object.values(pins).filter(p => p.pwm).length}</span>
                </div>
            </div>
        </section>
    </main>
</div>

<style>
    * {
        box-sizing: border-box;
    }

    .container {
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
        font-family: 'Inter', 'Segoe UI', sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }

    /* Motor Control Styles */
    .motor-section {
        margin-bottom: 30px;
    }

    .motor-control-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
        margin-bottom: 30px;
    }

    .tank-drive, .directional-controls {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    .tank-drive h3, .directional-controls h3 {
        margin-top: 0;
        color: #2d3748;
        text-align: center;
    }

    .tank-controls {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .tank-slider label {
        display: block;
        margin-bottom: 8px;
        font-weight: 600;
        color: #4a5568;
    }

    .tank-range, .speed-slider {
        width: 100%;
        height: 8px;
        border-radius: 5px;
        background: #e2e8f0;
        outline: none;
        -webkit-appearance: none;
    }

    .tank-range::-webkit-slider-thumb, .speed-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #667eea;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }

    .direction-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 10px;
        margin-top: 15px;
    }

    .direction-btn {
        padding: 15px 10px;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 14px;
        background: #f7fafc;
        color: #4a5568;
        border: 2px solid #e2e8f0;
    }

    .direction-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }

    .direction-btn.forward, .direction-btn.backward {
        background: #4299e1;
        color: white;
        border-color: #4299e1;
    }

    .direction-btn.left, .direction-btn.right {
        background: #48bb78;
        color: white;
        border-color: #48bb78;
    }

    .direction-btn.spin-left, .direction-btn.spin-right {
        background: #ed8936;
        color: white;
        border-color: #ed8936;
    }

    .direction-btn.stop {
        background: #e53e3e;
        color: white;
        border-color: #e53e3e;
    }

    .motor-status {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }

    .motor-status h3 {
        margin-top: 0;
        color: #2d3748;
        text-align: center;
    }

    .motor-status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 15px;
    }

    .motor-pin-status {
        text-align: center;
        padding: 15px;
        background: #f7fafc;
        border-radius: 10px;
        border: 2px solid #e2e8f0;
    }

    .motor-pin-name {
        display: block;
        font-weight: 600;
        color: #2d3748;
        margin-bottom: 5px;
    }

    .motor-pin-value {
        display: block;
        font-size: 12px;
        padding: 4px 8px;
        border-radius: 6px;
        margin-bottom: 5px;
    }

    .motor-pin-value.high {
        background: #c6f6d5;
        color: #22543d;
    }

    .motor-pin-value.low {
        background: #fed7d7;
        color: #742a2a;
    }

    .motor-pwm {
        display: block;
        font-size: 10px;
        color: #718096;
    }

    /* High/Low Button Styles */
    .high-low-buttons {
        display: flex;
        gap: 10px;
        margin-bottom: 15px;
    }

    .hl-btn {
        flex: 1;
        padding: 12px;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 14px;
        opacity: 0.6;
    }

    .hl-btn.high {
        background: #48bb78;
        color: white;
    }

    .hl-btn.low {
        background: #e53e3e;
        color: white;
    }

    .hl-btn.active {
        opacity: 1;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
    }

    .mini-hl-buttons {
        display: flex;
        gap: 5px;
        margin-bottom: 8px;
    }

    .mini-hl-btn {
        flex: 1;
        padding: 6px;
        border: none;
        border-radius: 4px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 10px;
        opacity: 0.6;
    }

    .mini-hl-btn.high {
        background: #48bb78;
        color: white;
    }

    .mini-hl-btn.low {
        background: #e53e3e;
        color: white;
    }

    .mini-hl-btn.active {
        opacity: 1;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
    }

    header {
        text-align: center;
        margin-bottom: 30px;
        padding: 30px;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }

    h1 {
        margin: 0 0 20px 0;
        font-size: 3em;
        background: linear-gradient(45deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }

    .connection-status {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 20px;
        border-radius: 50px;
        font-weight: 600;
        margin-bottom: 20px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .status-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    .connection-status.connected {
        background: #d4edda;
        color: #155724;
    }

    .connection-status.connected .status-dot {
        background: #28a745;
    }

    .connection-status.error {
        background: #f8d7da;
        color: #721c24;
    }

    .connection-status.error .status-dot {
        background: #dc3545;
    }

    .connection-status.disconnected {
        background: #fff3cd;
        color: #856404;
    }

    .connection-status.disconnected .status-dot {
        background: #ffc107;
    }

    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }

    .api-config {
        display: flex;
        gap: 15px;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
    }

    .api-config input {
        padding: 12px 20px;
        border: 2px solid #e0e0e0;
        border-radius: 50px;
        font-size: 16px;
        min-width: 300px;
        background: white;
        transition: all 0.3s;
    }

    .api-config input:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 30px;
        margin-bottom: 30px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }

    .card h2 {
        margin-top: 0;
        color: #2d3748;
        font-size: 1.8em;
        font-weight: 600;
        margin-bottom: 25px;
    }

    .predefined-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 20px;
    }

    .predefined-card {
        background: white;
        border-radius: 15px;
        padding: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 3px solid transparent;
        transition: all 0.3s;
    }

    .predefined-card.output {
        border-color: #48bb78;
    }

    .predefined-card.input {
        border-color: #4299e1;
    }

    .predefined-card h3 {
        margin: 0 0 10px 0;
        font-size: 1.5em;
        color: #2d3748;
    }

    .pin-number {
        color: #718096;
        font-weight: 500;
        margin-bottom: 20px;
    }

    .config-buttons {
        display: flex;
        gap: 10px;
    }

    .config-btn {
        flex: 1;
        padding: 15px;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
        font-size: 16px;
    }

    .config-btn.output {
        background: #48bb78;
        color: white;
    }

    .config-btn.input {
        background: #4299e1;
        color: white;
    }

    .config-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }

    .power-btn {
        width: 100%;
        padding: 20px;
        border: none;
        border-radius: 15px;
        font-size: 18px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s;
        margin-bottom: 20px;
    }

    .power-btn.on {
        background: #48bb78;
        color: white;
        box-shadow: 0 0 20px rgba(72, 187, 120, 0.4);
    }

    .power-btn.off {
        background: #e2e8f0;
        color: #4a5568;
    }

    .pwm-section label {
        display: block;
        margin-bottom: 10px;
        font-weight: 600;
        color: #4a5568;
    }

    .power-slider {
        width: 100%;
        height: 8px;
        border-radius: 5px;
        background: #e2e8f0;
        outline: none;
        -webkit-appearance: none;
        margin-bottom: 15px;
    }

    .power-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #667eea;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }

    .gpio-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 15px;
    }

    .gpio-pin {
        background: white;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 2px solid #e2e8f0;
        transition: all 0.3s;
        position: relative;
    }

    .gpio-pin.output {
        border-color: #48bb78;
    }

    .gpio-pin.input {
        border-color: #4299e1;
    }

    .gpio-pin.active {
        box-shadow: 0 0 15px rgba(72, 187, 120, 0.3);
    }

    .pin-header {
        margin-bottom: 10px;
    }

    .pin-name {
        font-weight: 600;
        color: #2d3748;
        display: block;
        font-size: 14px;
    }

    .pin-number {
        font-size: 12px;
        color: #718096;
    }

    .pin-status-indicator {
        font-size: 24px;
        margin: 10px 0;
    }

    .quick-config {
        display: flex;
        gap: 5px;
        margin-top: 10px;
    }

    .mini-btn {
        flex: 1;
        padding: 8px;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.3s;
    }

    .mini-btn.output {
        background: #48bb78;
        color: white;
    }

    .mini-btn.input {
        background: #4299e1;
        color: white;
    }

    .toggle-btn {
        width: 100%;
        padding: 8px;
        border: none;
        border-radius: 6px;
        margin-bottom: 10px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
    }

    .toggle-btn.on {
        background: #48bb78;
        color: white;
    }

    .toggle-btn.off {
        background: #e2e8f0;
        color: #4a5568;
    }

    .mini-slider {
        width: 100%;
        height: 4px;
        margin-bottom: 5px;
    }

    .pwm-value {
        font-size: 10px;
        color: #718096;
    }

    .input-display, .input-mini {
        margin-top: 10px;
    }

    .input-value, .input-state {
        padding: 10px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 12px;
    }

    .input-value.high, .input-state.high {
        background: #c6f6d5;
        color: #22543d;
    }

    .input-value.low, .input-state.low {
        background: #fed7d7;
        color: #742a2a;
    }

    .system-info .stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 20px;
    }

    .stat {
        text-align: center;
        padding: 20px;
        background: #f7fafc;
        border-radius: 12px;
    }

    .stat-label {
        display: block;
        color: #718096;
        font-size: 14px;
        margin-bottom: 5px;
    }

    .stat-value {
        display: block;
        color: #2d3748;
        font-size: 24px;
        font-weight: 700;
    }

    .refresh-btn, .cleanup-btn {
        padding: 12px 24px;
        border: none;
        border-radius: 50px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
    }

    .refresh-btn {
        background: #4299e1;
        color: white;
    }

    .cleanup-btn {
        background: #e53e3e;
        color: white;
    }

    .refresh-btn:hover, .cleanup-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }

    .stop-pwm {
        padding: 8px 16px;
        background: #e53e3e;
        color: white;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 12px;
    }

    /* Responsive design */
    @media (max-width: 768px) {
        .container {
            padding: 10px;
        }
        
        h1 {
            font-size: 2em;
        }
        
        .motor-control-grid {
            grid-template-columns: 1fr;
        }
        
        .direction-grid {
            grid-template-columns: 1fr 1fr;
        }
        
        .gpio-grid {
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        }
        
        .predefined-grid {
            grid-template-columns: 1fr;
        }
        
        .api-config {
            flex-direction: column;
        }
        
        .api-config input {
            min-width: auto;
            width: 100%;
        }
    }
</style>