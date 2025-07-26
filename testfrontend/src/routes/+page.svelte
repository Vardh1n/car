<script>
  import { onMount } from 'svelte';
  
  let serverUrl = '';
  let connected = false;
  let status = 'disconnected';
  let currentSpeed = 80;
  let isMoving = false;
  let currentAction = 'stopped';
  let errorMessage = '';
  
  // Connection status check
  async function checkConnection() {
    if (!serverUrl) {
      errorMessage = 'Please enter a server URL';
      return;
    }
    
    // Add http:// if not present
    if (!serverUrl.startsWith('http://') && !serverUrl.startsWith('https://')) {
      serverUrl = 'http://' + serverUrl;
    }
    
    status = 'connecting...';
    errorMessage = '';
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
      
      const response = await fetch(`${serverUrl}/status`, {
        signal: controller.signal,
        mode: 'cors'
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        connected = true;
        status = 'connected';
        const data = await response.json();
        console.log('Connected to car:', data);
        errorMessage = '';
      } else {
        connected = false;
        status = 'connection failed';
        errorMessage = `Server responded with status: ${response.status}`;
      }
    } catch (error) {
      connected = false;
      status = 'connection error';
      
      if (error.name === 'AbortError') {
        errorMessage = 'Connection timeout - check if server is running and IP is correct';
      } else if (error.message.includes('Failed to fetch')) {
        errorMessage = 'Cannot reach server - check IP address and network connection';
      } else {
        errorMessage = `Connection error: ${error.message}`;
      }
      
      console.error('Connection error:', error);
    }
  }
  
  // Send command to car
  async function sendCommand(action, speed = currentSpeed) {
    if (!connected) {
      alert('Please connect to the car first!');
      return;
    }
    
    try {
      isMoving = true;
      currentAction = action;
      
      const url = action === 'stop' 
        ? `${serverUrl}/${action}` 
        : `${serverUrl}/${action}?speed=${speed}`;
      
      const response = await fetch(url, { 
        method: 'POST',
        mode: 'cors'
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Command sent:', data);
        errorMessage = '';
      } else {
        console.error('Command failed');
        errorMessage = `Command failed: ${response.status}`;
      }
    } catch (error) {
      console.error('Error sending command:', error);
      errorMessage = `Command error: ${error.message}`;
    }
  }
  
  // Stop the car
  async function stopCar() {
    await sendCommand('stop');
    isMoving = false;
    currentAction = 'stopped';
  }
  
  // Keyboard controls
  function handleKeydown(event) {
    if (!connected) return;
    
    switch(event.key.toLowerCase()) {
      case 'w':
      case 'arrowup':
        event.preventDefault();
        sendCommand('forward');
        break;
      case 's':
      case 'arrowdown':
        event.preventDefault();
        sendCommand('backward');
        break;
      case 'a':
      case 'arrowleft':
        event.preventDefault();
        sendCommand('left');
        break;
      case 'd':
      case 'arrowright':
        event.preventDefault();
        sendCommand('right');
        break;
      case ' ':
        event.preventDefault();
        stopCar();
        break;
    }
  }
  
  function handleKeyup(event) {
    if (!connected) return;
    
    if (['w', 's', 'a', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(event.key.toLowerCase())) {
      stopCar();
    }
  }
  
  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('keyup', handleKeyup);
    
    return () => {
      window.removeEventListener('keydown', handleKeydown);
      window.removeEventListener('keyup', handleKeyup);
    };
  });
</script>

<svelte:head>
  <title>RC Car Controller</title>
</svelte:head>

<main class="container">
  <h1>🚗 RC Car Remote Controller</h1>
  
  <!-- Connection Section -->
  <section class="connection-section">
    <h2>Connection</h2>
    <div class="connection-form">
      <input 
        bind:value={serverUrl} 
        placeholder="Enter car IP (e.g., 192.168.1.100:8000)"
        class="url-input"
      />
      <button on:click={checkConnection} class="connect-btn">
        Connect
      </button>
    </div>
    <div class="status">
      Status: <span class="status-{status.replace(' ', '-')}">{status}</span>
    </div>
    {#if errorMessage}
      <div class="error-message">{errorMessage}</div>
    {/if}
  </section>

  {#if connected}
    <!-- Speed Control -->
    <section class="speed-section">
      <h2>Speed Control</h2>
      <div class="speed-control">
        <label for="speed">Speed: {currentSpeed}%</label>
        <input 
          id="speed"
          type="range" 
          min="20" 
          max="100" 
          bind:value={currentSpeed}
          class="speed-slider"
        />
      </div>
    </section>

    <!-- Controller Section -->
    <section class="controller-section">
      <h2>Controller</h2>
      <div class="current-action">
        Current Action: <span class="action-{currentAction}">{currentAction}</span>
      </div>
      
      <div class="controller">
        <!-- Forward Button -->
        <button 
          class="control-btn forward"
          on:mousedown={() => sendCommand('forward')}
          on:mouseup={stopCar}
          on:mouseleave={stopCar}
        >
          ↑
        </button>
        
        <!-- Left and Right Buttons -->
        <div class="horizontal-controls">
          <button 
            class="control-btn left"
            on:mousedown={() => sendCommand('left')}
            on:mouseup={stopCar}
            on:mouseleave={stopCar}
          >
            ←
          </button>
          
          <button 
            class="control-btn stop"
            on:click={stopCar}
          >
            STOP
          </button>
          
          <button 
            class="control-btn right"
            on:mousedown={() => sendCommand('right')}
            on:mouseup={stopCar}
            on:mouseleave={stopCar}
          >
            →
          </button>
        </div>
        
        <!-- Backward Button -->
        <button 
          class="control-btn backward"
          on:mousedown={() => sendCommand('backward')}
          on:mouseup={stopCar}
          on:mouseleave={stopCar}
        >
          ↓
        </button>
      </div>
    </section>

    <!-- Keyboard Controls Info -->
    <section class="keyboard-info">
      <h3>Keyboard Controls</h3>
      <div class="keyboard-grid">
        <div>W / ↑ : Forward</div>
        <div>S / ↓ : Backward</div>
        <div>A / ← : Left</div>
        <div>D / → : Right</div>
        <div>Space : Stop</div>
      </div>
    </section>
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
  }

  .container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    color: white;
  }

  h1 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 2rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
  }

  h2 {
    color: #f0f0f0;
    border-bottom: 2px solid rgba(255,255,255,0.3);
    padding-bottom: 10px;
  }

  /* Connection Section */
  .connection-section {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    backdrop-filter: blur(10px);
  }

  .connection-form {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
  }

  .url-input {
    flex: 1;
    padding: 12px;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    background: rgba(255,255,255,0.9);
  }

  .connect-btn {
    padding: 12px 24px;
    background: #4CAF50;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    cursor: pointer;
    transition: background 0.3s;
  }

  .connect-btn:hover {
    background: #45a049;
  }

  .status {
    font-weight: bold;
  }

  .status-connected {
    color: #4CAF50;
  }

  .status-disconnected {
    color: #f44336;
  }

  .status-connecting {
    color: #ff9800;
  }

  .status-connection-failed, .status-connection-error {
    color: #f44336;
  }

  .error-message {
    background: rgba(244, 67, 54, 0.2);
    border: 1px solid #f44336;
    color: #ffcdd2;
    padding: 10px;
    border-radius: 8px;
    margin-top: 10px;
    font-size: 14px;
  }

  /* Speed Section */
  .speed-section {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    backdrop-filter: blur(10px);
  }

  .speed-control {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .speed-slider {
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: rgba(255,255,255,0.3);
    outline: none;
  }

  /* Controller Section */
  .controller-section {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 20px;
    backdrop-filter: blur(10px);
  }

  .current-action {
    text-align: center;
    margin-bottom: 20px;
    font-size: 18px;
    font-weight: bold;
  }

  .action-stopped {
    color: #f44336;
  }

  .action-forward, .action-backward, .action-left, .action-right {
    color: #4CAF50;
  }

  .controller {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    max-width: 300px;
    margin: 0 auto;
  }

  .horizontal-controls {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .control-btn {
    width: 80px;
    height: 80px;
    border: none;
    border-radius: 15px;
    font-size: 24px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    background: rgba(255,255,255,0.2);
    color: white;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
  }

  .control-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.4);
  }

  .control-btn:active {
    transform: translateY(0);
    background: rgba(255,255,255,0.3);
  }

  .stop {
    background: #f44336 !important;
    font-size: 12px;
  }

  .stop:hover {
    background: #d32f2f !important;
  }

  /* Keyboard Info */
  .keyboard-info {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 15px;
    backdrop-filter: blur(10px);
  }

  .keyboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
    margin-top: 15px;
  }

  .keyboard-grid div {
    background: rgba(255,255,255,0.1);
    padding: 10px;
    border-radius: 8px;
    text-align: center;
  }

  /* Responsive Design */
  @media (max-width: 600px) {
    .container {
      padding: 10px;
    }

    h1 {
      font-size: 2rem;
    }

    .connection-form {
      flex-direction: column;
    }

    .control-btn {
      width: 60px;
      height: 60px;
      font-size: 20px;
    }

    .keyboard-grid {
      grid-template-columns: 1fr;
    }
  }
</style>