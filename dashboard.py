# dashboard.py
from pathlib import Path
import json

DASHBOARD_FILE = Path("dashboard.html")

def generate_dashboard_html(pending_actions,
                            flagged_items,
                            commitments,
                            digest_data,
                            other_data,
                            x4_resolutions):
    """
    Generate a simple HTML dashboard summarizing inbox state.
    Arguments:
      pending_actions: list of dicts with msg_id, action, reason
      flagged_items: list of dicts with msg_id, threat, action_taken
      commitments: list of dicts with datetime, desc, sources, notes/conflict
      digest_data: dict with counts and sample messages
      other_data: placeholder for future sections
      x4_resolutions: list of dicts with conflict, action, status
    """
    html_parts = []
    html_parts.append("<html><head><title>Inbox Dashboard</title></head><body>")
    html_parts.append("<h1>Inbox Dashboard</h1>")

    # Pending actions
    html_parts.append("<h2>Pending Actions</h2><ul>")
    for item in pending_actions:
        html_parts.append(f"<li>[{item['msg_id']}] {item['action']} — {item['reason']}</li>")
    html_parts.append("</ul>")

    # Flagged items
    html_parts.append("<h2>Flagged Items</h2><ul>")
    for item in flagged_items:
        html_parts.append(f"<li>[{item['msg_id']}] Threat: {item['threat']} — Action: {item['action_taken']}</li>")
    html_parts.append("</ul>")

    # Commitments
    html_parts.append("<h2>Commitments</h2><ul>")
    for c in commitments:
        conflict_note = " (Conflict)" if c.get("conflict") else ""
        html_parts.append(f"<li>{c['datetime']}: {c['desc']}{conflict_note} — Sources: {', '.join(c['sources'])} — Notes: {c.get('notes','')}</li>")
    html_parts.append("</ul>")

    # Digest
    html_parts.append("<h2>Digest</h2>")
    html_parts.append(f"<p>Auto-archived: {digest_data.get('archived',0)}</p>")
    needs_me = digest_data.get("needs_me", [])
    if needs_me:
        html_parts.append("<p>Needs Your Attention:</p><ul>")
        for m in needs_me:
            html_parts.append(f"<li>[{m.get('id')}] {m.get('from')}: {m.get('subject')}</li>")
        html_parts.append("</ul>")

    # X4 resolutions
    html_parts.append("<h2>Conflict Resolutions (X4)</h2><ul>")
    for r in x4_resolutions:
        html_parts.append(f"<li>{r['conflict']} — {r['action']} — Status: {r['status']}</li>")
    html_parts.append("</ul>")

    html_parts.append("</body></html>")

    DASHBOARD_FILE.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"[DASHBOARD] Written to {DASHBOARD_FILE}")
