import asyncio
import websockets
import cv2
import numpy as np
import json
import logging
import threading
import time
from ultralytics import YOLO
import requests
from typing import Optional, Dict, Any
import base64
from websockets.server import serve
import aiohttp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TankCarClient:
    def __init__(self, server_url: str = "ws://10.116.163.140:8000", frontend_port: int = 8001):
        self.server_url = server_url
        self.http_url = server_url.replace("ws://", "http://")
        self.frontend_port = frontend_port
        
        # WebSocket connections
        self.camera_ws = None
        self.control_ws = None
        self.frontend_clients = set()
        
        # Video processing
        self.model = YOLO('yolov8n.pt')  # Load YOLOv8 nano model
        self.current_frame = None
        self.processed_frame = None
        self.detections = []
        
        # Control state
        self.is_running = False
        self.detection_enabled = True
        
        # Auto-movement feature
        self.target_objects = set()  # Objects to track for auto-movement
        self.auto_movement_enabled = False
        self.movement_active = False
        self.movement_task = None
        
        # IR sensor state
        self.ir_value = None
        self.ir_connected = False
        
    async def connect_camera_stream(self):
        """Connect to camera WebSocket stream"""
        while self.is_running:
            try:
                uri = f"{self.server_url}/ws/camera"
                self.camera_ws = await websockets.connect(uri)
                logger.info("Connected to camera stream")
                
                while self.is_running:
                    try:
                        # Receive frame data
                        frame_data = await asyncio.wait_for(self.camera_ws.recv(), timeout=5.0)
                        
                        if isinstance(frame_data, str):
                            logger.warning(f"Camera message: {frame_data}")
                            continue
                        
                        # Decode frame
                        nparr = np.frombuffer(frame_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            self.current_frame = frame
                            
                            # Process with YOLO if enabled
                            if self.detection_enabled:
                                await self.process_frame(frame)
                            else:
                                self.processed_frame = frame
                            
                            # Check for auto-movement
                            if self.auto_movement_enabled and not self.movement_active:
                                await self.check_auto_movement()
                            
                            # Send to frontend clients
                            await self.broadcast_frame()
                                
                    except asyncio.TimeoutError:
                        logger.warning("Camera stream timeout")
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("Camera stream connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Camera stream error: {e}")
                        await asyncio.sleep(0.1)
                        
            except Exception as e:
                logger.error(f"Failed to connect to camera stream: {e}")
                if self.is_running:
                    logger.info("Retrying camera connection in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    break
    
    async def connect_control_stream(self):
        """Connect to control WebSocket"""
        while self.is_running:
            try:
                uri = f"{self.server_url}/ws/control"
                self.control_ws = await websockets.connect(uri)
                logger.info("Connected to control stream")
                
                # Keep connection alive
                while self.is_running:
                    try:
                        await asyncio.sleep(1)
                        # Send ping to keep connection alive
                        await self.control_ws.ping()
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("Control stream connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Control stream keep-alive error: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Failed to connect to control stream: {e}")
                if self.is_running:
                    logger.info("Retrying control connection in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    break
    
    async def process_frame(self, frame):
        """Process frame with YOLOv8"""
        try:
            # Run YOLO detection
            results = self.model(frame, verbose=False)
            
            # Draw detections
            annotated_frame = frame.copy()
            self.detections = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = self.model.names[class_id]
                        
                        # Store detection
                        detection = {
                            'class': class_name,
                            'confidence': float(confidence),
                            'bbox': [int(x1), int(y1), int(x2), int(y2)]
                        }
                        self.detections.append(detection)
                        
                        # Draw bounding box (highlight target objects in red)
                        color = (0, 0, 255) if class_name in self.target_objects else (0, 255, 0)
                        cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                        
                        # Draw label
                        label = f"{class_name}: {confidence:.2f}"
                        if class_name in self.target_objects:
                            label += " [TARGET]"
                        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        cv2.rectangle(annotated_frame, (int(x1), int(y1) - label_size[1] - 10), 
                                    (int(x1) + label_size[0], int(y1)), color, -1)
                        cv2.putText(annotated_frame, label, (int(x1), int(y1) - 5), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            self.processed_frame = annotated_frame
            
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            self.processed_frame = frame
    
    async def check_auto_movement(self):
        """Check if any target objects are detected and trigger movement"""
        if not self.target_objects or not self.detections:
            return
        
        # Check if any detected object is in target list
        detected_classes = {detection['class'] for detection in self.detections}
        target_detected = bool(self.target_objects.intersection(detected_classes))
        
        if target_detected:
            detected_targets = self.target_objects.intersection(detected_classes)
            logger.info(f"Target objects detected: {', '.join(detected_targets)}. Starting movement.")
            await self.start_auto_movement()
    
    async def start_auto_movement(self):
        """Start automatic forward movement for 5 seconds"""
        if self.movement_active:
            return
        
        self.movement_active = True
        
        try:
            # Send forward command
            success = await self.send_control_command("forward")
            if success:
                logger.info("Auto-movement: Moving forward for 5 seconds")
                
                # Broadcast movement status to frontend
                await self.broadcast_movement_status("moving")
                
                # Wait for 5 seconds
                await asyncio.sleep(5.0)
                
                # Send stop command
                success = await self.send_control_command("stop")
                if success:
                    logger.info("Auto-movement: Stopped")
                
                # Broadcast movement status to frontend
                await self.broadcast_movement_status("stopped")
                
        except Exception as e:
            logger.error(f"Auto-movement error: {e}")
        finally:
            self.movement_active = False
    
    async def broadcast_movement_status(self, status: str):
        """Broadcast movement status to frontend clients"""
        if self.frontend_clients:
            message = {
                "type": "movement_status",
                "status": status,
                "timestamp": time.time()
            }
            
            disconnected_clients = set()
            for client in self.frontend_clients:
                try:
                    await client.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.add(client)
            
            self.frontend_clients -= disconnected_clients
    
    async def broadcast_frame(self):
        """Broadcast current frame to all frontend clients"""
        if self.processed_frame is not None and self.frontend_clients:
            try:
                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', self.processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Create message
                message = {
                    "type": "frame",
                    "data": frame_base64,
                    "detections": self.detections,
                    "target_objects": list(self.target_objects),
                    "auto_movement_enabled": self.auto_movement_enabled,
                    "movement_active": self.movement_active
                }
                
                # Send to all connected clients
                disconnected_clients = set()
                for client in self.frontend_clients:
                    try:
                        await client.send(json.dumps(message))
                    except websockets.exceptions.ConnectionClosed:
                        disconnected_clients.add(client)
                
                # Remove disconnected clients
                self.frontend_clients -= disconnected_clients
                
            except Exception as e:
                logger.error(f"Frame broadcast error: {e}")
    
    async def send_control_command(self, command: str, **kwargs):
        """Send control command to tank"""
        if not self.control_ws:
            logger.warning("Control WebSocket not connected")
            return False
        
        try:
            command_data = {"command": command, **kwargs}
            await self.control_ws.send(json.dumps(command_data))
            
            # Wait for response
            response = await asyncio.wait_for(self.control_ws.recv(), timeout=2.0)
            response_data = json.loads(response)
            
            if response_data.get("status") == "ok":
                logger.info(f"Command executed: {command}")
                return True
            else:
                logger.warning(f"Command failed: {response_data}")
                return False
                
        except asyncio.TimeoutError:
            logger.warning(f"Control command timeout: {command}")
            return False
        except Exception as e:
            logger.error(f"Control command error: {e}")
            return False
    
    async def handle_frontend_client(self, websocket, path):
        """Handle frontend WebSocket client"""
        self.frontend_clients.add(websocket)
        logger.info(f"Frontend client connected. Total clients: {len(self.frontend_clients)}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "control":
                        command = data.get("command")
                        params = data.get("params", {})
                        
                        # Execute control command
                        success = await self.send_control_command(command, **params)
                        
                        # Send response
                        response = {
                            "type": "control_response",
                            "success": success,
                            "command": command
                        }
                        await websocket.send(json.dumps(response))
                    
                    elif data.get("type") == "toggle_detection":
                        self.detection_enabled = data.get("enabled", True)
                        logger.info(f"Object detection {'enabled' if self.detection_enabled else 'disabled'}")
                        
                        response = {
                            "type": "detection_toggled",
                            "enabled": self.detection_enabled
                        }
                        await websocket.send(json.dumps(response))
                    
                    elif data.get("type") == "set_target_objects":
                        # New endpoint for setting target objects
                        objects_string = data.get("objects", "")
                        self.target_objects = set()
                        
                        if objects_string.strip():
                            # Parse comma-separated objects
                            objects = [obj.strip().lower() for obj in objects_string.split(",")]
                            self.target_objects = set(objects)
                        
                        logger.info(f"Target objects set: {list(self.target_objects)}")
                        
                        response = {
                            "type": "target_objects_set",
                            "objects": list(self.target_objects)
                        }
                        await websocket.send(json.dumps(response))
                    
                    elif data.get("type") == "toggle_auto_movement":
                        # Toggle auto-movement feature
                        self.auto_movement_enabled = data.get("enabled", True)
                        logger.info(f"Auto-movement {'enabled' if self.auto_movement_enabled else 'disabled'}")
                        
                        response = {
                            "type": "auto_movement_toggled",
                            "enabled": self.auto_movement_enabled
                        }
                        await websocket.send(json.dumps(response))
                    
                    elif data.get("type") == "get_status":
                        # Get current status
                        response = {
                            "type": "status",
                            "detection_enabled": self.detection_enabled,
                            "auto_movement_enabled": self.auto_movement_enabled,
                            "target_objects": list(self.target_objects),
                            "movement_active": self.movement_active
                        }
                        await websocket.send(json.dumps(response))
                
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received from frontend")
                except Exception as e:
                    logger.error(f"Error handling frontend message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.frontend_clients.remove(websocket)
            logger.info(f"Frontend client disconnected. Total clients: {len(self.frontend_clients)}")
    
    async def start_frontend_server(self):
        """Start WebSocket server for frontend clients"""
        try:
            server = await serve(
                self.handle_frontend_client,
                "localhost",
                self.frontend_port,
                ping_interval=None
            )
            logger.info(f"Frontend WebSocket server started on ws://localhost:{self.frontend_port}")
            return server
        except Exception as e:
            logger.error(f"Failed to start frontend server: {e}")
            return None
    
    async def connect_ir_stream(self):
        """Connect to IR sensor SSE stream and broadcast values to frontend clients."""
        while self.is_running:
            try:
                url = f"{self.http_url}/ir/stream"
                logger.info(f"Connecting to IR stream: {url}")
                timeout = aiohttp.ClientTimeout(total=None, connect=10)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            logger.error(f"Failed to connect to IR stream: {resp.status}")
                            logger.error(f"Response: {await resp.text()}")
                            await asyncio.sleep(5)
                            continue
                            
                        logger.info("Connected to IR stream successfully")
                        self.ir_connected = True
                        line_count = 0
                        
                        async for line in resp.content:
                            if not self.is_running:
                                break
                                
                            line_str = line.decode().strip()
                            line_count += 1
                            
                            if line_count % 30 == 0:  # Log every second
                                logger.info(f"IR stream: received {line_count} lines")
                            
                            if line_str.startswith("data:"):
                                try:
                                    value = line_str.split("data:")[1].strip()
                                    self.ir_value = value
                                    logger.debug(f"IR value: {value}")
                                    await self.broadcast_ir_value(value)
                                except (IndexError, ValueError) as e:
                                    logger.warning(f"Invalid IR data format: {line_str}")
                            elif line_str:
                                logger.debug(f"Non-data line: {line_str}")
                                    
            except asyncio.CancelledError:
                logger.info("IR stream task cancelled")
                break
            except Exception as e:
                logger.error(f"IR stream error: {e}")
                self.ir_connected = False
                if self.is_running:
                    logger.info("Retrying IR connection in 10 seconds...")
                    await asyncio.sleep(10)
                else:
                    break

    async def broadcast_ir_value(self, value):
        """Broadcast IR sensor value to frontend clients."""
        if self.frontend_clients:
            message = {
                "type": "ir",
                "value": value,
                "timestamp": time.time()
            }
            disconnected_clients = set()
            for client in self.frontend_clients:
                try:
                    await client.send(json.dumps(message))
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.add(client)
            self.frontend_clients -= disconnected_clients

    async def run(self):
        """Main run loop"""
        self.is_running = True

        # Start frontend server
        frontend_server = await self.start_frontend_server()
        if not frontend_server:
            logger.error("Failed to start frontend server, exiting...")
            return

        # Create tasks for each connection
        camera_task = asyncio.create_task(self.connect_camera_stream())
        control_task = asyncio.create_task(self.connect_control_stream())
        ir_task = asyncio.create_task(self.connect_ir_stream())

        try:
            # Run all tasks concurrently, but don't let one failure stop others
            await asyncio.gather(
                camera_task, 
                control_task, 
                ir_task,
                return_exceptions=True  # This prevents one task failure from stopping others
            )
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.is_running = False
            
            # Cancel all tasks
            for task in [camera_task, control_task, ir_task]:
                if not task.done():
                    task.cancel()
            
            # Clean up connections
            if self.camera_ws:
                await self.camera_ws.close()
            if self.control_ws:
                await self.control_ws.close()
            if frontend_server:
                frontend_server.close()
                await frontend_server.wait_closed()

async def main():
    # Use your server's IP address
    client = TankCarClient("ws://10.116.163.140:8000", 8001)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())