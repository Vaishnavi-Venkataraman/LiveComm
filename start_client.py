import subprocess
import time
import os
import sys
import tkinter as tk
from tkinter import simpledialog 

CLIENT_FILES = [
    'video_client.py', 
    'audio_client.py', 
]

def get_user_name_gui():
    root = tk.Tk()
    root.withdraw() 
    root.title("Client Setup")

    name = simpledialog.askstring(
        "Meeting Setup", 
        "Enter your display name:", 
        parent=root
    )
    root.destroy()
    return name

def run_clients():

    user_name = get_user_name_gui()
    if not user_name:
        print("[INFO] Client startup cancelled or no name entered.")
        return

    print(f"--- Starting Meeting Client for User: {user_name} ---")
    
    processes = []
    
    for filename in CLIENT_FILES:
        try:
            command = [sys.executable, filename, user_name]
            
            process = subprocess.Popen(command, shell=True)
            processes.append(process)
            print(f"[STATUS] Successfully started {filename} (PID: {process.pid})")
            
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"[FATAL] Failed to start {filename}. Error: {e}")
    
    print(f"\n[INFO] Clients for {user_name} are running. Close the Tkinter control windows to quit.")

    try:
        while True:
            time.sleep(1)
            if all(p.poll() is not None for p in processes):
                break
    except KeyboardInterrupt:
        print("\n--- Terminating Clients ---")
        for p in processes:
            if p.poll() is None:
                p.terminate()

    print("Client driver finished.")


if __name__ == '__main__':
    run_clients()