"""The conversation itself: which question comes next, when to stop and what to say. The replies are
templated on purpose. The AI part of this project is understanding free text answers, not
improvising, so the assistant stays on topic and never promises anything the business has not."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable

from .extract_rules import detect_services
from .scoring import Score, score_lead

STEPS = ["need", "name", "company", "email", "budget", "timeline"]
MAX_TRIES = 2

QUESTIONS = {
    "need": "What are you looking to build or automate?",
    "name": "Thanks, that helps. Who am I speaking with?",
    "company": "Nice to meet you, {name}. Which company is this for?",
    "email": "What is the best email address to reach you on?",
    "budget": "Roughly what budget do you have in mind? A ballpark is fine, or say you are not sure.",
    "timeline": "And when would you like to get started?",
}
RETRY = {
    "need": "Could you tell me a little more about what you want to build or automate?",
    "name": "Sorry, I did not catch your name. What should I call you?",
    "company": "Which company or organisation is this for? You can say you are independent.",
    "email": "I could not find an email address in that. Could you type it out, like name@company.com?",
    "budget": "A rough number is enough, for example 3000 or 2k. Or say you are not sure yet.",
    "timeline": "For example: as soon as possible, in 2 weeks, or in 3 months. Or say there is no rush.",
}
GREETING = "Hi, I am the assistant for this site. I can work out quickly whether we are a good fit. " + QUESTIONS["need"]
NO_EMAIL = (
    "Thank you. I did not get an email address, so there is no way for the team to reply. "
    "If you would like a follow up, refresh the page and start again with an email."
)
FINISHED = "This conversation is finished and your details are saved. Refresh the page to start a new one."
CLOSING = {
    "Hot": "Thank you. This looks like a strong fit, so I have marked it as a priority for the team to follow up.",
    "Warm": "Thank you. I have passed your details to the team and someone will follow up with you.",
    "Cold": "Thank you. I have saved your details. If the plan firms up, reply here and we will pick it up.",
}


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    fields: dict = field(default_factory=dict)
    tries: dict = field(default_factory=dict)
    skipped: set = field(default_factory=set)
    done: bool = False
    lead_id: str | None = None

    def have(self, step: str) -> bool:
        if step == "budget":
            return "budget_amount" in self.fields or self.fields.get("budget_unknown", False)
        if step == "timeline":
            return "timeline_months" in self.fields or self.fields.get("timeline_unknown", False)
        return bool(self.fields.get(step))

    def next_step(self) -> str | None:
        for step in STEPS:
            if not self.have(step) and step not in self.skipped:
                return step
        return None


Extractor = Callable[[str, str], dict]


def handle_message(session: Session, message: str, extract: Extractor) -> tuple[str, Score | None]:
    """Advance the conversation by one visitor message. Returns the reply and, once the
    conversation is finished, the lead score."""
    if session.done:
        return FINISHED, None
    asking = session.next_step()
    if asking is None:
        session.done = True
        return FINISHED, None

    found = extract(message, asking)
    for key, value in found.items():
        if value in (None, "", False):
            continue
        # A later email or name is allowed to correct an earlier one. Other answers keep the first value.
        if key in ("email", "name") or key not in session.fields:
            session.fields[key] = value
    if "need" in session.fields:
        session.fields["services"] = detect_services(session.fields["need"])

    if not session.have(asking):
        session.tries[asking] = session.tries.get(asking, 0) + 1
        if session.tries[asking] >= MAX_TRIES:
            session.skipped.add(asking)
        else:
            return RETRY[asking], None

    upcoming = session.next_step()
    if upcoming == "company" and "name" not in session.fields:
        return "Which company is this for?", None
    if upcoming is not None:
        return QUESTIONS[upcoming].format(name=session.fields.get("name", "there").split()[0]), None

    score = score_lead(session.fields)
    session.done = True
    return (CLOSING[score.label] if session.fields.get("email") else NO_EMAIL), score
