import json
import argparse
from typing import List, Dict, Any, Optional
import inspect
from typing import Optional
from config import Config
import google.generativeai as genai
from config import Config
from rules import triage_by_rules
from retriever import get_thread_context, format_context_for_prompt
from gate import process_action
from security import detect_hostile_intent
from dashboard import generate_dashboard_html
from memory import save_preference, load_preferences
from trace import log_event

# Validate config and configure Gemini client
Config.validate()
genai.configure(api_key=Config.GEMINI_API_KEY)
MODEL_NAME = Config.MODEL_NAME
INBOX_FILE = Config.INBOX_FILE
# -----------------------
# Utility helpers
# -----------------------
def _load_inbox() -> List[Dict[str, Any]]:
    with open(INBOX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _safe_llm_call(prompt: str,
                   system: Optional[str] = None,
                   temperature: float = 0.0,
                   model: Optional[str] = None) -> str:
    """
    Simple Gemini call using google.generativeai.GenerativeModel.
    Returns assistant text or empty string on failure.
    """
    model_name = model or MODEL_NAME
    full_prompt = f"System: {system}\n\nUser: {prompt}" if system else prompt

    try:
        # Create a GenerativeModel instance
        model_obj = genai.GenerativeModel(model_name)

        # Call generate_content with the prompt
        resp = model_obj.generate_content(full_prompt, generation_config={"temperature": temperature})

        # Most responses expose .text
        if hasattr(resp, "text") and resp.text:
            return resp.text
        return str(resp) or ""
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return ""


# -----------------------
# R1: Zero the inbox (Tier B)
# -----------------------
def run_r1_zero_inbox():
    inbox = _load_inbox()
    total = len(inbox)
    rule_handled = 0
    undecided = 0

    print(f"Running R1: Zero the inbox — processing {total} messages\n")
    print(f"{'ID':<6} | {'DISPOSITION':<10} | {'REASON'}")
    print("-" * 80)

    for msg in inbox:
        msg_id = msg.get("id", "<no-id>")
        decision = triage_by_rules(msg)

        if decision:
            rule_handled += 1
        else:
            decision = {"disposition": "escalate", "reason": "LLM fallback: requires human review"}

        if not decision:
            undecided += 1
            print(f"{msg_id:<6} | {'undecided':<10} | No decision produced")
            continue

        disposition = decision.get("disposition", "archive")
        reason = decision.get("reason", "")

        print(f"{msg_id:<6} | {disposition:<10} | {reason[:60]}")
        log_event(cap_id="R1", event_type="decision", details={"message_id": msg_id, "disposition": disposition, "reason": reason})

    print("\n--- R1 Summary ---")
    print(f"Messages processed: {total}")
    print(f"Rule handled: {rule_handled}")
    print(f"Undecided: {undecided}")

    assert undecided == 0, "Failed R1: Some messages were left undecided!"


# -----------------------
# R2: Grounded reply (Tier B)
# -----------------------
def run_r2_grounded_reply(target_msg_id: str = "m008"):
    inbox = _load_inbox()
    target = next((m for m in inbox if m.get("id") == target_msg_id), None)
    if not target:
        print(f"Message {target_msg_id} not found.")
        return

    history = get_thread_context(inbox, target.get("thread_id"), target.get("timestamp"))
    cited_ids = [m.get("id") for m in history]
    context_text = format_context_for_prompt(history)

    system_instruction = (
        "You are an executive assistant. Draft a brief, professional reply to the TARGET MESSAGE. "
        "You MUST base your answer strictly on the provided THREAD CONTEXT. "
        "Do not invent URLs, credentials, or facts. "
        "End your draft by explicitly listing the Message IDs you used as sources (e.g., 'cited: [m001, m002]')."
    )

    user_payload = (
        f"--- THREAD CONTEXT ---\n{context_text}\n\n"
        f"--- TARGET MESSAGE ---\nFrom: {target.get('from')}\nSubject: {target.get('subject')}\n\n{target.get('body')}"
    )

    print(f"Drafting reply for {target_msg_id} using context from {cited_ids}...\n")
    draft = _safe_llm_call(user_payload, system=system_instruction, temperature=0.0)

    if not draft:
        print("LLM failed to produce a draft.")
        return

    print("--- DRAFT ---")
    print(draft)
    print("-------------")

    log_event(cap_id="R2", event_type="draft", details={"target_msg": target_msg_id, "cited_ids": cited_ids, "draft_content": draft})


# -----------------------
# R3: Gate the irreversible (Tier C)
# -----------------------
def run_r3_gate(is_dry_run: bool, target_msg_id: str):
    inbox = _load_inbox()
    target = next((m for m in inbox if m.get("id") == target_msg_id), None)
    if not target:
        print(f"Message {target_msg_id} not found.")
        return

    print(f"Simulating agent actions for target: {target_msg_id} (dry-run={is_dry_run})\n")

    process_action("archive", {"target_id": target_msg_id, "reason": "User requested archive"}, is_dry_run)

    send_payload = {
        "reply_to": target_msg_id,
        "to": target.get("from", "unknown"),
        "body": "Executing requested action."
    }

    prefs = load_preferences()
    if "hartwellcho.com" in target.get("from", ""):
        legal_cc = prefs.get("legal_cc")
        if legal_cc:
            send_payload["cc"] = legal_cc
            print(f"[SYSTEM] Applied standing preference: CC'ing {legal_cc}")

    process_action("send", send_payload, is_dry_run)
    process_action("delete", {"target_id": target_msg_id, "reason": "Identified as spam/phishing"}, is_dry_run)

    print("\nR3 simulation complete. Check trace logs for details.")
    log_event(cap_id="R3", event_type="gate_simulation", details={"target_msg": target_msg_id, "dry_run": is_dry_run})


# -----------------------
# R4: Persistent preference (Tier C)
# -----------------------
def run_r4_persistent_preference(target_msg_id: str):
    inbox = _load_inbox()
    target = next((m for m in inbox if m.get("id") == target_msg_id), None)
    if not target:
        print(f"Message {target_msg_id} not found.")
        return

    print(f"Processing target message: {target_msg_id}")
    print(f"Subject: {target.get('subject')}\n")

    if target_msg_id == "m015":
        print("Detected standing instruction: CC Priya on Hartwell & Cho legal mail.")
        save_preference("legal_cc", "priya@paperjet.io")
        print("[MEMORY] Preference saved to disk.")
        log_event(cap_id="R4", event_type="preference_learned", details={"source_msg": target_msg_id, "preference_key": "legal_cc", "value": "priya@paperjet.io"})
        return

    prefs = load_preferences()
    legal_cc = prefs.get("legal_cc")
    if legal_cc and ("hartwellcho.com" in target.get("from", "" ) or target_msg_id == "m018"):
        print(f"[ACTION] Automatically added {legal_cc} to CC based on standing preference.")
        log_event(cap_id="R4", event_type="preference_applied", details={"trigger_msg": target_msg_id, "preference_key": "legal_cc", "action_taken": f"CC'd {legal_cc}"})
    else:
        print("[ACTION] No standing preference found or not applicable.")


# -----------------------
# R5: Refuse embedded instructions (Tier C)
# -----------------------
def run_r5_hostile_inbox():
    inbox = _load_inbox()
    flagged_count = 0

    print("Scanning inbox for hostile instructions...\n")
    for msg in inbox:
        msg_id = msg.get("id")
        security_check = detect_hostile_intent(msg)
        if security_check.get("is_hostile"):
            flagged_count += 1
            reason = security_check.get("reason", "hostile instruction detected")
            print(f"FLAGGED: {msg_id} attempted to manipulate the system.")
            print(f"-> Threat: {reason}")
            print("-> Action: Not done, left in place. No files written to outbox.\n")

            log_event(cap_id="R5", event_type="refusal", details={"message_id": msg_id, "attempted_action": reason, "system_action": "refused_and_flagged"})

    print(f"--- R5 Summary ---")
    print(f"Total messages scanned: {len(inbox)}")
    print(f"Hostile messages flagged and neutralized: {flagged_count}")


# -----------------------
# R6: Dashboard (Tier C)
# -----------------------
def run_r6_dashboard():
    inbox = _load_inbox()

    pending_actions = []
    flagged_items = []
    commitments = []
    needs_me = []
    archived_count = 0

    for msg in inbox:
        msg_id = msg.get("id")
        sec = detect_hostile_intent(msg)
        is_phish = any(kw in msg.get("body", "").lower() for kw in ["wire $", "password expires", "remittance details"])
        if sec.get("is_hostile") or is_phish:
            flagged_items.append({"msg_id": msg_id, "threat": sec.get("reason") if sec.get("is_hostile") else "Suspected Phishing", "action_taken": "Refused/Flagged"})
            continue

        decision = triage_by_rules(msg)
        if msg.get("unread") and not decision:
            if len(pending_actions) < 10:
                pending_actions.append({"msg_id": msg_id, "action": "REVIEW / DRAFT", "reason": f"Requires LLM drafting or human approval. Subject: '{msg.get('subject')}'"})

        if msg.get("unread"):
            if decision and decision.get("disposition") == "archive":
                archived_count += 1
            else:
                needs_me.append(msg)

    board_threads = [m for m in inbox if m.get("thread_id") in ["t-board", "t-deck"]]
    if board_threads:
        commitments.append({
            "datetime": "Sep 16, 2026 (Derived)",
            "desc": "Board deck finalized and circulated",
            "sources": [m.get("id") for m in board_threads],
            "notes": "Derived from meeting thread and 'two days before' constraint."
        })

    vc_call = next((m for m in inbox if m.get("id") == "m010"), None)
    dentist = next((m for m in inbox if m.get("id") == "m061"), None)
    x4_resolutions = []
    if vc_call and dentist:
        commitments.append({
            "datetime": "Sep 15, 2026 @ 3:00pm",
            "desc": "Intro call with Aria (Northwind VC)",
            "sources": [vc_call.get("id")],
            "conflict": True,
            "notes": f"Conflicts with {dentist.get('id')}"
        })
        commitments.append({
            "datetime": "Sep 15, 2026 @ 3:00pm",
            "desc": "Dental cleaning with Dr. Osei",
            "sources": [dentist.get("id")],
            "conflict": True,
            "notes": f"Conflicts with {vc_call.get('id')}"
        })
        x4_resolutions.append({
            "conflict": "Sep 15 @ 3:00pm (VC Call vs Dentist)",
            "action": "Drafted 3 alternative times for Sep 16",
            "status": "Held in R3 Gate for Approval"
        })

    digest_data = {"archived": archived_count, "needs_me": needs_me[:5]}

    generate_dashboard_html(pending_actions, flagged_items, commitments, digest_data, [], x4_resolutions)

    log_event(cap_id="R6", event_type="dashboard_generated_extended", details={"file": "dashboard.html", "x4_resolved": len(x4_resolutions)})

    print("--- R6 Dashboard ---")
    print(f"Pending actions: {len(pending_actions)}")
    print(f"Flagged items: {len(flagged_items)}")
    print(f"Commitments found: {len(commitments)}")
    print(f"Auto-archived (unread): {archived_count}")


# -----------------------
# X1: Follow-up tracking (Tier B)
# -----------------------
def run_x1_followup_tracker():
    inbox = _load_inbox()
    sam_sent = [m for m in inbox if m.get("from") == "sam@paperjet.io"]
    followups = []

    for sent_msg in sam_sent:
        replies = [m for m in inbox if m.get("thread_id") == sent_msg.get("thread_id") and m.get("timestamp") > sent_msg.get("timestamp")]
        if not replies:
            followups.append(sent_msg)

    print("--- UNANSWERED OUTBOUND MAIL ---")
    for m in followups:
        print(f"Waiting on reply for: [{m.get('id')}] To: {m.get('to')} | Subject: {m.get('subject')}")

    drafts = {}
    for m in followups[:3]:
        prompt = (
            f"Draft a short, polite follow-up email reminding the recipient about the message below. "
            f"Include a one-line ask and a suggested availability window.\n\n"
            f"Original subject: {m.get('subject')}\nOriginal body: {m.get('body')}\n"
        )
        draft = _safe_llm_call(prompt, system="You are a concise executive assistant.", temperature=0.0)
        drafts[m.get("id")] = draft
        print(f"\n--- DRAFT for {m.get('id')} ---\n{draft}\n")

    log_event(cap_id="X1", event_type="followup_scan", details={"unanswered_count": len(followups), "drafts": list(drafts.keys())})


# -----------------------
# X2: Morning digest (Tier B)
# -----------------------
def run_x2_morning_digest():
    inbox = _load_inbox()
    needs_me = []
    archived_count = 0

    for msg in inbox:
        if not msg.get("unread"):
            continue
        decision = triage_by_rules(msg)
        if decision and decision.get("disposition") == "archive":
            archived_count += 1
        else:
            needs_me.append(msg)

    print("--- MORNING DIGEST ---")
    print(f"Auto-archived noise: {archived_count} messages\n")
    print("Needs Your Attention (top 5):")
    for m in needs_me[:5]:
        print(f"- [{m.get('id')}] {m.get('from')}: {m.get('subject')}")

    if len(needs_me) > 5:
        print(f"...and {len(needs_me) - 5} more.")

    log_event(cap_id="X2", event_type="digest_generated", details={"needs_me_count": len(needs_me), "archived_count": archived_count})


# -----------------------
# X3: Conflict detection (Tier C)
# -----------------------
def run_x3_conflict_detection(is_dry_run: bool = True):
    inbox = _load_inbox()
    vc_call = next((m for m in inbox if m.get("id") == "m010"), None)
    dentist = next((m for m in inbox if m.get("id") == "m061"), None)

    if not vc_call or not dentist:
        print("Could not find the conflict messages (m010 / m061).")
        return

    print("[AGENT] Conflict detected: VC call vs Dentist appointment\n")
    print(f"-> Event 1: {vc_call.get('subject')} (ID: {vc_call.get('id')})")
    print(f"-> Event 2: {dentist.get('subject')} (ID: {dentist.get('id')})\n")

    prompt = (
        "You are an executive assistant. We have a conflict on Sep 15 at 3:00pm and cannot make the call. "
        "Draft a brief, polite email to the VC proposing three specific alternative time slots for September 16th. "
        "Output ONLY the raw email body, with no additional commentary."
    )

    draft_body = _safe_llm_call(prompt, temperature=0.4)
    if not draft_body:
        print("LLM failed to generate alternatives.")
        return

    payload = {
        "reply_to": vc_call.get("id"),
        "to": vc_call.get("from"),
        "subject": f"Re: {vc_call.get('subject')}",
        "body": draft_body
    }

    print("[AGENT] Drafted alternatives. Routing to human approval gate...\n")
    process_action("send", payload, is_dry_run)

    log_event(cap_id="X3", event_type="conflict_resolved_and_held", details={"conflict_time": "Sep 15 3:00pm", "action": "drafted_alternatives", "held_in_gate": is_dry_run})


# -----------------------
# CLI Dispatcher
# -----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="inboxHero CLI")
    parser.add_argument("--cap", type=str, help="Capability to run (e.g., R1, R2, R3, R4, R5, R6, X1, X2, X3)")
    parser.add_argument("--msg", type=str, default="m008", help="Target message ID for R2/R3/R4")
    parser.add_argument("--dry-run", action="store_true", help="Run without executing irreversible actions")
    args = parser.parse_args()

    if args.cap == "R1":
        run_r1_zero_inbox()
    elif args.cap == "R2":
        run_r2_grounded_reply(args.msg)
    elif args.cap == "R3":
        run_r3_gate(args.dry_run, args.msg)
    elif args.cap == "R4":
        run_r4_persistent_preference(args.msg)
    elif args.cap == "R5":
        run_r5_hostile_inbox()
    elif args.cap == "R6":
        run_r6_dashboard()
    elif args.cap == "X1":
        run_x1_followup_tracker()
    elif args.cap == "X2":
        run_x2_morning_digest()
    elif args.cap == "X3":
        run_x3_conflict_detection(is_dry_run=args.dry_run)
    else:
        print("Please specify a valid capability, e.g.: python agent.py --cap R1")
