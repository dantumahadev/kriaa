"""
KRIA OS — Emergency Monitor (PS #26: Remote Patient Monitoring Agent)
─────────────────────────────────────────────────────────────────────
Real-time pipeline:
  1. Triple-Tap  → JotForm Voice Agent launches + recording begins
  2. Every 10 s  → audio chunk transcribed
  3. If keyword detected in chunk:
       → full accumulated transcript sent to Groq (Llama 3, free tier)
       → Groq returns severity + cause summary
       → if severity is CRITICAL or LIFE_THREATENING:
           → SOS call made to emergency contact (ADB dialer)
           → WhatsApp alert with Groq summary sent
           → no further alerts for this session (one SOS max)
  4. Double-Tap  → pure ABORT (no analysis, no alerts)

Free API: https://console.groq.com  (no credit card, 14 400 req/day)
Set env:  GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx
"""

import subprocess
import threading
import time
import os
import json
import wave
import tempfile
import datetime
import re
import urllib.request
import urllib.parse

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
EMERGENCY_CONTACT_PHONE = "7993048928"      # emergency contact
SESSION_RECORD_DIR      = os.path.join(os.path.dirname(__file__), "session_logs")
PHONE_RECORDING_PATH   = "/sdcard/kria_session.mp4"   # path on the Android device
RECORDING_CHUNK_SECONDS = 10               # transcribe every N seconds
MAX_SESSION_MINUTES     = 15              # hard cap on session length

# Groq free API — sign up at https://console.groq.com → API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL   = "llama-3.1-8b-instant"               # fastest free model

# Severities that trigger SOS — must match exactly what the prompt asks for
SOS_SEVERITIES = {"critical", "life_threatening"}

os.makedirs(SESSION_RECORD_DIR, exist_ok=True)

# ─── KEYWORD TRIGGERS (local, instant, no API) ─────────────────────────────────
# These gate the Groq call — only spend an API call when something sounds wrong
TRIGGER_KEYWORDS = [
    # Breathing / cardiac
    "can't breathe", "cannot breathe", "not breathing", "chest pain",
    "heart attack", "cardiac", "palpitation",
    # Neurological
    "stroke", "seizure", "unconscious", "unresponsive", "fainted",
    # Trauma
    "bleeding", "blood", "fallen", "fell down", "head injury", "broken",
    # Severe distress
    "help me", "ambulance", "dying", "severe pain", "vomiting blood",
    "choking", "allergic", "can't move", "cannot move",
    "oxygen", "call doctor",
]

def _has_trigger_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in TRIGGER_KEYWORDS)


# ─── ADB HELPER ────────────────────────────────────────────────────────────────
def _run_adb(command) -> str:
    try:
        cmd = ["adb"] + (command.split() if isinstance(command, str) else command)
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="ignore")
        return result.stdout.strip()
    except Exception as e:
        print(f"[EM] ADB error: {e}")
        return ""


# ─── PHONE RECORDING (screenrecord) ────────────────────────────────────────────
_screenrecord_proc = None   # global handle to the adb screenrecord subprocess

def _start_phone_recording():
    """Starts adb shell screenrecord on the phone in a background subprocess."""
    global _screenrecord_proc
    try:
        # Delete any leftover file from previous session
        _run_adb(f"shell rm -f {PHONE_RECORDING_PATH}")
        _screenrecord_proc = subprocess.Popen(
            ["adb", "shell", "screenrecord",
             "--time-limit", str(MAX_SESSION_MINUTES * 60),
             PHONE_RECORDING_PATH],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[EM] Phone recording started -> {PHONE_RECORDING_PATH}")
    except Exception as e:
        print(f"[EM] Phone recording start error: {e}")
        _screenrecord_proc = None

def _stop_phone_recording():
    """
    Gracefully stops screenrecord with SIGINT so it finalises the MP4,
    then waits up to 5 s for it to finish writing.
    """
    global _screenrecord_proc
    if _screenrecord_proc is None:
        return
    try:
        # SIGINT (Ctrl+C) makes screenrecord close the file properly
        _run_adb("shell pkill -SIGINT screenrecord")
        try:
            _screenrecord_proc.wait(timeout=5)
        except Exception:
            _screenrecord_proc.kill()
        print("[EM] Phone recording stopped.")
    except Exception as e:
        print(f"[EM] Stop recording error: {e}")
    finally:
        _screenrecord_proc = None

def _send_recording_whatsapp(phone: str):
    """
    Shares the phone recording file to WhatsApp.
    Opens the Android share-sheet with the MP4 pre-selected;
    WhatsApp will be one of the options.
    """
    try:
        # Let Android index the new file so apps can see it
        _run_adb([
            "shell", "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{PHONE_RECORDING_PATH}"
        ])
        time.sleep(1)

        clean = re.sub(r'\D', '', phone)
        if not clean.startswith("91") and len(clean) == 10:
            clean = "91" + clean

        # Open WhatsApp directly to the emergency contact, ready to attach
        _run_adb([
            "shell", "am", "start",
            "-a", "android.intent.action.SEND",
            "-t", "video/mp4",
            "--eu", "android.intent.extra.STREAM",
                    f"file://{PHONE_RECORDING_PATH}",
            "--es", "android.intent.extra.TEXT",
                    "KRIA OS emergency session recording",
            "-p", "com.whatsapp"
        ])
        print(f"[EM] Recording share sheet opened in WhatsApp.")
    except Exception as e:
        print(f"[EM] Recording share error: {e}")


# ─── GROQ ANALYSIS ─────────────────────────────────────────────────────────────
_GROQ_PROMPT = """\
You are a medical emergency triage AI built into KRIA OS, an accessibility \
platform for patients with paralysis, ALS, and blindness.

A patient just spoke with an AI medical assistant. Analyse their conversation \
and determine whether it is a life-threatening emergency.

CONVERSATION TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Respond ONLY with a single JSON object — no markdown, no extra text:
{{
  "severity": "critical | life_threatening | moderate | low",
  "is_sos": true or false,
  "cause": "one sentence describing the medical concern",
  "summary": "2-3 sentences explaining the patient's condition and what happened",
  "recommended_action": "what the emergency contact should do RIGHT NOW"
}}

Rules:
- Use "critical" or "life_threatening" ONLY if there is immediate danger to life.
- Use "moderate" if the patient needs medical attention but is not in immediate danger.
- Use "low" if there is no clear emergency.
- Set "is_sos" to true ONLY for critical or life_threatening.
"""

def call_groq(transcript: str) -> dict | None:
    """
    Sends the transcript to Groq (Llama 3, free tier) and returns parsed JSON.
    Returns None if the call fails or key is missing.
    """
    if not GROQ_API_KEY:
        print("[EM] No GROQ_API_KEY set — skipping Groq analysis.")
        return None

    try:
        print("[EM] 🤖 Sending transcript to Groq...")
        payload = json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise medical triage AI. Respond ONLY with valid JSON."
                },
                {
                    "role": "user",
                    "content": _GROQ_PROMPT.format(transcript=transcript[:4000])
                }
            ],
            "temperature": 0.1,
            "max_tokens":  400,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data  = json.loads(resp.read().decode("utf-8"))
            raw   = data["choices"][0]["message"]["content"]
            match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                print(f"[EM] ✅ Groq response: severity={result.get('severity')} "
                      f"is_sos={result.get('is_sos')}")
                return result

    except Exception as e:
        print(f"[EM] Groq error: {e}")

    return None


# ─── SOS ALERT CHAIN ───────────────────────────────────────────────────────────
def _make_call(phone: str):
    print(f"[EM] 🚨 CALLING {phone}")
    _run_adb(f"shell am start -a android.intent.action.CALL -d tel:{phone}")


def _send_whatsapp(phone: str, groq_result: dict, audio_path: str):
    ts    = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    sev   = groq_result.get("severity", "critical").upper()
    cause = groq_result.get("cause",    "Unknown cause")
    summ  = groq_result.get("summary",  "")
    act   = groq_result.get("recommended_action", "Attend to patient immediately.")

    message = (
        f"🚨 *KRIA OS — SOS EMERGENCY ALERT* 🚨\n\n"
        f"🔴 *Severity* : {sev}\n"
        f"🕐 *Time*     : {ts}\n\n"
        f"⚠️ *Cause*    : {cause}\n\n"
        f"📋 *Summary* :\n{summ}\n\n"
        f"⚡ *Action*  :\n{act}\n\n"
        f"📁 *Recording* : {os.path.basename(audio_path)}\n"
        f"_Auto-generated by KRIA OS Emergency Monitor_"
    )

    clean = re.sub(r'\D', '', phone)
    if not clean.startswith("91") and len(clean) == 10:
        clean = "91" + clean

    wa_url = f"https://wa.me/{clean}?text={urllib.parse.quote(message)}"
    _run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", wa_url])
    print(f"[EM] 📲 WhatsApp SOS sent to {phone}")


def fire_sos(groq_result: dict, audio_path: str):
    """Runs the full SOS chain: stop recording → call → WhatsApp text → share recording."""
    print("\n[EM] ================================================")
    print(f"[EM]  SOS TRIGGERED -- {groq_result.get('severity','').upper()}")
    print(f"[EM]  Cause : {groq_result.get('cause','')}")
    print("[EM] ================================================\n")

    # 1. Stop phone recording so file is saved cleanly
    _stop_phone_recording()
    time.sleep(2)

    # 2. Call emergency contact
    _make_call(EMERGENCY_CONTACT_PHONE)
    time.sleep(4)

    # 3. Send WhatsApp text summary
    _send_whatsapp(EMERGENCY_CONTACT_PHONE, groq_result, audio_path)
    time.sleep(3)

    # 4. Share the phone recording file via WhatsApp
    _send_recording_whatsapp(EMERGENCY_CONTACT_PHONE)


# ─── CALL RECORDER ─────────────────────────────────────────────────────────────
class CallRecorder:
    """
    Records mic audio in chunks and transcribes each chunk.
    On keyword detection → calls Groq → fires SOS if critical.
    Fires SOS at most once per session.
    """

    def __init__(self):
        self.is_recording     = False
        self.transcript_chunks: list[str] = []
        self.full_audio_path  = ""
        self.sos_sent         = False           # guard: only one SOS per session
        self._stop_event      = threading.Event()
        self._thread          = None

    # ── Public ────────────────────────────────────────────────────────────────
    def start(self, session_id: str):
        self.is_recording     = True
        self.sos_sent         = False
        self.transcript_chunks = []
        self._stop_event.clear()

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.full_audio_path  = os.path.join(SESSION_RECORD_DIR, f"session_{ts}.wav")

        self._thread = threading.Thread(target=self._record_loop,
                                        args=(session_id,), daemon=True)
        self._thread.start()
        print(f"[EM] 🎙️  Recording → {self.full_audio_path}")

    def stop(self) -> str:
        if not self.is_recording:
            return ""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=15)
        self.is_recording = False
        transcript = " ".join(self.transcript_chunks).strip()
        print(f"[EM] 🛑  Stopped. Transcript: {len(transcript)} chars")
        return transcript

    # ── Internal ──────────────────────────────────────────────────────────────
    def _record_loop(self, session_id: str):
        try:
            import speech_recognition as sr
            import pyaudio
        except ImportError as e:
            print(f"[EM] ❌ Missing package: {e}"); return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold        = 300
        recognizer.dynamic_energy_threshold = True

        RATE, CHUNK  = 16000, 1024
        FORMAT, CHANNELS = pyaudio.paInt16, 1

        pa     = pyaudio.PyAudio()
        stream = pa.open(format=FORMAT, channels=CHANNELS,
                         rate=RATE, input=True, frames_per_buffer=CHUNK)

        print("[EM] 🔴 Live recording active...")
        all_frames, chunk_frames = [], []
        chunk_start = time.time()
        max_end     = time.time() + (MAX_SESSION_MINUTES * 60)

        while not self._stop_event.is_set() and time.time() < max_end:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                all_frames.append(data)
                chunk_frames.append(data)

                if time.time() - chunk_start >= RECORDING_CHUNK_SECONDS:
                    self._process_chunk(chunk_frames, recognizer, RATE, pa, FORMAT)
                    chunk_frames = []
                    chunk_start  = time.time()
            except Exception:
                break

        if chunk_frames:
            self._process_chunk(chunk_frames, recognizer, RATE, pa, FORMAT)

        stream.stop_stream()
        stream.close()
        pa.terminate()
        self._save_wav(all_frames, RATE, pa, FORMAT)

    def _process_chunk(self, frames, recognizer, rate, pa, fmt):
        """Transcribes one audio chunk, then checks for keywords → Groq → SOS."""
        text = self._transcribe(frames, recognizer, rate, pa, fmt)
        if not text:
            return

        self.transcript_chunks.append(text)
        print(f"[EM] 📝 {text[:90]}")

        # ── Already sent SOS this session — don't repeat ──
        if self.sos_sent:
            return

        # ── Fast local gate: only spend Groq call if keywords present ──
        if not _has_trigger_keyword(text):
            return

        print(f"[EM] ⚠️  Keyword detected — escalating to Groq...")
        full_transcript = " ".join(self.transcript_chunks)

        # Run Groq call in a side-thread so it doesn't block recording
        threading.Thread(
            target=self._groq_and_sos,
            args=(full_transcript,),
            daemon=True
        ).start()

    def _groq_and_sos(self, transcript: str):
        """Groq call + conditional SOS. Runs in its own thread."""
        result = call_groq(transcript)

        if result is None:
            # Groq unavailable — no SOS (don't false-positive on keywords alone)
            print("[EM] Groq unavailable. No SOS triggered.")
            return

        severity  = result.get("severity", "low").strip().lower().replace(" ", "_")
        is_sos    = result.get("is_sos", False)

        # Save what Groq said regardless
        self._save_groq_log(result, transcript)

        if is_sos or severity in SOS_SEVERITIES:
            if not self.sos_sent:          # double-check the flag (thread safety)
                self.sos_sent = True
                fire_sos(result, self.full_audio_path)
        else:
            print(f"[EM] Groq rated severity={severity} — no SOS needed. Monitoring continues.")

    def _transcribe(self, frames, recognizer, rate, pa, fmt) -> str:
        try:
            import speech_recognition as sr
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            self._write_wav(frames, rate, pa, fmt, tmp.name)
            tmp.close()
            with sr.AudioFile(tmp.name) as src:
                audio = recognizer.record(src)
            text = recognizer.recognize_google(audio)
            os.unlink(tmp.name)
            return text.strip()
        except Exception:
            return ""

    def _save_wav(self, frames, rate, pa, fmt):
        try:
            self._write_wav(frames, rate, pa, fmt, self.full_audio_path)
            print(f"[EM] 💾 Saved: {self.full_audio_path}")
        except Exception as e:
            print(f"[EM] Save error: {e}")

    def _write_wav(self, frames, rate, pa, fmt, path):
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(pa.get_sample_size(fmt))
            wf.setframerate(rate)
            wf.writeframes(b"".join(frames))

    def _save_groq_log(self, result: dict, transcript: str):
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SESSION_RECORD_DIR, f"groq_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"groq_result": result, "transcript": transcript}, f, indent=2)
        print(f"[EM] 📄 Groq log → {path}")


# ─── SESSION MANAGER ───────────────────────────────────────────────────────────
class EmergencySessionManager:
    """
    Used by phone_mirror_automation.py:
        emergency_session.start_session()   ← on 3-tap
        emergency_session.end_session()     ← on 2-tap (clean stop, no analysis)
    """

    def __init__(self):
        self.recorder   = CallRecorder()
        self.session_id = ""
        self.active     = False

    def start_session(self):
        if self.active:
            print("[EM] Session already active."); return
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.active     = True
        # Start laptop mic (for keyword detection)
        self.recorder.start(self.session_id)
        # Start phone screen recording (for WhatsApp file share on SOS)
        threading.Thread(target=_start_phone_recording, daemon=True).start()
        print(f"[EM] Session started. Emergency contact: {EMERGENCY_CONTACT_PHONE}")

    def end_session(self):
        """Stops everything. SOS + recording share already handled mid-session if triggered."""
        if not self.active:
            return
        self.recorder.stop()
        _stop_phone_recording()   # no-op if SOS already stopped it
        self.active = False
        print("[EM] Session ended.")


# ─── SINGLETON ─────────────────────────────────────────────────────────────────
emergency_session = EmergencySessionManager()


# ─── STANDALONE TEST ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== KRIA OS Emergency Monitor — Test Mode ===")
    print("Recording 20 seconds. Say something medical near the mic.\n")
    emergency_session.start_session()
    time.sleep(20)
    emergency_session.end_session()
