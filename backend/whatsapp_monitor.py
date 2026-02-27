"""
KRIA OS - WhatsApp Caregiver Monitor
=============================================================================
Activated by 5-tap gesture.

What it does:
  • Polls phone notifications every 5 seconds (via ADB dumpsys)
  • When a WhatsApp message matches a caregiver pattern
    ("did you eat?", "medicine?", "how are you?" etc.)
    → Reads the message aloud through the speaker (pyttsx3)
    → Listens for patient voice response via laptop mic
    → If patient says an affirmative/negative word
      → Opens WhatsApp, navigates to the chat, types & sends the reply

No manual typing needed — patient just speaks.
"""

import subprocess
import threading
import time
import re
import os
import datetime

# --- SESSION HELPERS ---
def _get_latest_emergency_contact() -> str:
    try:
        # User requested to hardcode 'Varuni' as the primary caregiver
        return "Varuni"
    except Exception:
        return "Varuni"

# --- ADB HELPER ---
_ADB_SERIAL = None

def _detect_device():
    global _ADB_SERIAL
    if _ADB_SERIAL: return _ADB_SERIAL
    try:
        import subprocess
        res = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = res.stdout.strip().split('\n')[1:]
        active = [l.split('\t')[0] for l in lines if '\tdevice' in l]
        if active:
            _ADB_SERIAL = active[0]
            print(f"[WhatsApp] Using device: {_ADB_SERIAL}")
            return _ADB_SERIAL
    except Exception: pass
    return None

def _adb(cmd) -> str:
    serial = _detect_device()
    try:
        base = ["adb"]
        if serial: base += ["-s", serial]
        args = base + (cmd.split() if isinstance(cmd, str) else cmd)
        r = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", timeout=12)
        return r.stdout.strip()
    except Exception as e:
        print(f"[WhatsApp] ADB error: {e}")
        return ""

# --- TTS ---
_tts_lock = threading.Lock()

def _speak(text: str):
    """Speaks through laptop speaker (audible in patient's room)."""
    print(f"[WhatsApp] (TTS): {text}")
    try:
        import pyttsx3
        with _tts_lock:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.say(text)
            engine.runAndWait()
    except Exception as e:
        print(f"[WhatsApp] TTS error: {e}")

# --- CARE PATTERNS ---
# Each entry: (regex pattern, spoken prompt, auto_reply_yes, auto_reply_no)
CARE_PATTERNS = [
    (
        r"did.{0,10}eat|have.{0,10}eaten|had.{0,10}(food|meal|lunch|dinner|breakfast)",
        "Message from your caregiver: Did you eat?",
        "Yes, I have eaten.",
        "No, I have not eaten yet.",
    ),
    (
        r"(take|taken|have.{0,10}taken).{0,20}(medicine|tablet|pill|medication|dose)|"
        r"(medicine|tablet|pill|medication|dose).{0,20}(taken|done|finished)",
        "Message from your caregiver: Did you take the medicine?",
        "Yes, I have taken the medicine.",
        "No, I have not taken the medicine yet.",
    ),
    (
        r"drink.{0,10}water|had.{0,10}water|water.{0,10}intake",
        "Message from your caregiver: Did you drink water?",
        "Yes, I drank water.",
        "No, I have not had water yet.",
    ),
    (
        r"how are you|are you okay|you alright|feeling (okay|fine|well)|you fine",
        "Your caregiver is asking: How are you?",
        "I am doing fine, thank you.",
        "I am not feeling well. Please check on me.",
    ),
    (
        r"(did.{0,10})?(sleep|slept|rest|rested|nap)|good (night|sleep)",
        "Message from your caregiver: Did you sleep well?",
        "Yes, I slept well.",
        "No, I could not sleep well.",
    ),
    (
        r"emergency|need help|are you safe|okay there",
        "Your caregiver is asking if you need help.",
        "I am fine. No emergency.",
        "Yes, I need help. Please come.",
    ),
]

def _match_pattern(message_text: str):
    """Returns (spoken_prompt, yes_reply, no_reply) or None."""
    t = message_text.lower()
    for pattern, prompt, yes_reply, no_reply in CARE_PATTERNS:
        if re.search(pattern, t, re.IGNORECASE):
            return prompt, yes_reply, no_reply
    return None

# --- NOTIFICATION READER ---
def _get_whatsapp_notifications() -> list[dict]:
    """
    Expands the notification shade, dumps the visible UI, and scans ALL
    node text for care pattern keywords. No fragile label-offset logic.
    """
    notifications = []
    dump_path  = "/sdcard/notif_ui.xml"
    local_path = "notif_ui.xml"

    try:
        _adb("shell cmd statusbar expand-notifications")
        time.sleep(1.5)

        _adb(f"shell uiautomator dump {dump_path}")
        _adb(["pull", dump_path, local_path])

        if not os.path.exists(local_path):
            print("[WhatsApp] UI dump not found.")
            return []

        import xml.etree.ElementTree as ET
        tree = ET.parse(local_path)
        root = tree.getroot()

        # Collect every piece of visible text from the shade
        for node in root.iter("node"):
            raw = (node.get("text", "") or node.get("content-desc", "")).strip()
            if not raw or len(raw) < 5:
                continue

            # Directly check if this text matches a care pattern
            match = _match_pattern(raw)
            if match:
                print(f"[WhatsApp] Matched in shade: '{raw}'")
                notifications.append({"sender": "Caregiver", "text": raw})
                break   # one match per poll cycle is enough

    except Exception as e:
        print(f"[WhatsApp] Notification read error: {e}")
    finally:
        _adb("shell cmd statusbar collapse")
        if os.path.exists(local_path):
            os.remove(local_path)

    return notifications


# --- VOICE LISTENER ---
AFFIRMATIVES = {"yes", "yeah", "yep", "yup", "sure", "okay", "ok",
                "done", "fine", "eaten", "taken", "had", "did", "have"}
NEGATIVES    = {"no", "nope", "not", "haven't", "didn't", "cant",
                "cannot", "won't", "nah"}

def _listen_for_response(timeout_sec: int = 8) -> str | None:
    """
    Listens via laptop mic for 'yes'/'no' type response.
    Returns 'yes', 'no', or None (timeout/silence).
    """
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.energy_threshold         = 250
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print(f"[WhatsApp] Listening for patient response ({timeout_sec}s)...")
            audio = recognizer.listen(source, timeout=timeout_sec, phrase_time_limit=5)

        text = recognizer.recognize_google(audio).lower()
        print(f"[WhatsApp] Patient said: '{text}'")

        words = set(text.split())

        if words & AFFIRMATIVES:
            return "yes"
        if words & NEGATIVES:
            return "no"

        # Fallback: first word decides
        first = text.split()[0] if text.split() else ""
        if first in AFFIRMATIVES:
            return "yes"
        if first in NEGATIVES:
            return "no"

        return "yes"  # default if something was said but unclear → positive

    except Exception as e:
        print(f"[WhatsApp] Listener timeout or error: {e}")
        return None

# --- WHATSAPP REPLY SENDER ---
def _send_whatsapp_reply(reply_text: str, contact: str = "Varuni"):
    """
    Surgical WhatsApp automation:
    1. Force Restart WhatsApp
    2. Tap Search -> Type Name
    3. Select Chat Result
    4. Focus Message Box -> Send Reply
    """
    print(f"\n[WhatsApp] [Surgical Send] Target: {contact}")
    
    # 1. CLEAN START
    _adb("shell am force-stop com.whatsapp")
    time.sleep(1.5)
    _adb("shell monkey -p com.whatsapp -c android.intent.category.LAUNCHER 1")
    print("[WhatsApp] Opening WhatsApp...")
    time.sleep(6) # Give it time to load the main list

    dump_path  = "/sdcard/wa_dump.xml"
    local_path = "wa_dump.xml"

    # 2. FIND SEARCH BAR & TYPE NAME
    _adb(f"shell uiautomator dump {dump_path}")
    _adb(["pull", dump_path, local_path])
    
    found_search = False
    if os.path.exists(local_path):
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(local_path).getroot()
            for node in root.iter("node"):
                text = (node.get("text") or "").lower()
                desc = (node.get("content-desc") or "").lower()
                hint = (node.get("hint") or "").lower()
                
                # Target the big search bar at top
                if "search" in text or "search" in desc or "search" in hint or "meta ai" in text:
                    bounds = node.get("bounds", "")
                    nums = re.findall(r"\d+", bounds)
                    if len(nums) == 4:
                        x, y = (int(nums[0])+int(nums[2]))//2, (int(nums[1])+int(nums[3]))//2
                        _adb(f"shell input tap {x} {y}")
                        print(f"[WhatsApp] [UI] Tapped Search Bar at ({x}, {y})")
                        found_search = True
                        break
        except Exception: pass
        finally: 
            if os.path.exists(local_path): os.remove(local_path)

    if not found_search:
        _adb("shell input tap 500 150") # generic top search bar pos
    
    time.sleep(2)
    _adb(f"shell input text {contact}")
    print(f"[WhatsApp] Searching for: {contact}")
    time.sleep(4) # Wait for results list to appear

    # 3. SELECT THE CHAT RESULT (The one below the search bar)
    _adb(f"shell uiautomator dump {dump_path}")
    _adb(["pull", dump_path, local_path])
    
    selected = False
    if os.path.exists(local_path):
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(local_path).getroot()
            for node in root.iter("node"):
                text = node.get("text", "")
                clickable = node.get("clickable", "")
                
                # Find a node containing the contact name that is NOT the search bar
                if contact.lower() in text.lower() and clickable == "true":
                    bounds = node.get("bounds", "")
                    nums = re.findall(r"\d+", bounds)
                    if len(nums) == 4:
                        y = (int(nums[1]) + int(nums[3])) // 2
                        if y > 350: # Ensure it's in the results list, not the search bar text
                            x = (int(nums[0]) + int(nums[2])) // 2
                            _adb(f"shell input tap {x} {y}")
                            print(f"[WhatsApp] Selected chat result at ({x}, {y})")
                            selected = True
                            break
        except Exception: pass
        finally: 
            if os.path.exists(local_path): os.remove(local_path)

    if not selected:
        print("[WhatsApp] Result list not scanned, using best-guess tap...")
        _adb("shell input tap 500 450") # Usually where the first result is

    time.sleep(4) # Wait for chat UI to load

    # 4. FIND MESSAGE BOX & SEND THE REPLY
    _adb(f"shell uiautomator dump {dump_path}")
    _adb(["pull", dump_path, local_path])
    
    typed = False
    if os.path.exists(local_path):
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(local_path).getroot()
            for node in root.iter("node"):
                cls  = node.get("class", "")
                text = (node.get("text") or "").lower()
                hint = (node.get("hint") or "").lower()
                
                # Chat message box is usually bottom-most EditText with 'message' text/hint
                if "EditText" in cls and ("message" in text or "message" in hint or not text):
                    bounds = node.get("bounds", "")
                    nums = re.findall(r"\d+", bounds)
                    if len(nums) == 4:
                        y = (int(nums[1]) + int(nums[3])) // 2
                        if y > 1500: # Ensure it's the bottom message box
                            x = (int(nums[0]) + int(nums[2])) // 2
                            _adb(f"shell input tap {x} {y}")
                            time.sleep(0.5)
                            _adb(f"shell input text {reply_text.replace(' ', '%s')}")
                            time.sleep(1)
                            
                            # 5. CLICK THE SEND BUTTON (Green Rocket)
                            # After typing, the Send button usually replaces the Mic icon
                            _adb(f"shell uiautomator dump {dump_path}")
                            _adb(["pull", dump_path, local_path])
                            
                            sent = False
                            if os.path.exists(local_path):
                                try:
                                    inner_root = ET.parse(local_path).getroot()
                                    for s_node in inner_root.iter("node"):
                                        s_desc = (s_node.get("content-desc") or "").lower()
                                        s_resid = (s_node.get("resource-id") or "").lower()
                                        
                                        if "send" in s_desc or "send" in s_resid:
                                            s_bounds = s_node.get("bounds", "")
                                            s_nums = re.findall(r"\d+", s_bounds)
                                            if len(s_nums) == 4:
                                                sx, sy = (int(s_nums[0])+int(s_nums[2]))//2, (int(s_nums[1])+int(s_nums[3]))//2
                                                _adb(f"shell input tap {sx} {sy}")
                                                print(f"[WhatsApp] Tapped SEND button at ({sx}, {sy})")
                                                sent = True
                                                break
                                except Exception: pass

                            if not sent:
                                # Standard fallback for Send button (bottom right)
                                print("[WhatsApp] Send button not found in UI, using fallback tap...")
                                _adb("shell input tap 980 2200") 
                            
                            print(f"[WhatsApp] SUCCESS: Reply sent to {contact}")
                            typed = True
                            break
        except Exception: pass
        finally: 
            os.remove(local_path) if os.path.exists(local_path) else None

    if not typed:
        print("[WhatsApp] Final fallback send sequence...")
        _adb("shell input tap 540 2200") # Tap msg box
        _adb(f"shell input text {reply_text.replace(' ', '%s')}")
        time.sleep(0.5)
        _adb("shell input tap 980 2200") # Tap send

# --- MONITOR LOOP ---
class WhatsAppMonitor:
    """
    Background monitor that reads WhatsApp notifications, speaks them aloud,
    listens for patient voice response, and auto-replies.
    """

    def __init__(self):
        self.active         = False
        self._stop_event    = threading.Event()
        self._thread        = None
        self._seen_messages = set()   # avoid processing same message twice

    def start(self):
        if self.active:
            print("[WhatsApp] Already running.")
            return
        self.active = True
        self._stop_event.clear()
        self._seen_messages.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        _speak("WhatsApp monitor is now active. I will read your messages and reply for you.")
        print("[WhatsApp] Monitor started.")

    def stop(self):
        self._stop_event.set()
        self.active = False
        print("[WhatsApp] Monitor stopped.")

    def _monitor_loop(self):
        POLL_INTERVAL = 5  # seconds between notification checks
        print("[WhatsApp] Polling notifications every 5s...")

        while not self._stop_event.is_set():
            try:
                notifications = _get_whatsapp_notifications()
                for notif in notifications:
                    msg_key = f"{notif['sender']}::{notif['text']}"

                    if msg_key in self._seen_messages:
                        continue  # already handled

                    match = _match_pattern(notif["text"])
                    if match is None:
                        # Not a care-check pattern — mark seen and skip
                        self._seen_messages.add(msg_key)
                        continue

                    prompt, yes_reply, no_reply = match
                    self._seen_messages.add(msg_key)

                    print(f"\n[WhatsApp] Message from {notif['sender']}: {notif['text']}")

                    # Speak the question aloud
                    _speak(prompt)
                    time.sleep(0.5)
                    _speak("Please say yes or no.")

                    # Listen for response
                    response = _listen_for_response(timeout_sec=8)

                    if response == "yes":
                        reply = yes_reply
                        _speak("Okay, I will reply yes.")
                    elif response == "no":
                        reply = no_reply
                        _speak("Okay, I will reply no.")
                    else:
                        # No voice detected — send a default "checking in" reply
                        reply = "I received your message. The patient is present but could not respond verbally right now."
                        _speak("No response heard. Sending a default reply.")

                    # Force target to 'Varuni' as per user request
                    contact = "Varuni"

                    # Send the reply through WhatsApp
                    _send_whatsapp_reply(reply, contact=contact)
                    _speak(f"Message sent.")

            except Exception as e:
                print(f"[WhatsApp] Monitor error: {e}")

            time.sleep(POLL_INTERVAL)


# --- SINGLETON ---
whatsapp_monitor = WhatsAppMonitor()


# --- STANDALONE TEST ---
if __name__ == "__main__":
    print("=== KRIA OS WhatsApp Monitor - Test Mode ===")
    print("Running for 60 seconds. Send a WhatsApp message like 'did you eat?' to the phone.\n")
    whatsapp_monitor.start()
    time.sleep(60)
    whatsapp_monitor.stop()
