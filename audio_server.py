import socket
import pyaudio
import threading
import time
import struct
import os

# --- Configuration ---
HOST_IP = '0.0.0.0' 
AUDIO_PORT = 5000
CHUNK_SIZE = 2048 

# Audio Configuration (Must match client)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# --- Server State ---
clients = {} 
next_client_id = 1
lock = threading.Lock() 

# --- Setup ---
try:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST_IP, AUDIO_PORT))
    server_socket.listen(5)
    print(f"Audio Server listening on {HOST_IP}:{AUDIO_PORT}")
    audio = pyaudio.PyAudio()
except Exception as e:
    print(f"[FATAL] Failed to set up server socket or PyAudio: {e}")
    os._exit(1)


def get_next_client_id():
    """Generates a unique client ID."""
    global next_client_id
    with lock:
        client_id = next_client_id
        next_client_id += 1
        return client_id

def broadcast_audio(audio_chunk, sender_id):
    """
    Sends the audio chunk, prefixed with the sender's ID, to all other connected clients.
    The data format sent over the network is: [8-byte sender ID] + [Audio Chunk].
    """
    
    # 1. Prefix the audio chunk with the sender's ID (8 bytes 'Q')
    client_id_bytes = struct.pack("Q", sender_id)
    data_to_send = client_id_bytes + audio_chunk
    
    # 2. Broadcast to all clients except the sender
    with lock:
        clients_to_remove = []
        current_clients = list(clients.items()) 
        
        for cid, client_socket in current_clients:
            if cid != sender_id:
                try:
                    client_socket.sendall(data_to_send)
                except:
                    clients_to_remove.append(cid)
                    
        # 3. Cleanup disconnected clients
        for cid in clients_to_remove:
            print(f"[AUDIO] Client {cid} disconnected during broadcast cleanup.")
            if cid in clients:
                try: clients[cid].close() 
                except: pass
                del clients[cid]

def handle_audio_client(client_socket, addr, client_id):
    """Handles continuous audio reception and broadcasting for a single client."""
    print(f"[AUDIO] New Client {client_id} connected from {addr}")
    
    with lock:
        clients[client_id] = client_socket
        
    try:
        while True:
            # We must receive exactly CHUNK_SIZE bytes of raw audio data
            data = b''
            bytes_left = CHUNK_SIZE
            
            # Robustly receive the full chunk
            while bytes_left > 0:
                chunk = client_socket.recv(bytes_left)
                if not chunk: 
                    raise ConnectionError("Client socket closed.")
                data += chunk
                bytes_left -= len(chunk)

            # If the full chunk size was received, broadcast it
            if len(data) == CHUNK_SIZE:
                broadcast_audio(data, client_id)
            
    except ConnectionError as e:
        print(f"[AUDIO] Client {client_id} disconnected: {e}")
    except Exception as e:
        print(f"[AUDIO] Error handling client {client_id}: {e}")
        
    # --- Cleanup on exit ---
    with lock:
        if client_id in clients:
            try: clients[client_id].close()
            except: pass
            del clients[client_id]
            print(f"[AUDIO] Client {client_id} removed from active connections.")

# --- Main Server Loop ---
try:
    while True:
        client_socket, addr = server_socket.accept()
        client_id = get_next_client_id()
        client_thread = threading.Thread(target=handle_audio_client, args=(client_socket, addr, client_id), daemon=True)
        client_thread.start()
        
except KeyboardInterrupt:
    print("\nAudio Server shutting down gracefully.")
except Exception as e:
    print(f"An unexpected server error occurred: {e}")

finally:
    server_socket.close()
    if 'audio' in locals():
        audio.terminate()