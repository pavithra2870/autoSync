"""Runs Smart KYC on the 12 specimen applicants and compares the verdict with what we expect.

    python scripts/eval_kyc.py            # parse images (about 5 s per document) and cache the result
    python scripts/eval_kyc.py --cached   # reuse the cache, instant
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app.config import DATA_DIR, VAR_DIR  # noqa: E402
from app.kyc.parse import parse_document  # noqa: E402
from app.kyc.validate import verify  # noqa: E402

SLOTS = {"gst": "gst_certificate", "udyam": "udyam_certificate", "id": "signatory_id", "address": "address_proof"}
CACHE = VAR_DIR / "kyc_parse_cache.json"

# What a careful human reviewer would conclude from each pack (see docs/kyc_findings in the README).
EXPECTED = {
    "K01": ("blocked", {"gstin_status"}),          # GSTIN cancelled; Udyam number missing on certificate
    "K02": ("verified", set()),                    # tilted photo, but all genuine
    "K03": ("verified", set()),
    "K04": ("action_needed", {"quality"}),         # blurred GST certificate
    "K05": ("action_needed", {"completeness"}),    # Udyam certificate not supplied
    "K06": ("verified", set()),                    # OCR misread the GSTIN, repaired and flagged for confirmation
    "K07": ("manual_review", {"gst_name"}),        # legal name differs from the registry
    "K08": ("verified", set()),
    "K09": ("verified", set()),
    "K10": ("verified", set()),
    "K11": ("action_needed", {"address_fresh"}),   # bill older than 90 days
    "K12": ("verified", set()),
}


def parse_all(cached: bool) -> dict:
    if cached and CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    out = {}
    for k in EXPECTED:
        out[k] = {}
        for slot, name in SLOTS.items():
            f = DATA_DIR / "kyc_documents" / f"{k}_{name}.png"
            if f.exists():
                t = time.time()
                out[k][slot] = parse_document(Image.open(f))
                print(f"  parsed {f.name} in {time.time() - t:.1f}s", flush=True)
    CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def main():
    parsed = parse_all("--cached" in sys.argv)
    ok = 0
    for k, (exp_verdict, exp_checks) in EXPECTED.items():
        r = verify(parsed[k])
        failing = {c["id"] for c in r["checks"] if c["status"] == "fail"}
        good = r["verdict"] == exp_verdict and exp_checks <= failing
        ok += good
        print(f"{'OK  ' if good else 'FAIL'} {k}: {r['verdict']:<14} (expected {exp_verdict})")
        for c in r["checks"]:
            if c["status"] != "pass":
                print(f"       {c['status']:<4} {c['severity']:<6} {c['id']:<14} {c['detail']}")
    print(f"\n{ok}/{len(EXPECTED)} applicants match expectations")


if __name__ == "__main__":
    main()
