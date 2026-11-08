"""Back-office: which dropped leads are worth a human's time, and what to do with each.

A logistic regression on profile-only fields (nothing that is only known after the funnel, such as
stage reached or dates, so there is no leakage). Scores are cross-validated, so a lead is never
scored by a model that saw its own outcome. Logistic regression is used on purpose: every score
can be explained to a sales manager as 'GSTIN +, referral +, micro shop -'."""
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import SEGMENT_NAMES, leads

CAT = ["lead_source", "segment", "city_tier", "preferred_language", "has_gstin", "has_udyam", "current_internet",
       "current_provider", "annual_turnover_band", "contact_role"]
NUM = ["employee_count", "num_sites", "monthly_telecom_spend_inr", "n_interest"]

ACTIONS = {
    "Price too high": ("Digital counter-offer", "Re-quote on the starter bundle or a 24-month term and send it on WhatsApp."),
    "Competitor offered cheaper plan": ("Digital counter-offer", "Send a price-matched bundle with one bill and one support number."),
    "Quote too complex to understand": ("Plain-language quote", "Send the advisor link: one monthly price, no product codes."),
    "Quote took too long to arrive": ("Instant quote link", "Send the advisor link. The quote is ready in minutes."),
    "Owner had no time for a visit": ("Self-serve link", "Send the advisor link in their language. No visit needed."),
    "Visit not scheduled by sales": ("Self-serve link", "Send the advisor link; offer a visit only if they ask."),
    "Unreachable after 3 attempts": ("WhatsApp nudge", "One WhatsApp message in their preferred language at a quiet time of day."),
    "Missing GST or Udyam document": ("Assisted KYC", "Partner helps collect documents, or switch to the Udyam-only starter path."),
    "Found paperwork too long": ("Smart KYC link", "Send the 4-document upload link; fields are read automatically."),
    "Document details did not match": ("Assisted KYC", "Partner visit to fix the name or address mismatch with the owner."),
    "Authorised signatory not available": ("E-sign link", "Send an e-sign link to the signatory instead of a visit."),
    "Installation delayed beyond 21 days": ("Install escalation", "Escalate to the installation team and give the owner a tracker link."),
    "Site not feasible for fibre": ("Switch product", "Offer 5G AirFiber (P04), which needs no fibre."),
    "First payment failed": ("Payment retry", "Send a payment link; offer UPI autopay."),
    "Customer cancelled before install": ("Win-back call", "Call to understand the reason. Offer a fixed install date."),
    "Locked in with current provider": ("Nurture", "Note the contract end date and re-contact 60 days before it."),
    "Only wanted a mobile plan": ("Mobile-first upsell", "Offer business SIMs now, then a bundle after 30 days."),
    "Decided to wait": ("Follow up in 30 days", "Schedule one reminder."),
    "Not interested on first call": ("Low priority", "Do not spend field time. Keep in the WhatsApp newsletter."),
    "Wrong or invalid number": ("Fix contact data", "Find another contact (referral, website form) before any outreach."),
}
DEFAULT_ACTION = ("Review", "Look at this lead manually.")


def _frame() -> pd.DataFrame:
    d = leads().copy()
    d["n_interest"] = d["products_of_interest"].fillna("").map(lambda s: len([x for x in s.split(";") if x]))
    d["city_tier"] = d["city_tier"].astype(str)
    for c in CAT:
        d[c] = d[c].fillna("Unknown").astype(str)
    d["y"] = (d["outcome"] == "Activated").astype(int)
    return d


def _pipeline() -> Pipeline:
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore"), CAT),
                             ("n", StandardScaler(), NUM)])
    return Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000, C=0.5))])


def _pretty(name: str) -> str:
    """'c__lead_source_Referral' -> 'lead source: Referral'."""
    n = name.split("__", 1)[1]
    for col in CAT + NUM:
        if n == col:
            return col.replace("_", " ")
        if n.startswith(col + "_"):
            return f"{col.replace('_', ' ')}: {n[len(col) + 1:]}"
    return n


@lru_cache
def model() -> dict:
    d = _frame()
    X, y = d[CAT + NUM], d["y"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=7)
    holdout = _pipeline().fit(Xtr, ytr)
    p_te = holdout.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p_te)
    top = np.argsort(-p_te)[: max(1, len(p_te) // 10)]
    lift = float(np.asarray(yte)[top].mean() / np.asarray(yte).mean())

    full = _pipeline().fit(X, y)
    cv = cross_val_predict(_pipeline(), X, y, cv=StratifiedKFold(5, shuffle=True, random_state=7), method="predict_proba")[:, 1]
    names = full.named_steps["pre"].get_feature_names_out()
    coef = full.named_steps["lr"].coef_[0]
    order = np.argsort(coef)
    pretty = _pretty
    return {
        "auc": round(float(auc), 3), "top_decile_lift": round(lift, 2), "base_rate": round(float(y.mean()), 3),
        "n": int(len(d)), "scores": cv, "pipe": full, "names": names, "coef": coef,
        "drivers_up": [(pretty(names[i]), round(float(coef[i]), 2)) for i in order[::-1][:8]],
        "drivers_down": [(pretty(names[i]), round(float(coef[i]), 2)) for i in order[:8]],
    }


def _reasons(row_X: pd.DataFrame, m: dict, k: int = 3) -> list[str]:
    pre = m["pipe"].named_steps["pre"]
    x = pre.transform(row_X)
    x = x.toarray()[0] if hasattr(x, "toarray") else x[0]
    contrib = x * m["coef"]
    idx = np.argsort(-np.abs(contrib))[:k]
    out = []
    for i in idx:
        if abs(contrib[i]) < 0.05:
            continue
        label = _pretty(m["names"][i])
        out.append(("+ " if contrib[i] > 0 else "- ") + label)
    return out


def _owner(seg: str, tier: int, reason_action: str) -> str:
    if seg in ("multi", "mfg"):
        return "Field sales"
    if reason_action in ("Assisted KYC", "Install escalation", "Win-back call"):
        return "Channel partner"
    return "Digital nudge" if seg == "micro" else ("Channel partner" if tier == 2 else "Digital nudge")


@lru_cache
def segment_value() -> dict[str, float]:
    d = leads()
    a = d[d["outcome"] == "Activated"]
    return a.groupby("segment_key")["monthly_bundle_value_inr"].mean().to_dict()


def priority_leads(limit: int = 50, segment: str | None = None, owner: str | None = None) -> list[dict]:
    m = model()
    d = _frame()
    d["score"] = m["scores"]
    d = d[d["outcome"] == "Dropped"]
    d = d[~d["drop_reason"].isin(["Wrong or invalid number"])]  # nobody to call
    if segment:
        d = d[d["segment_key"] == segment]
    seg_val = segment_value()
    d["expected_mrr"] = d["score"] * d["segment_key"].map(seg_val)
    rows = []
    for _, r in d.sort_values("expected_mrr", ascending=False).iterrows():
        title, how = ACTIONS.get(r["drop_reason"], DEFAULT_ACTION)
        own = _owner(r["segment_key"], int(r["city_tier"]), title)
        if owner and own != owner:
            continue
        rows.append({
            "lead_id": r["lead_id"], "business": r["business_name"], "business_type": r["business_type"],
            "segment": SEGMENT_NAMES[r["segment_key"]], "segment_key": r["segment_key"], "city": r["city"],
            "language": r["preferred_language"], "source": r["lead_source"], "stage": r["stage_reached"],
            "drop_reason": r["drop_reason"], "score": round(float(r["score"]), 3),
            "expected_mrr": round(float(r["expected_mrr"])), "action": title, "how": how, "owner": own,
            "has_gstin": r["has_gstin"], "why": _reasons(r[CAT + NUM].to_frame().T, m),
        })
        if len(rows) >= limit:
            break
    return rows


@lru_cache
def insights() -> dict:
    d = leads()
    d = d.assign(act=d["outcome"] == "Activated")
    funnel_order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
    rank = {s: i for i, s in enumerate(funnel_order)}
    counts = [int((d["stage_reached"].map(rank) >= i).sum()) for i in range(len(funnel_order))]
    seg = []
    for key, g in d.groupby("segment_key"):
        a = g[g["act"]]
        seg.append({
            "segment": SEGMENT_NAMES[key], "key": key, "leads": int(len(g)), "share": round(len(g) / len(d) * 100, 1),
            "conversion": round(g["act"].mean() * 100, 1), "activated": int(len(a)),
            "avg_monthly_value": round(float(a["monthly_bundle_value_inr"].mean())),
            "cac": round(float(g["acquisition_cost_inr"].sum() / max(len(a), 1))),
            "churn": round(float((a["churned_within_6_months"] == "Y").mean() * 100), 1),
            "days_to_activate": round(float(a["days_lead_to_activation"].mean()), 1),
        })
    drops = d[d["outcome"] == "Dropped"]["drop_reason"].value_counts().head(8)
    return {
        "funnel": [{"stage": s, "leads": c} for s, c in zip(funnel_order, counts)],
        "segments": sorted(seg, key=lambda x: -x["avg_monthly_value"] / max(x["cac"], 1)),
        "drop_reasons": [{"reason": k, "count": int(v)} for k, v in drops.items()],
        "gstin": {"with": round(d[d["has_gstin"] == "Y"]["act"].mean() * 100, 1),
                  "without": round(d[d["has_gstin"] == "N"]["act"].mean() * 100, 1)},
    }
