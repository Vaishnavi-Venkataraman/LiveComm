import socket
import cv2
import pickle
import struct
import threading
import time
import os
import numpy as np
import tkinter as tk
from tkinter import scrolledtext
import sys

SERVER_IP = '127.0.0.1' 
VIDEO_PORT = 9999
CHAT_PORT = 5001
MAX_CHAT_MESSAGE = 1024

USER_NAME = input("Enter your display name: ")
CLIENT_ID = None 

IS_VIDEO_OFF = False
SHOULD_QUIT = threading.Event() 

video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    video_socket.connect((SERVER_IP, VIDEO_PORT))
    print(f"[VIDEO] Connected to video server.")
    chat_socket.connect((SERVER_IP, CHAT_PORT))
    print(f"[CHAT] Connected to chat server.")
except Exception as e:
    print(f"[FATAL] Connection failed. Error: {e}")
    os._exit(1)

CAMERA_INDEX = 0 
vid = cv2.VideoCapture(CAMERA_INDEX)

if not vid.isOpened():
    print(f"[FATAL] Could not open video device index {CAMERA_INDEX}.")
    os._exit(1)

_, base_frame = vid.read()
if base_frame is not None:
    H, W = base_frame.shape[:2]
else: 
    H, W = 480, 640
    
PLACEHOLDER_FRAME = np.zeros((H, W, 3), dtype=np.uint8)
cv2.putText(PLACEHOLDER_FRAME, f"VIDEO OFF - {USER_NAME}", (W // 4, H // 2), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
PICKLED_PLACEHOLDER = pickle.dumps(PLACEHOLDER_FRAME)


chat_display = None
chat_input = None
video_button = None

def toggle_video(button):
    global IS_VIDEO_OFF
    IS_VIDEO_OFF = not IS_VIDEO_OFF
    
    if IS_VIDEO_OFF:
        button.config(text="Video ON", bg="#70ff70", fg="black")
        print("[STATUS] Video is now OFF.")
    else:
        button.config(text="Video OFF", bg="#ff7070", fg="white")
        print("[STATUS] Video is now ON.")
def send_chat_message(event=None):
    message = chat_input.get()
    if message.strip():
        full_message = f"[{USER_NAME}]: {message}"
        try:
            chat_socket.send(full_message.encode('utf-8')[:MAX_CHAT_MESSAGE])
            chat_display.insert(tk.END, full_message + '\n', 'local')
            chat_display.yview(tk.END)
            chat_input.delete(0, tk.END)
        except Exception:
            chat_display.insert(tk.END, "[ERROR] Failed to send message.\n", 'error')


def create_gui():
    global chat_display, chat_input, video_button
    
    root = tk.Tk()
    root.title(f"Meeting Client - {USER_NAME}")
    root.geometry("600x400")
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))

    control_frame = tk.Frame(root, pady=10)
    control_frame.pack(fill='x')
    
    video_button = tk.Button(control_frame, text="Video OFF", command=lambda: toggle_video(video_button), 
                             font=("Arial", 12, "bold"), bg="#ff7070", fg="white", padx=10, pady=5)
    video_button.pack(side=tk.LEFT, padx=10)

    chat_frame = tk.Frame(root, padx=10, pady=5)
    chat_frame.pack(fill='both', expand=True)

    chat_display = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, height=15, width=70)
    chat_display.pack(fill='both', expand=True)
    
    chat_display.tag_config('local', foreground='blue')
    chat_display.tag_config('remote', foreground='green')
    chat_display.tag_config('error', foreground='red')

    input_frame = tk.Frame(root, padx=10, pady=5)
    input_frame.pack(fill='x')
    
    chat_input = tk.Entry(input_frame, width=50)
    chat_input.bind("<Return>", send_chat_message)
    chat_input.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
    
    send_button = tk.Button(input_frame, text="Send", command=send_chat_message)
    send_button.pack(side=tk.RIGHT)
    
    root.mainloop()

def on_close(root):
    SHOULD_QUIT.set()
    root.destroy()

def read_chat_thread():
    global chat_display
    while not SHOULD_QUIT.is_set():
        try:
            message_data = chat_socket.recv(MAX_CHAT_MESSAGE)
            if not message_data: raise ConnectionError("Chat Server closed.")
            
            message = message_data.decode('utf-8')
            chat_display.after(0, lambda: chat_display.insert(tk.END, message + '\n', 'remote'))
            chat_display.after(0, lambda: chat_display.yview(tk.END))

        except ConnectionError:
            print("\n[CHAT] Server connection closed. Shutting down.")
            SHOULD_QUIT.set()
            break
        except Exception:
            break
    print("[CHAT] Read thread closed.")

def send_metadata(name):
    name_bytes = name.encode('utf-8')[:100]
    payload = struct.pack("Q", len(name_bytes)) + name_bytes
    metadata = struct.pack("Q", 0) + struct.pack("Q", len(payload)) + payload
    try:
        video_socket.sendall(metadata)
        print(f"[VIDEO] Sent username: {name}")
    except Exception as e:
        print(f"[VIDEO] Failed to send metadata: {e}")

def send_video():
    print("[VIDEO] Starting video sender thread...")
    while vid.isOpened() and not SHOULD_QUIT.is_set(): 
        
        if IS_VIDEO_OFF:
            data = PICKLED_PLACEHOLDER
            frame = PLACEHOLDER_FRAME
        else:
            success, frame = vid.read() 
            if not success or frame is None: 
                break
            
            cv2.putText(frame, f"{USER_NAME} (YOU)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
            data = pickle.dumps(frame)
        
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
    
    vid.release()
    cv2.destroyAllWindows()
    print("[VIDEO] Sender thread closed.")


def receive_video():
    data = b""
    type_and_payload_size = struct.calcsize("Q") * 2 
    remote_names = {} 

    print("[VIDEO] Starting video receiver thread...")
    while not SHOULD_QUIT.is_set():
        try:
            while len(data) < type_and_payload_size:
                packet = video_socket.recv(4 * 1024)
                if not packet: raise ConnectionError("Server closed connection.")
                data += packet
                
            type_code = struct.unpack("Q", data[:8])[0]
            packed_msg_size = data[8:16]
            full_msg_size = struct.unpack("Q", packed_msg_size)[0]
            data = data[type_and_payload_size:]

            while len(data) < full_msg_size:
                data += video_socket.recv(4 * 1024)
            full_data = data[:full_msg_size]
            data = full_data[full_msg_size:]
            
            if type_code == 0:
                sender_id = struct.unpack("Q", full_data[:8])[0]
                name_len = struct.unpack("Q", full_data[8:16])[0]
                name_bytes = full_data[16:16 + name_len]
                remote_name = name_bytes.decode('utf-8')
                remote_names[sender_id] = remote_name

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

        except Exception:
            break
    print("[VIDEO] Receiver thread closed.")


if __name__ == '__main__':
    send_metadata(USER_NAME)

    video_sender_thread = threading.Thread(target=send_video, daemon=True)
    video_receiver_thread = threading.Thread(target=receive_video, daemon=True)
    chat_reader_thread = threading.Thread(target=read_chat_thread, daemon=True)

    video_sender_thread.start()
    video_receiver_thread.start()
    chat_reader_thread.start()

    create_gui() 

    time.sleep(0.5) 
    video_socket.close()
    chat_socket.close()
    print("[VIDEO/CHAT] Client shutdown complete.")
    os._exit(0)