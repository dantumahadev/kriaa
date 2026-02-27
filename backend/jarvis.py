import speech_recognition as sr
import pyttsx3
import subprocess
import time
import os
import threading

# --- CONFIGURATION ---
JARVIS_NAME = "Jarvis"
DEVICE_ID = None

def get_device_id():
    """Get the first connected device ID."""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')[1:]
        for line in lines:
            if "device" in line and "offline" not in line:
                return line.split()[0]
    except Exception:
        pass
    return None

DEVICE_ID = get_device_id()

# --- ADB UTILS ---
def run_adb(command):
    """Executes ADB command on specific device."""
    try:
        if DEVICE_ID:
            cmd_list = ["adb", "-s", DEVICE_ID] + command.split()
        else:
             cmd_list = ["adb"] + command.split()
        result = subprocess.run(cmd_list, capture_output=True, text=True, errors="ignore")
        return result.stdout.strip()
    except Exception as e:
        print(f"ADB Error: {e}")
        return ""

def check_notifications(package_name):
    """Checks for notifications from a specific app."""
    dump = run_adb("shell dumpsys notification --noredact")
    if package_name in dump:
        # Very accessible heuristic
        return True
    return False

# --- TTS ENGINE ---
engine = pyttsx3.init()
def speak(text):
    print(f"[JARVIS]: {text}")
    engine.say(text)
    engine.runAndWait()

# --- COMMAND PROCESSING ---
def process_command(text):
    text = text.lower()
    print(f"Heard: {text}")

    # 1. APP OPENING
    if "open" in text:
        app_map = {
            "whatsapp": "com.whatsapp",
            "youtube": "com.google.android.youtube",
            "chrome": "com.android.chrome",
            "settings": "com.android.settings",
            "camera": "com.android.camera",
            "zomato": "com.application.zomato"
        }
        
        for app_name, pkg in app_map.items():
            if app_name in text:
                speak(f"Opening {app_name} on your phone.")
                run_adb(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
                
                # Contextual Follow-up
                if app_name == "whatsapp":
                    time.sleep(2) # Wait for launch
                    if check_notifications(pkg):
                        speak("You have unread notifications from WhatsApp. Do you want me to read them?")
                    else:
                        speak("WhatsApp is open. Who do you want to message?")
                
                elif app_name == "youtube":
                    speak("YouTube is active. What should I search for?")
                
                return

    # 2. SCROLLING
    if "scroll down" in text:
        run_adb("shell input swipe 500 1500 500 500 300")
        return
    if "scroll up" in text:
        run_adb("shell input swipe 500 500 500 1500 300")
        return

    # 3. HOME / BACK
    if "home" in text:
        run_adb("shell input keyevent 3")
        speak("Going home.")
        return
    if "back" in text:
        run_adb("shell input keyevent 4")
        return
    
    # 4. TYPING
    if "type" in text:
        content = text.split("type", 1)[1].strip()
        run_adb(f"shell input text {content.replace(' ', '%s')}")
        speak(f"Typed {content}")
        return

# --- MAIN LOOP ---
def start_listening():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        print("\n--- JARVIS LISTENING (Laptop Mic) ---")
        print(f"Targeting Phone: {DEVICE_ID}")
        speak("System Online. I am listening.")

    while True:
        try:
            with mic as source:
                print("Listening...")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            
            try:
                text = recognizer.recognize_google(audio)
                if text:
                    process_command(text)
            except sr.UnknownValueError:
                pass # Ignore silence/noise
            except sr.RequestError:
                print("Network/API Error")
                
        except Exception as e:
            # Timeout or other reset
            continue

if __name__ == "__main__":
    start_listening()
