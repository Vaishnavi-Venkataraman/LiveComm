import subprocess
import time
import os
import sys
import tkinter as tk
from tkinter import messagebox

CLIENT_FILES = [
    'video_client.py',
    'audio_client.py',
]

def run_clients():
    print("--- Starting Meeting Client ---")
    processes = []
    
    for filename in CLIENT_FILES:
        try:
            process = subprocess.Popen([sys.executable, filename], shell=True)
            processes.append(process)
            print(f"[STATUS] Successfully started {filename} (PID: {process.pid})")
        except Exception as e:
            print(f"[FATAL] Failed to start {filename}. Error: {e}")
    
    print("\n[INFO] Clients are running. Close the Tkinter control windows to quit.")

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