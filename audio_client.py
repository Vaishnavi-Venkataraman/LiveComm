import socket
import pyaudio
import threading
import struct 
import time
import os
import tkinter as tk 
import sys

SERVER_IP = '127.0.0.1' 
AUDIO_PORT = 5000

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK_SIZE = 2048

IS_MUTED = False
SHOULD_QUIT = threading.Event() 
USER_NAME = sys.argv[1] if len(sys.argv) > 1 else "Anonymous"

audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    audio_socket.connect((SERVER_IP, AUDIO_PORT))
    print(f"[AUDIO] Connected to server at {SERVER_IP}:{AUDIO_PORT}")
except Exception as e:
    print(f"[FATAL] Failed to connect to server: {e}")
    os._exit(1)

audio = pyaudio.PyAudio()

def toggle_mute(mute_button):
    global IS_MUTED
    IS_MUTED = not IS_MUTED
    
    if IS_MUTED:
        mute_button.config(text="Unmute", bg="#70ff70", fg="black")
        print(f"[STATUS] Microphone is now muted by {USER_NAME}")
    else:
        mute_button.config(text="Mute", bg="#ff7070", fg="white")
        print(f"[STATUS] Microphone is now unmuted by {USER_NAME}")

def create_controls():
    root = tk.Tk()
    root.title(f"Audio Controls - {USER_NAME}")
    root.geometry("250x100")
    root.resizable(False, False)
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root)) 

    label = tk.Label(root, text=f"Microphone Status ({USER_NAME}):", font=("Arial", 10))
    label.pack(pady=5)
    
    mute_button = tk.Button(root, text="Mute", command=lambda: toggle_mute(mute_button), 
                            font=("Arial", 12, "bold"), bg="#ff7070", fg="white", padx=10, pady=5)
    mute_button.pack(pady=5)
    
    root.mainloop()

def on_close(root):
    SHOULD_QUIT.set()
    root.destroy()
    
def send_audio():
    print("[AUDIO] Starting audio sender thread...")
    
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK_SIZE)
    except Exception as e:
        print(f"[AUDIO] Error opening input audio stream: {e}")
        SHOULD_QUIT.set()
        return
        
    while not SHOULD_QUIT.is_set():
        if IS_MUTED:
            time.sleep(0.05) 
            continue
            
        try:
            data = stream.read(CHUNK_SIZE) 
            audio_socket.sendall(data)
        except Exception:
            break
            
    stream.close()
    print("[AUDIO] Sender thread closed.")


def recv_audio():
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

if __name__ == '__main__':
    send_thread = threading.Thread(target=send_audio, daemon=True)
    recv_thread = threading.Thread(target=recv_audio, daemon=True)

    send_thread.start()
    recv_thread.start()
    create_controls()

    time.sleep(0.5) 
    audio_socket.close()
    audio.terminate()
    print("[AUDIO] Client shutdown complete.")
    os._exit(0)