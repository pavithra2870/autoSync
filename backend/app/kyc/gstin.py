"""GSTIN / Udyam format checks and OCR-error repair.

OCR confuses look-alike characters (O/0, 5/8, I/1). GSTINs carry a checksum and the registry is the
source of truth, so a misread is only 'repaired' when the result passes the checksum AND exists in the
registry. Anything repaired is shown to the owner to confirm; nothing is silently changed."""
import re
from itertools import combinations, product

from ..data import gstin_registry, udyam_registry

CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^\d{2}[A-Z0-9]{10}[A-Z0-9]Z[A-Z0-9]$")
CONFUSABLE = ["0OQD", "1IJ", "58SB", "2Z", "6G"]
_alt = {c: [x for x in g if x != c] for g in CONFUSABLE for c in g}


def clean(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def checksum_ok(g: str) -> bool:
    if not GSTIN_RE.match(g):
        return False
    total = 0
    for i, c in enumerate(g[:14]):
        v = CH.index(c) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return g[14] == CH[(36 - total % 36) % 36]


def mask(s: str | None) -> str:
    """For logs and UI: keep the first 2 and last 3 characters."""
    if not s or len(s) < 8:
        return "***"
    return s[:2] + "*" * (len(s) - 5) + s[-3:]


def lev(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _windows(s: str) -> list[str]:
    if len(s) <= 15:
        return [s]
    return [s[i:i + 15] for i in range(len(s) - 14)]


def repair_gstin(raw: str | None) -> tuple[str | None, str]:
    """Returns (gstin, status) where status is ok | corrected | unreadable | invalid."""
    s = clean(raw)
    if len(s) < 12:
        return None, "unreadable"
    reg = gstin_registry()
    for w in _windows(s):
        if checksum_ok(w):
            return w, "ok"
    base = _windows(s)[0]
    # 1) swap look-alike characters (up to two) and keep only checksum-valid registry hits
    pos = [i for i, c in enumerate(base) if c in _alt]
    hits = set()
    for n in (1, 2):
        for idx in combinations(pos, n):
            for choice in product(*[_alt[base[i]] for i in idx]):
                cand = list(base)
                for i, ch in zip(idx, choice):
                    cand[i] = ch
                cand = "".join(cand)
                if cand in reg:
                    hits.add(cand)
    if len(hits) == 1:
        return hits.pop(), "corrected"
    # 2) closest registry entry in the same state, at most 2 edits
    close = [g for g in reg if g[:2] == base[:2] and lev(base, g, 2) <= 2]
    if len(close) == 1:
        return close[0], "corrected"
    return base, "invalid"


UDYAM_RE = re.compile(r"UDYAM[-\s]*([A-Z]{2})[-\s]*([0-9OIS]{2})[-\s]*([0-9OIS]{7})")


def _digits(s: str) -> str:
    return s.replace("O", "0").replace("I", "1").replace("S", "5")


def repair_udyam(raw: str | None) -> tuple[str | None, str]:
    text = (raw or "").upper()
    m = UDYAM_RE.search(text)
    if not m:
        return None, "unreadable" if len(clean(text)) < 6 else "invalid"
    num = f"UDYAM-{m.group(1)}-{_digits(m.group(2))}-{_digits(m.group(3))}"
    reg = udyam_registry()
    if num in reg:
        return num, "ok" if num == f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" else "corrected"
    close = [u for u in reg if u[:8] == num[:8] and lev(num, u, 2) <= 2]
    if len(close) == 1:
        return close[0], "corrected"
    return num, "invalid"
