from app.conversation import FINISHED, GREETING, MAX_TRIES, Session, handle_message
from app.extract_rules import extract


def run(session, *replies):
    out = []
    for r in replies:
        out.append(handle_message(session, r, extract))
    return out


def test_happy_path_asks_each_question_once_in_order():
    s = Session()
    steps = run(s, "I want a chatbot that answers customer support questions", "Dana Reyes", "Northwind", "dana@northwind.io", "6000", "next month")
    replies = [r for r, _ in steps]
    assert "Who am I speaking with" in replies[0]
    assert "Which company" in replies[1] and "Dana" in replies[1]
    assert "email" in replies[2]
    assert "budget" in replies[3]
    assert "start" in replies[4]
    final, score = steps[-1]
    assert score is not None and s.done
    assert score.label in {"Hot", "Warm"}
    assert s.fields["email"] == "dana@northwind.io"


def test_volunteered_details_are_not_asked_again():
    s = Session()
    reply, score = handle_message(s, "I'm Dana Reyes from Northwind, dana@northwind.io, need a CRM integration, budget 5k, start in 2 weeks", extract)
    assert score is not None and s.done
    assert "Thank you" in reply


def test_unclear_answer_is_asked_again_then_skipped():
    s = Session()
    run(s, "automate our invoices")
    first, _ = handle_message(s, "No thanks", extract)
    assert "did not catch your name" in first
    second, _ = handle_message(s, "No thanks", extract)
    assert "Which company" in second  # moved on after MAX_TRIES
    assert "name" in s.skipped and MAX_TRIES == 2


def test_lead_with_skipped_details_still_finishes_and_is_scored():
    s = Session()
    out = run(s, "automate our invoices", *["no"] * 10)
    scores = [sc for _, sc in out if sc is not None]
    assert len(scores) == 1 and scores[0].label == "Cold"
    assert "did not get an email" in [r for r, sc in out if sc][0]


def test_no_email_means_no_promise_of_a_follow_up():
    s = Session()
    out = run(s, "automate our invoices and sync them to our CRM", "Sam Lee", "Acme", "no", "no", "8000", "asap")
    reply, score = [o for o in out if o[1]][0]
    assert score.label == "Cold" and "no email to follow up on" in score.reasons[-1]
    assert "no way for the team to reply" in reply and "follow up with you" not in reply


def test_company_question_does_not_say_hello_to_nobody():
    s = Session()
    run(s, "build a dashboard", "no")
    reply, _ = handle_message(s, "no", extract)
    assert reply == "Which company is this for?"


def test_a_corrected_email_replaces_the_first_one():
    s = Session()
    run(s, "build a dashboard", "Sam Lee", "Acme", "sam@acm.com")
    handle_message(s, "sorry, typo, it is sam@acme.com", extract)
    assert s.fields["email"] == "sam@acme.com"


def test_messages_after_the_end_do_nothing():
    s = Session()
    run(s, "chatbot please", "Sam Lee", "Acme", "sam@acme.com", "2000", "asap")
    assert s.done
    reply, score = handle_message(s, "hello again", extract)
    assert reply == FINISHED and score is None


def test_greeting_asks_the_first_question():
    assert GREETING.endswith("What are you looking to build or automate?")
