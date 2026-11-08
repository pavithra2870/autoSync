"""Re-creates every README/deck screenshot by driving the real UI in headless Chrome.
Needs the server on :8000 (LLM on for the Hindi free-text turn and the AI-written explanation) and `pip install playwright`.
    python backend/scripts/take_screenshots.py [--skip-hindi] [--only-kyc K06,K07]
"""
import sys
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

B = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
PHONE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

# Answers per question slot (chip values). Pain points are multi-select.
OFFICE = {"segment": "prof", "needs": ["uptime", "security"], "city": "Pune", "employees": "10", "sites": "1",
          "internet": "home_broadband", "gst": "gst", "spend": "3500"}
KIRANA = {"segment": "micro", "needs": ["uptime", "pos", "bills"], "city": "Pune", "employees": "3", "sites": "1",
          "internet": "mobile_hotspot", "gst": "none", "spend": "1500"}


def settle(pg, t=60000):
    pg.wait_for_selector(".typing", state="detached", timeout=t)
    pg.wait_for_timeout(400)


def slot(pg):
    pg.wait_for_selector(".chips[data-slot], .dock .btn.primary.block", timeout=30000)
    el = pg.locator(".chips[data-slot]")
    return el.get_attribute("data-slot") if el.count() else None


def answer(pg, plan, stop_at=None):
    """Answer questions by tapping chips until the plan button shows (or `stop_at` slot is asked)."""
    for _ in range(12):
        s = slot(pg)
        if s is None or s == stop_at:
            return s
        v = plan[s]
        if isinstance(v, list):
            for x in v:
                pg.locator(f'.chips .chip[data-value="{x}"]').click()
            pg.locator(".chip.go").click()
        else:
            pg.locator(f'.chips .chip[data-value="{v}"]').click()
        settle(pg)
    raise RuntimeError("advisor did not finish")


def scroll_to(pg, sel, offset=70):
    pg.evaluate("([s,o]) => window.scrollTo(0, document.querySelector(s).getBoundingClientRect().top + window.scrollY - o)", [sel, offset])
    pg.wait_for_timeout(350)


def open_plan(pg):
    pg.click(".dock .btn.primary.block")
    pg.wait_for_selector(".price-card", timeout=20000)
    pg.wait_for_timeout(500)


def start(br, lang_label="English"):
    ctx = br.new_context(**PHONE)
    pg = ctx.new_page()
    pg.goto(B); pg.wait_for_selector(".lang-card"); pg.click(f"text={lang_label}"); pg.wait_for_selector(".chip")
    try:  # screenshots should show the AI badge, not a transient 'Simple mode'
        pg.wait_for_selector(".mode.ai", timeout=15000)
    except Exception:
        pass
    settle(pg)
    return ctx, pg


def to_kyc(br):
    ctx, pg = start(br)
    answer(pg, OFFICE)
    open_plan(pg)
    return ctx, pg


def kyc_case(br, k, shots):
    ctx, pg = to_kyc(br)
    pg.click(".dock .btn.primary"); pg.wait_for_selector(".consent")
    if "consent" in shots: pg.screenshot(path=str(OUT / "05_consent.png"))
    pg.click("text=I agree"); pg.wait_for_selector(".sample select")
    pg.select_option(".sample select", k)
    pg.wait_for_function("document.querySelectorAll('.slot.done').length>=3", timeout=240000)
    pg.wait_for_function("document.querySelectorAll('.slot.uploading').length===0", timeout=240000)
    pg.click("text=Check my documents"); pg.wait_for_selector(".verdict", timeout=60000)
    scroll_to(pg, ".sample"); pg.screenshot(path=str(OUT / f"06_kyc_{k}_documents.png"))
    scroll_to(pg, ".verdict"); pg.screenshot(path=str(OUT / f"07_kyc_{k}_verdict.png"))
    return ctx, pg


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)

        if "--skip-hindi" not in sys.argv and "--only-kyc" not in sys.argv:
            # --- Hindi: language screen, one sentence fills four answers, pain question, plan ---
            ctx = br.new_context(**PHONE); pg = ctx.new_page()
            pg.goto(B); pg.wait_for_selector(".lang-card"); pg.screenshot(path=str(OUT / "01_language.png"))
            pg.click("text=हिन्दी"); pg.wait_for_selector(".chip"); settle(pg)
            pg.screenshot(path=str(OUT / "02_chat_hindi_start.png"))
            pg.fill(".composer input", "मेरा पुणे में एक डेंटल क्लिनिक है, 12 लोग काम करते हैं। हमारे पास GST है।")
            pg.click(".composer .btn"); pg.wait_for_selector(".typing", timeout=8000); settle(pg, 150000); pg.wait_for_timeout(1000)
            pg.screenshot(path=str(OUT / "03_chat_hindi_understood.png"))
            answer(pg, OFFICE)
            open_plan(pg)
            pg.wait_for_selector(".why-card p", timeout=150000)
            pg.screenshot(path=str(OUT / "04_plan_hindi.png"))
            ctx.close()

        if "--only-kyc" not in sys.argv:
            # --- English kirana: pain chips, live pack, reveal, and the selling plan page ---
            ctx, pg = start(br)
            pg.locator('.chips .chip[data-value="micro"]').click(); settle(pg)
            for x in KIRANA["needs"]:
                pg.locator(f'.chips .chip[data-value="{x}"]').click()
            pg.mouse.move(2, 2); pg.wait_for_timeout(1200)
            pg.screenshot(path=str(OUT / "03b_chat_pains.png"))
            pg.locator(".chip.go").click(); settle(pg)
            answer(pg, KIRANA, stop_at="gst")
            pg.mouse.move(2, 2); pg.wait_for_timeout(1200)  # let the chat finish scrolling, no hover state
            pg.screenshot(path=str(OUT / "03c_chat_pack.png"))
            answer(pg, KIRANA)
            pg.click(".dock .btn.primary.block"); pg.wait_for_selector(".reveal li"); pg.wait_for_timeout(1700)
            pg.screenshot(path=str(OUT / "04a_reveal.png"))
            pg.wait_for_selector(".price-card", timeout=20000); pg.wait_for_timeout(600)
            pg.screenshot(path=str(OUT / "04b_plan_top.png"))
            scroll_to(pg, ".fixes", 62); pg.screenshot(path=str(OUT / "04c_plan_fix_compare.png"))
            scroll_to(pg, ".offers", 62); pg.screenshot(path=str(OUT / "04d_plan_offers.png"))
            ctx.close()

        # --- KYC cases ---
        only = sys.argv[sys.argv.index("--only-kyc") + 1].split(",") if "--only-kyc" in sys.argv else None
        for k, extra in [("K06", {"consent"}), ("K07", set()), ("K04", set()), ("K01", set()), ("K11", set())]:
            if only and k not in only:
                continue
            ctx, pg = kyc_case(br, k, extra)
            if k == "K06":
                pg.locator(".confirm-box input").check(); pg.click("text=Continue →"); pg.wait_for_selector(".confirm")
                pg.fill(".field input", "Pooja Shah"); pg.locator(".confirm-box input").check()
                pg.screenshot(path=str(OUT / "08_confirm_and_sign.png"))
                pg.click("text=Place order"); pg.wait_for_selector(".timeline")
                for _ in range(3):
                    pg.click("text=Demo: move to next step"); pg.wait_for_timeout(700)
                pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(300)
                pg.screenshot(path=str(OUT / "09_tracker.png"))
            ctx.close()

        if "--only-kyc" in sys.argv:
            br.close()
            print("done (kyc only)")
            return

        # --- Back office (desktop) ---
        r = httpx.post(f"{B}/api/session", json={"language": "en"}, timeout=60).json()
        httpx.post(f"{B}/api/session/{r['session_id']}/answer", json={"text": "I want to talk to a person"}, timeout=200)
        ctx = br.new_context(viewport={"width": 1440, "height": 860}, device_scale_factor=2); pg = ctx.new_page()
        pg.goto(B + "/#/admin"); pg.wait_for_selector("tbody tr", timeout=90000); pg.wait_for_timeout(500)
        pg.screenshot(path=str(OUT / "10_admin_leads.png"))
        pg.click("text=Live hand-offs"); pg.wait_for_selector("tbody tr", timeout=20000); pg.wait_for_timeout(500)
        pg.screenshot(path=str(OUT / "11_admin_handoffs.png"))
        pg.click("text=Insights"); pg.wait_for_selector(".bar-row"); pg.wait_for_timeout(500)
        pg.screenshot(path=str(OUT / "12_admin_insights.png"))
        br.close()
    print("done:", sorted(x.name for x in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
