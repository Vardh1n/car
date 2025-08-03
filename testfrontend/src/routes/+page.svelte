<script>
  import { onMount, onDestroy } from 'svelte';
  import { writable } from 'svelte/store';
  import "./style.css";
  // WebSocket connection
  let ws = null;
  let connectionStatus = 'Disconnected';
  
  // Video stream
  let videoElement;
  let currentFrame = '';
  
  // Detection data
  let detections = [];
  let detectionEnabled = true;
  
  // Auto-movement features
  let targetObjects = '';
  let autoMovementEnabled = false;
  let movementActive = false;
  let currentTargetObjects = [];
  let movementStatus = '';
  
  // Control state
  let speed = 50;
  let keysPressed = new Set();
  
  // Reactive stores
  const isConnected = writable(false);

  let irValue = null; // Add this line

  onMount(() => {
    connectToBackend();
    setupKeyboardControls();
  });

  onDestroy(() => {
    if (ws) {
      ws.close();
    }
    document.removeEventListener('keydown', handleKeyDown);
    document.removeEventListener('keyup', handleKeyUp);
  });

  function connectToBackend() {
    try {
      ws = new WebSocket('ws://localhost:8001');
      
      ws.onopen = () => {
        connectionStatus = 'Connected';
        isConnected.set(true);
        console.log('Connected to backend');
        
        // Request current status when connected
        requestStatus();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      };

      ws.onclose = () => {
        connectionStatus = 'Disconnected';
        isConnected.set(false);
        console.log('Disconnected from backend');
        
        // Attempt to reconnect after 3 seconds
        setTimeout(connectToBackend, 3000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        connectionStatus = 'Error';
      };
    } catch (error) {
      console.error('Failed to connect:', error);
      connectionStatus = 'Error';
    }
  }

  function handleMessage(data) {
    switch (data.type) {
      case 'frame':
        currentFrame = `data:image/jpeg;base64,${data.data}`;
        detections = data.detections || [];
        currentTargetObjects = data.target_objects || [];
        autoMovementEnabled = data.auto_movement_enabled || false;
        movementActive = data.movement_active || false;
        break;
      
      case 'control_response':
        console.log(`Control command ${data.command} ${data.success ? 'succeeded' : 'failed'}`);
        break;
      
      case 'detection_toggled':
        detectionEnabled = data.enabled;
        break;
      
      case 'target_objects_set':
        currentTargetObjects = data.objects || [];
        targetObjects = currentTargetObjects.join(', ');
        console.log('Target objects updated:', currentTargetObjects);
        break;
      
      case 'auto_movement_toggled':
        autoMovementEnabled = data.enabled;
        console.log(`Auto-movement ${autoMovementEnabled ? 'enabled' : 'disabled'}`);
        break;
      
      case 'movement_status':
        movementStatus = data.status;
        console.log('Movement status:', data.status);
        break;
      
      case 'status':
        detectionEnabled = data.detection_enabled;
        autoMovementEnabled = data.auto_movement_enabled;
        currentTargetObjects = data.target_objects || [];
        targetObjects = currentTargetObjects.join(', ');
        movementActive = data.movement_active;
        break;
      
      case 'ir':
        irValue = data.value;
        break;

      default:
        console.log('Unknown message type:', data.type);
    }
  }

  function sendControlCommand(command, params = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'control',
        command: command,
        params: { speed, ...params }
      };
      ws.send(JSON.stringify(message));
    }
  }

  function toggleDetection() {
    detectionEnabled = !detectionEnabled;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'toggle_detection',
        enabled: detectionEnabled
      };
      ws.send(JSON.stringify(message));
    }
  }

  function setTargetObjects() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'set_target_objects',
        objects: targetObjects
      };
      ws.send(JSON.stringify(message));
    }
  }

  function toggleAutoMovement() {
    autoMovementEnabled = !autoMovementEnabled;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'toggle_auto_movement',
        enabled: autoMovementEnabled
      };
      ws.send(JSON.stringify(message));
    }
  }

  function requestStatus() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const message = {
        type: 'get_status'
      };
      ws.send(JSON.stringify(message));
    }
  }

  function setupKeyboardControls() {
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keyup', handleKeyUp);
  }

  function handleKeyDown(event) {
    if (keysPressed.has(event.key)) return; // Prevent repeated commands
    
    keysPressed.add(event.key);
    
    switch (event.key.toLowerCase()) {
      case 'w':
        sendControlCommand('forward');
        break;
      case 's':
        sendControlCommand('backward');
        break;
      case 'a':
        sendControlCommand('left');
        break;
      case 'd':
        sendControlCommand('right');
        break;
      case 'q':
        sendControlCommand('pivot_left');
        break;
      case 'e':
        sendControlCommand('pivot_right');
        break;
    }
  }

  function handleKeyUp(event) {
    keysPressed.delete(event.key);
    
    if (['w', 's', 'a', 'd', 'q', 'e'].includes(event.key.toLowerCase())) {
      sendControlCommand('stop');
    }
  }

  // Button control functions
  function moveForward() { sendControlCommand('forward'); }
  function moveBackward() { sendControlCommand('backward'); }
  function moveLeft() { sendControlCommand('left'); }
  function moveRight() { sendControlCommand('right'); }
  function pivotLeft() { sendControlCommand('pivot_left'); }
  function pivotRight() { sendControlCommand('pivot_right'); }
  function stop() { sendControlCommand('stop'); }

  // Helper function to check if object is a target
  function isTargetObject(objectClass) {
    return currentTargetObjects.includes(objectClass);
  }
</script>

<main class="container">
  <h1>Tank Car Controller</h1>
  
  <!-- Connection Status -->
  <div class="status-bar">
    <span class="status" class:connected={$isConnected} class:disconnected={!$isConnected}>
      {connectionStatus}
    </span>
    {#if movementActive}
      <span class="movement-indicator">🚗 Auto-moving...</span>
    {/if}
  </div>

  <!-- IR Sensor Value -->
  <div class="ir-panel">
    <h3>IR Sensor</h3>
    <p>
      Value: 
      {#if irValue !== null}
        <span class="ir-value">{irValue}</span>
      {:else}
        <span class="ir-value">No data</span>
      {/if}
    </p>
  </div>

  <!-- Video Feed -->
  <div class="video-container">
    <div class="video-wrapper">
      {#if currentFrame}
        <img src={currentFrame} alt="Tank Camera Feed" class="video-feed" />
      {:else}
        <div class="no-video">No Video Feed</div>
      {/if}
    </div>
    
    <!-- Detection Info -->
    <div class="detection-panel">
      <div class="detection-header">
        <h3>Object Detection</h3>
        <label class="toggle">
          <input 
            type="checkbox" 
            bind:checked={detectionEnabled} 
            on:change={toggleDetection}
          />
          <span class="slider"></span>
        </label>
      </div>
      
      <div class="detection-list">
        <p>Objects detected: {detections.length}</p>
        {#each detections.slice(0, 8) as detection}
          <div class="detection-item" class:target={isTargetObject(detection.class)}>
            <span class="object-class">{detection.class}</span>
            <span class="confidence">{(detection.confidence * 100).toFixed(1)}%</span>
            {#if isTargetObject(detection.class)}
              <span class="target-badge">TARGET</span>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  </div>

  <!-- Auto-Movement Controls -->
  <div class="auto-movement-section">
    <h3>Auto-Movement Settings</h3>
    
    <div class="auto-movement-controls">
      <div class="target-objects-input">
        <label for="targetObjects">Target Objects (comma-separated):</label>
        <div class="input-group">
          <input 
            type="text" 
            id="targetObjects"
            bind:value={targetObjects}
            placeholder="e.g., person, car, dog"
            class="target-input"
          />
          <button on:click={setTargetObjects} class="set-btn">Set</button>
        </div>
        <small>Current targets: {currentTargetObjects.length > 0 ? currentTargetObjects.join(', ') : 'None'}</small>
      </div>
      
      <div class="auto-movement-toggle">
        <label class="toggle-label">
          <span>Auto-Movement:</span>
          <label class="toggle">
            <input 
              type="checkbox" 
              bind:checked={autoMovementEnabled} 
              on:change={toggleAutoMovement}
            />
            <span class="slider"></span>
          </label>
        </label>
      </div>
    </div>
    
    <div class="auto-movement-info">
      <p><strong>Status:</strong> {autoMovementEnabled ? 'Enabled' : 'Disabled'}</p>
      {#if movementStatus}
        <p><strong>Movement:</strong> {movementStatus}</p>
      {/if}
      <p><small>When enabled, the tank will automatically move forward for 5 seconds when target objects are detected.</small></p>
    </div>
  </div>

  <!-- Controls -->
  <div class="controls">
    <!-- Movement Controls -->
    <div class="movement-controls">
      <h3>Manual Movement Controls</h3>
      <div class="movement-grid">
        <button 
          class="control-btn" 
          on:mousedown={moveForward}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          ↑ Forward
        </button>
        <button 
          class="control-btn" 
          on:mousedown={moveLeft}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          ← Left
        </button>
        <button class="control-btn stop-btn" on:click={stop}>
          ⏹ Stop
        </button>
        <button 
          class="control-btn" 
          on:mousedown={moveRight}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          → Right
        </button>
        <button 
          class="control-btn" 
          on:mousedown={moveBackward}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          ↓ Backward
        </button>
      </div>
    </div>

    <!-- Pivot Controls -->
    <div class="pivot-controls">
      <h3>Pivot Controls</h3>
      <div class="pivot-buttons">
        <button 
          class="control-btn pivot-btn" 
          on:mousedown={pivotLeft}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          ↶ Pivot Left
        </button>
        <button 
          class="control-btn pivot-btn" 
          on:mousedown={pivotRight}
          on:mouseup={stop}
          on:mouseleave={stop}
          disabled={movementActive}
        >
          ↷ Pivot Right
        </button>
      </div>
    </div>

    <!-- Speed Control -->
    <div class="speed-control">
      <h3>Speed Control</h3>
      <div class="speed-slider">
        <label for="speed">Speed: {speed}%</label>
        <input 
          type="range" 
          id="speed" 
          min="0" 
          max="100" 
          bind:value={speed}
          class="slider-input"
        />
      </div>
    </div>
  </div>

  <!-- Keyboard Instructions -->
  <div class="instructions">
    <h3>Keyboard Controls</h3>
    <div class="key-instructions">
      <span><kbd>W</kbd> Forward</span>
      <span><kbd>S</kbd> Backward</span>
      <span><kbd>A</kbd> Left</span>
      <span><kbd>D</kbd> Right</span>
      <span><kbd>Q</kbd> Pivot Left</span>
      <span><kbd>E</kbd> Pivot Right</span>
    </div>
  </div>
</main>

<style>
  .ir-panel {
  margin: 1em 0;
  padding: 0.5em 1em;
  background: #f7f7f7;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.ir-value {
  font-weight: bold;
  color: #007bff;
}
</style>
