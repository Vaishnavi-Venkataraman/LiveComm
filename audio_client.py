import socket
import pyaudio
import threading
import struct 
import time
import os

# --- Configuration ---
# CHANGE THIS TO THE SERVER'S IP ADDRESS IF RUNNING ON DIFFERENT MACHINES
SERVER_IP = '127.0.0.1' 
AUDIO_PORT = 5000

# Audio Configuration (Must match server)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK_SIZE = 2048

# --- Setup ---
audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    audio_socket.connect((SERVER_IP, AUDIO_PORT))
    print(f"[AUDIO] Connected to server at {SERVER_IP}:{AUDIO_PORT}")
except Exception as e:
    print(f"[AUDIO] Failed to connect to server: {e}")
    os._exit(1)

audio = pyaudio.PyAudio()

# --- Audio Logic ---

def send_audio():
    """Captures audio chunks and sends them to the server."""
    print("[AUDIO] Starting audio sender thread...")
    
    try:
        # PyAudio fix applied: removed 'exception_on_overflow=False'
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK_SIZE)
    except Exception as e:
        print(f"[AUDIO] Error opening input audio stream: {e}")
        return
        
    while True:
        try:
            # Read audio data from the microphone
            data = stream.read(CHUNK_SIZE)
            audio_socket.sendall(data)
        except Exception:
            # Server connection lost or stream error
            break
            
    stream.close()

def recv_audio():
    """Receives audio streams from the server and plays them."""
    print("[AUDIO] Starting audio receiver thread...")
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK_SIZE)
    except Exception as e:
        print(f"[AUDIO] Error opening output audio stream: {e}")
        return

    # Size of the sender ID (8 bytes 'Q')
    id_size = struct.calcsize("Q") 
    data_to_receive = id_size + CHUNK_SIZE 

    while True:
        try:
            data = b''
            bytes_left = data_to_receive
            
            # Robustly receive the full packet (ID + Audio Data)
            while bytes_left > 0:
                chunk = audio_socket.recv(bytes_left)
                if not chunk: 
                    raise ConnectionError("Server socket closed.")
                data += chunk
                bytes_left -= len(chunk)
            
            if len(data) != data_to_receive:
                continue

            # 1. Separate Sender ID and Audio Data
            sender_id = struct.unpack("Q", data[:id_size])[0]
            audio_chunk = data[id_size:]
            
            # 2. Play the audio
            stream.write(audio_chunk)

        except ConnectionError as e:
            print(f"[AUDIO] Server connection closed. Error: {e}")
            break
        except Exception:
            break
            
    stream.close()

# --- Main Execution ---
send_thread = threading.Thread(target=send_audio, daemon=True)
recv_thread = threading.Thread(target=recv_audio, daemon=True)

send_thread.start()
recv_thread.start()

try:
    send_thread.join()
    recv_thread.join()
except:
    pass

audio_socket.close()
audio.terminate()
print("[AUDIO] Client shutdown complete.")