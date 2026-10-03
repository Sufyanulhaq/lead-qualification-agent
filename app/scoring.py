"""Turns a captured lead into a score from 0 to 100 and says why. Every point comes from a visible
rule, so a salesperson can see the reason and the rules can be changed in one place."""
from __future__ import annotations

from dataclasses import dataclass, field

HOT = 70
WARM = 45


@dataclass
class Score:
    total: int
    label: str
    reasons: list[str] = field(default_factory=list)


def _fit(services: list[str]) -> tuple[int, str]:
    if len(services) >= 2:
        return 25, f"clear need across {len(services)} areas ({', '.join(services)})"
    if len(services) == 1:
        return 18, f"clear need: {services[0]}"
    return 5, "need is vague"


def _budget(amount: float | None, unknown: bool) -> tuple[int, str]:
    if amount is None:
        return 8, "budget not stated" if unknown else "budget not given"
    for floor, points in ((5000, 30), (2000, 24), (1000, 18), (500, 10)):
        if amount >= floor:
            return points, f"budget of {amount:,.0f}"
    return 4, f"small budget of {amount:,.0f}"


def _timeline(months: float | None, unknown: bool) -> tuple[int, str]:
    if months is None:
        return 8, "no timeline given" if not unknown else "timeline is open"
    if months <= 1:
        return 25, "wants to start within a month"
    if months <= 3:
        return 15, "wants to start within three months"
    return 6, "timeline is more than three months away"


def _contact(email: str | None, company: str | None, name: str | None) -> tuple[int, str]:
    points = (12 if email else 0) + (4 if company else 0) + (4 if name else 0)
    missing = [n for n, v in (("email", email), ("company", company), ("name", name)) if not v]
    return points, "full contact details" if not missing else "missing " + ", ".join(missing)


def score_lead(fields: dict) -> Score:
    parts = [
        _fit(fields.get("services", [])),
        _budget(fields.get("budget_amount"), bool(fields.get("budget_unknown"))),
        _timeline(fields.get("timeline_months"), bool(fields.get("timeline_unknown"))),
        _contact(fields.get("email"), fields.get("company"), fields.get("name")),
    ]
    total = sum(p for p, _ in parts)
    label = "Hot" if total >= HOT else "Warm" if total >= WARM else "Cold"
    reasons = [r for _, r in parts]
    if not fields.get("email") and label != "Cold":
        # Nobody can follow up a lead they cannot reach, however good the rest looks.
        label = "Cold"
        reasons.append("held at Cold because there is no email to follow up on")
    return Score(total, label, reasons)
