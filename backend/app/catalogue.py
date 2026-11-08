"""Product catalogue and the hard eligibility rules. No LLM is involved here, by design."""
from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from .config import DATA_DIR


@dataclass(frozen=True)
class Product:
    id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup: int
    min_contract: int
    tiers: frozenset
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: frozenset
    install_days: int
    segments: frozenset


@dataclass
class Profile:
    language: str = "en"
    business_type: str | None = None
    segment_hint: str | None = None
    segment: str | None = None
    employees: int | None = None
    sites: int | None = None
    city: str | None = None
    city_tier: int | None = None
    state: str | None = None
    city_verified: bool = True
    current_internet: str | None = None
    has_gstin: bool | None = None
    has_udyam: bool | None = None
    monthly_spend: int | None = None
    needs: list = field(default_factory=list)


@lru_cache
def catalogue() -> dict[str, Product]:
    df = pd.read_csv(DATA_DIR / "product_catalogue.csv")
    out = {}
    for r in df.to_dict("records"):
        dep = r["requires_one_of"]
        out[r["product_id"]] = Product(
            id=r["product_id"], category=r["category"], name=r["product_name"], description=r["description"],
            unit=r["unit"], price_min=int(r["price_min_inr_per_month"]), price_max=int(r["price_max_inr_per_month"]),
            setup=int(r["one_time_setup_inr"]), min_contract=int(r["min_contract_months"]),
            tiers=frozenset(int(x) for x in str(r["available_city_tiers"]).split(";")),
            min_employees=int(r["min_employees"]), min_sites=int(r["min_sites"]),
            requires_gstin=r["requires_gstin"] == "Y",
            requires_one_of=frozenset(str(dep).split("|")) if isinstance(dep, str) else frozenset(),
            install_days=int(r["typical_install_days"]), segments=frozenset(str(r["target_segments"]).split(";")),
        )
    return out


def ineligible_reasons(p: Product, prof: Profile, gst_verified: bool | None = None) -> list[dict]:
    """Why this product cannot be sold to this profile. Empty list = eligible.

    gst_verified: None = not checked yet (trust what the owner said), True/False = result of KYC.
    A product that needs a GSTIN is 'pending' until KYC confirms it.
    """
    reasons = []
    if prof.city_tier is not None and prof.city_tier not in p.tiers:
        reasons.append({"code": "tier", "params": {}})
    if prof.employees is not None and prof.employees < p.min_employees:
        reasons.append({"code": "min_employees", "params": {"n": p.min_employees}})
    if prof.sites is not None and prof.sites < p.min_sites:
        reasons.append({"code": "min_sites", "params": {"n": p.min_sites}})
    if p.requires_gstin:
        if gst_verified is False or (gst_verified is None and prof.has_gstin is False):
            reasons.append({"code": "needs_gstin", "params": {}})
    return reasons


def pending_gst(p: Product, gst_verified: bool | None) -> bool:
    return p.requires_gstin and gst_verified is None
