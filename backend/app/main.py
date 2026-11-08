"""FastAPI app. One process serves the API and the built React frontend."""
import io
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from . import advisor, db, i18n, leads_ml, llm, orders
from .catalogue import Profile
from .config import ADDRESS_PROOF_MAX_DAYS, DATA_DIR, FRONTEND_DIST, LLM_MODEL, RETENTION_DAYS_ABANDONED, RETENTION_DAYS_ACTIVE, TODAY
from .data import gstin_registry, udyam_registry
from .kyc import gstin as gst
from .kyc.parse import parse_document
from .kyc.validate import EXPECTED, verify
from .recommender import quote

CONSENT_VERSION = "2026-07-v1"
CONSENT_PURPOSES = ["verify_business", "activate_service"]
MAX_UPLOAD = 8 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    # warm things that are slow on first use so the demo does not stall
    if llm.available():
        llm.warm()
    threading.Thread(target=leads_ml.model, daemon=True).start()
    yield


app = FastAPI(title="Accel Business: Udyam Digital", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _session(sid: str) -> dict:
    s = db.load_session(sid)
    if not s:
        raise HTTPException(404, "Unknown session")
    return s


# ------------------------------------------------------------------------------------------
# meta
# ------------------------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.available(), "model": LLM_MODEL, "demo_today": TODAY.isoformat()}


@app.get("/api/i18n/{lang}")
def get_i18n(lang: str):
    i18n.ensure_translation_async(lang)
    return {"lang": lang, "strings": i18n.get_dict(lang), "coverage": round(i18n.translation_coverage(lang), 2)}


# ------------------------------------------------------------------------------------------
# advisor
# ------------------------------------------------------------------------------------------
class NewSession(BaseModel):
    language: str = "en"


class Answer(BaseModel):
    text: str | None = None
    slot: str | None = None
    value: str | int | list[str] | None = None
    skip: bool = False


@app.post("/api/session")
def new_session(body: NewSession):
    lang = body.language if body.language in llm.LANG_NAMES else "en"
    i18n.ensure_translation_async(lang)
    return advisor.start(lang)


@app.post("/api/session/{sid}/answer")
def answer(sid: str, body: Answer):
    s = _session(sid)
    return advisor.answer(s, text=body.text, slot=body.slot, value=body.value, skip=body.skip)


# ------------------------------------------------------------------------------------------
# quote
# ------------------------------------------------------------------------------------------
class QuoteReq(BaseModel):
    selections: dict[str, int] | None = None
    contract_months: int | None = None


@app.get("/api/session/{sid}/quote")
def get_quote(sid: str):
    s = _session(sid)
    if not s["done"]:
        raise HTTPException(409, "Advisor has not finished")
    return advisor.build_quote(s)


@app.post("/api/session/{sid}/quote")
def post_quote(sid: str, body: QuoteReq):
    s = _session(sid)
    s["selections"], s["contract"] = body.selections, body.contract_months
    db.save_session(s)
    return advisor.build_quote(s)


@app.get("/api/session/{sid}/explanation")
def get_explanation(sid: str):
    return advisor.explanation(_session(sid))


# ------------------------------------------------------------------------------------------
# registry lookups (the mock "GSTIN lookup" and "Udyam lookup" APIs)
# ------------------------------------------------------------------------------------------
@app.get("/api/registry/gstin/{number}")
def lookup_gstin(number: str):
    g = gst.clean(number)
    fmt = gst.checksum_ok(g)
    row = gstin_registry().get(g)
    db.audit(None, "gstin_lookup", f"{gst.mask(g)} found={bool(row)}")
    if not row:
        return {"found": False, "format_ok": fmt}
    return {"found": True, "format_ok": fmt, "legal_name": row["legal_name"], "trade_name": row["trade_name"],
            "constitution": row["constitution"], "address": row["principal_place_of_business"],
            "status": row["status"], "registered": row["registration_date"]}


@app.get("/api/registry/udyam/{number}")
def lookup_udyam(number: str):
    u, _ = gst.repair_udyam(number)
    row = udyam_registry().get(u or "")
    db.audit(None, "udyam_lookup", f"{gst.mask(u)} found={bool(row)}")
    if not row:
        return {"found": False}
    return {"found": True, "name": row["enterprise_name"], "type": row["enterprise_type"], "activity": row["major_activity"],
            "city": row["city"], "state": row["state"], "registered": row["date_of_registration"], "number": u}


# ------------------------------------------------------------------------------------------
# KYC
# ------------------------------------------------------------------------------------------
class Consent(BaseModel):
    granted: bool


class VerifyReq(BaseModel):
    gstin: str | None = None
    udyam: str | None = None


def _kyc(s: dict) -> dict:
    s["kyc"] = s.get("kyc") or {"consent": False, "docs": {}, "result": None}
    return s["kyc"]


@app.get("/api/kyc/policy")
def kyc_policy():
    return {"version": CONSENT_VERSION, "purposes": CONSENT_PURPOSES, "retention_days_active": RETENTION_DAYS_ACTIVE,
            "retention_days_abandoned": RETENTION_DAYS_ABANDONED, "images_stored": False,
            "address_proof_max_days": ADDRESS_PROOF_MAX_DAYS}


@app.post("/api/session/{sid}/consent")
def consent(sid: str, body: Consent):
    s = _session(sid)
    db.add_consent(sid, CONSENT_VERSION, s["lang"], CONSENT_PURPOSES, body.granted)
    k = _kyc(s)
    k["consent"] = body.granted
    if not body.granted:
        k["docs"], k["result"] = {}, None  # withdrawing consent erases what we extracted
    db.audit(sid, "consent", f"granted={body.granted} v={CONSENT_VERSION}")
    db.save_session(s)
    return {"granted": body.granted, "version": CONSENT_VERSION}


@app.post("/api/session/{sid}/kyc/document")
def upload_document(sid: str, slot: str = Form(...), file: UploadFile = File(...)):
    s = _session(sid)
    k = _kyc(s)
    if not k["consent"]:
        raise HTTPException(403, "Consent is required before documents are collected")
    if slot not in EXPECTED:
        raise HTTPException(400, "Unknown document slot")
    raw = file.file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (8 MB max)")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "That file is not an image")
    parsed = parse_document(img)  # image lives only in memory; it is never written to disk
    del raw, img
    def store(cur):  # atomic: parallel uploads and a late AI explanation must not overwrite each other
        kk = _kyc(cur)
        kk["docs"][slot] = parsed
        kk["result"] = None

    db.update_session(sid, store)
    db.audit(sid, "kyc_doc", f"slot={slot} type={parsed['doc_type']} blurry={parsed['blurry']}")
    return {"slot": slot, "doc_type": parsed["doc_type"], "blurry": parsed["blurry"], "sharpness": parsed["sharpness"],
            "deskewed_deg": parsed.get("deskewed_deg"), "corrections": parsed["corrections"],
            "fields": {kk: v for kk, v in parsed["fields"].items() if not kk.endswith("_raw")}}


@app.delete("/api/session/{sid}/kyc/document/{slot}")
def delete_document(sid: str, slot: str):
    def drop(cur):
        kk = _kyc(cur)
        kk["docs"].pop(slot, None)
        kk["result"] = None

    db.update_session(sid, drop)
    return {"ok": True}


@app.post("/api/session/{sid}/kyc/verify")
def kyc_verify(sid: str, body: VerifyReq):
    s = _session(sid)
    k = _kyc(s)
    if not k["consent"]:
        raise HTTPException(403, "Consent is required")
    prof = advisor.profile_of(s)
    typed = {"gstin": gst.clean(body.gstin) or None, "udyam": gst.repair_udyam(body.udyam)[0] if body.udyam else None}
    result = verify(k["docs"], typed, needs_gst=prof.has_gstin is not False)
    k["result"] = result
    s["gst_verified"] = result["gst_verified"]
    if result["verdict"] in ("blocked", "manual_review"):
        advisor.handoff(s, prof, f"kyc_{result['verdict']}")
    db.audit(sid, "kyc_verify", f"verdict={result['verdict']} gst_verified={result['gst_verified']}")
    db.save_session(s)
    q = advisor.build_quote(s)
    held = [l["product_id"] for l in q["lines"] if any(r["code"] == "needs_gstin" for r in l["locked"])
            and l["group"] in ("core", "rec")]
    return {**result, "held_products": held, "quote": q}


@app.get("/api/kyc/specimens")
def specimens():
    out = []
    for i in range(1, 13):
        k = f"K{i:02d}"
        files = {slot: f"{k}_{name}.png" for slot, name in
                 {"gst": "gst_certificate", "udyam": "udyam_certificate", "id": "signatory_id", "address": "address_proof"}.items()
                 if (DATA_DIR / "kyc_documents" / f"{k}_{name}.png").exists()}
        out.append({"id": k, "slots": list(files)})
    return out


@app.get("/api/kyc/specimen/{k}/{slot}")
def specimen_file(k: str, slot: str):
    names = {"gst": "gst_certificate", "udyam": "udyam_certificate", "id": "signatory_id", "address": "address_proof"}
    if slot not in names or not (k.startswith("K") and k[1:].isdigit()):
        raise HTTPException(404)
    f = DATA_DIR / "kyc_documents" / f"{k}_{names[slot]}.png"
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="image/png")


# ------------------------------------------------------------------------------------------
# checkout + tracker
# ------------------------------------------------------------------------------------------
class Checkout(BaseModel):
    signed_name: str
    agree: bool


@app.post("/api/session/{sid}/checkout")
def checkout(sid: str, body: Checkout):
    s = _session(sid)
    k = _kyc(s)
    result = k.get("result")
    if not body.agree or len(body.signed_name.strip()) < 3:
        raise HTTPException(400, "Please type your full name and accept the terms")
    if not result or result["verdict"] == "action_needed":
        raise HTTPException(409, "Documents are not verified yet")
    wanted = advisor.build_quote({**s, "gst_verified": None})  # what they chose before KYC
    q = advisor.build_quote(s)
    held = [{"product_id": l["product_id"], "name": l["name"]} for l in wanted["lines"] if l["selected"]
            and l["product_id"] not in {x["product_id"] for x in q["lines"] if x["selected"]}]
    order = orders.create_order(s, q, held, result["verdict"], body.signed_name.strip())
    s["order_id"] = order["id"]
    db.audit(sid, "order", f"id={order['id']} verdict={result['verdict']}")
    db.save_session(s)
    return order


@app.get("/api/orders/{oid}")
def get_order(oid: str):
    o = db.load_order(oid)
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@app.post("/api/orders/{oid}/advance")
def advance_order(oid: str):
    o = db.load_order(oid)
    if not o:
        raise HTTPException(404, "Order not found")
    return orders.advance(o)


# ------------------------------------------------------------------------------------------
# back office
# ------------------------------------------------------------------------------------------
@app.get("/api/admin/leads")
def admin_leads(limit: int = 40, segment: str | None = None, owner: str | None = None):
    return leads_ml.priority_leads(min(limit, 200), segment, owner)


@app.get("/api/admin/model")
def admin_model():
    m = leads_ml.model()
    return {k: m[k] for k in ("auc", "top_decile_lift", "base_rate", "n", "drivers_up", "drivers_down")}


@app.get("/api/admin/insights")
def admin_insights():
    return leads_ml.insights()


@app.get("/api/admin/handoffs")
def admin_handoffs():
    return db.list_handoffs()


# ------------------------------------------------------------------------------------------
# frontend (built with `npm run build` in /frontend)
# ------------------------------------------------------------------------------------------
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="web")
