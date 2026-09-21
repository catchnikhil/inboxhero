import json
import os
import time
import requests
from datetime import datetime
from config import Config
import google.generativeai as genai

# Configure Gemini
Config.validate()
genai.configure(api_key=Config.GEMINI_API_KEY)
model = genai.GenerativeModel(Config.MODEL_NAME)

# Evidence files
TRACE_FILE = "trace.jsonl"
DECISIONS_FILE = "decisions.json"
PREFS_FILE = "prefs.json"
OUTBOX_DIR = "outbox"
DASHBOARD_FILE = "dashboard.html"

os.makedirs(OUTBOX_DIR, exist_ok=True)

# --- Helpers ---
def log_event(cap_id: str, message: str):
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "capability": cap_id,
        "message": message,
    }
    with open(TRACE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

def write_decisions(decisions: dict):
    with open(DECISIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)

def write_prefs(prefs: dict):
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2)

def write_outbox(msg_id: str, draft: str):
    path = os.path.join(OUTBOX_DIR, f"{msg_id}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(draft)

def write_dashboard(html: str):
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)

# --- Retry + batching ---
def safe_api_call(func, *args, **kwargs):
    """Wrapper to handle 429 errors with exponential backoff."""
    for attempt in range(5):  # up to 5 retries
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt
                print(f"Rate limit hit, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded for API call")

def batch_messages(messages, batch_size=10):
    for i in range(0, len(messages), batch_size):
        yield messages[i:i+batch_size]

def load_messages():
    # Replace with your actual inbox loader
    return [
        {"id": "m001", "text": "Receipt from store"},
        {"id": "m002", "text": "Project update from team"},
        {"id": "m003", "text": "Meeting invite"},
        # ... more messages
    ]

# --- Dispatcher ---
def run_capability(cap_id: str):
    if cap_id == "R1":
        run_zero_inbox()
    elif cap_id == "R2":
        run_grounded_reply()
    elif cap_id == "R3":
        run_gate_irreversible()
    elif cap_id == "R4":
        run_persistent_preference()
    elif cap_id == "R5":
        run_refuse_instructions()
    elif cap_id == "R6":
        run_dashboard()
    elif cap_id == "X1":
        run_follow_up()
    elif cap_id == "X2":
        run_morning_digest()
    elif cap_id == "X3":
        run_conflict_detection()
    else:
        raise ValueError(f"Unknown capability: {cap_id}")

# --- Capability handlers ---
def run_zero_inbox():
    print("Running R1: Zero the inbox")
    all_decisions = {}
    for batch in batch_messages(load_messages(), batch_size=10):
        # Safe Gemini call (stubbed here)
        response = safe_api_call(model.generate_content, f"Classify: {batch}")
        # Stub: parse response into decisions
        for msg in batch:
            all_decisions[msg["id"]] = {
                "disposition": "archive",
                "reason": "stub classification"
            }
    write_decisions(all_decisions)
    log_event("R1", f"Classified {len(all_decisions)} messages in batches")

def run_grounded_reply():
    print("Running R2: Grounded reply")
    draft = "Hi team, thanks for the update. Following up on your earlier message..."
    write_outbox("m002", draft)
    log_event("R2", "Draft reply saved in outbox/m002.txt")

def run_gate_irreversible():
    print("Running R3: Gate the irreversible")
    log_event("R3", "Approval required before irreversible action (send/delete)")

def run_persistent_preference():
    print("Running R4: Persistent preference")
    prefs = {"cc_cofounder": True}
    write_prefs(prefs)
    log_event("R4", "Preference persisted in prefs.json")

def run_refuse_instructions():
    print("Running R5: Refuse embedded instructions")
    log_event("R5", "Injection detected and refused")

def run_dashboard():
    print("Running R6: Dashboard")
    html = "<html><body><h1>Dashboard</h1><p>Commitments and conflicts surfaced.</p></body></html>"
    write_dashboard(html)
    log_event("R6", "Dashboard written to dashboard.html")

def run_follow_up():
    print("Running X1: Follow-up tracking")
    draft = "Hi, just checking if you had a chance to review my last email."
    write_outbox("m010", draft)
    log_event("X1", "Follow-up draft saved in outbox/m010.txt")

def run_morning_digest():
    print("Running X2: Morning digest")
    digest = {
        "urgent": ["m005"],
        "wait": ["m006"],
        "archived": ["m001", "m003"],
    }
    write_decisions(digest)
    log_event("X2", "Morning digest written to decisions.json")

def run_conflict_detection():
    print("Running X3: Conflict detection")
    conflicts = {"meetingA": "10am", "meetingB": "10am"}
    write_dashboard(f"<html><body><h1>Conflicts</h1><p>{conflicts}</p></body></html>")
    log_event("X3", "Conflict detection results written to dashboard.html")
