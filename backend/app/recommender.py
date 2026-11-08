"""Turns a business profile into a bundle and a price. Pure Python rules, no LLM.

Bundle shapes come from what activated customers in each segment actually bought
(smb_leads.csv): e.g. every professional office took cloud email, every multi-site
business took mobile lines, most micro shops took fibre 100 + postpaid 299.
"""
import math
from dataclasses import dataclass

from .catalogue import Product, Profile, catalogue, ineligible_reasons, pending_gst
from .data import SEGMENT_NAMES
from .segments import is_retail, is_sensitive

# Where inside the catalogue's min..max price range we quote. Micro shops are the most price
# sensitive and the costliest to acquire by field visit, so digital sign-up passes the saving on.
BASE_POSITION = {"micro": 0.30, "prof": 0.45, "multi": 0.50, "mfg": 0.50}
LONG_CONTRACT_DISCOUNT = 0.15  # 24 months moves the price this far towards the bottom of the range
EXCLUSIVE_INTERNET = ("P01", "P02", "P03", "P04", "P05", "P06")


@dataclass
class Spec:
    pid: str
    qty: int
    why: str
    group: str  # core | rec | addon
    exclusive: str | None = None


def _clamp(x, lo, hi):
    return int(max(lo, min(hi, x)))


def _internet_choice(prof: Profile, seg: str, emp: int, sites: int, gst_verified) -> tuple[str, list[str]]:
    gst_ok = gst_verified if gst_verified is not None else prof.has_gstin is not False
    tier = prof.city_tier or 2
    if seg == "micro":
        return "P01", ["P04"]
    if seg == "prof":
        if emp <= 7:
            return "P01", ["P02", "P03"]
        if emp >= 15 and tier == 1 and gst_ok:
            return "P03", ["P02", "P01"]
        return "P02", ["P01", "P03"]
    if seg == "multi":
        return ("P01", ["P02"]) if emp / max(sites, 1) < 8 else ("P02", ["P01"])
    if gst_ok and emp >= 10:  # manufacturers
        return "P05", ["P06", "P03", "P02"]
    return "P02", ["P03", "P01"]


def build_specs(prof: Profile, gst_verified: bool | None = None) -> list[Spec]:
    cat = catalogue()
    seg = prof.segment or "micro"
    emp = prof.employees or 1
    sites = max(prof.sites or 1, 1)
    needs = set(prof.needs or [])
    retail = is_retail(prof.business_type)
    sensitive = is_sensitive(prof.business_type)
    specs: list[Spec] = []

    def add(pid, qty, why, group, exclusive=None):
        specs.append(Spec(pid, _clamp(qty, 1, 99), why, group, exclusive))

    # --- internet: one primary link per site, other speeds offered as swaps ---
    default, alts = _internet_choice(prof, seg, emp, sites, gst_verified)
    options = [default] + alts
    ok = [pid for pid in options if not ineligible_reasons(cat[pid], prof, gst_verified)]
    chosen = ok[0] if ok else "P01"
    why = "leased" if chosen in ("P05", "P06") else "internet_core"
    add(chosen, sites, why, "core", "internet")
    for pid in options:
        if pid != chosen:
            add(pid, sites, "alt_internet", "addon", "internet")

    # --- mobile lines ---
    if seg == "micro":
        add("P07", _clamp(math.ceil(emp / 2), 1, 3), "mobile_lines", "core")
    elif seg == "prof":
        add("P07" if emp < 10 else "P08", _clamp(math.ceil(emp / 5), 1, 6), "mobile_lines", "core")
    elif seg == "multi":
        add("P08", _clamp(math.ceil(emp / 15), 2, 10), "mobile_lines", "core")
    else:
        add("P08", _clamp(math.ceil(emp / 20), 2, 10), "mobile_lines", "core")

    # --- segment specific ---
    uptime = "uptime" in needs  # "my internet keeps going down"
    if seg == "micro":
        add("P19", 1, "pos", "rec" if "pos" in needs else "addon")
        add("P23", 2, "cctv", "rec" if "cctv" in needs else "addon")
        add("P15", 1, "whatsapp", "rec" if "whatsapp" in needs else "addon")
        add("P09", 1, "failover_sites", "rec" if uptime else "addon")
        add("P22", 1, "wifi", "addon")
        add("P18", 1, "website", "rec" if "website" in needs else "addon")
    elif seg == "prof":
        add("P16", _clamp(round(emp * 0.55), 1, 40), "email_cloud", "core")
        guard = "security" in needs or sensitive
        add("P20", _clamp(round(emp * 0.4), 1, 50), "data_security", "rec" if guard else "addon")
        add("P17", 1, "backup", "rec" if (guard or "backup" in needs) else "addon")
        add("P09", sites, "failover_sites", "rec" if uptime else "addon")
        add("P12", 2, "phone_system", "rec" if "phone" in needs else "addon")
        add("P15", 1, "whatsapp", "rec" if "whatsapp" in needs else "addon")
        add("P23", 2, "cctv", "rec" if "cctv" in needs else "addon")
        add("P22", sites, "wifi", "addon")
        add("P11", 1, "static_ip", "addon")
        add("P18", 1, "website", "rec" if "website" in needs else "addon")
    elif seg == "multi":
        add("P09", sites, "failover_sites", "rec")
        add("P10", sites, "sdwan", "rec")
        add("P19", sites, "pos", "rec" if (retail or "pos" in needs) else "addon")
        add("P23", sites * 2, "cctv", "rec" if "cctv" in needs else "addon")
        add("P22", sites, "wifi", "rec" if "security" in needs else "addon")
        add("P15", 1, "whatsapp", "rec" if "whatsapp" in needs else "addon")
        add("P16", _clamp(round(emp * 0.2), 2, 40), "email_cloud", "addon")
        add("P20", _clamp(round(emp * 0.2), 2, 50), "data_security", "addon")
        add("P12", 2, "phone_system", "rec" if "phone" in needs else "addon")
    else:  # mfg
        add("P16", _clamp(round(emp * 0.12), 2, 25), "email_cloud", "core")
        add("P21", sites, "firewall", "rec" if ("security" in needs or emp >= 30) else "addon")
        add("P24", _clamp(round(emp / 8), 2, 15), "iot", "rec" if "iot" in needs else "addon")
        add("P25", 2, "fleet", "rec" if "fleet" in needs else "addon")
        add("P11", 1, "static_ip", "addon")
        add("P20", _clamp(round(emp * 0.15), 2, 50), "data_security", "rec" if "security" in needs else "addon")
        add("P09", sites, "failover_sites", "rec" if uptime else "addon")
        add("P23", 4, "cctv", "rec" if "cctv" in needs else "addon")
    return specs


def unit_price(p: Product, seg: str, contract: int) -> int:
    pos = BASE_POSITION.get(seg, 0.5)
    if contract >= 24:
        pos = max(0.0, pos - LONG_CONTRACT_DISCOUNT)
    return round(p.price_min + pos * (p.price_max - p.price_min))


def _prune(chosen: dict[str, int]) -> tuple[dict[str, int], dict[str, str]]:
    """Enforce one internet plan and the 'needs one of' dependencies."""
    dropped: dict[str, str] = {}
    cat = catalogue()
    net = [p for p in chosen if p in EXCLUSIVE_INTERNET]
    for extra in net[1:]:
        chosen.pop(extra)
    changed = True
    while changed:
        changed = False
        for pid in list(chosen):
            deps = cat[pid].requires_one_of
            if deps and not (deps & set(chosen)):
                chosen.pop(pid)
                dropped[pid] = "needs_base"
                changed = True
    return chosen, dropped


def quote(prof: Profile, selections: dict[str, int] | None = None, contract: int | None = None,
          gst_verified: bool | None = None) -> dict:
    """Price a selection. selections=None means 'the default recommendation'."""
    cat = catalogue()
    seg = prof.segment or "micro"
    specs = build_specs(prof, gst_verified)
    by_id = {s.pid: s for s in specs}

    if selections is None:
        selections = {}
        for s in specs:
            if s.group in ("core", "rec") and not ineligible_reasons(cat[s.pid], prof, gst_verified):
                selections[s.pid] = s.qty
    selections = {pid: max(1, min(int(q), 99)) for pid, q in selections.items() if pid in cat}
    # drop anything the profile cannot buy (e.g. GSTIN failed verification)
    removed: dict[str, str] = {}
    for pid in list(selections):
        if ineligible_reasons(cat[pid], prof, gst_verified):
            selections.pop(pid)
            removed[pid] = "ineligible"
    if len([p for p in selections if p in EXCLUSIVE_INTERNET]) == 0:
        # the base internet plan must exist; fall back to the recommended one
        base = next(s.pid for s in specs if s.exclusive == "internet" and s.group == "core")
        selections[base] = by_id[base].qty
    selections, dropped = _prune(selections)
    removed.update(dropped)

    required = max([cat[p].min_contract for p in selections] + [12])
    options = [c for c in (12, 24) if c >= required]
    contract = contract if contract in options else options[0]

    lines = []
    monthly = setup = 0
    for s in specs:
        p = cat[s.pid]
        sel = s.pid in selections
        qty = selections.get(s.pid, s.qty)
        price = unit_price(p, seg, contract)
        reasons = ineligible_reasons(p, prof, gst_verified)
        if s.pid in removed and removed[s.pid] == "needs_base":
            reasons = reasons + [{"code": "needs_base", "params": {}}]
        line = {
            "product_id": p.id, "name": p.name, "description": p.description, "unit": p.unit,
            "qty": qty, "unit_price": price, "price_min": p.price_min, "price_max": p.price_max,
            "line_monthly": price * qty if sel else 0, "setup_each": p.setup,
            "line_setup": p.setup * qty if sel else 0, "why": s.why, "group": s.group,
            "exclusive": s.exclusive, "selected": sel, "locked": reasons,
            "pending_gst": pending_gst(p, gst_verified) and not reasons,
            "min_contract": p.min_contract, "install_days": p.install_days,
        }
        lines.append(line)
        if sel:
            monthly += line["line_monthly"]
            setup += line["line_setup"]

    selected = [l for l in lines if l["selected"]]
    install_days = max((l["install_days"] for l in selected), default=0)
    spend = prof.monthly_spend
    return {
        "segment": seg, "segment_name": SEGMENT_NAMES.get(seg, seg),
        "lines": lines, "contract_months": contract, "contract_options": options,
        "totals": {"monthly": monthly, "setup": setup},
        "install_days": install_days, "current_spend": spend,
        "removed": [{"product_id": k, "reason": v} for k, v in removed.items()],
    }
