import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from config import Config
from trace import log_event

OUTBOX_DIR = Config.OUTBOX_DIR
# Explicit classification as required by the assignment manifest
IRREVERSIBLE_ACTIONS = {"send", "delete"}
REVERSIBLE_ACTIONS = {"draft", "archive", "defer", "label"}


def process_action(action_type: str, payload: Dict[str, Any], is_dry_run: bool) -> bool:
    """
    Gates irreversible actions. Reversible actions pass through automatically.
    Returns True if the action was executed/approved, False if denied/suppressed.

    Behavior:
      - Reversible actions are executed immediately (mocked) and return True.
      - Unknown actions return False.
      - Irreversible actions are either suppressed in dry-run mode or require
        explicit user approval. Approved 'send' actions are written to OUTBOX_DIR.
      - All gate decisions are logged via log_event for audit/evidence.
    """
    action = (action_type or "").strip().lower()

    # Reversible actions: auto-execute
    if action in REVERSIBLE_ACTIONS:
        print(f"[AUTO] Executed reversible action: {action}")
        log_event(
            cap_id="R3",
            event_type="action_executed",
            details={"action": action, "payload": payload, "mode": "reversible"}
        )
        return True

    # Unknown action types
    if action not in IRREVERSIBLE_ACTIONS:
        print(f"[ERROR] Unknown action type: {action_type}")
        log_event(
            cap_id="R3",
            event_type="action_unknown",
            details={"action": action_type, "payload": payload}
        )
        return False

    # At this point, action is irreversible
    print(f"\n[GATE] Proposed IRREVERSIBLE action: {action.upper()}")
    try:
        pretty_payload = json.dumps(payload, indent=2, ensure_ascii=False)
    except Exception:
        pretty_payload = str(payload)
    print(f"Payload:\n{pretty_payload}\n")

    decision = "denied"

    if is_dry_run:
        # Dry-run: do not perform irreversible actions
        print("[GATE] DRY-RUN MODE: Action suppressed. No files written.")
        decision = "dry-run-suppressed"
    else:
        # Interactive approval
        try:
            user_input = input("Approve this action? (y/n): ").strip().lower()
        except Exception:
            user_input = "n"

        if user_input == "y":
            decision = "approved"
            print("[GATE] Action approved by user.")
        else:
            decision = "denied"
            print("[GATE] Action denied by user.")

    # Log the gate decision for Part 4 evidence
    log_event(
        cap_id="R3",
        event_type="gate",
        details={
            "proposed_action": action,
            "payload": payload,
            "decision": decision,
            "dry_run": bool(is_dry_run),
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
    )

    # Execute approved irreversible actions
    if decision == "approved":
        if action == "send":
            try:
                _write_to_outbox(payload)
                log_event(
                    cap_id="R3",
                    event_type="action_executed",
                    details={"action": "send", "payload": payload}
                )
            except Exception as e:
                print(f"[ERROR] Failed to write outbox: {e}")
                log_event(
                    cap_id="R3",
                    event_type="action_failed",
                    details={"action": "send", "payload": payload, "error": str(e)}
                )
                return False
        elif action == "delete":
            # In a real system this would remove the message from storage.
            # Here we mock the deletion and log it.
            target_id = payload.get("target_id") or payload.get("id") or "<unknown>"
            print(f"[ACTION] Message {target_id} permanently deleted (mocked).")
            log_event(
                cap_id="R3",
                event_type="action_executed",
                details={"action": "delete", "target_id": target_id}
            )
        return True

    # Any other decision (denied, dry-run-suppressed) results in no execution
    return False


def _write_to_outbox(payload: Dict[str, Any]) -> None:
    """
    Writes an approved message to the outbox directory, one file per message.
    Ensures the OUTBOX_DIR exists and uses a timestamped filename.

    Filename format: outbound_<reply_to or new>_<YYYYmmddTHHMMSSZ>.json
    """
    outbox_dir = Path(OUTBOX_DIR)
    outbox_dir.mkdir(parents=True, exist_ok=True)

    # Use reply_to or generate a short id
    msg_ref = payload.get("reply_to") or payload.get("id") or "new"
    # Normalize msg_ref to a filesystem-safe string
    msg_ref_safe = "".join(c for c in str(msg_ref) if c.isalnum() or c in ("-", "_")).strip() or "new"

    timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = outbox_dir / f"outbound_{msg_ref_safe}_{timestamp}.json"

    # Write atomically: write to temp file then rename
    temp_filename = filename.with_suffix(".json.tmp")
    with open(temp_filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    temp_filename.replace(filename)

    print(f"[OUTBOX] Message written to outbox/{filename.name}")
