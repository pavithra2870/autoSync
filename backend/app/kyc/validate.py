"""KYC rules. Takes parsed documents (and optional typed IDs) and decides what is wrong, who must act,
and whether GST-dependent products can be sold. Deterministic: no LLM involved."""
import re
from datetime import date
from difflib import SequenceMatcher

from ..config import ADDRESS_PROOF_MAX_DAYS, TODAY
from ..data import gstin_registry, udyam_registry
from .gstin import mask

EXPECTED = {"gst": "gst_certificate", "udyam": "udyam_certificate", "id": "signatory_id", "address": "address_proof"}
SLOT_LABEL = {"gst": "GST certificate", "udyam": "Udyam certificate", "id": "Signatory ID", "address": "Address proof"}
AUTHORISED = ["owner", "proprietor", "partner", "director", "managing director", "authorised signatory", "ceo"]

# severity: what has to happen next
#   block  - cannot sell GST-dependent products on this registration
#   fix    - the owner can fix it now (retake photo, upload missing document)
#   review - a human on the Accel side should look at it
#   info   - shown for transparency only
SEV_RANK = {"block": 3, "fix": 2, "review": 1, "info": 0}


def nrm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def sim(a, b) -> float:
    a, b = nrm(a), nrm(b)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def split_legal(name: str | None) -> tuple[str | None, str | None]:
    """'Neha Kaur (Prop. Vindhya Tours)' -> ('Neha Kaur', 'Vindhya Tours')."""
    m = re.match(r"\s*(.*?)\s*\(\s*prop\.?\s*(.*?)\)\s*$", name or "", re.I)
    return (m.group(1), m.group(2)) if m else (None, name)


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


class Checks:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, cid, status, sev, doc, detail):
        self.items.append({"id": cid, "status": status, "severity": sev if status != "pass" else "info",
                           "doc": doc, "detail": detail})


def verify(docs: dict[str, dict], typed: dict | None = None, needs_gst: bool = True) -> dict:
    typed = typed or {}
    c = Checks()
    greg, ureg = gstin_registry(), udyam_registry()

    # --- 1. each document: readable and the right kind ------------------------------------
    usable: dict[str, dict] = {}
    for slot, d in docs.items():
        if d["blurry"]:
            c.add("quality", "fail", "fix", slot, f"{SLOT_LABEL[slot]} is too blurry to read. Please retake it flat and in good light.")
        elif d["doc_type"] != EXPECTED[slot]:
            seen = (d["doc_type"] or "an unrecognised document").replace("_", " ")
            c.add("doc_type", "fail", "fix", slot, f"This slot needs a {SLOT_LABEL[slot]} but we found {seen}.")
        else:
            note = f" Photo was tilted {abs(d['deskewed_deg'])}°; we straightened it." if d.get("deskewed_deg") else ""
            c.add("quality", "pass", "info", slot, f"{SLOT_LABEL[slot]} is readable.{note}")
            usable[slot] = d

    # --- 2. completeness ------------------------------------------------------------------
    typed_udyam = typed.get("udyam")
    typed_udyam_ok = bool(typed_udyam and typed_udyam in ureg)
    required = ["id", "address"] + (["gst"] if needs_gst else []) + ([] if typed_udyam_ok else ["udyam"])
    missing = [s for s in required if s not in docs]
    if missing:
        names = ", ".join(SLOT_LABEL[s] for s in missing)
        extra = " (or type your Udyam number)" if "udyam" in missing else ""
        c.add("completeness", "fail", "fix", None, f"Missing: {names}{extra}.")
    else:
        c.add("completeness", "pass", "info", None, "All required documents provided.")

    gst_verified = None
    reg_row = None
    business_names: list[tuple[str, str]] = []
    gst_address = None
    biz_cert = None

    # --- 3. GST ---------------------------------------------------------------------------
    if "gst" in usable:
        f = usable["gst"]["fields"]
        gstin, st = f.get("gstin"), f.get("gstin_status")
        for corr in usable["gst"].get("corrections", []):
            c.add("autocorrected", "warn", "info", "gst",
                  f"We read the GSTIN as {corr['read_as']} and corrected it to {corr['corrected_to']} "
                  "(checksum and registry match). Please confirm.")
        if st == "unreadable" or not gstin:
            c.add("gstin_valid", "fail", "fix", "gst", "Could not read the GSTIN. Retake the photo or type it in.")
        elif st == "invalid":
            c.add("gstin_valid", "fail", "fix", "gst", f"GSTIN {mask(gstin)} fails the checksum and matches no registry entry.")
            gst_verified = False
        else:
            c.add("gstin_valid", "pass", "info", "gst", f"GSTIN {mask(gstin)} has a valid format and checksum.")
            if typed.get("gstin") and typed["gstin"] != gstin:
                c.add("gstin_input", "warn", "review", "gst", "The GSTIN you typed differs from the one on the certificate.")
            reg_row = greg.get(gstin)
            if not reg_row:
                c.add("gstin_registry", "fail", "block", "gst", "GSTIN is not in the GST registry.")
                gst_verified = False
            else:
                c.add("gstin_registry", "pass", "info", "gst", "GSTIN found in the registry.")
                if reg_row["status"] != "Active":
                    c.add("gstin_status", "fail", "block", "gst",
                          f"GSTIN is {reg_row['status']}. GST-dependent products cannot be sold on it.")
                    gst_verified = False
                else:
                    c.add("gstin_status", "pass", "info", "gst", "GSTIN is active.")
                    gst_verified = True
                prop_c, biz_c = split_legal(f.get("legal_name"))
                prop_r, biz_r = split_legal(reg_row["legal_name"])
                problems = []
                if sim(biz_c, biz_r) < 0.85:
                    problems.append(f'legal name "{f.get("legal_name")}" vs registry "{reg_row["legal_name"]}"')
                if prop_c and prop_r and sim(prop_c, prop_r) < 0.85:
                    problems.append(f'proprietor "{prop_c}" vs registry "{prop_r}"')
                if f.get("trade_name") and sim(f["trade_name"], reg_row["trade_name"]) < 0.85:
                    problems.append(f'trade name "{f["trade_name"]}" vs registry "{reg_row["trade_name"]}"')
                if problems:
                    c.add("gst_name", "fail", "review", "gst", "Name on the certificate does not match the registry: " + "; ".join(problems) + ".")
                else:
                    c.add("gst_name", "pass", "info", "gst", "Name matches the registry.")
                if sim(f.get("address"), reg_row["principal_place_of_business"]) < 0.9:
                    c.add("gst_address", "warn", "review", "gst", "Address on the certificate differs from the registry.")
                else:
                    c.add("gst_address", "pass", "info", "gst", "Address matches the registry.")
        biz_cert = f.get("trade_name") or split_legal(f.get("legal_name"))[1]
        gst_address = f.get("address")
        if biz_cert:
            business_names.append(("GST certificate", biz_cert))

    # --- 4. Udyam -------------------------------------------------------------------------
    udyam_name = None
    if "udyam" in usable:
        f = usable["udyam"]["fields"]
        num, st = f.get("udyam_number"), f.get("udyam_status")
        if not num or st == "unreadable":
            c.add("udyam_number", "fail", "fix", "udyam", "The Udyam number is missing or unreadable on the certificate. Upload a clear copy or type the number.")
        elif st == "invalid":
            c.add("udyam_number", "fail", "fix", "udyam", "The Udyam number could not be read in a valid format.")
        else:
            c.add("udyam_number", "pass", "info", "udyam", f"Udyam number {mask(num)} read.")
            for corr in usable["udyam"].get("corrections", []):
                c.add("autocorrected", "warn", "info", "udyam", f"Udyam number corrected to {corr['corrected_to']}. Please confirm.")
            if num in ureg:
                c.add("udyam_registry", "pass", "info", "udyam", "Udyam number found in the registry.")
                if sim(f.get("name"), ureg[num]["enterprise_name"]) < 0.85:
                    c.add("udyam_name", "fail", "review", "udyam", f'Enterprise name "{f.get("name")}" does not match the registry "{ureg[num]["enterprise_name"]}".')
                else:
                    c.add("udyam_name", "pass", "info", "udyam", "Name matches the registry.")
            else:
                c.add("udyam_registry", "fail", "review", "udyam", "Udyam number not found in the registry.")
        udyam_name = f.get("name")
        if udyam_name:
            business_names.append(("Udyam certificate", udyam_name))
    elif typed_udyam_ok:
        c.add("udyam_registry", "pass", "info", None, "Typed Udyam number found in the registry.")
        udyam_name = ureg[typed_udyam]["enterprise_name"]
        business_names.append(("Udyam registry", udyam_name))

    # --- 5. Signatory ---------------------------------------------------------------------
    if "id" in usable:
        f = usable["id"]["fields"]
        proprietor = None
        if reg_row:
            proprietor = split_legal(reg_row["legal_name"])[0]
        elif "gst" in usable:
            proprietor = split_legal(usable["gst"]["fields"].get("legal_name"))[0]
        desig = (f.get("designation") or "").lower()
        if proprietor and sim(f.get("name"), proprietor) >= 0.85:
            c.add("signatory", "pass", "info", "id", f"{f.get('name')} is the proprietor named on the GST registration.")
        elif any(a in desig for a in AUTHORISED):
            c.add("signatory", "pass", "info", "id", f"{f.get('name')} signs as {f.get('designation')}.")
        else:
            c.add("signatory", "warn", "review", "id", f'{f.get("name")} is listed as "{f.get("designation")}". An authorisation letter from the owner is needed.')
        vt = _d(f.get("valid_till"))
        if vt is None:
            c.add("id_valid", "fail", "fix", "id", "Could not read the ID's validity date.")
        elif vt < TODAY:
            c.add("id_valid", "fail", "fix", "id", f"ID expired on {vt}.")
        else:
            c.add("id_valid", "pass", "info", "id", f"ID valid until {vt}.")
        if f.get("business"):
            business_names.append(("Signatory ID", f["business"]))

    # --- 6. Address proof -----------------------------------------------------------------
    if "address" in usable:
        f = usable["address"]["fields"]
        bd = _d(f.get("bill_date"))
        if bd is None:
            c.add("address_fresh", "fail", "fix", "address", "Could not read the bill date.")
        else:
            age = (TODAY - bd).days
            if age < 0:
                c.add("address_fresh", "fail", "fix", "address", f"Bill date {bd} is in the future.")
            elif age > ADDRESS_PROOF_MAX_DAYS:
                c.add("address_fresh", "fail", "fix", "address", f"Bill dated {bd} is {age} days old. It must be within {ADDRESS_PROOF_MAX_DAYS} days. Please upload a recent bill.")
            else:
                c.add("address_fresh", "pass", "info", "address", f"Bill is {age} days old (limit {ADDRESS_PROOF_MAX_DAYS}).")
        ref_name = biz_cert or udyam_name
        mismatches = []
        if ref_name and sim(f.get("billed_to"), ref_name) < 0.85:
            mismatches.append(f'billed to "{f.get("billed_to")}" but business is "{ref_name}"')
        if gst_address and sim(f.get("address"), gst_address) < 0.9:
            mismatches.append("supply address differs from the GST address")
        if mismatches:
            c.add("address_match", "warn", "review", "address", "Address proof " + " and ".join(mismatches) + ".")
        else:
            c.add("address_match", "pass", "info", "address", "Address proof matches the business name and address.")
        if f.get("billed_to"):
            business_names.append(("Address proof", f["billed_to"]))

    # --- 7. same business name everywhere ---------------------------------------------------
    if len(business_names) >= 2:
        base_src, base = business_names[0]
        odd = [f'{src}: "{n}"' for src, n in business_names[1:] if sim(n, base) < 0.85]
        if odd:
            c.add("name_consistent", "warn", "review", None, f'Business name differs across documents. {base_src}: "{base}" vs ' + "; ".join(odd) + ".")
        else:
            c.add("name_consistent", "pass", "info", None, "Business name is the same on every document.")

    # --- verdict ----------------------------------------------------------------------------
    worst = max((SEV_RANK[i["severity"]] for i in c.items if i["status"] != "pass"), default=0)
    verdict = {3: "blocked", 2: "action_needed", 1: "manual_review", 0: "verified"}[worst]
    fixes = sorted({i["doc"] for i in c.items if i["status"] == "fail" and i["severity"] == "fix" and i["doc"]})
    gst_doc = usable.get("gst", {}).get("fields", {})
    return {
        "verdict": verdict, "checks": c.items, "gst_verified": gst_verified,
        "fix_docs": fixes,
        "summary": {
            "business_name": biz_cert or udyam_name,
            "gstin_masked": mask(gst_doc.get("gstin")) if gst_doc.get("gstin") else None,
            "gst_status": reg_row["status"] if reg_row else None,
            "address": gst_address,
            "signatory": usable.get("id", {}).get("fields", {}).get("name"),
        },
    }
