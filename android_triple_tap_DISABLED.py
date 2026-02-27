import subprocess
import re
import time
import sys
import threading
import os
import xml.etree.ElementTree as ET

# Configuration
TARGET_URL = "https://www.jotform.com/agent/019a4add964b79f3aa038b973d1fea25967d"
TAP_THRESHOLD = 3
TIME_WINDOW = 1.0  # Seconds to register 3 taps
AUTO_SELECT_VOICE = True

def run_adb_command(command):
    """Run an ADB commapython phone_mirror_automation.pynd and return output."""
    try:
        # For 'pull', we use the list format to handle paths with spaces if needed
        if command.startswith("pull"):
            parts = command.split()
            result = subprocess.run(["adb"] + parts, capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
        else:
            result = subprocess.run(
                ["adb"] + command.split(),
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
                 errors='ignore'
            )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return None
    except FileNotFoundError:
        print("Error: 'adb' not found. Please ensure Android Platform Tools are installed and in PATH.")
        sys.exit(1)

def get_touch_device():
    """Identify the touchscreen input device."""
    print("Scanning for touchscreen device...")
    output = run_adb_command("shell getevent -pl")
    if not output:
        return None

    current_device = None
    touch_device = None

    for line in output.split('\n'):
        if line.startswith("add device"):
            # format: add device 1: /dev/input/eventX
            match = re.search(r'add device \d+: (/dev/input/event\d+)', line)
            if match:
                current_device = match.group(1)
        elif "ABS_MT_POSITION_X" in line:
            if current_device:
                touch_device = current_device
                # We found a multitouch X axis, good candidate
                # Don't break immediately, some phones have multiple (stylus etc), 
                # but usually the first one with MT is the screen.
                break
    
    return touch_device

def find_and_click_voice_button():
    """Attempt to find and click the voice call button using UI Automator."""
    print("Waiting for page and assets to load (10s)...")
    time.sleep(10) 
    
    dump_path = "/sdcard/ui_dump.xml"
    local_path = "ui_dump.xml"
    
    def get_ui_dump():
        run_adb_command(f"shell uiautomator dump {dump_path}")
        run_adb_command(f"pull {dump_path} {local_path}")
        if os.path.exists(local_path):
            try:
                tree = ET.parse(local_path)
                return tree.getroot()
            except:
                return None
        return None

    # Step 1: Look for Menu/Grid icon to open sidebar if not visible
    print("Checking if side menu needs to be opened...")
    root = get_ui_dump()
    if root is not None:
        # Looking for a button that might open the "Agent Channels" sidebar
        # Often a grid-like icon or hamburger in top left.
        menu_found = False
        for node in root.iter('node'):
            desc = node.get('content-desc', '').lower()
            res = node.get('resource-id', '').lower()
            # Common identifiers for the sidebar toggle in Jotform Agents
            if 'menu' in desc or 'grid' in desc or 'navigation' in desc or 'sidebar' in res:
                bounds = node.get('bounds')
                m = re.findall(r'\d+', bounds)
                if len(m) == 4:
                    x = (int(m[0]) + int(m[2])) // 2
                    y = (int(m[1]) + int(m[3])) // 2
                    print(f"Opening menu at ({x}, {y})...")
                    run_adb_command(f"shell input tap {x} {y}")
                    menu_found = True
                    time.sleep(2) # Wait for animation
                    break
        
        # Step 2: Now look for "Voice" specifically
        root = get_ui_dump() # Refresh dump
        if root is not None:
            keywords = ['voice', 'call', 'audio']
            found_node = None
            
            for node in root.iter('node'):
                text = node.get('text', '').lower()
                desc = node.get('content-desc', '').lower()
                
                if any(kw == text or kw in desc for kw in keywords):
                    found_node = node
                    break
            
            if found_node:
                bounds = found_node.get('bounds')
                print(f"Selecting Voice option at {bounds}")
                m = re.findall(r'\d+', bounds)
                if len(m) == 4:
                    x = (int(m[0]) + int(m[2])) // 2
                    y = (int(m[1]) + int(m[3])) // 2
                    print(f"Automating click at ({x}, {y}) to start voice mode.")
                    run_adb_command(f"shell input tap {x} {y}")
                    return True
            else:
                # Fallback: Check for floating microphone icon near the bottom right (common in mobile view)
                print("Voice option not found in menu, checking for microphone icon...")
                for node in root.iter('node'):
                    desc = node.get('content-desc', '').lower()
                    if 'mic' in desc or 'microphone' in desc or 'audio' in desc:
                        bounds = node.get('bounds')
                        m = re.findall(r'\d+', bounds)
                        if len(m) == 4:
                            x = (int(m[0]) + int(m[2])) // 2
                            y = (int(m[1]) + int(m[3])) // 2
                            run_adb_command(f"shell input tap {x} {y}")
                            return True

    print("Could not automate voice selection. Please confirm the screen content.")
    if os.path.exists(local_path):
        os.remove(local_path)
    return False

def trigger_action():
    """Open the URL on the device and optionally start voice mode."""
    print(f"\n!!! TRIPLE TAP DETECTED - Opening Medical Assistant !!!")
    run_adb_command(f"shell am start -a android.intent.action.VIEW -d {TARGET_URL}")
    
    if AUTO_SELECT_VOICE:
        # Run in a background thread to avoid hanging the tap monitor
        threading.Thread(target=find_and_click_voice_button, daemon=True).start()

def monitor_taps(device_path):
    """Monitor raw events for taps."""
    print(f"Monitoring events on {device_path}...")
    
    # Process: adb shell getevent -lt [device]
    # -l: label (human readable names)
    # -t: timestamp
    cmd = ["adb", "shell", "getevent", "-lt", device_path]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding='utf-8', 
        errors='ignore'
    )

    tap_times = []
    
    # Regex to find Touch Down events.
    # Different protocols exist (Type A vs Type B).
    # Common indicator: ABS_MT_TRACKING_ID [some_value] (start of contact)
    # Or BTN_TOUCH DOWN
    
    # Pattern for tracking ID (Type B - most modern phones)
    # [   4522.254124] EV_ABS       ABS_MT_TRACKING_ID   00000001 
    # Value ffffffff is release. Any other value is touch down.
    
    tracking_id_pattern = re.compile(r'EV_ABS\s+ABS_MT_TRACKING_ID\s+([0-9a-fA-F]+)')
    
    # Pattern for BTN_TOUCH (Type A / older or some stylus)
    btn_touch_pattern = re.compile(r'EV_KEY\s+BTN_TOUCH\s+DOWN')

    print("Listening for 3 rapid taps globally... (Press Ctrl+C to stop)")

    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            # Check for Touch Down
            is_touch_down = False
            
            # Check Type B
            match_b = tracking_id_pattern.search(line)
            if match_b:
                val = match_b.group(1)
                # ffffffff is -1 in 32-bit hex, meaning Release. Anything else is press.
                if val.lower() != 'ffffffff':
                    is_touch_down = True
            
            # Check Type A
            if not is_touch_down and btn_touch_pattern.search(line):
                is_touch_down = True

            if is_touch_down:
                now = time.time()
                # Clean up old taps
                tap_times = [t for t in tap_times if now - t < TIME_WINDOW]
                
                tap_times.append(now)
                # print(f"Tap detected! Count: {len(tap_times)}") # Removed for less console spam
                
                if len(tap_times) >= TAP_THRESHOLD:
                    trigger_action()
                    tap_times = [] # Reset
                    time.sleep(1.0) # Debounce to prevent double trigger

    except Exception as e:
        print(f"Error reading stream: {e}")
    finally:
        process.terminate()

def main():
    print("--- Medical Assist: Triple Tap Automation Server ---")
    
    # Check if ADB is working
    if run_adb_command("devices") is None:
        print("Device not responding. Please check USB connection and adb status.")
        sys.exit(1)

    # Loop to wait for device
    device_path = None
    while not device_path:
        device_path = get_touch_device()
        if not device_path:
            print("Connecting to phone... (Ensure USB Debugging is ON)")
            time.sleep(3)
    
    print(f"Ready. Triple tap on the phone screen will launch assistance.")
    monitor_taps(device_path)

if __name__ == "__main__":
    main()
