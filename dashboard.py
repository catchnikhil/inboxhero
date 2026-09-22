"""
dashboard_builder.py

Reads the inbox JSON and generates a simple, self-contained HTML dashboard
with three panes: Pending Actions, Commitments, and Flagged Items.

Usage:
    python dashboard_builder.py --inbox path/to/inbox.json --out dashboard.html
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple

from trace import log_event
from rules import triage_by_rules
from security import detect_hostile_intent

# Defaults (can be overridden via CLI)
DEFAULT_INBOX = Path("inbox.json")
DEFAULT_OUTPUT = Path("dashboard.html")


# -----------------------
# Data extraction helpers
# -----------------------
def _load_inbox(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _short(text: str, length: int = 140) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


# -----------------------
# Dashboard pipelines
# -----------------------
def find_pending_actions(inbox: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    """
    Pending actions are unread messages that are not auto-archived by rules
    and are not flagged as hostile. Return a list of dicts with summary fields.
    """
    pending = []
    for msg in inbox:
        if not msg.get("unread"):
            continue
        if detect_hostile_intent(msg).get("is_hostile"):
            continue
        rule_decision = triage_by_rules(msg)
        if rule_decision and rule_decision.get("disposition") == "archive":
            continue
        pending.append(
            {
                "id": msg.get("id"),
                "from": msg.get("from"),
                "subject": _short(msg.get("subject", "")),
                "snippet": _short(msg.get("body", ""), 200),
                "timestamp": msg.get("timestamp"),
            }
        )
        if len(pending) >= limit:
            break
    return pending


def find_flagged_items(inbox: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flagged items include messages detected as hostile or containing phishing indicators.
    """
    flagged = []
    for msg in inbox:
        sec = detect_hostile_intent(msg)
        if sec.get("is_hostile"):
            flagged.append(
                {
                    "id": msg.get("id"),
                    "from": msg.get("from"),
                    "subject": _short(msg.get("subject", "")),
                    "reason": sec.get("reason", ""),
                    "timestamp": msg.get("timestamp"),
                }
            )
            continue

        # Simple phishing heuristics (complementary to detect_hostile_intent)
        body = (msg.get("body") or "").lower()
        if any(k in body for k in ["wire $", "password expires", "send credentials", "verify your account"]):
            flagged.append(
                {
                    "id": msg.get("id"),
                    "from": msg.get("from"),
                    "subject": _short(msg.get("subject", "")),
                    "reason": "Suspected phishing / social engineering",
                    "timestamp": msg.get("timestamp"),
                }
            )
    return flagged


def find_commitments(inbox: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Heuristic detection of commitments: messages that belong to threads
    with keywords like 'board', 'deck', 'meeting', or explicit date/time patterns.
    """
    commitments = []
    for msg in inbox:
        subj = (msg.get("subject") or "").lower()
        body = (msg.get("body") or "").lower()
        thread_id = msg.get("thread_id")
        # Heuristics for commitments
        if any(k in subj for k in ["board", "deck", "final", "deadline", "deliverable", "due"]) or any(
            k in body for k in ["meeting", "call", "schedule", "agenda", "due by", "deliver by"]
        ):
            commitments.append(
                {
                    "id": msg.get("id"),
                    "thread_id": thread_id,
                    "from": msg.get("from"),
                    "subject": _short(msg.get("subject", "")),
                    "snippet": _short(msg.get("body", ""), 200),
                    "timestamp": msg.get("timestamp"),
                }
            )
    # Deduplicate by thread_id, keep earliest timestamp per thread
    seen_threads = {}
    for c in commitments:
        tid = c.get("thread_id") or c.get("id")
        if tid not in seen_threads or (c.get("timestamp") or "") < (seen_threads[tid].get("timestamp") or ""):
            seen_threads[tid] = c
    return list(seen_threads.values())


# -----------------------
# HTML rendering
# -----------------------
def _render_section(title: str, rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> str:
    """
    Render a simple table section.
    columns: list of (column_key, column_label)
    """
    if not rows:
        return f"<h3>{title}</h3><p><em>None</em></p>"

    header_cells = "".join(f"<th>{label}</th>" for _, label in columns)
    body_rows = []
    for r in rows:
        cells = []
        for key, _ in columns:
            val = r.get(key, "")
            # Escape minimal HTML-sensitive characters
            val = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            cells.append(f"<td>{val}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    body_html = "\n".join(body_rows)
    return f"""
    <h3>{title}</h3>
    <table class="table">
      <thead><tr>{header_cells}</tr></thead>
      <tbody>
        {body_html}
      </tbody>
    </table>
    """


def generate_dashboard_html(inbox: List[Dict[str, Any]], output_path: Path) -> None:
    """
    Build a three-pane dashboard and write it to output_path (HTML).
    """
    pending = find_pending_actions(inbox, limit=20)
    flagged = find_flagged_items(inbox)
    commitments = find_commitments(inbox)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Inbox Dashboard</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 20px; color: #111; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .pane {{ border: 1px solid #ddd; padding: 12px; border-radius: 6px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
    h1 {{ margin-top: 0; }}
    .table {{ width: 100%; border-collapse: collapse; }}
    .table th, .table td {{ text-align: left; padding: 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
    .muted {{ color: #666; font-size: 0.9em; }}
    .small {{ font-size: 0.9em; }}
    footer {{ margin-top: 18px; color: #666; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>Inbox Dashboard</h1>
  <p class="muted">Generated: {now} UTC</p>

  <div class="grid">
    <div class="pane">
      { _render_section("Pending Actions (Needs Your Attention)", pending, [("id","ID"),("from","From"),("subject","Subject"),("snippet","Snippet")]) }
    </div>

    <div class="pane">
      { _render_section("Flagged Items (Security / Hostile)", flagged, [("id","ID"),("from","From"),("subject","Subject"),("reason","Reason")]) }
    </div>

    <div class="pane" style="grid-column: 1 / -1;">
      { _render_section("Commitments (Cited Sources & Deadlines)", commitments, [("id","ID"),("thread_id","Thread"),("subject","Subject"),("snippet","Snippet")]) }
    </div>
  </div>

  <footer>
    <div class="small">Summary: Pending {len(pending)} • Flagged {len(flagged)} • Commitments {len(commitments)}</div>
  </footer>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[DASHBOARD] Written to {output_path}")
    log_event(cap_id="R6", event_type="dashboard_generated", details={"file": str(output_path), "pending": len(pending), "flagged": len(flagged), "commitments": len(commitments)})


# -----------------------
# CLI
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="Build an HTML dashboard from inbox JSON")
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX, help="Path to inbox JSON file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output HTML file path")
    args = parser.parse_args()

    inbox = _load_inbox(args.inbox)
    generate_dashboard_html(inbox, args.out)


if __name__ == "__main__":
    main()
