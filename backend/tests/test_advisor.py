import os
os.environ["LLM_MODE"] = "off"  # rules-only: tests must not depend on a running model

from app import advisor
from app.advisor import answer, build_quote, start
from app.db import load_session


def run(chips):
    r = start("en")
    s = load_session(r["session_id"])
    for slot, value in chips:
        assert r["question"]["slot"] == slot, (slot, r["question"])
        r = answer(s, slot=slot, value=value)
        s = load_session(r["session_id"])
    return r, s


def test_chip_journey_reaches_quote():
    r, s = run([("segment", "prof"), ("needs", ["cctv"]), ("city", "Kochi"), ("employees", "10"), ("sites", "1"),
                ("internet", "home_broadband"), ("gst", "gst"), ("spend", "3500")])
    assert r["done"] and s["done"]
    q = build_quote(s)
    assert q["segment"] == "prof" and q["totals"]["monthly"] > 0
    assert any(l["product_id"] == "P23" and l["selected"] for l in q["lines"])
    assert q["sell"]["saving_year"] > 0 and len(q["tiers"]) >= 2


def test_pain_question_comes_second_and_fits_the_business():
    r = start("en")
    s = load_session(r["session_id"])
    assert r["preview"] is None and r["left"] == 8
    r = answer(s, slot="segment", value="mfg")
    assert r["question"]["slot"] == "needs"
    assert {"iot", "fleet"} <= {c["value"] for c in r["question"]["chips"]}
    assert r["preview"]["monthly"] > 0 and r["preview"]["items"]  # the pack starts building straight away


def test_internet_keeps_dropping_adds_backup_link():
    r, s = run([("segment", "micro"), ("needs", ["uptime", "bills"]), ("city", "Pune"), ("employees", "3"),
                ("internet", "mobile_hotspot"), ("gst", "none"), ("spend", "1500")])
    q = build_quote(s)
    assert any(l["product_id"] == "P09" and l["selected"] for l in q["lines"])


def test_micro_skips_sites_question():
    r = start("en")
    s = load_session(r["session_id"])
    r = answer(s, slot="segment", value="micro")
    s = load_session(r["session_id"])
    r = answer(s, slot="needs", value=["pos"])
    s = load_session(r["session_id"])
    r = answer(s, slot="city", value="Ludhiana")
    assert r["question"]["slot"] == "employees"
    s = load_session(r["session_id"])
    r = answer(s, slot="employees", value="3")
    assert r["question"]["slot"] == "internet"  # sites auto = 1


def test_free_text_fills_many_slots_offline():
    r = start("en")
    s = load_session(r["session_id"])
    r = answer(s, text="I run a bakery in Ludhiana, 3 people work here")
    p = r["profile"]
    assert p["city"] == "Ludhiana" and p["employees"] == 3 and p["segment"] == "micro"
    assert r["question"]["slot"] == "needs"
    assert r["left"] == 4  # needs, internet, gst, spend


def test_two_unintelligible_answers_create_handoff():
    from app.db import list_handoffs
    r = start("en")
    s = load_session(r["session_id"])
    r = answer(s, text="hmm")
    s = load_session(r["session_id"])
    r = answer(s, text="not sure")
    assert any(h["session_id"] == s["id"] and h["reason"] == "advisor_stuck" for h in list_handoffs())


def test_wants_human_creates_handoff():
    from app.db import list_handoffs
    r = start("en")
    s = load_session(r["session_id"])
    answer(s, text="I want to talk to a person")
    assert any(h["session_id"] == s["id"] and h["reason"] == "wants_human" for h in list_handoffs())


def test_unknown_city_flags_partner_check():
    r, s = run([("segment", "micro"), ("needs", []), ("city", "Shimla"), ("employees", "3"), ("internet", "none"),
                ("gst", "none"), ("spend", "1500")])
    from app.db import list_handoffs
    assert any(h["session_id"] == s["id"] and h["reason"] == "city_unverified" for h in list_handoffs())


def test_explanation_template_when_llm_off():
    r, s = run([("segment", "prof"), ("needs", []), ("city", "Kochi"), ("employees", "10"), ("sites", "1"),
                ("internet", "home_broadband"), ("gst", "gst"), ("spend", "3500")])
    e = advisor.explanation(s)
    assert e["source"] == "template" and "₹" in e["text"]


def test_model_guess_about_internet_is_dropped_unless_owner_mentioned_it(monkeypatch):
    guess = {"business_type": "dental clinic", "city": "Pune", "current_internet": "business_broadband"}
    monkeypatch.setattr(advisor.llm, "extract_profile", lambda text, slot: dict(guess))
    data, _ = advisor.understand("मेरा पुणे में एक डेंटल क्लिनिक है, 12 लोग काम करते हैं।", None)
    assert data["current_internet"] is None and data["city"] == "Pune"
    for said in ["हमारे पास ब्रॉडबैंड है", "we use airtel fibre", "मेरे पास इंटरनेट है"]:
        assert advisor.understand(said, None)[0]["current_internet"] == "business_broadband", said
    assert advisor.understand("the first one", "internet")[0]["current_internet"] == "business_broadband"
