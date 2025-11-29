import subprocess
import time
import os
import sys

SERVER_FILES = [
    'video_server.py',
    'audio_server.py',
    'chat_server.py',
]

def run_servers():
    print("--- Starting Meeting Application Servers ---")
    
    processes = []
    
    for filename in SERVER_FILES:
        try:
            process = subprocess.Popen([sys.executable, filename], shell=True)
            processes.append(process)
            print(f"[STATUS] Successfully started {filename} (PID: {process.pid})")
        except Exception as e:
            print(f"[FATAL] Failed to start {filename}. Check dependencies. Error: {e}")

    print("\n[INFO] All servers are running. Press Ctrl+C to stop all servers.")
    
    try:
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    print(f"\n[ALERT] Server {SERVER_FILES[processes.index(p)]} crashed unexpectedly!")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\n--- Shutting Down All Servers ---")
        for p in processes:
            if p.poll() is None: 
                p.terminate()
        
        time.sleep(1)
        print("Shutdown complete.")

if __name__ == '__main__':
    run_servers()