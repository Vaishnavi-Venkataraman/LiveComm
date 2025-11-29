import socket
import cv2
import pickle
import struct
import threading
import os

HOST_IP = '0.0.0.0'
VIDEO_PORT = 9999

clients = {} 
client_names = {} 
next_client_id = 1
lock = threading.Lock() 

try:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST_IP, VIDEO_PORT))
    server_socket.listen()
    print(f"Video Server is listening on {HOST_IP}:{VIDEO_PORT}")
except Exception as e:
    print(f"[FATAL] Video server setup failed: {e}")
    os._exit(1)


def get_next_client_id():
    """Generates a unique client ID."""
    global next_client_id
    with lock:
        client_id = next_client_id
        next_client_id += 1
        return client_id

def broadcast_message(message_type, data_to_send, sender_id):
    """General function to broadcast either frame data (type 1) or metadata (type 0)."""
    
    type_bytes = struct.pack("Q", message_type)
    message = type_bytes + struct.pack("Q", len(data_to_send)) + data_to_send
    
    with lock:
        clients_to_remove = []
        current_clients = list(clients.items()) 

        for cid, client_socket in current_clients:
            if message_type == 1 and cid == sender_id:
                continue
            
            try:
                client_socket.sendall(message)
            except:
                clients_to_remove.append(cid)
                    
        for cid in clients_to_remove:
            print(f"[VIDEO] Client {cid} disconnected during broadcast cleanup.")
            if cid in clients:
                try: clients[cid].close()
                except: pass
                del clients[cid]
            if cid in client_names:
                del client_names[cid]
                
def broadcast_all_names_to_new_client(new_client_socket, new_client_id):
    with lock:
        for cid, name in client_names.items():
            if cid != new_client_id:
                name_bytes = name.encode('utf-8')
                
                name_metadata = struct.pack("Q", cid) + struct.pack("Q", len(name_bytes)) + name_bytes
                
                type_bytes = struct.pack("Q", 0)
                message = type_bytes + struct.pack("Q", len(name_metadata)) + name_metadata
                
                try:
                    new_client_socket.sendall(message)
                except Exception as e:
                    print(f"[WARNING] Failed to send existing name map to new client {new_client_id}: {e}")

def receive_client_name(client_socket, client_id):

    data = b""
    type_and_payload_size = struct.calcsize("Q") * 2 # 16 bytes (Type + Size)
    
    try:
        # 1. Receive Header (Type and Message Size)
        while len(data) < type_and_payload_size:
            packet = client_socket.recv(4 * 1024)
            if not packet: raise ConnectionError("Client closed during handshake.")
            data += packet
            
        type_code = struct.unpack("Q", data[:8])[0]
        packed_msg_size = data[8:16]
        msg_size = struct.unpack("Q", packed_msg_size)[0]
        data = data[type_and_payload_size:]

        if type_code != 0:
            return False, b""

        while len(data) < msg_size:
            data += client_socket.recv(4 * 1024)
        payload = data[:msg_size]
        
        name_len = struct.unpack("Q", payload[:8])[0]
        name_bytes = payload[8:8 + name_len]
        name = name_bytes.decode('utf-8')
        
        with lock:
            client_names[client_id] = name
            print(f"[NAME] Client {client_id} identified as {name}")
        
        name_metadata = struct.pack("Q", client_id) + payload
        broadcast_message(0, name_metadata, client_id)
        
        return True, data[msg_size:] 

    except Exception as e:
        print(f"[ERROR] Failed to receive initial client name for {client_id}: {e}")
        return False, b""


def handle_video_client(client_socket, addr, client_id):
    print(f"[VIDEO] New Client {client_id} connected from {addr}")
    
    with lock:
        clients[client_id] = client_socket
        
    success, leftover_data = receive_client_name(client_socket, client_id)
    if not success:
        client_socket.close()
        return 
    
    broadcast_all_names_to_new_client(client_socket, client_id)
    
    data = leftover_data
    type_and_payload_size = struct.calcsize("Q") * 2 
    
    try:
        while True:
            while len(data) < type_and_payload_size:
                packet = client_socket.recv(4 * 1024)
                if not packet: raise ConnectionError
                data += packet
                
            type_code = struct.unpack("Q", data[:8])[0]
            packed_msg_size = data[8:16]
            msg_size = struct.unpack("Q", packed_msg_size)[0]
            data = data[type_and_payload_size:]

            while len(data) < msg_size:
                data += client_socket.recv(4 * 1024)
            payload = data[:msg_size]
            data = data[msg_size:]
            
            if type_code == 1:
                data_to_send = struct.pack("Q", client_id) + payload
                broadcast_message(1, data_to_send, client_id)
            else:
                print(f"[WARNING] Received unexpected message type {type_code} in main loop.")

    except:
        pass
        
    print(f"[VIDEO] Client {client_id} disconnected.")
    with lock:
        if client_id in clients:
            try: clients[client_id].close()
            except: pass
            del clients[client_id]
        if client_id in client_names:
            del client_names[client_id]

try:
    while True:
        client_socket, addr = server_socket.accept()
        client_id = get_next_client_id()
        client_thread = threading.Thread(target=handle_video_client, args=(client_socket, addr, client_id), daemon=True)
        client_thread.start()
except KeyboardInterrupt:
    print("\nVideo Server shutting down.")
except Exception as e:
    print(f"Server error: {e}")

finally:
    server_socket.close()
    cv2.destroyAllWindows()