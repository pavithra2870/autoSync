"""Maps a business description to one of the four MSME segments."""
import re

from .data import business_types

# Order matters: multi-site words win over the single-shop words they contain ("bakery chain").
KEYWORDS = [
    ("multi", ["chain", "outlets", "branches", "showrooms", "franchise", "hotel group", "stores across"]),
    ("mfg", ["factory", "manufactur", "workshop", "unit", "mill", "press", "foundry", "fabricat", "plant",
             "moulding", "packaging", "textile", "auto-parts", "auto parts", "processing", "production"]),
    ("prof", ["clinic", "doctor", "dental", "dentist", "physio", "lab", "diagnostic", "chartered", "ca firm",
              "accountant", "law", "lawyer", "advocate", "coaching", "tuition", "classes", "institute",
              "insurance", "real estate", "realty", "architect", "studio", "consultan", "travel agency",
              "agency", "office"]),
    ("micro", ["shop", "store", "kirana", "grocery", "salon", "parlour", "parlor", "pharmacy", "medical",
               "bakery", "sweet", "boutique", "tailor", "stationery", "hardware", "optician", "repair",
               "restaurant", "cafe", "hotel", "dhaba", "retail"]),
]

SENSITIVE_DATA_WORDS = ["clinic", "dental", "physio", "lab", "diagnostic", "ca firm", "chartered", "law",
                        "advocate", "insurance", "accountant"]
RETAIL_WORDS = ["shop", "store", "kirana", "pharmacy", "bakery", "sweet", "boutique", "stationery", "hardware",
                "optician", "restaurant", "cafe", "retail", "showroom", "chain", "outlet", "salon", "dhaba"]


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(r"\b" + re.escape(w), text) for w in words)


def segment_from_text(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip().lower()
    matches = [(len(known), seg) for known, seg in business_types().items() if known in t or t in known]
    if matches:
        return max(matches)[1]  # longest known type wins ("bakery chain" over "bakery")
    for seg, words in KEYWORDS:
        if _has(t, words):
            return seg
    return None


def is_sensitive(business_type: str | None) -> bool:
    return bool(business_type) and _has(business_type.lower(), SENSITIVE_DATA_WORDS)


def is_retail(business_type: str | None) -> bool:
    return bool(business_type) and _has(business_type.lower(), RETAIL_WORDS)


def derive_segment(business_type: str | None, hint: str | None, employees: int | None, sites: int | None) -> str | None:
    """Sites >= 3 always means multi-site. Otherwise trust the business type, then the owner's pick,
    then fall back to size."""
    if sites is not None and sites >= 3:
        return "multi"
    seg = segment_from_text(business_type) or hint
    if seg == "multi" and sites is not None and sites < 3:
        # "chain" said, but only 1-2 sites: treat as the single-shop version of the business.
        seg = "micro" if (employees or 0) <= 6 else "prof"
    if seg:
        return seg
    if employees is None:
        return None
    return "micro" if employees <= 6 else "prof" if employees <= 25 else "mfg"
