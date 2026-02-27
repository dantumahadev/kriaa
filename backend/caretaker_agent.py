"""
KRIA OS — Caretaker Agent (PS #1: Autonomous Patient Follow-up Agent)
═══════════════════════════════════════════════════════════════════════
Powered by Groq (Llama 3) — no extra API cost.

Responsibilities:
  • Parse discharge summary + prescription → extract medication schedule
  • Generate proactive check-in questions (medication, diet, symptoms)
  • Analyze patient responses → severity classification
  • Trigger emergency call if symptoms are critical
  • Generate a final patient recovery report
"""

import json
import datetime
import re
import urllib.request
import urllib.parse
import os
import subprocess

GROQ_API_KEY = "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"
GROQ_MODEL   = "llama-3.3-70b-versatile"   # smarter model for medical parsing

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "caretaker_sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# In-memory session store  {session_id → session_dict}
_sessions: dict = {}


# ─── GROQ HELPER ───────────────────────────────────────────────────────────────
def _groq(system_prompt: str, user_prompt: str, max_tokens: int = 1200) -> str:
    """Raw Groq call. Returns the assistant's text or '' on failure."""
    try:
        payload = json.dumps({
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system",  "content": system_prompt},
                {"role": "user",    "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens":  max_tokens,
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Caretaker] Groq error: {e}")
        return ""


def _extract_json(raw: str) -> dict | list | None:
    """Pull the first JSON object or array out of an LLM response."""
    try:
        match = re.search(r'(\{[\s\S]+\}|\[[\s\S]+\])', raw)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None


# ─── PRESCRIPTION PARSER ───────────────────────────────────────────────────────
def parse_patient_data(patient_name: str, discharge_summary: str,
                       prescription: str, dietary_conditions: str,
                       emergency_contact: str) -> dict:
    """
    Calls Groq to extract structured data from the intake form.
    Returns a full session dict ready to store.
    """
    system = (
        "You are a clinical AI assistant. Parse medical documents and return "
        "ONLY valid JSON — no markdown fences, no extra text."
    )

    user = f"""
Patient: {patient_name}

DISCHARGE SUMMARY:
{discharge_summary}

PRESCRIPTION:
{prescription}

DIETARY CONDITIONS:
{dietary_conditions}

Extract and return this JSON:
{{
  "medications": [
    {{
      "name": "Drug name",
      "dosage": "500mg",
      "frequency": "twice daily",
      "timing": ["08:00", "20:00"],
      "with_food": true,
      "notes": "Avoid alcohol"
    }}
  ],
  "dietary_restrictions": ["no spicy food", "high protein"],
  "recovery_duration_days": 10,
  "key_symptoms_to_watch": ["fever", "swelling", "nausea"],
  "daily_checkin_questions": [
    "Have you taken all your morning medications?",
    "How would you rate your pain on a scale of 1-10?",
    "Did you follow your dietary restrictions today?",
    "Any new symptoms or side effects?"
  ],
  "post_surgery_restrictions": ["no heavy lifting", "rest for 3 days"]
}}
"""

    raw    = _groq(system, user, max_tokens=1000)
    parsed = _extract_json(raw)

    if not parsed or not isinstance(parsed, dict):
        # Fallback minimal structure
        parsed = {
            "medications": [],
            "dietary_restrictions": [],
            "recovery_duration_days": 7,
            "key_symptoms_to_watch": ["fever", "pain", "swelling"],
            "daily_checkin_questions": [
                "Have you taken your medications?",
                "How is your pain level (1-10)?",
                "Any new symptoms today?",
                "Did you eat as per your dietary plan?"
            ],
            "post_surgery_restrictions": []
        }

    session = {
        "session_id":          _new_session_id(),
        "patient_name":        patient_name,
        "emergency_contact":   emergency_contact,
        "discharge_summary":   discharge_summary,
        "prescription":        prescription,
        "dietary_conditions":  dietary_conditions,
        "parsed":              parsed,
        "responses":           [],   # list of check-in response dicts
        "alerts":              [],   # list of alert dicts
        "started_at":          _now(),
        "status":              "active",
        "report":              None,
    }

    return session


# ─── RESPONSE ANALYSER ─────────────────────────────────────────────────────────
def analyse_response(session_id: str, question: str, answer: str) -> dict:
    """
    Analyses one patient check-in response.
    Returns {severity, summary, action, is_emergency}
    """
    session = _sessions.get(session_id, {})
    patient = session.get("patient_name", "Patient")
    symptoms = session.get("parsed", {}).get("key_symptoms_to_watch", [])

    system = (
        "You are a post-surgery recovery monitoring AI. "
        "Classify the patient's response and return ONLY valid JSON."
    )

    user = f"""
Patient: {patient}
Symptoms to watch: {', '.join(symptoms)}

Check-in question: {question}
Patient response: {answer}

CRITICAL SYMPTOMS RULES:
- If the patient mentions "shortness of breath", "chest pain", "bleeding", or "severe pain", severity MUST be "critical" and is_emergency MUST be true.
- If they seem confused or state they cannot stay awake, set to "critical".

Return JSON:
{{
  "severity": "stable|monitor|warning|critical",
  "is_emergency": false,
  "summary": "one sentence clinical summary",
  "action": "what caretaker/doctor should do",
  "follow_up_question": "optional follow-up question or null"
}}
"""

    raw    = _groq(system, user, max_tokens=400)
    result = _extract_json(raw)

    # Force emergency based on robust keyword scan (Safety Layer)
    answer_lower = answer.lower()
    emergency_phrases = [
        "shortness of breath", "shortness of breathe", "cant breathe", "cannot breathe", 
        "severe pain", "severety in pain", "extreme pain", "too much pain", 
        "unbearable pain", "pain is extreme",
        "chest pain", "heart attack", "bleeding", "emergency", "help me"
    ]
    if any(p in answer_lower for p in emergency_phrases):
        if not result: result = {}
        result["severity"] = "critical"
        result["is_emergency"] = True
        result["action"] = "IMMEDIATE ATTENTION: Calling emergency contact."
        result["summary"] = "Patient reported life-threatening symptoms."

    if not result:
        # Final fallback
        result = {
            "severity":          "stable",
            "is_emergency":      False,
            "summary":           answer[:200],
            "action":            "Continue monitoring.",
            "follow_up_question": None
        }

    # Store response in session
    entry = {
        "timestamp":          _now(),
        "question":           question,
        "answer":             answer,
        "analysis":           result,
    }

    if session_id in _sessions:
        _sessions[session_id]["responses"].append(entry)
        if result.get("severity") in ("warning", "critical"):
            _sessions[session_id]["alerts"].append({
                "timestamp": _now(),
                "severity":  result["severity"],
                "summary":   result["summary"],
                "action":    result["action"],
            })
        if result.get("is_emergency"):
            _trigger_emergency(session)

    return result


# ─── REPORT GENERATOR ──────────────────────────────────────────────────────────
def generate_report(session_id: str) -> str:
    """
    Generates a comprehensive markdown recovery report using Groq.
    """
    session = _sessions.get(session_id)
    if not session:
        return "Session not found."

    responses_text = "\n".join([
        f"Q: {r['question']}\nA: {r['answer']}\nAssessment: {r['analysis'].get('summary','')}"
        for r in session["responses"]
    ])

    alerts_text = "\n".join([
        f"[{a['timestamp']}] {a['severity'].upper()}: {a['summary']}"
        for a in session["alerts"]
    ]) or "No alerts triggered during recovery."

    system = (
        "You are a clinical documentation AI. Generate a professional, "
        "compassionate patient recovery report."
    )

    user = f"""
Generate a recovery report for:
Patient: {session['patient_name']}
Session started: {session['started_at']}
Medications: {json.dumps(session['parsed'].get('medications', []))}

CHECK-IN RESPONSES:
{responses_text or 'No check-in responses recorded.'}

ALERTS:
{alerts_text}

Write a structured report with these sections:
1. Executive Summary
2. Medication Adherence
3. Symptom Progress
4. Dietary Compliance  
5. Alerts & Incidents
6. Recommendations
7. Follow-up Required

Be clinical but clear. Use markdown formatting.
"""

    report = _groq(system, user, max_tokens=1500)
    if not report:
        report = f"# Recovery Report — {session['patient_name']}\n\nReport generation failed. Please review session data manually."

    if session_id in _sessions:
        _sessions[session_id]["report"] = report

    # Save report to file
    path = os.path.join(SESSIONS_DIR, f"report_{session_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    return report


# ─── EMERGENCY TRIGGER ─────────────────────────────────────────────────────────
def _trigger_emergency(session: dict):
    """Calls emergency contact via ADB dialer."""
    phone = session.get("emergency_contact", "")
    if not phone:
        return
    print(f"[Caretaker] EMERGENCY — calling {phone}")
    try:
        subprocess.run(
            ["adb", "shell", "am", "start",
             "-a", "android.intent.action.CALL",
             "-d", f"tel:{phone}"],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Caretaker] Emergency call error: {e}")


# ─── SESSION HELPERS ───────────────────────────────────────────────────────────
def _new_session_id() -> str:
    return datetime.datetime.now().strftime("CT%Y%m%d%H%M%S")

def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def store_session(session: dict) -> str:
    sid = session["session_id"]
    _sessions[sid] = session
    # Persist to disk
    path = os.path.join(SESSIONS_DIR, f"{sid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)
    return sid

def get_session(session_id: str) -> dict | None:
    if session_id in _sessions:
        return _sessions[session_id]
    # Try loading from disk
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(path):
        with open(path) as f:
            session = json.load(f)
        _sessions[session_id] = session
        return session
    return None
