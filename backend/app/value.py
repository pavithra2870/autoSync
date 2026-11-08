"""Why the pack is worth buying: tiers, honest savings, effort and time saved, online sign-up offers.

All numbers are computed here by code, never by the LLM. Honesty rules:
- We never claim savings against what the owner pays today (most pay less today for fewer services).
- "Separately" means the same services bought one by one at the top of our own list-price range,
  with full setup fees. The assumption is shown to the owner under "How we worked this out".
- Time and follow-up calls for "the usual way" come from Accel's own sales records (smb_leads.csv).
- Offers are capped so their cost stays below what a digital sign-up saves versus a field sale
  (field CAC Rs 24,335 vs website Rs 6,352 in the data).
"""
import math
from datetime import timedelta
from functools import lru_cache

import pandas as pd

from .catalogue import Profile, catalogue, ineligible_reasons, pending_gst
from .config import TODAY
from .data import leads
from .recommender import EXCLUSIVE_INTERNET, build_specs, quote

SETUP_WAIVER_CAP = 5000       # online sign-up: setup fee waived up to this amount
FIRST_MONTH_OFF = 0.5          # first month at half price ...
FIRST_MONTH_CAP = 5000         # ... capped at this amount
PRICE_HOLD_DAYS = 7

# Services that would usually come from different providers when bought one by one.
PROVIDER_GROUP = {
    "P01": "internet", "P02": "internet", "P03": "internet", "P04": "internet", "P05": "internet", "P06": "internet",
    "P09": "internet", "P11": "internet", "P22": "internet",
    "P07": "mobile", "P08": "mobile",
    "P10": "network", "P21": "network",
    "P12": "phone", "P13": "phone", "P14": "phone",
    "P15": "whatsapp", "P16": "office", "P17": "office", "P18": "website", "P19": "billing",
    "P20": "security", "P23": "cctv", "P24": "iot", "P25": "fleet",
}


@lru_cache
def segment_stats() -> dict:
    """Per segment: customers who joined, and how long the usual (field) process took them."""
    d = leads()
    a = d[d["outcome"] == "Activated"].copy()
    pre = (pd.to_datetime(a["kyc_complete_date"]) - pd.to_datetime(a["created_date"])).dt.days
    a["pre"] = pre
    out = {}
    for seg, g in a.groupby("segment_key"):
        out[seg] = {
            "customers": int(len(g)),
            "paperwork_days": int(round(g["pre"].mean())),
            "calls": int(round(g["customer_follow_up_calls"].mean())),
            "by_city": {k: int(v) for k, v in g.groupby("city").size().items()},
        }
    return out


def _ids(q: dict) -> set[str]:
    return {l["product_id"] for l in q["lines"] if l["selected"]}


def tiers(prof: Profile, contract: int | None, gst_verified: bool | None) -> list[dict]:
    """Basic / Recommended / Complete. Recommended is the default quote (what similar businesses bought)."""
    cat = catalogue()
    specs = build_specs(prof, gst_verified)
    rec_q = quote(prof, None, contract, gst_verified)
    rec_sel = {l["product_id"]: l["qty"] for l in rec_q["lines"] if l["selected"]}
    core = {pid: q for pid, q in rec_sel.items() if next(s.group for s in specs if s.pid == pid) == "core"}
    if set(core) == set(rec_sel):  # nothing extra recommended: basic = internet only
        core = {pid: q for pid, q in rec_sel.items() if pid in EXCLUSIVE_INTERNET}
    extra = {}
    for s in specs:
        p = cat[s.pid]
        if (s.pid in rec_sel or s.exclusive == "internet" or ineligible_reasons(p, prof, gst_verified)
                or pending_gst(p, gst_verified)):
            continue
        extra[s.pid] = s.qty
        if len(extra) == 2:
            break
    out = []
    for key, sel in (("basic", core), ("recommended", rec_sel), ("complete", {**rec_sel, **extra} if extra else None)):
        if not sel:
            continue
        # price every tier on the same contract length so the comparison is fair
        q = rec_q if key == "recommended" else quote(prof, sel, rec_q["contract_months"], gst_verified)
        if out and _ids(q) == set(out[-1]["ids"]):
            continue
        out.append({"key": key, "selections": {l["product_id"]: l["qty"] for l in q["lines"] if l["selected"]},
                    "ids": sorted(_ids(q)), "monthly": q["totals"]["monthly"], "count": len(_ids(q)),
                    "items": [l["why"] for l in q["lines"] if l["selected"]]})
    return out


def sell(q: dict, prof: Profile) -> dict:
    """The selling block for one priced quote."""
    sel = [l for l in q["lines"] if l["selected"]]
    monthly, setup = q["totals"]["monthly"], q["totals"]["setup"]
    seg = q["segment"]
    stats = segment_stats().get(seg, {})

    # --- money ---
    separate_monthly = sum(l["price_max"] * l["qty"] for l in sel)
    setup_off = min(setup, SETUP_WAIVER_CAP)
    first_off = min(round(monthly * FIRST_MONTH_OFF), FIRST_MONTH_CAP)
    year_separate = separate_monthly * 12 + setup
    year_pack = monthly * 12 + setup - setup_off - first_off
    saving = max(0, year_separate - year_pack)
    months_free = int(saving // monthly) if monthly else 0

    # --- compared with what they pay today (never framed as a saving unless it truly is one) ---
    spend = prof.monthly_spend
    vs_today = None
    if spend:
        diff = monthly - spend
        # round the extra cost per day UP, so we never understate it
        vs_today = {"spend": spend, "diff_month": diff, "diff_day": math.ceil(diff / 30) if diff > 0 else 0}

    # --- effort ---
    providers = len({PROVIDER_GROUP.get(l["product_id"], l["product_id"]) for l in sel})

    # --- offers (only for signing up online) ---
    offers = []
    if setup_off:
        offers.append({"key": "setup", "amount": setup_off, "full": setup_off == setup})
    if first_off:
        offers.append({"key": "half", "amount": first_off, "full": first_off == round(monthly * FIRST_MONTH_OFF)})
    if prof.current_internet and prof.current_internet != "none":
        offers.append({"key": "switch"})
    offers.append({"key": "lang"})
    offers.append({"key": "ontime", "days": q["install_days"]})
    offers.append({"key": "exit"})
    offers.append({"key": "lock", "months": q["contract_months"]})

    city_n = stats.get("by_city", {}).get(prof.city or "", 0)
    return {
        "per_day": round(monthly / 30),
        "separate_monthly": separate_monthly,
        "year_separate": year_separate, "year_pack": year_pack,
        "saving_year": saving, "saving_pct": round(100 * saving / year_separate) if year_separate else 0,
        "months_free": months_free,
        "first_month_pay": monthly - first_off, "setup_pay": setup - setup_off,
        "vs_today": vs_today,
        "providers": providers,
        "usual_days": stats.get("paperwork_days", 13), "usual_calls": stats.get("calls", 3),
        "install_days": q["install_days"],
        "offers": offers,
        "proof": {"segment": stats.get("customers", 0), "city": city_n if city_n >= 5 else 0, "city_name": prof.city},
        "held_until": (TODAY + timedelta(days=PRICE_HOLD_DAYS)).isoformat(),
    }
