"""Order record and tracker timeline. Expected dates come from each product's typical_install_days."""
import uuid
from datetime import date, timedelta

from .config import TODAY
from . import db

STAGES = ["quote", "kyc", "sign", "install_sched", "installing", "active"]


def add_working_days(start: date, days: int) -> date:
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


def _stages(install_days: int, kyc_done: bool) -> list[dict]:
    expected = {
        "quote": TODAY,
        "kyc": add_working_days(TODAY, 0 if kyc_done else 1),
        "sign": add_working_days(TODAY, 1),
        "install_sched": add_working_days(TODAY, 1),
        "installing": add_working_days(TODAY, max(1, install_days // 2)),
        "active": add_working_days(TODAY, max(2, install_days + 1)),
    }
    out = [{"key": k, "state": "todo", "expected": expected[k].isoformat(), "done_on": None} for k in STAGES]
    done = ["quote"] + (["kyc"] if kyc_done else [])
    for st in out:
        if st["key"] in done:
            st["state"], st["done_on"] = "done", TODAY.isoformat()
    _mark_current(out)
    return out


def _mark_current(stages: list[dict]) -> None:
    for st in stages:
        if st["state"] != "done":
            st["state"] = "current"
            break


def _msg(order: dict, stage: str) -> None:
    order["messages"].append({"stage": stage, "channel": "WhatsApp", "when": order["stages"][STAGES.index(stage)]["expected"]})


def create_order(session: dict, quote: dict, held: list[dict], kyc_verdict: str, signer: str) -> dict:
    kyc_done = kyc_verdict == "verified"
    sel = [l for l in quote["lines"] if l["selected"]]
    order = {
        "id": "AB" + uuid.uuid4().hex[:6].upper(), "session_id": session["id"], "created": TODAY.isoformat(),
        "business": quote.get("profile", {}).get("business_type") or quote["segment_name"],
        "city": quote.get("profile", {}).get("city"), "language": session["lang"], "signed_by": signer,
        "kyc_verdict": kyc_verdict,
        "items": [{k: l[k] for k in ("product_id", "name", "qty", "unit_price", "line_monthly", "line_setup", "unit")} for l in sel],
        "held": held, "totals": quote["totals"], "contract_months": quote["contract_months"],
        "offers": quote.get("sell", {}).get("offers", []),
        "first_month_pay": quote.get("sell", {}).get("first_month_pay"),
        "setup_pay": quote.get("sell", {}).get("setup_pay"),
        "stages": _stages(quote["install_days"], kyc_done), "messages": [],
    }
    order["stages"][2]["state"] = "done" if kyc_done else order["stages"][2]["state"]
    if kyc_done:
        order["stages"][2]["done_on"] = TODAY.isoformat()
        for st in order["stages"]:
            st["state"] = "done" if st["key"] in ("quote", "kyc", "sign") else "todo"
        _mark_current(order["stages"])
    _msg(order, "quote")
    if kyc_done:
        _msg(order, "kyc")
        _msg(order, "sign")
    db.save_order(order)
    return order


def current_stage(order: dict) -> str | None:
    return next((s["key"] for s in order["stages"] if s["state"] == "current"), None)


def advance(order: dict) -> dict:
    """Demo control: complete the current step and open the next one."""
    cur = current_stage(order)
    if cur is None:
        return order
    st = order["stages"][STAGES.index(cur)]
    st["state"], st["done_on"] = "done", st["expected"]
    if cur == "kyc":
        order["kyc_verdict"] = "verified"
    _msg(order, cur)
    _mark_current(order["stages"])
    db.save_order(order)
    return order
