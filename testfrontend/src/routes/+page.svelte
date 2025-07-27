<script>
    import { onMount } from 'svelte';
    
    // API Configuration
    let apiUrl = 'http://192.168.196.140:8000'; // Default IP, make this configurable
    let connectionStatus = 'disconnected';
    
    // Pin data
    let pins = {};
    let availablePins = {};
    let predefinedPins = {};
    
    // Form data
    let newPinConfig = {
        pin: '',
        mode: 'output',
        initial_state: false,
        pull_up_down: 'floating'
    };
    
    let digitalWriteData = {
        pin: '',
        state: false
    };
    
    let pwmConfig = {
        pin: '',
        frequency: 1000,
        duty_cycle: 0
    };
    
    // Load initial data
    onMount(async () => {
        await loadAllPins();
        await loadPredefinedPins();
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
            alert(`Error: ${error.message}`);
            throw error;
        }
    }
    
    async function loadAllPins() {
        try {
            const data = await makeRequest('/pins/all');
            pins = data.pins;
            availablePins = data.available_pins;
        } catch (error) {
            console.error('Failed to load pins:', error);
        }
    }
    
    async function loadPredefinedPins() {
        try {
            const data = await makeRequest('/pins/predefined');
            predefinedPins = data.predefined_pins;
        } catch (error) {
            console.error('Failed to load predefined pins:', error);
        }
    }
    
    async function configurePin() {
        try {
            const config = {
                pin: parseInt(newPinConfig.pin),
                mode: newPinConfig.mode,
                initial_state: newPinConfig.mode === 'output' ? newPinConfig.initial_state : null,
                pull_up_down: newPinConfig.mode === 'input' ? newPinConfig.pull_up_down : null
            };
            
            await makeRequest('/pin/configure', 'POST', config);
            await loadAllPins();
            
            // Reset form
            newPinConfig = { pin: '', mode: 'output', initial_state: false, pull_up_down: 'floating' };
        } catch (error) {
            console.error('Failed to configure pin:', error);
        }
    }
    
    async function digitalWrite() {
        try {
            const data = {
                pin: parseInt(digitalWriteData.pin),
                state: digitalWriteData.state
            };
            
            await makeRequest('/digital/write', 'POST', data);
            await loadAllPins();
        } catch (error) {
            console.error('Failed to write digital pin:', error);
        }
    }
    
    async function digitalRead(pin) {
        try {
            const data = await makeRequest(`/digital/read/${pin}`);
            await loadAllPins();
            return data;
        } catch (error) {
            console.error('Failed to read digital pin:', error);
        }
    }
    
    async function startPWM() {
        try {
            const config = {
                pin: parseInt(pwmConfig.pin),
                frequency: parseFloat(pwmConfig.frequency),
                duty_cycle: parseFloat(pwmConfig.duty_cycle)
            };
            
            await makeRequest('/pwm/start', 'POST', config);
            await loadAllPins();
        } catch (error) {
            console.error('Failed to start PWM:', error);
        }
    }
    
    async function updatePWM(pin, dutyCycle) {
        try {
            const data = {
                pin: parseInt(pin),
                duty_cycle: parseFloat(dutyCycle)
            };
            
            await makeRequest('/pwm/update', 'PUT', data);
            await loadAllPins();
        } catch (error) {
            console.error('Failed to update PWM:', error);
        }
    }
    
    async function stopPWM(pin) {
        try {
            await makeRequest(`/pwm/stop/${pin}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to stop PWM:', error);
        }
    }
    
    async function cleanupAllPins() {
        try {
            await makeRequest('/pins/cleanup', 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to cleanup pins:', error);
        }
    }
    
    async function togglePredefinedPin(pinName, currentState) {
        try {
            const newState = !currentState;
            await makeRequest(`/pins/predefined/${pinName}/digital?state=${newState}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to toggle predefined pin:', error);
        }
    }
    
    async function updatePredefinedPWM(pinName, dutyCycle) {
        try {
            await makeRequest(`/pins/predefined/${pinName}/pwm?duty_cycle=${dutyCycle}`, 'POST');
            await loadAllPins();
        } catch (error) {
            console.error('Failed to update predefined PWM:', error);
        }
    }
</script>

<div class="container">
    <header>
        <h1>GPIO Controller</h1>
        <div class="connection-status {connectionStatus}">
            Status: {connectionStatus.toUpperCase()}
        </div>
        
        <div class="api-config">
            <label>
                API URL:
                <input type="text" bind:value={apiUrl} placeholder="http://192.168.1.100:8000" />
            </label>
            <button on:click={loadAllPins}>Refresh</button>
        </div>
    </header>

    <main>
        <!-- Pin Configuration Section -->
        <section class="card">
            <h2>Configure New Pin</h2>
            <form on:submit|preventDefault={configurePin}>
                <div class="form-group">
                    <label>
                        Pin Number:
                        <input type="number" bind:value={newPinConfig.pin} required />
                    </label>
                    
                    <label>
                        Mode:
                        <select bind:value={newPinConfig.mode}>
                            <option value="output">Output</option>
                            <option value="input">Input</option>
                        </select>
                    </label>
                    
                    {#if newPinConfig.mode === 'output'}
                        <label>
                            <input type="checkbox" bind:checked={newPinConfig.initial_state} />
                            Initial State (HIGH)
                        </label>
                    {/if}
                    
                    {#if newPinConfig.mode === 'input'}
                        <label>
                            Pull Resistor:
                            <select bind:value={newPinConfig.pull_up_down}>
                                <option value="floating">Floating</option>
                                <option value="up">Pull Up</option>
                                <option value="down">Pull Down</option>
                            </select>
                        </label>
                    {/if}
                </div>
                
                <button type="submit">Configure Pin</button>
            </form>
        </section>

        <!-- Quick Digital Control -->
        <section class="card">
            <h2>Digital Control</h2>
            <form on:submit|preventDefault={digitalWrite}>
                <div class="form-group">
                    <label>
                        Pin:
                        <select bind:value={digitalWriteData.pin} required>
                            <option value="">Select Pin</option>
                            {#each Object.entries(pins).filter(([pin, config]) => config.mode === 'output') as [pin, config]}
                                <option value={pin}>Pin {pin}</option>
                            {/each}
                        </select>
                    </label>
                    
                    <label>
                        <input type="checkbox" bind:checked={digitalWriteData.state} />
                        Set HIGH
                    </label>
                </div>
                
                <button type="submit">Write Digital</button>
            </form>
        </section>

        <!-- PWM Control -->
        <section class="card">
            <h2>PWM Control</h2>
            <form on:submit|preventDefault={startPWM}>
                <div class="form-group">
                    <label>
                        Pin:
                        <select bind:value={pwmConfig.pin} required>
                            <option value="">Select Pin</option>
                            {#each Object.entries(pins).filter(([pin, config]) => config.mode === 'output') as [pin, config]}
                                <option value={pin}>Pin {pin}</option>
                            {/each}
                        </select>
                    </label>
                    
                    <label>
                        Frequency (Hz):
                        <input type="number" bind:value={pwmConfig.frequency} min="0.1" max="40000" step="0.1" required />
                    </label>
                    
                    <label>
                        Duty Cycle (%):
                        <input type="number" bind:value={pwmConfig.duty_cycle} min="0" max="100" step="0.1" required />
                    </label>
                </div>
                
                <button type="submit">Start PWM</button>
            </form>
        </section>

        <!-- Configured Pins Display -->
        <section class="card">
            <h2>Configured Pins</h2>
            
            {#if Object.keys(pins).length === 0}
                <p>No pins configured yet.</p>
            {:else}
                <div class="pins-grid">
                    {#each Object.entries(pins) as [pin, config]}
                        <div class="pin-card">
                            <h3>Pin {pin}</h3>
                            <p><strong>Mode:</strong> {config.mode}</p>
                            
                            {#if config.mode === 'output'}
                                <p><strong>State:</strong> {config.state ? 'HIGH' : 'LOW'}</p>
                                
                                <div class="pin-controls">
                                    <button 
                                        class="btn-toggle {config.state ? 'active' : ''}"
                                        on:click={() => digitalWrite({pin: parseInt(pin), state: !config.state})}
                                    >
                                        Toggle
                                    </button>
                                    
                                    <button on:click={() => digitalRead(pin)}>Read</button>
                                </div>
                                
                                {#if config.pwm}
                                    <div class="pwm-control">
                                        <p><strong>PWM:</strong> {config.pwm.frequency}Hz, {config.pwm.duty_cycle}%</p>
                                        
                                        <label>
                                            Duty Cycle:
                                            <input 
                                                type="range" 
                                                min="0" 
                                                max="100" 
                                                step="1"
                                                value={config.pwm.duty_cycle}
                                                on:input={(e) => updatePWM(pin, e.target.value)}
                                            />
                                            <span>{config.pwm.duty_cycle}%</span>
                                        </label>
                                        
                                        <button class="btn-danger" on:click={() => stopPWM(pin)}>Stop PWM</button>
                                    </div>
                                {:else}
                                    <button on:click={() => startPWM({pin: parseInt(pin), frequency: 1000, duty_cycle: 50})}>
                                        Start PWM
                                    </button>
                                {/if}
                            {:else}
                                <p><strong>Pull:</strong> {config.pull || 'floating'}</p>
                                <button on:click={() => digitalRead(pin)}>Read Value</button>
                            {/if}
                        </div>
                    {/each}
                </div>
            {/if}
        </section>

        <!-- Predefined Pins -->
        {#if Object.keys(predefinedPins).length > 0}
            <section class="card">
                <h2>Predefined Pins</h2>
                <div class="predefined-pins">
                    {#each Object.entries(predefinedPins) as [name, pin]}
                        <div class="predefined-pin">
                            <h4>{name} (Pin {pin})</h4>
                            
                            {#if pins[pin] && pins[pin].mode === 'output'}
                                <div class="controls">
                                    <button 
                                        class="btn-toggle {pins[pin].state ? 'active' : ''}"
                                        on:click={() => togglePredefinedPin(name, pins[pin].state)}
                                    >
                                        {pins[pin].state ? 'ON' : 'OFF'}
                                    </button>
                                    
                                    <label>
                                        PWM:
                                        <input 
                                            type="range" 
                                            min="0" 
                                            max="100" 
                                            value={pins[pin].pwm?.duty_cycle || 0}
                                            on:input={(e) => updatePredefinedPWM(name, e.target.value)}
                                        />
                                        <span>{pins[pin].pwm?.duty_cycle || 0}%</span>
                                    </label>
                                </div>
                            {:else}
                                <p class="not-configured">Not configured as output</p>
                            {/if}
                        </div>
                    {/each}
                </div>
            </section>
        {/if}

        <!-- System Controls -->
        <section class="card">
            <h2>System Controls</h2>
            <div class="system-controls">
                <button class="btn-danger" on:click={cleanupAllPins}>
                    Cleanup All Pins
                </button>
                <button on:click={loadAllPins}>
                    Refresh All Data
                </button>
            </div>
        </section>
    </main>
</div>

<style>
    .container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    header {
        text-align: center;
        margin-bottom: 30px;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
    }

    h1 {
        margin: 0 0 15px 0;
        font-size: 2.5em;
    }

    .connection-status {
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        margin-bottom: 15px;
    }

    .connection-status.connected {
        background-color: #4CAF50;
    }

    .connection-status.disconnected {
        background-color: #FF9800;
    }

    .connection-status.error {
        background-color: #f44336;
    }

    .api-config {
        display: flex;
        gap: 10px;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
    }

    .api-config input {
        padding: 8px;
        border: none;
        border-radius: 5px;
        margin-left: 5px;
        min-width: 250px;
    }

    .card {
        background: white;
        border-radius: 10px;
        padding: 25px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
    }

    .card h2 {
        margin-top: 0;
        color: #333;
        border-bottom: 2px solid #667eea;
        padding-bottom: 10px;
    }

    .form-group {
        display: flex;
        gap: 15px;
        align-items: center;
        flex-wrap: wrap;
        margin-bottom: 15px;
    }

    .form-group label {
        display: flex;
        align-items: center;
        gap: 5px;
        font-weight: 500;
    }

    input, select {
        padding: 8px 12px;
        border: 2px solid #ddd;
        border-radius: 5px;
        font-size: 14px;
        transition: border-color 0.3s;
    }

    input:focus, select:focus {
        outline: none;
        border-color: #667eea;
    }

    button {
        background: #667eea;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.3s;
    }

    button:hover {
        background: #5a67d8;
        transform: translateY(-1px);
    }

    .btn-danger {
        background: #e53e3e;
    }

    .btn-danger:hover {
        background: #c53030;
    }

    .btn-toggle {
        background: #718096;
    }

    .btn-toggle.active {
        background: #48bb78;
    }

    .pins-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 20px;
    }

    .pin-card {
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        background: #f7fafc;
    }

    .pin-card h3 {
        margin-top: 0;
        color: #2d3748;
    }

    .pin-controls {
        display: flex;
        gap: 10px;
        margin: 15px 0;
        flex-wrap: wrap;
    }

    .pwm-control {
        margin-top: 15px;
        padding: 15px;
        background: #edf2f7;
        border-radius: 5px;
    }

    .pwm-control label {
        display: block;
        margin: 10px 0;
    }

    .pwm-control input[type="range"] {
        width: 100%;
        margin: 5px 0;
    }

    .predefined-pins {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 15px;
    }

    .predefined-pin {
        border: 1px solid #cbd5e0;
        border-radius: 5px;
        padding: 15px;
        background: #f8f9fa;
    }

    .predefined-pin h4 {
        margin-top: 0;
        color: #2d3748;
    }

    .controls {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .controls label {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 14px;
    }

    .not-configured {
        color: #718096;
        font-style: italic;
    }

    .system-controls {
        display: flex;
        gap: 15px;
        flex-wrap: wrap;
    }

    /* Responsive design */
    @media (max-width: 768px) {
        .container {
            padding: 10px;
        }
        
        .form-group {
            flex-direction: column;
            align-items: stretch;
        }
        
        .pins-grid {
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