import socket
import cv2
import pickle
import struct
import threading
import time
import os
import sys
import numpy as np # Needed for creating the placeholder frame

# --- Configuration ---
SERVER_IP = '127.0.0.1' 
VIDEO_PORT = 9999
USER_NAME = input("Enter your display name (e.g., Alice): ")
CLIENT_ID = None 

# --- Global Control Flags ---
IS_VIDEO_OFF = False
SHOULD_QUIT = threading.Event() 

# --- Setup ---
video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    video_socket.connect((SERVER_IP, VIDEO_PORT))
    print(f"[VIDEO] Connected to server at {SERVER_IP}:{VIDEO_PORT}")
except Exception as e:
    print(f"[FATAL] Failed to connect to server: {e}")
    os._exit(1)

# --- CAMERA INITIALIZATION ---
CAMERA_INDEX = 0 
vid = cv2.VideoCapture(CAMERA_INDEX)

if not vid.isOpened():
    print(f"[FATAL] Could not open video device index {CAMERA_INDEX}.")
    os._exit(1)
# -----------------------------

# --- Placeholders ---
_, base_frame = vid.read()
if base_frame is not None:
    H, W = base_frame.shape[:2]
else: 
    H, W = 480, 640
    
PLACEHOLDER_FRAME = np.zeros((H, W, 3), dtype=np.uint8)
cv2.putText(PLACEHOLDER_FRAME, f"VIDEO OFF - {USER_NAME}", (W // 4, H // 2), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
PICKLED_PLACEHOLDER = pickle.dumps(PLACEHOLDER_FRAME)


# --- Control Logic ---

def control_loop():
    """Reads commands from the terminal to toggle video or quit."""
    global IS_VIDEO_OFF
    
    print("\n[CONTROLS] Type 'v' to Toggle Video, or 'q' to Quit.")
    
    while not SHOULD_QUIT.is_set():
        try:
            command = input("Video Command: ").strip().lower()
            
            if command == 'v':
                IS_VIDEO_OFF = not IS_VIDEO_OFF
                status = "OFF (Sending placeholder)" if IS_VIDEO_OFF else "ON (Sending live feed)"
                print(f"[STATUS] Video is now {status}.")
            
            elif command == 'q':
                print("[STATUS] Quit command received.")
                SHOULD_QUIT.set()
                break
                
            else:
                print("[WARNING] Invalid command. Use 'v' or 'q'.")
                
        except EOFError:
            SHOULD_QUIT.set()
        except KeyboardInterrupt:
            SHOULD_QUIT.set()


# --- Handshake and Video Logic ---

def send_metadata(name):
    """Sends the user's name to the server immediately after connection."""
    name_bytes = name.encode('utf-8')[:100]
    payload = struct.pack("Q", len(name_bytes)) + name_bytes
    metadata = struct.pack("Q", 0) + struct.pack("Q", len(payload)) + payload
    
    try:
        video_socket.sendall(metadata)
        print(f"[VIDEO] Sent username: {name}")
    except Exception as e:
        print(f"[VIDEO] Failed to send metadata: {e}")

def send_video():
    """Captures video frames and sends them to the server."""
    print("[VIDEO] Starting video sender thread...")
    
    while vid.isOpened() and not SHOULD_QUIT.is_set(): 
        
        if IS_VIDEO_OFF:
            data = PICKLED_PLACEHOLDER
            frame = PLACEHOLDER_FRAME
        else:
            success, frame = vid.read() 
            if not success or frame is None: 
                print("[VIDEO] Camera capture failed (frame read error).")
                break
            
            # Display own Name on video
            cv2.putText(frame, f"{USER_NAME} (YOU)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            data = pickle.dumps(frame)
        
        # Message format: [Q: code 1] + [Q: message size] + [Frame Data]
        message = struct.pack("Q", 1) + struct.pack("Q", len(data)) + data
        try:
            video_socket.sendall(message)
        except:
            print("[VIDEO] Server connection lost while sending video.")
            break
            
        cv2.imshow(f"Your Video Stream ({USER_NAME})", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            SHOULD_QUIT.set()
            break
    
    # Cleanup on thread exit
    vid.release()
    cv2.destroyAllWindows()
    print("[VIDEO] Sender thread closed.")


def receive_video():
    """Receives video streams from the server and displays them."""
    global CLIENT_ID
    print("[VIDEO] Starting video receiver thread...")
    
    data = b""
    type_and_payload_size = struct.calcsize("Q") * 2 
    remote_names = {} 

    while not SHOULD_QUIT.is_set():
        try:
            # --- Receive Header ---
            while len(data) < type_and_payload_size:
                packet = video_socket.recv(4 * 1024)
                if not packet: raise ConnectionError("Server closed connection.")
                data += packet
                
            # Unpack Type and Message Size
            type_code = struct.unpack("Q", data[:8])[0]
            packed_msg_size = data[8:16]
            full_msg_size = struct.unpack("Q", packed_msg_size)[0]
            data = data[type_and_payload_size:]

            # --- Receive Full Message ---
            while len(data) < full_msg_size:
                data += video_socket.recv(4 * 1024)
            full_data = data[:full_msg_size]
            data = full_data[full_msg_size:] # Only consume payload size of data buffer
            
            # --- Process Message ---
            
            # Case 0: Metadata (Name Map)
            if type_code == 0:
                sender_id = struct.unpack("Q", full_data[:8])[0]
                name_len = struct.unpack("Q", full_data[8:16])[0]
                name_bytes = full_data[16:16 + name_len]
                remote_name = name_bytes.decode('utf-8')
                remote_names[sender_id] = remote_name

            # Case 1: Video Frame
            elif type_code == 1:
                id_size = struct.calcsize("Q")
                sender_id = struct.unpack("Q", full_data[:id_size])[0]
                frame_data = full_data[id_size:]
                
                frame = pickle.loads(frame_data)
                
                display_name = remote_names.get(sender_id, f"Client {sender_id}")
                cv2.imshow(f"{display_name}'s Video", frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'): 
                SHOULD_QUIT.set()
                break

        except Exception as e:
            # print(f"[VIDEO] Receiver thread error: {e}")
            break
    print("[VIDEO] Receiver thread closed.")


# --- Main Execution ---

# 1. Send our name immediately (Handshake)
send_metadata(USER_NAME)

# 2. Start communication threads
send_thread = threading.Thread(target=send_video, daemon=True)
receive_thread = threading.Thread(target=receive_video, daemon=True)
control_thread = threading.Thread(target=control_loop, daemon=True)

send_thread.start()
receive_thread.start()
control_thread.start()


try:
    # Wait until quit signal is received
    while not SHOULD_QUIT.is_set():
        time.sleep(0.1)
except KeyboardInterrupt:
    SHOULD_QUIT.set()

# Cleanup and force exit
time.sleep(0.5) 
video_socket.close()
print("[VIDEO] Client shutdown complete.")
os._exit(0)