"""Offline understanding of a visitor's reply. Plain pattern matching, so the demo runs with no
API key. It reads whatever the visitor volunteered, not only the answer to the last question."""
from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NOT_A_NAME = {
    "looking", "interested", "trying", "wanting", "hoping", "planning", "thinking", "building",
    "here", "just", "a", "an", "the", "from", "at", "with", "not", "so", "really", "very", "new",
    "in", "on", "for", "to", "after", "needing", "wondering", "currently",
}
REFUSAL = re.compile(r"^(no|nope|none|skip|why|not|rather|prefer|n/?a)\b", re.I)
UNKNOWN_WORDS = re.compile(r"\b(not sure|no idea|don'?t know|flexible|depends|open|no budget|no rush|whenever|exploring|tbd)\b", re.I)
WORD_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
TIME_UNIT = r"(?:day|week|month|year|hour)s?"

SERVICES = {
    "chatbot": ("chatbot", "chat bot", "assistant", "support bot", "customer support"),
    "automation": ("automate", "automation", "workflow", "n8n", "zapier", "repetitive", "manual"),
    "integration": ("integrat", "api", "webhook", "connect", "crm", "sync"),
    "web app": ("web app", "website", "dashboard", "portal", "saas", "mvp", "admin panel", "platform"),
    "documents": ("pdf", "document", "invoice", "contract"),
    "email": ("email", "inbox"),
    "data": ("scrap", "spreadsheet", "report", "etl", "data pipeline"),
}


def detect_services(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(tag for tag, words in SERVICES.items() if any(w in lowered for w in words))


def _title(words: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in words.split())


def _name(message: str, asking: str) -> str | None:
    explicit = re.search(r"(?:my name is|name's|call me|this is)\s+([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){0,2})", message, re.I)
    if explicit:
        words = explicit.group(1).split()
        if words[0].lower() not in NOT_A_NAME:
            return _title(" ".join(words))
    capitalised = re.search(r"\b(?:I'm|I am)\s+([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2})", message)
    if capitalised and capitalised.group(1).split()[0].lower() not in NOT_A_NAME:
        return capitalised.group(1)
    if asking == "name":
        cleaned = re.sub(r"[^\w\s'-]", "", message).strip()
        if cleaned and len(cleaned.split()) <= 4 and not re.search(r"\d", cleaned) and not REFUSAL.match(cleaned):
            return _title(cleaned)
    return None


def _company(message: str, asking: str) -> str | None:
    if asking == "company":
        text = re.sub(r"^(it'?s|its|we are|we're|i work (?:at|for)|i'm (?:at|with)|company is|called)\s+", "", message.strip(), flags=re.I)
        text = text.strip(" .!")
        if re.fullmatch(r"(none|n/?a|freelance\w*|self[- ]employed|myself|no company|independent)", text, re.I):
            return "Independent"
        if text and len(text.split()) <= 5 and not REFUSAL.match(text):
            return text
        return None
    found = re.search(r"\b(?:at|from|work for|work at|company is|called)\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})", message)
    return found.group(1) if found else None


def _budget(message: str, asking: str) -> tuple[float | None, bool]:
    has_money_cue = bool(re.search(r"[$£€]|\bbudget\b|\busd\b|\bgbp\b|\beur\b|dollars|pounds|euros|\d\s?k\b", message, re.I))
    if asking != "budget" and not has_money_cue:
        return None, False
    # A number followed by a time unit is a duration, not money ("in 2 weeks").
    for match in re.finditer(rf"[$£€]?\s?(\d[\d,]*(?:\.\d+)?)\s*(k\b|thousand\b)?(?!\s*{TIME_UNIT}\b)", message, re.I):
        amount = float(match.group(1).replace(",", ""))
        if match.group(2):
            amount *= 1000
        if amount > 0:
            return amount, False
    if UNKNOWN_WORDS.search(message) or (asking == "budget" and re.search(r"\b(none|zero|nothing)\b", message, re.I)):
        return None, True
    return None, False


def _timeline(message: str, asking: str) -> tuple[float | None, bool]:
    text = message.lower()
    cue = re.search(r"\b(start|begin|launch|live|deadline|deliver|ready|within|asap|urgent|need it|need this|by next|by the end)\b", text)
    if asking != "timeline" and not cue:
        return None, False
    if re.search(r"\b(asap|immediately|urgent|right away|today|tomorrow|this week|next week)\b", text):
        return 0.25, False
    if "this month" in text:
        return 0.5, False
    if "next month" in text:
        return 1.0, False
    unit = re.search(rf"\b(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six)\s*({TIME_UNIT})\b", text)
    if unit:
        raw = unit.group(1)
        n = float(WORD_NUMBERS.get(raw, raw))
        return {"day": n / 30, "week": n * 7 / 30, "month": n, "year": n * 12, "hour": 0.0}[unit.group(2).rstrip("s")], False
    if re.search(r"\b(couple of months|few months|end of (?:the )?year|next quarter)\b", text):
        return 3.0, False
    if UNKNOWN_WORDS.search(text) and asking == "timeline":
        return None, True
    return None, False


def extract(message: str, asking: str) -> dict:
    """Return only what was found. Missing keys mean the message did not say."""
    out: dict = {}
    email = EMAIL.search(message)
    if email:
        out["email"] = email.group(0).lower()
    body = EMAIL.sub(" ", message).strip()
    name = _name(body, asking)
    if name:
        out["name"] = name
    company = _company(body, asking)
    if company:
        out["company"] = company
    if asking == "need":
        out["need"] = message.strip()[:400]
    amount, budget_unknown = _budget(body, asking)
    if amount is not None:
        out["budget_amount"] = amount
    if budget_unknown:
        out["budget_unknown"] = True
    months, timeline_unknown = _timeline(body, asking)
    if months is not None:
        out["timeline_months"] = months
    if timeline_unknown:
        out["timeline_unknown"] = True
    return out
