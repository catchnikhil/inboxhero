import json
from datetime import datetime
from config import Config
TRACE_FILE = Config.TRACE_FILE

def log_event(cap_id: str, event_type: str, details: dict):
    """
    Appends a structured event to trace.jsonl.
    cap_id: The capability ID (e.g., 'R1', 'R2', 'X1')
    event_type: e.g., 'decision', 'draft', 'gate', 'refusal'
    details: The context payload
    """
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cap": cap_id,
        "type": event_type,
        "details": details
    }
    
    with open(TRACE_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")