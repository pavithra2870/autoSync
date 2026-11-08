"""Conversation flow. The LLM understands what the owner typed; code decides what to ask next,
which bundle to offer and what it costs."""
import re
import uuid
from dataclasses import asdict

from . import db, i18n, llm, value
from .catalogue import Profile, catalogue
from .data import cities, find_city
from .recommender import quote
from .segments import derive_segment, segment_from_text

# Business first, then what is bothering them (so the plan can answer it), then the practical details.
SLOTS = ["segment", "needs", "city", "employees", "sites", "internet", "gst", "spend"]
INTERNET = ["business_broadband", "home_broadband", "mobile_hotspot", "leased_line", "mixed_per_site", "none"]
INTERNET_LABEL = {"business_broadband": "net.business", "home_broadband": "net.home", "mobile_hotspot": "net.hotspot",
                  "leased_line": "net.leased", "mixed_per_site": "net.mixed", "none": "net.none"}
# The needs question is asked as "what is troubling you?" with problems that fit the kind of business.
PAINS = {
    "micro": ["uptime", "pos", "cctv", "whatsapp", "website", "bills"],
    "prof": ["uptime", "security", "phone", "whatsapp", "website", "bills"],
    "multi": ["uptime", "pos", "cctv", "security", "whatsapp", "bills"],
    "mfg": ["uptime", "security", "cctv", "iot", "fleet", "bills"],
}
NEEDS = ["uptime", "pos", "cctv", "whatsapp", "website", "security", "phone", "bills"]
ALL_NEEDS = NEEDS + ["backup", "iot", "fleet"]
EMP_CHIPS = [("3", "1–5"), ("10", "6–15"), ("30", "16–50"), ("80", "51+")]
SITE_CHIPS = [("1", "1"), ("2", "2"), ("4", "3–5"), ("8", "6–10"), ("12", "10+")]
SPEND_CHIPS = [("1500", "Under ₹2,000"), ("3500", "₹2,000–5,000"), ("10000", "₹5,000–15,000"), ("25000", "Over ₹15,000")]


# ------------------------------------------------------------------------------------------
# session helpers
# ------------------------------------------------------------------------------------------
def new_session(lang: str) -> dict:
    return {"id": uuid.uuid4().hex[:12], "lang": lang, "profile": asdict(Profile(language=lang)), "asked": [],
            "current": None, "fails": 0, "selections": None, "contract": None, "explanation": None,
            "gst_verified": None, "kyc": None, "order_id": None, "done": False}


def profile_of(s: dict) -> Profile:
    return Profile(**s["profile"])


def _store(s: dict, p: Profile) -> None:
    s["profile"] = asdict(p)


def refresh_derived(p: Profile) -> None:
    c = find_city(p.city) if p.city else None
    if c:
        p.city, p.city_tier, p.state, p.city_verified = c["name"], c["tier"], c["state"], True
    p.segment = derive_segment(p.business_type, p.segment_hint, p.employees, p.sites)
    if p.segment == "micro" and p.sites is None:
        p.sites = 1  # every micro business in the data is a single shop


def _needed(p: Profile, s: dict) -> list[str]:
    out = []
    if p.segment is None and p.segment_hint is None and segment_from_text(p.business_type) is None:
        out.append("segment")
    if "needs" not in s["asked"]:
        out.append("needs")
    if p.city is None:
        out.append("city")
    if p.employees is None:
        out.append("employees")
    if p.sites is None:
        out.append("sites")
    if p.current_internet is None and "internet" not in s["asked"]:
        out.append("internet")
    if p.has_gstin is None:
        out.append("gst")
    if "spend" not in s["asked"]:
        out.append("spend")
    return out


# ------------------------------------------------------------------------------------------
# questions
# ------------------------------------------------------------------------------------------
def question(slot: str, lang: str, segment: str | None = None) -> dict:
    T = lambda k, **kw: i18n.t(lang, k, **kw)  # noqa: E731
    q = {"slot": slot, "text": T(f"q.{ 'internet' if slot == 'internet' else slot}"), "multi": False,
         "skippable": slot in ("needs", "spend", "internet"), "chips": []}
    if slot == "segment":
        q["chips"] = [{"value": k, "label": T(f"seg.{k}")} for k in ("micro", "prof", "multi", "mfg")]
    elif slot == "city":
        q["chips"] = [{"value": c["name"], "label": c["name"]} for c in list(cities().values())[:8]]
    elif slot == "employees":
        q["chips"] = [{"value": v, "label": l} for v, l in EMP_CHIPS]
    elif slot == "sites":
        q["chips"] = [{"value": v, "label": l} for v, l in SITE_CHIPS]
    elif slot == "internet":
        q["chips"] = [{"value": k, "label": T(INTERNET_LABEL[k])} for k in INTERNET]
    elif slot == "gst":
        q["chips"] = [{"value": k, "label": T(f"gst.{k}")} for k in ("yes", "udyam", "none")]
        q["chips"][0]["value"] = "gst"
    elif slot == "needs":
        q["multi"] = True
        q["chips"] = [{"value": k, "label": T(f"pain.{k}")} for k in PAINS.get(segment or "", NEEDS[:6])]
    elif slot == "spend":
        q["chips"] = [{"value": v, "label": l} for v, l in SPEND_CHIPS]
    return q


# ------------------------------------------------------------------------------------------
# understanding answers
# ------------------------------------------------------------------------------------------
def _to_int(v, lo, hi):
    try:
        n = int(float(str(llm.ascii_digits(str(v))).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def extract_offline(text: str, slot: str | None) -> dict:
    """Rules-only understanding (English / Hinglish). Used when no LLM is running."""
    t = llm.ascii_digits(text).lower()
    out: dict = {"needs": []}
    nums = [int(n) for n in re.findall(r"\d+", t)]
    m = re.search(r"(\d+)\s*(people|persons|staff|employees|workers|log|members)", t)
    if m:
        out["employees"] = int(m.group(1))
    m = re.search(r"(\d+)\s*(shops?|stores?|outlets?|branches|locations?|sites?|units?|showrooms?)", t)
    if m:
        out["sites"] = int(m.group(1))
    if nums and slot == "employees" and "employees" not in out:
        out["employees"] = nums[0]
    if nums and slot == "sites" and "sites" not in out:
        out["sites"] = nums[0]
    if nums and slot == "spend":
        out["monthly_spend"] = nums[0] * (1000 if nums[0] < 200 else 1)
    c = find_city(t)
    if c:
        out["city"] = c["name"]
    elif slot == "city" and text.strip():
        out["city"] = text.strip().title()
    if slot in ("segment", None) and segment_from_text(t):
        out["business_type"] = t.strip()[:60]
    for key, words in {"mobile_hotspot": ["hotspot"], "leased_line": ["leased"], "home_broadband": ["home"],
                       "business_broadband": ["broadband", "fibre", "fiber", "wifi", "airtel"],
                       "none": ["no internet", "nothing"]}.items():
        if any(w in t for w in words):
            out["current_internet"] = key
            break
    if "no gst" in t or "without gst" in t:
        out["has_gstin"] = False
    elif "gst" in t:
        out["has_gstin"] = True
    if "udyam" in t:
        out["has_udyam"] = "no udyam" not in t
        if slot == "gst" and "gst" not in t:
            out["has_gstin"] = False
    for need, words in {"uptime": ["keeps going down", "goes down", "drops", "disconnect", "net problem", "slow internet"],
                        "bills": ["too many bills", "many bills"],
                        "cctv": ["cctv", "camera"], "whatsapp": ["whatsapp"], "pos": ["pos", "billing"],
                        "security": ["security", "antivirus"], "backup": ["backup"], "phone": ["ivr", "telephony"],
                        "website": ["website"], "iot": ["iot", "machine"], "fleet": ["fleet", "gps"]}.items():
        if any(w in t for w in words):
            out["needs"].append(need)
    out["wants_human"] = any(w in t for w in ["human", "talk to", "call me", "agent", "representative", "salesperson"])
    return out


NET_WORDS = re.compile(
    r"\b(internet|net|broadband|wi-?fi|fib(re|er)|hotspot|leased|data|jio|airtel|bsnl|vi)\b"
    r"|इंटरनेट|इन्टरनेट|ब्रॉडबैंड|ब्रॉडबैन्ड|वाई-?फ़ाई|वाई-?फाई|नेट|हॉटस्पॉट|डेटा|இணைய|இன்டர்நெட்|ইন্টারনেট|ఇంటర్నెట్|"
    r"ઇન્ટરનેટ|ಇಂಟರ್ನೆಟ್|ഇന്റർനെറ്റ്|ਇੰਟਰਨੈੱਟ|ਇੰਟਰਨੈਟ", re.I)


def understand(text: str, slot: str | None) -> tuple[dict, str]:
    data = llm.extract_profile(text, slot)
    if data is not None:
        # small models fill this field even when the owner said nothing about internet: keep it only if they did
        if slot != "internet" and not NET_WORDS.search(text):
            data["current_internet"] = None
        return data, "ai"
    return extract_offline(text, slot), "rules"


def merge(p: Profile, s: dict, data: dict) -> list[str]:
    """Apply extracted values; return the list of fields that changed."""
    changed = []
    bt = data.get("business_type")
    if isinstance(bt, str) and bt.strip():
        p.business_type = bt.strip()[:60]
        changed.append("business_type")
    city = data.get("city")
    if isinstance(city, str) and city.strip():
        c = find_city(city)
        if c:
            p.city = c["name"]
        else:
            p.city, p.city_tier, p.state, p.city_verified = city.strip().title()[:40], None, None, False
        changed.append("city")
    n = _to_int(data.get("employees"), 1, 5000)
    if n:
        p.employees = n
        changed.append("employees")
    n = _to_int(data.get("sites"), 1, 500)
    if n:
        p.sites = n
        changed.append("sites")
    if data.get("current_internet") in INTERNET:
        p.current_internet = data["current_internet"]
        changed.append("internet")
    for key in ("has_gstin", "has_udyam"):
        if isinstance(data.get(key), bool):
            setattr(p, key, data[key])
            changed.append("gst")
    n = _to_int(data.get("monthly_spend"), 100, 10_000_000)
    if n:
        p.monthly_spend = n
        changed.append("spend")
    needs = [x for x in (data.get("needs") or []) if x in ALL_NEEDS]
    if needs:
        p.needs = sorted(set(p.needs) | set(needs))
        changed.append("needs")
    return changed


def apply_chip(p: Profile, s: dict, slot: str, value) -> None:
    if slot == "segment":
        p.segment_hint = value
    elif slot == "city":
        merge(p, s, {"city": value})
    elif slot == "employees":
        p.employees = int(value)
    elif slot == "sites":
        p.sites = int(value)
    elif slot == "internet":
        p.current_internet = None if value == "skip" else value
        s["asked"].append("internet")
    elif slot == "gst":
        p.has_gstin = value == "gst"
        p.has_udyam = value in ("gst", "udyam")
    elif slot == "needs":
        vals = value if isinstance(value, list) else [value]
        p.needs = sorted(set(v for v in vals if v in ALL_NEEDS))
        s["asked"].append("needs")
    elif slot == "spend":
        p.monthly_spend = None if value == "skip" else int(value)
        s["asked"].append("spend")


def skip_slot(s: dict, slot: str) -> None:
    if slot in ("needs", "spend", "internet") and slot not in s["asked"]:
        s["asked"].append(slot)


# ------------------------------------------------------------------------------------------
# main entry points
# ------------------------------------------------------------------------------------------
def preview(p: Profile) -> dict | None:
    """The pack as it stands so far, shown live while the owner answers. None until we know the business."""
    if not p.segment:
        return None
    try:
        q = quote(p)
    except Exception:  # a half-filled profile must never break the conversation
        return None
    sel = [l for l in q["lines"] if l["selected"]]
    return {"monthly": q["totals"]["monthly"],
            "items": [{"id": l["product_id"], "why": l["why"], "qty": l["qty"]} for l in sel]}


def handoff(s: dict, p: Profile, reason: str) -> None:
    db.add_handoff(s["id"], reason, {"profile": asdict(p), "language": s["lang"]})


def _state_response(s: dict, p: Profile, msgs: list[str], mode: str) -> dict:
    lang = s["lang"]
    refresh_derived(p)
    need = _needed(p, s)
    resp = {"session_id": s["id"], "messages": [{"role": "bot", "text": m} for m in msgs], "mode": mode,
            "profile": asdict(p), "done": False, "question": None, "left": len(need), "total": len(SLOTS),
            "preview": preview(p)}
    if not need:
        s["done"] = True
        s["current"] = None
        resp["done"] = True
        resp["messages"].append({"role": "bot", "text": i18n.t(lang, "chat.done")})
        if not p.city_verified:
            resp["messages"].append({"role": "bot", "text": i18n.t(lang, "chat.city_unverified")})
            handoff(s, p, "city_unverified")
    else:
        s["current"] = need[0]
        resp["question"] = question(need[0], lang, p.segment)
    _store(s, p)
    db.save_session(s)
    return resp


def start(lang: str) -> dict:
    s = new_session(lang)
    p = profile_of(s)
    return _state_response(s, p, [i18n.t(lang, "chat.greeting")], "ai" if llm.available() else "rules")


def answer(s: dict, text: str | None = None, slot: str | None = None, value=None, skip: bool = False) -> dict:
    lang = s["lang"]
    p = profile_of(s)
    msgs: list[str] = []
    mode = "rules"
    current = s.get("current")

    if skip and current:
        skip_slot(s, current)
        s["fails"] = 0
    elif slot is not None and value is not None:
        apply_chip(p, s, slot, value)
        s["fails"] = 0
    elif text and text.strip():
        data, mode = understand(text.strip(), current)
        before = asdict(p)
        changed = merge(p, s, data)
        if current in ("needs", "spend", "internet") and current not in s["asked"] and (
                current in changed or current == "needs" and "needs" in changed):
            s["asked"].append(current)
        if data.get("wants_human") is True:
            handoff(s, p, "wants_human")
            msgs.append(i18n.t(lang, "chat.human"))
        refresh_derived(p)
        progressed = asdict(p) != before or current in s["asked"]
        if not progressed and not data.get("wants_human"):
            s["fails"] += 1
            msgs.append(i18n.t(lang, "chat.retry"))
            if s["fails"] >= 2:
                handoff(s, p, "advisor_stuck")
                msgs.append(i18n.t(lang, "chat.human"))
                s["fails"] = 0
        else:
            s["fails"] = 0
    return _state_response(s, p, msgs, mode if text else ("ai" if llm.available() else "rules"))


# ------------------------------------------------------------------------------------------
# recommendation + explanation
# ------------------------------------------------------------------------------------------
def build_quote(s: dict) -> dict:
    p = profile_of(s)
    refresh_derived(p)
    q = quote(p, s.get("selections"), s.get("contract"), s.get("gst_verified"))
    q["profile"] = asdict(p)
    q["tiers"] = value.tiers(p, q["contract_months"], s.get("gst_verified"))
    q["sell"] = value.sell(q, p)
    return q


def explanation(s: dict) -> dict:
    """Plain-language 'why this plan'. LLM-written when available and safe, otherwise a template."""
    if s.get("explanation"):
        return s["explanation"]
    lang = s["lang"]
    p = profile_of(s)
    q = build_quote(s)
    sel = [l for l in q["lines"] if l["selected"]]
    cat = catalogue()
    facts = {
        "business": p.business_type or q["segment_name"], "people": p.employees, "locations": p.sites, "city": p.city,
        "plan": [{"product": l["name"], "quantity": l["qty"], "purpose": i18n.t("en", f"why.{l['why']}")} for l in sel],
        "monthly_price_inr": q["totals"]["monthly"], "contract_months": q["contract_months"],
    }
    text, source = None, "template"
    if llm.available():
        text = llm.write_explanation(lang, facts)
        allowed = {q["totals"]["monthly"], q["totals"]["setup"], q["contract_months"], p.employees or 0, p.sites or 0}
        for l in sel:
            allowed |= {l["unit_price"], l["line_monthly"], l["qty"]}
        bundle = {l["name"] for l in sel}
        if text and llm.explanation_is_safe(text, allowed, bundle, {x.name for x in cat.values()}):
            source = "ai"
        else:
            text = None
    if not text:
        items = ", ".join(i18n.t(lang, f"why.{l['why']}") for l in sel[:3])
        text = i18n.t(lang, "explain.template", business=facts["business"], staff=p.employees or "-",
                      city=p.city or "-", items=items, total=f"{q['totals']['monthly']:,}")
    result = {"text": text, "source": source}
    s["explanation"] = result
    # store only this field, on a fresh copy: the owner may have given consent or uploaded documents
    # while the model was thinking, and saving our stale copy would erase that.
    db.update_session(s["id"], lambda cur: cur.__setitem__("explanation", result))
    return result
