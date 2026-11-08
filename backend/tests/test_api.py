from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)


def journey():
    r = c.post("/api/session", json={"language": "en"}).json()
    sid = r["session_id"]
    for slot, value in [("segment", "prof"), ("needs", ["cctv"]), ("city", "Kochi"), ("employees", "10"), ("sites", "1"),
                        ("internet", "home_broadband"), ("gst", "gst"), ("spend", "3500")]:
        assert r["question"]["slot"] == slot
        r = c.post(f"/api/session/{sid}/answer", json={"slot": slot, "value": value}).json()
    assert r["done"]
    return sid


def test_health_and_i18n():
    assert c.get("/api/health").json()["ok"]
    hi = c.get("/api/i18n/hi").json()
    assert hi["coverage"] == 1.0 and "सलाहकार" in hi["strings"]["step.chat"]


def test_quote_toggle_reprices_on_server():
    sid = journey()
    q = c.get(f"/api/session/{sid}/quote").json()
    base = q["totals"]["monthly"]
    sel = {l["product_id"]: l["qty"] for l in q["lines"] if l["selected"]}
    sel["P22"] = 1  # add secure wifi
    q2 = c.post(f"/api/session/{sid}/quote", json={"selections": sel}).json()
    assert q2["totals"]["monthly"] > base
    q3 = c.post(f"/api/session/{sid}/quote", json={"selections": sel, "contract_months": 24}).json()
    assert q3["totals"]["monthly"] < q2["totals"]["monthly"]


def test_registry_lookup_and_status():
    ok = c.get("/api/registry/gstin/37IHKXV5167L1ZS").json()
    assert ok["found"] and ok["status"] == "Cancelled"  # K01
    assert not c.get("/api/registry/gstin/99ZZZZZZZZZZ1Z1").json()["found"]
    u = c.get("/api/registry/udyam/UDYAM-WB-00-5053330").json()
    assert u["found"] and u["name"] == "Harmony Dental Care"


def test_documents_require_consent():
    sid = journey()
    r = c.post(f"/api/session/{sid}/kyc/document", data={"slot": "gst"}, files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 403
    c.post(f"/api/session/{sid}/consent", json={"granted": True})
    r = c.post(f"/api/session/{sid}/kyc/document", data={"slot": "gst"}, files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_checkout_blocked_until_kyc_done():
    sid = journey()
    r = c.post(f"/api/session/{sid}/checkout", json={"signed_name": "Test Owner", "agree": True})
    assert r.status_code == 409


def test_admin_endpoints():
    assert c.get("/api/admin/insights").json()["funnel"][0]["leads"] == 5000
    leads = c.get("/api/admin/leads?limit=5").json()
    assert len(leads) == 5 and leads[0]["score"] >= leads[0]["score"] * 0 and "action" in leads[0]
    assert c.get("/api/admin/model").json()["auc"] > 0.65


def test_parallel_uploads_do_not_lose_documents(monkeypatch):
    """Regression: four parallel uploads used to overwrite each other's session update."""
    import io
    from concurrent.futures import ThreadPoolExecutor

    from PIL import Image

    import app.main as m

    monkeypatch.setattr(m, "parse_document", lambda img: {"doc_type": "x", "sharpness": 500.0, "blurry": False,
                                                          "fields": {}, "corrections": []})
    sid = journey()
    c.post(f"/api/session/{sid}/consent", json={"granted": True})
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")

    def up(slot):
        return c.post(f"/api/session/{sid}/kyc/document", data={"slot": slot},
                      files={"file": ("a.png", buf.getvalue(), "image/png")}).status_code

    with ThreadPoolExecutor(4) as ex:
        assert list(ex.map(up, ["gst", "udyam", "id", "address"])) == [200] * 4
    from app.db import load_session
    assert set(load_session(sid)["kyc"]["docs"]) == {"gst", "udyam", "id", "address"}


def test_late_explanation_does_not_erase_consent():
    """Regression: the AI explanation finishes after the owner has already consented; it must not
    overwrite the session with the stale copy it loaded before the model started."""
    from app import advisor
    from app.db import load_session

    sid = journey()
    stale = load_session(sid)
    c.post(f"/api/session/{sid}/consent", json={"granted": True})
    advisor.explanation(stale)  # finishes "late"
    assert load_session(sid)["kyc"]["consent"] is True
