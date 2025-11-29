import socket
import cv2
import pickle
import struct
import threading
import time
import os

# --- Configuration ---
SERVER_IP = '127.0.0.1' 
VIDEO_PORT = 9999
USER_NAME = input("Enter your display name (e.g., Alice): ")
CLIENT_ID = None 

# --- Setup ---
video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    video_socket.connect((SERVER_IP, VIDEO_PORT))
    print(f"[VIDEO] Connected to server at {SERVER_IP}:{VIDEO_PORT}")
except Exception as e:
    print(f"[FATAL] Failed to connect to server at {SERVER_IP}:{VIDEO_PORT}. Error: {e}")
    print(">>> Check if video_server.py is running and listening.")
    os._exit(1)

# --- CAMERA INITIALIZATION ---
CAMERA_INDEX = 0 
vid = cv2.VideoCapture(CAMERA_INDEX)

if not vid.isOpened():
    print(f"[FATAL] Could not open video device index {CAMERA_INDEX}.")
    print(">>> Check if the camera is in use by another app or try index 1.")
    os._exit(1)
# -----------------------------

# --- Handshake and Video Logic ---

def send_metadata(name):
    """Sends the user's name to the server immediately after connection."""
    name_bytes = name.encode('utf-8')[:100]
    
    # Data payload: [Q: name length] + [Name Bytes]
    payload = struct.pack("Q", len(name_bytes)) + name_bytes
    
    # Message format: [Q: code 0] + [Q: total size] + [Payload]
    metadata = struct.pack("Q", 0) + struct.pack("Q", len(payload)) + payload
    
    try:
        video_socket.sendall(metadata)
        print(f"[VIDEO] Sent username: {name}")
    except Exception as e:
        print(f"[VIDEO] Failed to send metadata: {e}")

def send_video():
    """Captures video frames and sends them to the server."""
    print("[VIDEO] Starting video sender thread...")
    
    while vid.isOpened(): 
        success, frame = vid.read() 
        if not success or frame is None: 
            print("[VIDEO] Camera capture failed (frame read error).")
            break
        
        # Display own Name on video
        cv2.putText(frame, f"{USER_NAME} (YOU)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        
        data = pickle.dumps(frame)
        
        # Payload is just the pickled frame data
        
        # Message format: [Q: code 1] + [Q: total size] + [Payload]
        message = struct.pack("Q", 1) + struct.pack("Q", len(data)) + data
        try:
            video_socket.sendall(message)
        except:
            print("[VIDEO] Server connection lost while sending video.")
            break
            
        cv2.imshow(f"Your Video Stream ({USER_NAME})", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup on thread exit
    vid.release()
    cv2.destroyAllWindows()


def receive_video():
    """Receives video streams from the server and displays them."""
    global CLIENT_ID
    print("[VIDEO] Starting video receiver thread...")
    
    data = b""
    # Size of the type code (Q) + message length (Q)
    type_and_payload_size = struct.calcsize("Q") * 2 
    remote_names = {} 

    while True:
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
            data = data[full_msg_size:]
            
            # --- Process Message ---
            
            # Case 0: Metadata (Name Map)
            if type_code == 0:
                # Format: [Q: Sender ID] + [Q: Name Length] + [Name Bytes]
                sender_id = struct.unpack("Q", full_data[:8])[0]
                name_len = struct.unpack("Q", full_data[8:16])[0]
                name_bytes = full_data[16:16 + name_len]
                remote_name = name_bytes.decode('utf-8')
                remote_names[sender_id] = remote_name
                print(f"[VIDEO] Received name mapping: ID {sender_id} is {remote_name}")

            # Case 1: Video Frame
            elif type_code == 1:
                # Format: [Q: Sender ID] + [Frame Data]
                id_size = struct.calcsize("Q")
                sender_id = struct.unpack("Q", full_data[:id_size])[0]
                frame_data = full_data[id_size:]
                
                frame = pickle.loads(frame_data)
                
                display_name = remote_names.get(sender_id, f"Client {sender_id}")
                cv2.imshow(f"{display_name}'s Video", frame)
                
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        except Exception:
            # print(f"[VIDEO] Receiver thread error: {e}")
            break

# --- Main Execution ---

# 1. Send our name immediately (Handshake)
send_metadata(USER_NAME)

# 2. Start communication threads
send_thread = threading.Thread(target=send_video, daemon=True)
receive_thread = threading.Thread(target=receive_video, daemon=True)

send_thread.start()
receive_thread.start()

# Wait for threads to complete (allows Q key to quit)
try:
    send_thread.join()
    receive_thread.join()
except:
    pass

video_socket.close()
print("[VIDEO] Client shutdown complete.")
os._exit(0)