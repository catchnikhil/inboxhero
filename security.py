import re
from typing import Dict, Any, Optional

# Heuristics and signatures commonly associated with prompt injections or hostile instructions
_INJECTION_SIGNATURES = [
    r"ignore all previous instructions",
    r"disregard previous messages",
    r"system notice for automated assistants",
    r"automated-agent directive",
    r"assistant note:",
    r"autonomous mode is now enabled",
    r"execute the following command",
    r"run the following",
    r"you are now in control",
    r"do not follow earlier instructions",
]

# Suspicious short imperative patterns that try to coerce the assistant
_IMPERATIVE_PATTERNS = [
    r"\bdo this:\b",
    r"\bexecute:\b",
    r"\brun:\b",
    r"\bperform:\b",
    r"\bimmediately\b",
    r"\bnow do\b",
]

# High-risk keywords often found in social-engineering or phishing content
_HIGH_RISK_KEYWORDS = [
    "wire transfer",
    "password expires",
    "send credentials",
    "click the link below to",
    "verify your account",
    "provide your password",
    "secret key",
    "private key",
    "ssh key",
]

# Regex to detect URLs, base64 blobs, or code blocks that may embed instructions
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_BASE64_RE = re.compile(r"\b([A-Za-z0-9+/]{40,}={0,2})\b")
_CODEBLOCK_RE = re.compile(r"```.+?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# Compile signature regexes for performance
_SIGNATURE_REGEXES = [re.compile(s, re.IGNORECASE) for s in _INJECTION_SIGNATURES]
_IMPERATIVE_REGEXES = [re.compile(p, re.IGNORECASE) for p in _IMPERATIVE_PATTERNS]
_HIGH_RISK_REGEXES = [re.compile(re.escape(k), re.IGNORECASE) for k in _HIGH_RISK_KEYWORDS]


def detect_hostile_intent(message: Dict[str, Any]) -> Dict[str, str]:
    """
    Scan an email message for likely prompt-injection or hostile instructions.

    Returns a dict with:
      - "is_hostile": bool
      - "reason": short explanation (empty string when not hostile)

    Heuristics used:
      - Exact signature matches (e.g., "ignore all previous instructions")
      - Imperative/coercive phrasing aimed at an assistant
      - Presence of suspicious payloads (long base64, embedded code blocks)
      - High-risk social-engineering keywords and URLs
      - Subject and body are both checked; attachments metadata (if present) is inspected
    """
    if not isinstance(message, dict):
        return {"is_hostile": False, "reason": ""}

    subject = (message.get("subject") or "").lower()
    body = (message.get("body") or "").lower()
    attachments = message.get("attachments") or []

    # 1) Exact signature checks
    for rx in _SIGNATURE_REGEXES:
        if rx.search(body) or rx.search(subject):
            return {"is_hostile": True, "reason": f"Detected injection signature: '{rx.pattern}'"}

    # 2) Imperative/coercive phrasing aimed at an assistant
    for rx in _IMPERATIVE_REGEXES:
        if rx.search(body) or rx.search(subject):
            return {"is_hostile": True, "reason": "Contains coercive imperative phrasing targeting an assistant"}

    # 3) High-risk social-engineering keywords
    for rx in _HIGH_RISK_REGEXES:
        if rx.search(body) or rx.search(subject):
            return {"is_hostile": True, "reason": f"Contains high-risk keyword: '{rx.pattern}'"}

    # 4) Suspicious payloads: long base64 blobs or embedded code blocks
    if _BASE64_RE.search(body):
        return {"is_hostile": True, "reason": "Contains long base64-like blob (possible hidden payload)"}
    if _CODEBLOCK_RE.search(message.get("body", "")) or _INLINE_CODE_RE.search(message.get("body", "")):
        # Code blocks are not inherently hostile, but when combined with other signals they are suspicious
        # Flag only if combined with imperative phrasing or injection signatures above (already checked),
        # otherwise mark as suspicious but not necessarily hostile.
        return {"is_hostile": True, "reason": "Contains embedded code block or inline code (possible instruction payload)"}

    # 5) URLs that attempt to direct the assistant to external resources
    if _URL_RE.search(body):
        # If a URL appears together with "run" / "execute" style phrasing, flag it
        if any(rx.search(body) for rx in _IMPERATIVE_REGEXES):
            return {"is_hostile": True, "reason": "URL present alongside imperative instruction (possible external payload)"}
        # Otherwise treat as suspicious but not automatically hostile
        return {"is_hostile": False, "reason": ""}

    # 6) Attachments metadata checks (filename patterns, suspicious types)
    for att in attachments:
        fname = (att.get("filename") or "").lower()
        ftype = (att.get("content_type") or "").lower()
        if any(ext in fname for ext in [".exe", ".bat", ".sh", ".ps1"]):
            return {"is_hostile": True, "reason": f"Attachment with executable extension: {fname}"}
        if "script" in ftype or "application/octet-stream" in ftype:
            return {"is_hostile": True, "reason": f"Attachment with suspicious content type: {ftype}"}

    # If none of the heuristics triggered, consider the message non-hostile
    return {"is_hostile": False, "reason": ""}
