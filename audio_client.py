import socket
import pyaudio
import threading
import struct 
import time
import os
import sys

# --- Configuration ---
SERVER_IP = '127.0.0.1' 
AUDIO_PORT = 5000

# Audio Configuration (Must match server)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK_SIZE = 2048

# --- Global Control Flags ---
IS_MUTED = False
SHOULD_QUIT = threading.Event() # Used to signal all threads to stop

# --- Setup ---
audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    audio_socket.connect((SERVER_IP, AUDIO_PORT))
    print(f"[AUDIO] Connected to server at {SERVER_IP}:{AUDIO_PORT}")
except Exception as e:
    print(f"[FATAL] Failed to connect to server: {e}")
    os._exit(1)

audio = pyaudio.PyAudio()

# --- Control Logic ---

def control_loop():
    """Reads commands from the terminal to toggle mute or quit."""
    global IS_MUTED
    
    print("\n[CONTROLS] Type 'm' to Toggle Mute, or 'q' to Quit.")
    
    while not SHOULD_QUIT.is_set():
        try:
            command = input("Audio Command: ").strip().lower()
            
            if command == 'm':
                IS_MUTED = not IS_MUTED
                status = "MUTED (Stopping audio send)" if IS_MUTED else "UNMUTED (Sending audio)"
                print(f"[STATUS] Microphone is now {status}.")
            
            elif command == 'q':
                print("[STATUS] Quit command received.")
                SHOULD_QUIT.set()
                break
                
            else:
                print("[WARNING] Invalid command. Use 'm' or 'q'.")
                
        except EOFError:
            SHOULD_QUIT.set()
        except KeyboardInterrupt:
            SHOULD_QUIT.set()

# --- Audio Logic ---

def send_audio():
    """Captures audio chunks and sends them to the server."""
    print("[AUDIO] Starting audio sender thread...")
    
    try:
        # PyAudio fix applied
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK_SIZE)
    except Exception as e:
        print(f"[AUDIO] Error opening input audio stream: {e}")
        SHOULD_QUIT.set()
        return
        
    while not SHOULD_QUIT.is_set():
        if IS_MUTED:
            # When muted, sleep to save CPU and bandwidth
            time.sleep(0.05) 
            continue
            
        try:
            # Read audio data from the microphone
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False) 
            audio_socket.sendall(data)
        except Exception:
            break
            
    stream.close()
    print("[AUDIO] Sender thread closed.")


def recv_audio():
    """Receives audio streams from the server and plays them."""
    print("[AUDIO] Starting audio receiver thread...")
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK_SIZE)
    except Exception as e:
        print(f"[AUDIO] Error opening output audio stream: {e}")
        SHOULD_QUIT.set()
        return

    id_size = struct.calcsize("Q") 
    data_to_receive = id_size + CHUNK_SIZE 

    while not SHOULD_QUIT.is_set():
        try:
            data = b''
            bytes_left = data_to_receive
            
            while bytes_left > 0:
                chunk = audio_socket.recv(bytes_left)
                if not chunk: 
                    raise ConnectionError("Server socket closed.")
                data += chunk
                bytes_left -= len(chunk)
            
            if len(data) != data_to_receive:
                continue

            sender_id = struct.unpack("Q", data[:id_size])[0]
            audio_chunk = data[id_size:]
            
            stream.write(audio_chunk)

        except ConnectionError as e:
            print(f"[AUDIO] Server connection closed. Error: {e}")
            SHOULD_QUIT.set()
            break
        except Exception:
            break
            
    stream.close()
    print("[AUDIO] Receiver thread closed.")


# --- Main Execution ---
send_thread = threading.Thread(target=send_audio, daemon=True)
recv_thread = threading.Thread(target=recv_audio, daemon=True)
control_thread = threading.Thread(target=control_loop, daemon=True)

send_thread.start()
recv_thread.start()
control_thread.start()

try:
    # Wait until quit signal is received
    while not SHOULD_QUIT.is_set():
        time.sleep(0.1)
except KeyboardInterrupt:
    SHOULD_QUIT.set()
except Exception:
    SHOULD_QUIT.set()
    
# Wait a moment for threads to close gracefully
time.sleep(0.5) 
audio_socket.close()
audio.terminate()
print("[AUDIO] Client shutdown complete.")
os._exit(0)