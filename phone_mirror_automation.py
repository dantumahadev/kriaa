import subprocess
import re
import time
import sys
import threading
import os
import xml.etree.ElementTree as ET
import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# ─── KRIA OS Emergency Monitor ───────────────────────────────────────────────
try:
    from backend.emergency_monitor import emergency_session
    EMERGENCY_MONITOR_ENABLED = True
    print("[KRIA OS] Emergency Monitor loaded.")
except Exception as e:
    print(f"[KRIA OS] Emergency Monitor not available: {e}")
    EMERGENCY_MONITOR_ENABLED = False

# ─── KRIA OS WhatsApp Caregiver Monitor ────────────────────────────────────
try:
    from backend.whatsapp_monitor import whatsapp_monitor
    WHATSAPP_MONITOR_ENABLED = True
    print("[KRIA OS] WhatsApp Monitor loaded.")
except Exception as e:
    print(f"[KRIA OS] WhatsApp Monitor not available: {e}")
    WHATSAPP_MONITOR_ENABLED = False

# Configuration
TARGET_URL = "https://www.jotform.com/agent/019a4add964b79f3aa038b973d1fea25967d"
TAP_THRESHOLD = 3
TIME_WINDOW = 1.5  
AUTO_OPEN_MIRROR = True 
ADB_SERIAL = None 
AGENT_ACTIVE = False # Flag to prevent tap interference when an agent is active

def detect_device():
    """Detect the first active device serial."""
    global ADB_SERIAL
    try:
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = res.stdout.strip().split('\n')[1:] 
        active_devices = [l.split('\t')[0] for l in lines if '\tdevice' in l]
        if active_devices:
            ADB_SERIAL = active_devices[0]
            print(f"[KRIA OS] Using device: {ADB_SERIAL}")
            return True
        return False
    except Exception:
        return False

def run_adb_command(command):
    """Run an ADB command and return output."""
    global ADB_SERIAL
    try:
        base = ["adb"]
        if ADB_SERIAL:
            base += ["-s", ADB_SERIAL]
            
        if isinstance(command, str):
            cmd_list = base + command.split()
        else:
            cmd_list = base + command
            
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Silently fail if getevent fails on specific ports, but maybe log for debugging
        # print(f"ADB Error: {e.stderr}")
        return None
    except Exception:
        return None

def launch_scrcpy():
    """Launch scrcpy to mirror the phone screen."""
    print("Launching scrcpy screen mirroring...")
    try:
        # Launching scrcpy in a separate process
        # We use 'start' on windows to run it without blocking or in a new window
        subprocess.Popen(["scrcpy", "--always-on-top"], shell=True)
    except FileNotFoundError:
        print("Error: 'scrcpy' not found in PATH. Please install it to use mirroring.")
    except Exception as e:
        print(f"Failed to launch scrcpy: {e}")

def get_touch_device():
    """
    Identify the touchscreen input device.
    Method 1: getevent -pl (works over USB, may fail over TCP)
    Method 2: scan /dev/input/ directly (fallback for Wi-Fi/TCP)
    """
    # Method 1 — standard approach
    output = run_adb_command("shell getevent -pl")
    if output:
        current_device = None
        for line in output.split('\n'):
            if line.startswith("add device"):
                match = re.search(r'add device \d+: (/dev/input/event\d+)', line)
                if match: current_device = match.group(1)
            elif "ABS_MT_POSITION_X" in line and current_device:
                print(f"[Tap] Found touch device (method 1): {current_device}")
                return current_device

    # Method 2 — scan each event file directly (works over TCP/Wi-Fi)
    print("[Tap] Method 1 failed, scanning /dev/input/ directly...")
    ls = run_adb_command("shell ls /dev/input/")
    if ls:
        for entry in sorted(ls.split()):
            if not entry.startswith("event"):
                continue
            path = f"/dev/input/{entry}"
            info = run_adb_command(f"shell getevent -pl {path}")
            if info and "ABS_MT_POSITION_X" in info:
                print(f"[Tap] Found touch device (method 2): {path}")
                return path

    return None

def find_and_click_voice_button():
    """Navigate UI and select Voice mode, targeting the bottom tab."""
    print("Waiting for mobile page to load (8s)...")
    time.sleep(8)
    
    dump_path = "/sdcard/ui_dump.xml"
    local_path = "ui_dump.xml"
    
    # We want to find the "Voice" tab at the bottom
    for attempt in range(3): 
        run_adb_command(f"shell uiautomator dump {dump_path}")
        run_adb_command(["pull", dump_path, local_path])
        
        if not os.path.exists(local_path): 
            time.sleep(1)
            continue
        
        try:
            tree = ET.parse(local_path)
            root = tree.getroot()
            
            voice_nodes = []
            for node in root.iter('node'):
                text = node.get('text', '').lower()
                desc = node.get('content-desc', '').lower()
                
                if text == 'voice' or desc == 'voice':
                    voice_nodes.append(node)

            if voice_nodes:
                # Target the bottom-most 'Voice' node (highest Y coordinate)
                # This ensures we click the bottom tab rather than any other item
                def get_y_coord(n):
                    b = n.get('bounds')
                    m = re.findall(r'\d+', b)
                    return int(m[1]) if len(m) >= 2 else 0

                target_node = max(voice_nodes, key=get_y_coord)
                bounds = target_node.get('bounds')
                m = re.findall(r'\d+', bounds)
                if len(m) == 4:
                    x = (int(m[0]) + int(m[2])) // 2
                    y = (int(m[1]) + int(m[3])) // 2
                    print(f"Targeting Bottom Voice Tab at ({x}, {y})")
                    run_adb_command(f"shell input tap {x} {y}")
                    
                    # Wait for "Calling Agent" state
                    print("Waiting for calling state...")
                    time.sleep(3)
                    run_adb_command(f"shell uiautomator dump {dump_path}")
                    run_adb_command(["pull", dump_path, local_path])
                    
                    if os.path.exists(local_path):
                        new_tree = ET.parse(local_path)
                        new_root = new_tree.getroot()
                        for n in new_root.iter('node'):
                            t = n.get('text', '').lower()
                            if 'calling' in t or 'agent' in t or 'hi' in t:
                                print(">>> Voice Call Initialized Successfully! <<<")
                                return True
                    return True
            
            print(f"Voice tab not found in attempt {attempt+1}, retrying...")
            time.sleep(2)
        except Exception as e:
            print(f"Parsing error: {e}")
        finally:
            if os.path.exists(local_path): os.remove(local_path)
            
    print("Could not find Voice button. Please ensure the agent UI is fully loaded.")
    return False

def stop_action():
    """2-tap: Emergency ABORT — closes browser, goes home. Clears Busy flag."""
    global AGENT_ACTIVE
    print("\nXXX DOUBLE TAP DETECTED - Emergency Abort XXX")
    AGENT_ACTIVE = False
    run_adb_command("shell am force-stop com.android.chrome")
    run_adb_command("shell am force-stop com.sec.android.app.sbrowser")
    run_adb_command("shell input keyevent 3")

def trigger_action():
    """3-tap: Launch the JotForm Blind Assist voice agent."""
    global AGENT_ACTIVE
    if AGENT_ACTIVE:
        print("[KRIA OS] Busy with an active action. Abort first.")
        return
        
    print("\n!!! TRIPLE TAP DETECTED - Starting Blind Assist !!!")
    AGENT_ACTIVE = True
    run_adb_command(f"shell am start -a android.intent.action.VIEW -d {TARGET_URL}")
    threading.Thread(target=find_and_click_voice_button, daemon=True).start()

def trigger_whatsapp_monitor():
    """4-tap: Toggle WhatsApp caregiver message monitor on/off."""
    global AGENT_ACTIVE
    if AGENT_ACTIVE:
        print("[KRIA OS] Busy with Blind Assist. Abort first.")
        return
        
    if not WHATSAPP_MONITOR_ENABLED:
        print("[KRIA OS] WhatsApp Monitor not loaded.")
        return
    if whatsapp_monitor.active:
        print("\n!!! QUAD TAP - STOPPING WHATSAPP MONITOR !!!")
        whatsapp_monitor.stop()
    else:
        print("\n!!! QUAD TAP - STARTING WHATSAPP MONITOR !!!")
        threading.Thread(target=whatsapp_monitor.start, daemon=True).start()


def monitor_taps(device_path):
    print(f"Monitoring phone taps on {device_path}...")
    print("─────────────────────────────────────────────")
    print(" 2 taps → ABORT  (close browser, go home)   ")
    print(" 3 taps → BLIND ASSIST  (JotForm agent)      ")
    print("          ↳ Emergency monitor auto-starts     ")
    print("          ↳ SOS auto-fires if critical speech ")
    print(" 4 taps → WHATSAPP MONITOR  (toggle on/off)  ")
    print("─────────────────────────────────────────────")
    
    cmd = ["adb", "shell", "getevent", "-lt", device_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, encoding='utf-8', errors='ignore')

    import queue

    # Queue to decouple reading from processing
    event_queue = queue.Queue()

    def read_adb_output(proc):
        """Reads stdout and puts lines into the queue."""
        for line in iter(proc.stdout.readline, ''):
            event_queue.put(line)
        proc.stdout.close()

    # Start the reader thread
    reader_thread = threading.Thread(target=read_adb_output, args=(process,), daemon=True)
    reader_thread.start()

    tap_times = []
    tracking_pattern = re.compile(r'ABS_MT_TRACKING_ID\s+([0-9a-fA-F]+)')
    
    last_action_time = 0
    COOLDOWN = 3.0 # Wait 3 seconds after an action before allowing another

    try:
        while True:
            try:
                # Wait for a line with a short timeout to allow "silence" checks
                line = event_queue.get(timeout=0.1)
                
                now = time.time()
                match = tracking_pattern.search(line)
                
                # If a new touch down is detected
                if match and match.group(1).lower() != 'ffffffff':
                    # Ignore taps during cooldown
                    if now - last_action_time < COOLDOWN:
                        continue

                    # Remove taps that are too old (window for a single gesture)
                    tap_times = [t for t in tap_times if now - t < 2.0]
                    tap_times.append(now)
                    print(f"DEBUG: Tap {len(tap_times)} registered")

            except queue.Empty:
                # No new input: Check if we have a pending gesture that has finished
                now = time.time()
                if tap_times and (now - tap_times[-1] > 0.7):
                    count = len(tap_times)
                    print(f"DEBUG: Gesture Ended with {count} taps")
                    
                    if count == 2:
                        stop_action()
                        last_action_time = time.time()
                    elif count == 3:
                        trigger_action()
                        last_action_time = time.time()
                    elif count >= 4:
                        trigger_whatsapp_monitor()
                        last_action_time = time.time()
                    
                    tap_times = [] # Reset after check

    except Exception as e:
        print(f"Monitor error: {e}")
    finally:
        process.terminate()

def main():
    print("--- Medical Assist: SCRCPY + Triple Tap Server ---")
    
    # Check ADB and detect serial
    if not detect_device():
        print("Error: No active phone detected. Connect via USB or ensure Wi-Fi ADB is active.")
        # Try to show what we did find
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        print(f"Current devices:\n{res.stdout}")
        return

    # Find Touch Device
    device_path = get_touch_device()
    if not device_path:
        print("Error: Could not find touchscreen device.")
        print("Tip: Ensure your screen is ON and unlocked.")
        return

    # Optionally launch scrcpy
    if AUTO_OPEN_MIRROR:
        launch_scrcpy()

    monitor_taps(device_path)

if __name__ == "__main__":
    main()
