import json
from config import Config
PREFS_FILE = Config.PREFS_FILE

def save_preference(key: str, value: str):
    """Saves a preference to disk."""
    prefs = load_preferences()
    prefs[key] = value
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)
    print(f"[MEMORY] Saved preference: {key} -> {value}")

def load_preferences() -> dict:
    """Loads preferences from disk."""
    if not PREFS_FILE.exists():
        return {}
    with open(PREFS_FILE, "r") as f:
        return json.load(f)