"""Numbers behind the business-case slides. Everything here is computed from the case data pack,
except the single labelled assumption RECOVERY. Writes docs/impact.json.
    python scripts/impact.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.catalogue import Profile  # noqa: E402
from app.data import find_city  # noqa: E402
from app.recommender import quote  # noqa: E402
from app.segments import derive_segment  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RECOVERY = 0.20  # ASSUMPTION: share of digitally-addressable drop-offs the journey wins back

d = pd.read_csv(ROOT / "data" / "smb_leads.csv")
d["act"] = d["outcome"] == "Activated"
order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
rank = {s: i for i, s in enumerate(order)}
d["r"] = d["stage_reached"].map(rank)
reach = [int((d["r"] >= i).sum()) for i in range(6)]

# Drop reasons the digital journey removes directly
ADDRESSABLE = {
    "Quote too complex to understand": "plain one-price quote",
    "Quote took too long to arrive": "instant quote",
    "Owner had no time for a visit": "self-serve, no visit",
    "Visit not scheduled by sales": "self-serve, no visit",
    "Missing GST or Udyam document": "Smart KYC, Udyam-only path",
    "Found paperwork too long": "Smart KYC",
    "Document details did not match": "Smart KYC checks",
    "Authorised signatory not available": "e-sign link",
}
drops = d[(d["outcome"] == "Dropped") & d["drop_reason"].isin(ADDRESSABLE)].copy()
seg_val = d[d["act"]].groupby("segment")["monthly_bundle_value_inr"].mean()
# if saved, the lead moves to the next stage and then converts like everyone who got that far
drops["p_act"] = drops["r"].map(lambda s: reach[5] / reach[s + 1])
extra = float(drops["p_act"].sum() * RECOVERY)
mrr = float((drops["p_act"] * drops["segment"].map(seg_val)).sum() * RECOVERY)

src = d.groupby("lead_source").agg(leads=("act", "size"), act=("act", "sum"), spend=("acquisition_cost_inr", "sum"))
src["cac"] = (src["spend"] / src["act"]).round(0)
src["conv"] = (src["act"] / src["leads"] * 100).round(1)

a = d[d["act"]].copy()
a["churn"] = a["churned_within_6_months"] == "Y"
calls = a.groupby("customer_follow_up_calls")["churn"].mean().mul(100).round(1).to_dict()

# Representative starter bundles from the rules engine (median size of each segment in the data)
def bundle(btype, city, emp, sites, gst, needs=()):
    c = find_city(city)
    p = Profile(business_type=btype, segment=derive_segment(btype, None, emp, sites), employees=emp, sites=sites,
                city=c["name"], city_tier=c["tier"], state=c["state"], has_gstin=gst, needs=list(needs))
    q = quote(p)
    return {"segment": q["segment"], "monthly": q["totals"]["monthly"], "setup": q["totals"]["setup"],
            "contract": q["contract_months"], "days": q["install_days"],
            "items": [f'{l["name"]} x{l["qty"]}' for l in q["lines"] if l["selected"]]}

bundles = {
    "micro": bundle("kirana store", "Nagpur", 3, 1, False),
    "micro_pos": bundle("kirana store", "Nagpur", 3, 1, True, ["pos"]),
    "prof": bundle("dental clinic", "Nagpur", 14, 1, True),
    "multi": bundle("restaurant chain", "Pune", 71, 8, True, ["pos"]),
    "mfg": bundle("textile unit", "Surat", 85, 1, True),
}

out = {
    "reach": dict(zip(order, reach)),
    "baseline": {"leads": len(d), "activated": int(d["act"].sum()), "conv": round(d["act"].mean() * 100, 1),
                 "days": round(float(a["days_lead_to_activation"].mean()), 1),
                 "cac": round(float(d["acquisition_cost_inr"].sum() / d["act"].sum())),
                 "churn": round(float(a["churn"].mean() * 100), 1), "calls": round(float(a["customer_follow_up_calls"].mean()), 1),
                 "nps": round(float(a["nps_score"].mean()), 1)},
    "addressable": {"drops": int(len(drops)), "share_of_all_drops": round(len(drops) / (d["outcome"] == "Dropped").sum() * 100, 1),
                    "by_reason": drops["drop_reason"].value_counts().to_dict(),
                    "recovery_assumption": RECOVERY, "extra_activations_per_quarter": round(extra, 1),
                    "extra_mrr_inr": round(mrr), "extra_arr_inr": round(mrr * 12)},
    "by_source": src.reset_index().to_dict("records"),
    "churn_by_status_calls": calls,
    "bundles": bundles,
}
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "impact.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("reach", "baseline", "addressable", "churn_by_status_calls")}, indent=1, ensure_ascii=False))
print(src.to_string())
for k, v in bundles.items():
    print(k, v["monthly"], v["setup"], v["contract"], "mo", v["days"], "d |", ", ".join(v["items"]))
