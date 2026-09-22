from datetime import datetime
from typing import List, Dict, Any, Optional

# Helper: robust ISO timestamp parser with graceful fallback
def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Accepts ISO 8601 like "2023-09-01T12:34:56" or with timezone
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        try:
            # Fallback: try common formats
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

def get_thread_context(inbox: List[Dict[str, Any]], thread_id: str, current_timestamp: str) -> List[Dict[str, Any]]:
    """
    Retrieve prior messages in a thread, strictly earlier than current_timestamp.

    - Parses timestamps robustly and falls back to string comparison when parsing fails.
    - Returns messages sorted chronologically (oldest first).
    - Keeps the original message dicts so downstream code can access all fields.
    """
    if not thread_id:
        return []

    cutoff = _parse_timestamp(current_timestamp)
    candidates: List[Dict[str, Any]] = []

    for msg in inbox:
        if msg.get("thread_id") != thread_id:
            continue
        msg_ts = _parse_timestamp(msg.get("timestamp"))
        # If both parsed, compare datetimes; otherwise compare raw strings
        if cutoff and msg_ts:
            if msg_ts < cutoff:
                candidates.append(msg)
        else:
            raw_msg_ts = msg.get("timestamp", "")
            if raw_msg_ts and raw_msg_ts < (current_timestamp or ""):
                candidates.append(msg)

    # Sort by parsed timestamp when possible, otherwise by the raw timestamp string
    def _sort_key(m: Dict[str, Any]):
        parsed = _parse_timestamp(m.get("timestamp"))
        return parsed if parsed is not None else m.get("timestamp", "")

    return sorted(candidates, key=_sort_key)

def format_context_for_prompt(history: List[Dict[str, Any]]) -> str:
    """
    Format a list of prior messages into a compact, readable block for LLM prompts.

    - Includes Message ID, From, Date (ISO), Subject (if present), and a truncated Body.
    - Truncates long bodies to keep prompts concise while preserving the start and end of the message.
    - Lists attachments if present.
    """
    if not history:
        return "No prior thread context available."

    blocks: List[str] = []
    for msg in history:
        msg_id = msg.get("id", "<no-id>")
        sender = msg.get("from", "<unknown>")
        raw_ts = msg.get("timestamp", "")
        parsed_ts = _parse_timestamp(raw_ts)
        date_str = parsed_ts.isoformat() if parsed_ts else raw_ts or "unknown date"
        subject = msg.get("subject", "").strip()
        body = (msg.get("body") or "").strip()

        # Truncate body but keep start and end for context
        max_len = 800
        if len(body) > max_len:
            head = body[:400].rstrip()
            tail = body[-300:].lstrip()
            body_display = f"{head}\n\n...[truncated]...\n\n{tail}"
        else:
            body_display = body

        attachments = msg.get("attachments") or []
        attachments_str = ", ".join(a.get("filename", str(a)) for a in attachments) if attachments else "none"

        block = (
            f"--- Message ID: {msg_id} ---\n"
            f"From: {sender}\n"
            f"Date: {date_str}\n"
            f"Subject: {subject}\n"
            f"Attachments: {attachments_str}\n\n"
            f"Body:\n{body_display}\n"
        )
        blocks.append(block)

    return "\n".join(blocks)
