from app.scoring import HOT, WARM, score_lead


def lead(**kw):
    base = {"services": ["chatbot"], "budget_amount": 3000, "timeline_months": 1, "email": "a@b.co", "company": "Acme", "name": "Sam"}
    base.update(kw)
    return base


def test_strong_lead_is_hot_and_explained():
    s = score_lead(lead(services=["chatbot", "integration"], budget_amount=8000, timeline_months=0.5))
    assert s.label == "Hot" and s.total >= HOT
    assert any("8,000" in r for r in s.reasons)
    assert len(s.reasons) == 4


def test_middle_lead_is_warm():
    s = score_lead(lead(budget_amount=800, timeline_months=2))
    assert s.label == "Warm" and WARM <= s.total < HOT


def test_vague_lead_with_no_details_is_cold():
    s = score_lead({"services": [], "budget_unknown": True, "timeline_unknown": True})
    assert s.label == "Cold" and s.total < WARM
    assert "missing email, company, name" in s.reasons[-1]


def test_missing_email_costs_the_most_contact_points():
    with_email = score_lead(lead()).total
    without = score_lead(lead(email=None)).total
    assert with_email - without == 12


def test_score_is_never_above_100():
    assert score_lead(lead(services=["a", "b", "c"], budget_amount=1e9, timeline_months=0)).total <= 100


def test_a_strong_lead_with_no_email_is_held_at_cold():
    s = score_lead(lead(services=["chatbot", "integration"], budget_amount=8000, timeline_months=0.5, email=None))
    assert s.total >= WARM and s.label == "Cold"
    assert s.reasons[-1] == "held at Cold because there is no email to follow up on"
