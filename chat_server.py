import socket
import threading
import time
import os

HOST_IP = '0.0.0.0'
CHAT_PORT = 5001 
MAX_MESSAGE_SIZE = 1024 

clients = {} 
next_client_id = 1
lock = threading.Lock() 

try:
    chat_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    chat_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    chat_server_socket.bind((HOST_IP, CHAT_PORT))
    chat_server_socket.listen()
    print(f"Chat Server is listening on {HOST_IP}:{CHAT_PORT}")
except Exception as e:
    print(f"[FATAL] Chat server setup failed: {e}")
    os._exit(1)


def get_next_client_id():
    global next_client_id
    with lock:
        client_id = next_client_id
        next_client_id += 1
        return client_id

def broadcast_message(message_data, sender_id):    
    with lock:
        clients_to_remove = []
        current_clients = list(clients.items()) 

        for cid, client_socket in current_clients:
            if cid != sender_id:
                try:
                    client_socket.sendall(message_data) 
                except:
                    clients_to_remove.append(cid)
                    
        for cid in clients_to_remove:
            print(f"[CHAT] Client {cid} disconnected during broadcast cleanup.")
            if cid in clients:
                try: clients[cid].close()
                except: pass
                del clients[cid]

def handle_chat_client(client_socket, addr, client_id):
    print(f"[CHAT] New Client {client_id} connected from {addr}")
    
    with lock:
        clients[client_id] = client_socket
    
    try:
        while True:
            message_data = client_socket.recv(MAX_MESSAGE_SIZE)
            if not message_data: 
                raise ConnectionError
            
            broadcast_message(message_data, client_id)
            
    except:
        pass
        
    print(f"[CHAT] Client {client_id} disconnected.")
    with lock:
        if client_id in clients:
            try: clients[client_id].close()
            except: pass
            del clients[client_id]


try:
    while True:
        client_socket, addr = chat_server_socket.accept()
        client_id = get_next_client_id()
        client_thread = threading.Thread(target=handle_chat_client, args=(client_socket, addr, client_id), daemon=True)
        client_thread.start()
except KeyboardInterrupt:
    print("\nChat Server shutting down.")
except Exception as e:
    print(f"Server error: {e}")

finally:
    chat_server_socket.close()