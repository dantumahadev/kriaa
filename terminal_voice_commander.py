import speech_recognition as sr
import pyttsx3
import subprocess
import time
import sys

# --- CONFIGURATION ---
Keyword = "jarvis" # Optional wake word logic if needed, but we'll do continuous for now
Listening = True

# --- ADB & APP UTILITIES ---
APPS_MAP = {
    "whatsapp": "com.whatsapp",
    "youtube": "com.google.android.youtube",
    "spotify": "com.spotify.music",
    "instagram": "com.instagram.android",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "settings": "com.android.settings",
    "camera": "com.android.camera",
    "uber": "com.ubercab",
    "ola": "com.olacabs.customer",
    "rapido": "com.rapido.passenger",
    "zomato": "com.application.zomato",
    "swiggy": "in.swiggy.android",
    "phone": "com.google.android.dialer",
    "play store": "com.android.vending"
}

def speak(text):
    """Text to Speech Feedback"""
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"TTS Error: {e}")

def run_adb_command(command):
    """Run an ADB command and return output."""
    try:
        if isinstance(command, str):
            cmd_list = ["adb"] + command.split()
        else:
            cmd_list = ["adb"] + command
            
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"ADB Error: {e}")
        return None

def execute_command(text):
    text = text.lower()
    
    # 1. APP LAUNCHING
    if "open" in text or "launch" in text:
        for app_name, pkg in APPS_MAP.items():
            if app_name in text:
                print(f"🚀 Launching {app_name}...")
                speak(f"Opening {app_name}")
                run_adb_command(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
                return

    # 2. SYSTEM CONTROLS
    if "home" in text:
        print("🏠 Going Home")
        run_adb_command("shell input keyevent 3")
        return
    if "back" in text:
        print("🔙 Going Back")
        run_adb_command("shell input keyevent 4")
        return
    if "volume up" in text or "louder" in text:
        print("🔊 Volume Up")
        run_adb_command("shell input keyevent 24")
        return
    if "volume down" in text or "softer" in text:
        print("🔉 Volume Down")
        run_adb_command("shell input keyevent 25")
        return
    
    # 3. SCROLLING
    if "scroll down" in text:
        print("⬇️ Scrolling Down")
        run_adb_command("shell input swipe 500 1500 500 500 300")
        return
    if "scroll up" in text:
        print("⬆️ Scrolling Up")
        run_adb_command("shell input swipe 500 500 500 1500 300")
        return

    # 4. TYPING
    if "type" in text:
        content = text.split("type", 1)[1].strip()
        if content:
            print(f"⌨️ Typing: {content}")
            formatted = content.replace(" ", "%s")
            run_adb_command(f"shell input text {formatted}")
            return

    print(f"🤔 Command not recognized: {text}")

def listen_loop():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    print("--- 🎤 TERMINAL VOICE COMMANDER ACTIVATED ---")
    print("Speak commands like: 'Open YouTube', 'Scroll Down', 'Gp Home'")
    print("Press Ctrl+C to Exit")
    
    speak("System Online. Listening for commands.")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        
        while True:
            try:
                print("\nListening...", end="\r")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                print("Processing...", end="\r")
                
                text = recognizer.recognize_google(audio)
                print(f"🗣️ You said: '{text}'")
                
                execute_command(text)
                
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass # Ignored unintelligible speech
            except sr.RequestError as e:
                print(f"Network Error: {e}")
            except KeyboardInterrupt:
                print("\nStopping...")
                break

if __name__ == "__main__":
    try:
        listen_loop()
    except KeyboardInterrupt:
        pass
