"""The selling numbers must be honest and consistent."""
from app.catalogue import Profile
from app.data import find_city
from app.recommender import quote
from app.segments import derive_segment
from app.value import FIRST_MONTH_CAP, SETUP_WAIVER_CAP, sell, tiers


def mk(btype, city, emp, sites, gst=True, needs=(), internet=None, spend=None):
    c = find_city(city)
    return Profile(business_type=btype, segment=derive_segment(btype, None, emp, sites), employees=emp, sites=sites,
                   city=c["name"], city_tier=c["tier"], state=c["state"], has_gstin=gst, needs=list(needs),
                   current_internet=internet, monthly_spend=spend)


CASES = [
    mk("kirana store", "Pune", 3, 1, gst=False, internet="mobile_hotspot", spend=1500),
    mk("kirana store", "Pune", 3, 1, needs=["uptime", "pos", "cctv"]),
    mk("dental clinic", "Kochi", 12, 1, needs=["security"], spend=3500),
    mk("restaurant chain", "Pune", 60, 6, spend=10000),
    mk("textile unit", "Surat", 90, 2, spend=25000),
]


def test_saving_is_against_separate_list_price_and_adds_up():
    for p in CASES:
        q = quote(p)
        s = sell(q, p)
        sel = [l for l in q["lines"] if l["selected"]]
        assert s["separate_monthly"] == sum(l["price_max"] * l["qty"] for l in sel)
        assert s["separate_monthly"] >= q["totals"]["monthly"]
        assert s["year_separate"] - s["year_pack"] == s["saving_year"] > 0
        assert s["months_free"] == s["saving_year"] // q["totals"]["monthly"]


def test_offers_are_capped():
    for p in CASES:
        q = quote(p)
        s = sell(q, p)
        offers = {o["key"]: o for o in s["offers"]}
        assert offers.get("setup", {"amount": 0})["amount"] <= min(SETUP_WAIVER_CAP, q["totals"]["setup"])
        assert offers["half"]["amount"] <= FIRST_MONTH_CAP
        assert s["first_month_pay"] == q["totals"]["monthly"] - offers["half"]["amount"]


def test_today_spend_is_never_called_a_saving_when_we_cost_more():
    p = CASES[0]
    s = sell(quote(p), p)
    assert s["vs_today"]["diff_month"] > 0 and s["vs_today"]["diff_day"] > 0  # shown as "a little more a day"


def test_switch_offer_only_when_they_have_a_connection():
    assert "switch" in {o["key"] for o in sell(quote(CASES[0]), CASES[0])["offers"]}
    p = mk("kirana store", "Pune", 3, 1, internet="none")
    assert "switch" not in {o["key"] for o in sell(quote(p), p)["offers"]}


def test_tiers_grow_and_recommended_is_the_default():
    for p in CASES:
        q = quote(p)
        t = tiers(p, q["contract_months"], None)
        keys = [x["key"] for x in t]
        assert "recommended" in keys and len(t) >= 2
        rec = next(x for x in t if x["key"] == "recommended")
        assert set(rec["ids"]) == {l["product_id"] for l in q["lines"] if l["selected"]}
        prices = [x["monthly"] for x in t]
        assert prices == sorted(prices) and len(set(prices)) == len(prices)
        for x in t:  # every tier is itself a valid bundle
            tq = quote(p, x["selections"], q["contract_months"])
            assert {l["product_id"] for l in tq["lines"] if l["selected"]} == set(x["ids"])
