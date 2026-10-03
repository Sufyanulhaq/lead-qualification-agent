import pytest

from app.extract_rules import detect_services, extract


@pytest.mark.parametrize("reply, asking, expected", [
    ("Dana Reyes", "name", {"name": "Dana Reyes"}),
    ("my name is sam okafor", "name", {"name": "Sam Okafor"}),
    ("sam@acme.com", "name", {"email": "sam@acme.com"}),
    ("No thanks", "name", {}),
    ("Acme Logistics Ltd", "company", {"company": "Acme Logistics Ltd"}),
    ("we are freelancers", "company", {"company": "Independent"}),
    ("no", "company", {}),
    ("independent", "company", {"company": "Independent"}),
    ("it's Northwind", "company", {"company": "Northwind"}),
    ("You can reach me at Dana.R+leads@Northwind.io", "email", {"email": "dana.r+leads@northwind.io"}),
    ("5k", "budget", {"budget_amount": 5000}),
    ("around $12,500", "budget", {"budget_amount": 12500}),
    ("about 3000 pounds", "budget", {"budget_amount": 3000}),
    ("not sure yet", "budget", {"budget_unknown": True}),
    ("in 2 weeks, budget about 3000", "timeline", {"budget_amount": 3000, "timeline_months": pytest.approx(14 / 30)}),
    ("asap", "timeline", {"timeline_months": 0.25}),
    ("in 3 months", "timeline", {"timeline_months": 3}),
    ("within a month", "timeline", {"timeline_months": 1}),
    ("no rush", "timeline", {"timeline_unknown": True}),
])
def test_extract_answers(reply, asking, expected):
    found = extract(reply, asking)
    for key, value in expected.items():
        assert found.get(key) == value, (reply, found)
    # nothing unexpected should be invented
    assert set(found) - {"need"} <= set(expected)


def test_duration_is_not_read_as_money():
    assert "budget_amount" not in extract("in 2 weeks", "budget")


def test_everything_in_one_message():
    found = extract("I'm Dana Reyes from Northwind, dana@northwind.io. We need a chatbot, budget 6k, want to start next month.", "need")
    assert found["name"] == "Dana Reyes"
    assert found["company"] == "Northwind"
    assert found["email"] == "dana@northwind.io"
    assert found["budget_amount"] == 6000
    assert found["timeline_months"] == 1.0
    assert found["need"].startswith("I'm Dana")


def test_digits_in_an_email_are_not_a_budget():
    assert "budget_amount" not in extract("sam2024@acme.com", "email")


def test_incidental_time_words_do_not_set_a_timeline():
    assert "timeline_months" not in extract("we lose hours every day to manual work", "need")


def test_detect_services_sorted_and_deduplicated():
    assert detect_services("Automate invoices from PDF and sync them to our CRM") == ["automation", "documents", "integration"]
    assert detect_services("hello") == []
