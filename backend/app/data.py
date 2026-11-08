"""Loads the synthetic data pack once and exposes small lookup helpers."""
from functools import lru_cache

import pandas as pd

from .config import DATA_DIR

SEGMENT_KEYS = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}
SEGMENT_NAMES = {v: k for k, v in SEGMENT_KEYS.items()}


@lru_cache
def leads() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "smb_leads.csv")
    df["segment_key"] = df["segment"].map(SEGMENT_KEYS)
    return df


@lru_cache
def gstin_registry() -> dict[str, dict]:
    df = pd.read_csv(DATA_DIR / "mock_gstin_registry.csv")
    return {r["gstin"]: r for r in df.to_dict("records")}


@lru_cache
def udyam_registry() -> dict[str, dict]:
    df = pd.read_csv(DATA_DIR / "mock_udyam_registry.csv")
    return {r["udyam_number"]: r for r in df.to_dict("records")}


@lru_cache
def cities() -> dict[str, dict]:
    """lower-case city -> {name, tier, state}, ordered by how many leads each city has."""
    df = leads().groupby(["city", "city_tier", "state"]).size().reset_index(name="n")
    df = df.sort_values("n", ascending=False)
    return {r.city.lower(): {"name": r.city, "tier": int(r.city_tier), "state": r.state} for r in df.itertuples()}


CITY_ALIASES = {
    "bangalore": "bengaluru", "bengalooru": "bengaluru", "bombay": "mumbai", "madras": "chennai",
    "calcutta": "kolkata", "mysore": "mysuru", "vizag": "visakhapatnam", "baroda": "vadodara",
    "new delhi": "delhi", "poona": "pune",
}


def find_city(text: str | None) -> dict | None:
    if not text:
        return None
    t = text.strip().lower()
    t = CITY_ALIASES.get(t, t)
    if t in cities():
        return cities()[t]
    for alias, canon in CITY_ALIASES.items():
        if alias in t:
            return cities()[canon]
    for key, c in cities().items():
        if key in t:
            return c
    return None


@lru_cache
def business_types() -> dict[str, str]:
    """lower-case business type -> segment key, as seen in the leads data."""
    df = leads()[["business_type", "segment_key"]].drop_duplicates()
    return {r.business_type.lower(): r.segment_key for r in df.itertuples()}
