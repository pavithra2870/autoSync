import pytest

from app.catalogue import Profile, catalogue, ineligible_reasons
from app.data import find_city
from app.recommender import quote
from app.segments import derive_segment


def mk(btype, city, emp, sites, gst=True, needs=(), internet=None):
    c = find_city(city)
    seg = derive_segment(btype, None, emp, sites)
    return Profile(business_type=btype, segment=seg, employees=emp, sites=sites, city=c["name"],
                   city_tier=c["tier"], state=c["state"], has_gstin=gst, needs=list(needs),
                   current_internet=internet)


def selected(q):
    return {l["product_id"]: l["qty"] for l in q["lines"] if l["selected"]}


def test_every_default_bundle_respects_hard_rules():
    cat = catalogue()
    cases = [
        mk("kirana store", "Ludhiana", 3, 1, gst=False),
        mk("dental clinic", "Kochi", 12, 1),
        mk("CA firm", "Mumbai", 20, 1),
        mk("restaurant chain", "Pune", 60, 6),
        mk("textile unit", "Surat", 90, 2),
        mk("auto-parts unit", "Chennai", 30, 1, gst=False),
        mk("bakery chain", "Delhi", 40, 4, gst=False, needs=["cctv", "pos"]),
    ]
    for prof in cases:
        q = quote(prof)
        sel = selected(q)
        assert any(p in sel for p in ("P01", "P02", "P03", "P04", "P05", "P06")), "must include internet"
        assert sum(p in sel for p in ("P01", "P02", "P03", "P04", "P05", "P06")) == 1, "only one internet plan"
        for pid in sel:
            assert not ineligible_reasons(cat[pid], prof), (prof.business_type, pid)
            deps = cat[pid].requires_one_of
            assert not deps or deps & set(sel), (prof.business_type, pid, "dependency missing")
        assert q["contract_months"] >= max(cat[p].min_contract for p in sel)


def test_no_gstin_never_sells_gstin_products():
    cat = catalogue()
    q = quote(mk("dental clinic", "Kochi", 12, 1, gst=False, needs=["whatsapp", "phone"]))
    sel = selected(q)
    assert not any(cat[p].requires_gstin for p in sel)
    locked = {l["product_id"]: l["locked"] for l in q["lines"] if not l["selected"]}
    assert any(r["code"] == "needs_gstin" for r in locked["P15"])


def test_tier2_city_cannot_get_1g_fibre():
    q = quote(mk("CA firm", "Nagpur", 30, 1))
    assert "P03" not in selected(q)


def test_tier1_large_office_gets_1g_with_gstin():
    q = quote(mk("CA firm", "Mumbai", 30, 1))
    assert "P03" in selected(q)


def test_small_manufacturer_without_gstin_gets_fibre_not_leased_line():
    q = quote(mk("textile unit", "Surat", 40, 1, gst=False))
    assert "P02" in selected(q) and "P05" not in selected(q)


def test_leased_line_needs_10_staff():
    prof = mk("textile unit", "Surat", 8, 1)
    assert "P05" not in selected(quote(prof))


def test_multisite_gets_sdwan_and_24_month_contract():
    q = quote(mk("pharmacy chain", "Hyderabad", 50, 5))
    assert "P10" in selected(q)
    assert q["contract_months"] == 24


def test_removing_internet_drops_dependents():
    prof = mk("dental clinic", "Kochi", 12, 1)
    q = quote(prof, {"P07": 2, "P23": 2})  # camera needs internet; base gets re-added
    sel = selected(q)
    assert "P01" in sel or "P02" in sel
    assert "P23" in sel


def test_price_within_catalogue_range_and_24_month_is_cheaper():
    prof = mk("dental clinic", "Kochi", 12, 1)
    q12 = quote(prof, contract=12)
    q24 = quote(prof, contract=24)
    for l in q12["lines"]:
        assert l["price_min"] <= l["unit_price"] <= l["price_max"]
    assert q24["totals"]["monthly"] < q12["totals"]["monthly"]


def test_gst_failed_kyc_removes_gstin_products():
    cat = catalogue()
    prof = mk("textile unit", "Surat", 40, 1)  # has_gstin claimed
    assert "P05" in selected(quote(prof))
    q = quote(prof, None, None, gst_verified=False)
    assert not any(cat[p].requires_gstin for p in selected(q))


@pytest.mark.parametrize("btype,exp", [
    ("Kirana store", "micro"), ("dental clinic", "prof"), ("Bakery chain", "multi"),
    ("auto parts unit", "mfg"), ("law office", "prof"), ("salon", "micro"),
])
def test_segment_from_business_type(btype, exp):
    assert derive_segment(btype, None, None, None) == exp


def test_three_sites_forces_multi():
    assert derive_segment("kirana store", None, 10, 3) == "multi"
