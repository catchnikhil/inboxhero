import re
from typing import Dict, Any, Optional

# Rule categories and keywords
BILLING_SENDERS = {"receipts@", "billing@", "orders@", "invoice@"}
BILLING_SUBJECT_KEYWORDS = {"receipt", "invoice", "order confirmed", "bill"}
AUTOMATED_SENDERS = {"no-reply@", "noreply@", "notifications@", "alerts@"}
CALENDAR_SENDERS = {"calendar-notification@google.com", "calendly.com"}
NEWSLETTER_SUBJECT_KEYWORDS = {"digest", "newsletter"}
NEWSLETTER_BODY_KEYWORDS = {"unsubscribe"}

# Precompiled regex for faster repeated checks
RE_SECURITY_KEYWORDS = re.compile(r"\b(password|verification|login|security|new sign[- ]?in)\b", re.I)


def triage_by_rules(message: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Evaluate a message against deterministic rules.

    Returns:
      - A dict {"disposition": <str>, "reason": <str>} when a rule matches.
      - None when no deterministic rule applies (LLM required).

    Rules implemented (in priority order):
      1. Receipts / invoices / order confirmations -> archive
      2. Automated system notifications (no-reply) -> archive, but keep security-related alerts
      3. Newsletters / digests -> archive
      4. Calendar reminders -> archive
    """
    if not isinstance(message, dict):
        return None

    sender = (message.get("from") or "").lower()
    subject = (message.get("subject") or "").lower()
    body = (message.get("body") or "").lower()

    # Helper: contains any of the substrings in the set
    def _contains_any(text: str, keywords: set) -> bool:
        return any(k in text for k in keywords)

    # 1) Receipts and invoices (by sender or subject)
    if _contains_any(sender, BILLING_SENDERS) or _contains_any(subject, BILLING_SUBJECT_KEYWORDS):
        return {"disposition": "archive", "reason": "Rule match: Automated receipt / billing"}

    # 2) Automated system notifications (no-reply style)
    if _contains_any(sender, AUTOMATED_SENDERS):
        # If the notification appears to be a security-related alert, do not auto-archive
        if not RE_SECURITY_KEYWORDS.search(subject) and not RE_SECURITY_KEYWORDS.search(body):
            return {"disposition": "archive", "reason": "Rule match: Automated system notification"}

    # 3) Newsletters and digests (subject or body signals)
    if _contains_any(subject, NEWSLETTER_SUBJECT_KEYWORDS) or _contains_any(sender, {"newsletter", "news@"}) or any(k in body for k in NEWSLETTER_BODY_KEYWORDS):
        return {"disposition": "archive", "reason": "Rule match: Newsletter / digest"}

    # 4) Calendar reminders (explicit senders)
    if _contains_any(sender, CALENDAR_SENDERS):
        return {"disposition": "archive", "reason": "Rule match: Calendar auto-reminder"}

    # No deterministic rule matched
    return None
