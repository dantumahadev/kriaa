from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import time
import os
import json
import base64
import urllib.request
from pydantic import BaseModel

class GeneralActionRequest(BaseModel):
    command: str
    parameters: dict = {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_adb_command(command):
    """Run an ADB command and return output."""
    print(f"[ADB] Executing: {command}")
    try:
        # Check if we need to target specific device
        # For now, we trust ADB's default behavior unless we want to force -s <IP>
        # but adding -d or -e might help if mixed.
        # Let's just run it as is but Log it.
        
        # Default to the first connected device
        if isinstance(command, str):
            cmd_list = ["adb"] + command.split()
        else:
            cmd_list = ["adb"] + command
            
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=False, # Don't raise on error
            encoding='utf-8',
            errors='ignore'
        )
        if result.returncode != 0:
            print(f"[ADB] Failed: {result.stderr}")
        return result.stdout.strip()
    except Exception as e:
        print(f"ADB Error: {e}")
        return None

@app.get("/")
def read_root():
    return {"status": "KriaOS Backend Online"}

# --- JARVIS KNOWLEDGE BASE ---
APPS_MAP = {
    "whatsapp": "com.whatsapp",
    "youtube": "com.google.android.youtube",
    "spotify": "com.spotify.music",
    "instagram": "com.instagram.android",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "settings": "com.android.settings",
    "camera": "com.android.camera", # Generic, might vary
    "uber": "com.ubercab",
    "ola": "com.olacabs.customer",
    "rapido": "com.rapido.passenger",
    "zomato": "com.application.zomato",
    "swiggy": "in.swiggy.android",
    "phone": "com.google.android.dialer",
    "play store": "com.android.vending"
}

@app.post("/action/general")
def general_action(request: GeneralActionRequest):
    """
    The Brain of Jarvis. Routes generic commands to specific ADB actions.
    Supported Intents: 'open', 'scroll', 'click', 'type', 'system'
    """
    command = request.command
    parameters = request.parameters
    intent = command.lower()
    
    # --- 1. APP LAUNCHING ---
    if intent == "open_app":
        app_name = parameters.get("app_name", "").lower().strip()
        pkg = APPS_MAP.get(app_name)
        
        # Fuzzy / Direct match fallback
        if not pkg:
            # Try to find a package that simply contains the name
            # simple helper: just assume they might mean a package containing the string
            # This is risky but "Jarvis" tries its best.
            pass

        if pkg:
            run_adb_command(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
            return {"status": "success", "message": f"Opening {app_name}"}
        else:
            # Fallback: Search in Play Store if we don't know it
            run_adb_command(f"shell am start -a android.intent.action.VIEW -d market://search?q={app_name}")
            return {"status": "search", "message": f"Searching Play Store for {app_name}"}

    # --- 2. SYSTEM CONTROLS ---
    if intent == "system":
        action = parameters.get("action", "")
        if action == "home":
            run_adb_command("shell input keyevent 3")
        elif action == "back":
            run_adb_command("shell input keyevent 4")
        elif action == "recent":
            run_adb_command("shell input keyevent 187")
        elif action == "volume_up":
            run_adb_command("shell input keyevent 24")
        elif action == "volume_down":
            run_adb_command("shell input keyevent 25")
        elif action == "lock":
            run_adb_command("shell input keyevent 26")
        elif action == "screenshot":
            run_adb_command("shell input keyevent 120") # SysRq, might vary
        
        return {"status": "success", "message": f"System action: {action}"}

    # --- 3. SCROLLING / NAVIGATION ---
    if intent == "scroll":
        direction = parameters.get("direction", "down")
        if direction == "down":
            # Swipe UP to scroll DOWN
            run_adb_command("shell input swipe 500 1500 500 500 300")
        elif direction == "up":
            # Swipe DOWN to scroll UP
            run_adb_command("shell input swipe 500 500 500 1500 300")
        
        return {"status": "success", "message": f"Scrolling {direction}"}

    # --- 4. TEXT INPUT ---
    if intent == "type":
        text = parameters.get("text", "")
        # Replace spaces with %s for ADB
        formatted_text = text.replace(" ", "%s")
        run_adb_command(f"shell input text {formatted_text}")
        return {"status": "success", "message": f"Typing: {text}"}

    return {"status": "unknown", "message": "Command not recognized by Neural Core."}

# Keep the specialized food/camera ones as shortcuts or legacy
@app.post("/action/order-food")
def order_food(food_item: str):
    # Reuse previous logic or redirect to 'open' if simplistic
    # ... (Keeping existing robust logic for Zomato)
    apps = [("com.application.zomato", "Zomato"), ("in.swiggy.android", "Swiggy")]
    for pkg, name in apps:
         # ... existing implementation ...
         check = run_adb_command(f"shell pm list packages {pkg}")
         if check and pkg in check:
             if "zomato" in pkg:
                 deep_link = f"zomato://search?q={food_item}"
             else:
                 # Swiggy fallback
                 deep_link = f"swiggy://explore?query={food_item}"
             
             run_adb_command(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", deep_link, "-p", pkg])
             return {"status": "launched", "app": name, "action": f"Searching for {food_item}"}
    return {"status": "failed"}

@app.post("/action/camera-guide")
def camera_guide():
    """Lauches camera or prepares for guidance."""
    return {"status": "ready", "message": "Camera guide active"}


# ═══════════════════════════════════════════════════════════════════════════════
#  CARETAKER AGENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════
from pydantic import BaseModel as BM

class CaretakerSetupRequest(BM):
    patient_name:       str
    discharge_summary:  str
    prescription:       str
    dietary_conditions: str
    emergency_contact:  str

class CheckinRequest(BM):
    session_id: str
    question:   str
    answer:     str

class ReportRequest(BM):
    session_id: str

@app.post("/caretaker/setup")
def caretaker_setup(req: CaretakerSetupRequest):
    """Parse patient intake and start a caretaker session."""
    try:
        from caretaker_agent import parse_patient_data, store_session
        session = parse_patient_data(
            req.patient_name, req.discharge_summary,
            req.prescription, req.dietary_conditions,
            req.emergency_contact
        )
        session_id = store_session(session)
        return {
            "status":     "ok",
            "session_id": session_id,
            "parsed":     session["parsed"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/caretaker/checkin")
def caretaker_checkin(req: CheckinRequest):
    """Analyse a patient check-in response."""
    try:
        from caretaker_agent import analyse_response
        result = analyse_response(req.session_id, req.question, req.answer)
        return {"status": "ok", "analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/caretaker/session/{session_id}")
def caretaker_session(session_id: str):
    """Get current session state."""
    try:
        from caretaker_agent import get_session
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "ok", "session": session}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/caretaker/report")
def caretaker_report(req: ReportRequest):
    """Generate final patient recovery report."""
    try:
        from caretaker_agent import generate_report
        report = generate_report(req.session_id)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/caretaker/extract")
async def extract_document(file: UploadFile = File(...)):
    """
    Accepts a PDF or image file.
    - PDF  → extracts text with pypdf
    - Image → extracts text with Groq Vision (llama-3.2-11b-vision-preview)
    Then uses Groq to split the raw text into:
      discharge_summary, prescription, dietary_conditions
    """
    GROQ_KEY   = "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"
    GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
    content    = await file.read()
    fname      = (file.filename or "").lower()
    mime       = file.content_type or ""

    # ── Step 1: raw text extraction ──────────────────────────────────────────
    raw_text = ""

    if fname.endswith(".pdf") or "pdf" in mime:
        try:
            import io
            import pypdf
            reader   = pypdf.PdfReader(io.BytesIO(content))
            raw_text = "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except Exception as e:
            raise HTTPException(400, f"PDF parse error: {e}")

    elif any(fname.endswith(ext) for ext in (".jpg",".jpeg",".png",".webp",".bmp")) \
         or "image" in mime:
        try:
            import pytesseract
            from PIL import Image as PILImage
            import io as _io

            # Common Tesseract install path on Windows
            import os as _os
            tess_candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\DELL\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            ]
            for p in tess_candidates:
                if _os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

            img      = PILImage.open(_io.BytesIO(content)).convert("RGB")
            raw_text = pytesseract.image_to_string(img, config="--psm 3")
        except Exception as e:
            raise HTTPException(500, f"OCR error: {e}")

    else:
        raise HTTPException(400, "Unsupported file type. Upload a PDF or image (JPG/PNG/WEBP).")

    if not raw_text.strip():
        raise HTTPException(422, "Could not extract any text from the document.")

    # ── Step 2: Groq categorises the raw text ────────────────────────────────
    try:
        cat_payload = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system",
                 "content": "You are a clinical AI. Parse medical documents and return ONLY valid JSON."},
                {"role": "user",
                 "content": f"""
The following text was extracted from a medical document. 
Split it into these three sections and return ONLY JSON:
{{
  \"discharge_summary\": \"...\",
  \"prescription\": \"...\",
  \"dietary_conditions\": \"...\"
}}

If a section is not present, set it to an empty string.
Do not fabricate any information.

EXTRACTED TEXT:
{raw_text[:4000]}
"""
                }
            ],
            "temperature": 0.1,
            "max_tokens":  1200
        }).encode()
        req2 = urllib.request.Request(
            GROQ_URL, data=cat_payload,
            headers={"Content-Type":"application/json",
                     "Authorization":f"Bearer {GROQ_KEY}"},
            method="POST")
        with urllib.request.urlopen(req2, timeout=20) as r:
            cat_raw  = json.loads(r.read())["choices"][0]["message"]["content"]
        import re
        match = re.search(r'\{[\s\S]+\}', cat_raw)
        categorised = json.loads(match.group()) if match else {}
    except Exception:
        categorised = {}

    return {
        "raw_text":          raw_text,
        "discharge_summary":  categorised.get("discharge_summary", raw_text),
        "prescription":       categorised.get("prescription", ""),
        "dietary_conditions": categorised.get("dietary_conditions", ""),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

