"""Generates the architecture / KYC / journey diagrams as SVG + PNG.
    python docs/figures/make_figures.py        (needs: pip install playwright, Chrome installed)
SVG is used in the README; PNG (2x) is placed in the slide deck."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
RED, INK, GREY, SOFT, LINE = "#E40000", "#1B1B1F", "#6B6B76", "#FFF1F1", "#D9D9E0"
FONT = "'Segoe UI','Nirmala UI',Arial,sans-serif"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill="#fff", stroke=INK, sw=3, rx=18, dash=None, op=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} opacity="{op}"/>')

    def text(self, x, y, s, size=24, weight=400, fill=INK, anchor="start"):
        s = s.replace("&", "&amp;")
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>')

    def box(self, x, y, w, h, title, lines=(), fill="#fff", stroke=INK, tc=INK, lc=GREY, ts=30, ls=22, sw=3, center=False):
        self.rect(x, y, w, h, fill, stroke, sw)
        ax, anc = (x + w / 2, "middle") if center else (x + 20, "start")
        self.text(ax, y + 14 + ts, title, ts, 700, tc, anc)
        for i, ln in enumerate(lines):
            self.text(ax, y + 14 + ts + 12 + (i + 1) * (ls + 6), ln, ls, 400, lc, anc)

    def chip(self, x, y, w, h, lines, fill=SOFT, stroke=RED, tc=INK, size=21):
        self.rect(x, y, w, h, fill, stroke, 2, 14)
        n = len(lines)
        for i, ln in enumerate(lines):
            self.text(x + w / 2, y + h / 2 + (i - (n - 1) / 2) * (size + 5) + size * 0.36, ln, size, 600, tc, "middle")

    def cylinder(self, x, y, w, h, lines, size=21):
        ry = 14
        self.add(f'<path d="M{x},{y+ry} v{h-2*ry} a{w/2},{ry} 0 0 0 {w},0 v{-(h-2*ry)}" fill="#F1F1F4" stroke="{INK}" stroke-width="3"/>')
        self.add(f'<ellipse cx="{x+w/2}" cy="{y+ry}" rx="{w/2}" ry="{ry}" fill="#fff" stroke="{INK}" stroke-width="3"/>')
        for i, ln in enumerate(lines):
            self.text(x + w / 2, y + ry * 2 + 20 + i * (size + 4), ln, size, 600, INK, "middle")

    def arrow(self, d, both=False, color=INK, sw=3.5):
        ms = ' marker-start="url(#ah)"' if both else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round" marker-end="url(#ah)"{ms}/>')

    def num(self, x, y, n):
        self.add(f'<circle cx="{x}" cy="{y}" r="17" fill="{RED}"/>')
        self.text(x, y + 7, str(n), 21, 700, "#fff", "middle")

    def render(self):
        defs = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'font-family="{FONT}"><rect width="100%" height="100%" fill="#fff"/>{defs}{"".join(self.parts)}</svg>')


def architecture():
    s = Svg(1600, 810)
    # owner
    s.rect(15, 140, 215, 420, "#fff", INK, 3, 30)
    s.text(122, 190, "Owner's phone", 28, 700, INK, "middle")
    s.text(122, 224, "React · Vite", 22, 400, GREY, "middle")
    for i, t in enumerate(["Chat", "Plan", "Verify", "Track"]):
        s.chip(40, 252 + i * 62, 165, 48, [t], size=23)
    s.text(122, 530, "10 languages", 22, 600, RED, "middle")
    # trust boundary
    s.rect(265, 25, 1030, 770, SOFT, RED, 4, 34, dash="14 10", op=0.55)
    s.rect(290, 12, 400, 38, RED, RED, 0, 19)
    s.text(490, 38, "ONE MACHINE · NO DATA LEAVES", 21, 700, "#fff", "middle")
    # row 1
    s.box(290, 95, 300, 160, "Advisor", ["chat state machine", "asks only what's missing"])
    s.box(640, 95, 300, 160, "Local LLM", ["Gemma 3 4B · Ollama", "understands · explains"], fill=INK, tc="#fff", lc="#D9D9E0")
    s.box(990, 95, 285, 160, "Rules engine", ["bundle · price · 3 packs", "savings · capped offers"], fill=RED, stroke=RED, tc="#fff", lc="#FFE3E3")
    s.chip(640, 268, 300, 40, ["guard: no invented prices"], fill="#fff", stroke=INK, size=20)
    # row 2: KYC
    s.rect(290, 340, 985, 180, "#fff", RED, 4, 18)
    s.text(310, 384, "Smart KYC", 30, 700, INK)
    s.text(1255, 384, "mock GSTIN 3,534 · Udyam 2,723", 21, 600, GREY, "end")
    for i, lines in enumerate([["Blur · skew", "check"], ["RapidOCR", "(local)"], ["Checksum +", "registry repair"], ["Rule checks", "name · address · date"]]):
        s.chip(310 + i * 237, 410, 215, 84, lines, size=21)
        if i < 3:
            s.arrow(f"M{525 + i * 237},452 h22", sw=3)
    # row 3
    s.box(290, 575, 300, 115, "Orders & tracker", ["dates from install days"], ts=28)
    s.box(640, 575, 300, 115, "Consent & audit", ["gate before documents"], ts=28)
    s.box(990, 575, 285, 115, "Lead scoring", ["5,000 leads · AUC 0.74"], ts=28)
    s.cylinder(290, 705, 650, 82, ["SQLite · sessions · consents · orders", "no document images stored"], size=20)
    # back office
    s.rect(1325, 560, 265, 160, "#fff", RED, 4, 22)
    s.text(1457, 612, "Sales &", 28, 700, INK, "middle")
    s.text(1457, 646, "partners", 28, 700, INK, "middle")
    s.text(1457, 690, "who to call · hand-offs", 20, 400, GREY, "middle")
    # arrows
    s.arrow("M230,175 H290", both=True)
    s.arrow("M590,175 H640", both=True)
    s.arrow("M440,95 V70 H1132 V95", both=True)
    s.arrow("M230,430 H290")
    s.arrow("M440,520 V575")
    s.arrow("M790,575 V522")
    s.arrow("M1275,430 H1310 V600 H1325")
    s.arrow("M1275,660 H1325")
    s.arrow("M290,640 H122 V562")
    for x, y, n in [(260, 150, 1), (615, 150, 2), (785, 70, 3), (260, 405, 4), (470, 548, 5), (1310, 515, 6), (1300, 690, 7), (206, 640, 8)]:
        s.num(x, y, n)
    return s


def kyc():
    s = Svg(1600, 500)
    steps = [("1", "Upload", ["photo of each doc", "image stays in memory"]), ("2", "Quality", ["blur check", "auto-straighten tilt"]),
             ("3", "Read", ["OCR on cleaned page", "zoomed strip for IDs"]), ("4", "Repair", ["GSTIN checksum +", "registry match", "owner confirms"]),
             ("5", "Check", ["status · name · address", "signatory · ID expiry", "bill within 90 days"]), ("6", "Decide", ["four outcomes", "shown below"])]
    w = 238
    for i, (n, t, lines) in enumerate(steps):
        x = 12 + i * (w + 28)
        s.rect(x, 50, w, 200, "#fff", RED if i in (3, 5) else INK, 3.5, 20)
        s.add(f'<circle cx="{x+36}" cy="94" r="22" fill="{RED}"/>')
        s.text(x + 36, 102, n, 24, 700, "#fff", "middle")
        s.text(x + 72, 102, t, 31, 700, INK)
        for j, ln in enumerate(lines):
            s.text(x + 18, 156 + j * 30, ln, 21, 400, GREY)
        if i < 5:
            s.arrow(f"M{x + w + 3},150 h22", sw=3.5)
    outs = [("verified", "#0A8F4E", "continue"), ("fix now", "#B36B00", "retake · upload"), ("human review", "#2F54C4", "to partner queue"), ("blocked", RED, "GST items held")]
    xs = [12 + i * 395 + 182 for i in range(4)]
    s.add(f'<path d="M1469,250 V300 H{xs[0]}" fill="none" stroke="{GREY}" stroke-width="3.5"/>')
    s.add(f'<path d="M{xs[0]},300 H{xs[3]}" fill="none" stroke="{GREY}" stroke-width="3.5"/>')
    for i, (t, c, d) in enumerate(outs):
        x = 12 + i * 395
        s.arrow(f"M{xs[i]},300 V340", sw=3.5, color=GREY)
        s.rect(x, 345, 365, 130, "#fff", c, 4, 20)
        s.text(x + 24, 400, t, 31, 700, c)
        s.text(x + 24, 440, d, 23, 400, GREY)
    return s


def journey():
    s = Svg(1600, 330)
    items = [("Language", "10 languages"), ("Advisor", "pains · live pack"), ("Your plan", "3 packs · offers"), ("Consent + KYC", "documents read in seconds"),
             ("Sign", "typed name e-sign"), ("Track", "no support call")]
    w = 232
    for i, (t, d) in enumerate(items):
        x = 14 + i * (w + 38)
        s.rect(x, 60, w, 150, RED if i == 2 else "#fff", RED if i == 2 else INK, 3.5, 22)
        s.text(x + w / 2, 118, t, 29, 700, "#fff" if i == 2 else INK, "middle")
        s.text(x + w / 2, 160, d, 20, 400, "#FFE3E3" if i == 2 else GREY, "middle")
        s.num(x + 26, 80, i + 1)
        if i < 5:
            s.arrow(f"M{x + w + 3},135 h30", sw=3.5)
    s.rect(14, 245, 1572, 62, SOFT, RED, 2.5, 18, dash="10 8")
    s.text(800, 284, "At any step: “talk to a person” → partner or field-sales hand-off, with the profile already filled in", 23, 600, INK, "middle")
    return s


def main():
    figs = {"architecture": architecture(), "kyc_pipeline": kyc(), "journey": journey()}
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        for name, s in figs.items():
            svg = s.render()
            (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
            pg = br.new_page(viewport={"width": s.w, "height": s.h}, device_scale_factor=2)
            pg.set_content(f'<html><body style="margin:0;background:#fff">{svg}</body></html>')
            pg.screenshot(path=str(OUT / f"{name}.png"), clip={"x": 0, "y": 0, "width": s.w, "height": s.h})
            pg.close()
        br.close()
    print("wrote", [f.name for f in sorted(OUT.glob("*.png"))])


if __name__ == "__main__":
    main()
