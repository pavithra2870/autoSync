"""Turns one uploaded document image into typed fields. Local OCR only; the image is never saved."""
import re
import statistics
from difflib import SequenceMatcher
from itertools import combinations

from PIL import Image

from . import ocr
from .gstin import clean, repair_gstin, repair_udyam

BLUR_LIMIT = 100.0  # specimens: 800+ when sharp, 2 when blurred. Real photos need calibrating.

TITLES = [
    ("gst_certificate", ["gst registration", "gst certificate"]),
    ("udyam_certificate", ["udyam registration", "udyam certificate"]),
    ("signatory_id", ["signatory", "authorised signatory"]),
    ("address_proof", ["electricity bill", "water bill", "gas bill", "telephone bill", "utility bill"]),
]
ROW_LABELS = {
    "gst_certificate": {
        "gstin": ["gstin"], "legal_name": ["legal name"], "trade_name": ["trade name"],
        "constitution": ["constitution"], "address": ["address of principal"], "address2": ["place of business"],
        "date": ["date of liability"],
    },
    "udyam_certificate": {
        "udyam_number": ["udyam reg"], "name": ["enterprise name"], "activity": ["major activity"],
        "city": ["city"], "state": ["state"], "date": ["date of registration"],
    },
    "address_proof": {
        "consumer_no": ["consumer no"], "billed_to": ["billed to"], "address": ["supply address"],
        "bill_date": ["bill date"],
    },
}
CARD_LABELS = {"name": ["name"], "designation": ["designation"], "business": ["for business"],
               "id_no": ["id no"], "valid_till": ["valid till"]}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def classify(boxes: list[ocr.Box], height: float) -> str | None:
    top = _norm(" ".join(b.text for b in boxes if b.y0 < 0.14 * height))
    for doc_type, keys in TITLES:
        if any(_norm(k) in top for k in keys):
            return doc_type
    alltext = _norm(" ".join(b.text for b in boxes))
    for doc_type, keys in TITLES:
        if any(_norm(k) in alltext for k in keys):
            return doc_type
    return None


def _find_labels(boxes, labels, left_limit):
    found = {}
    for b in boxes:
        if b.x0 > left_limit:
            continue
        n = _norm(b.text)
        for key, variants in labels.items():
            if key in found:
                continue
            for v in variants:
                if n.startswith(_norm(v)) or SequenceMatcher(None, n, _norm(v)).ratio() > 0.86:
                    found[key] = b
                    break
    return found


# Row order on each form. Rows are evenly spaced, so a couple of detected labels pin down every row
# even when a stamp or watermark hides another label.
ROW_ORDER = {
    "gst_certificate": ["gstin", "legal_name", "trade_name", "constitution", "address", "address2", "date", "reg_type"],
    "udyam_certificate": ["udyam_number", "name", "activity", "city", "state", "date"],
    "address_proof": ["consumer_no", "billed_to", "address", "address2", "bill_date", "units", "amount"],
}
ID_FIELDS = {"gstin", "udyam_number"}  # monospaced IDs: re-read from a zoomed strip


def _geometry(found, order, h):
    pts = [(order.index(k), b.cy) for k, b in found.items() if k in order]
    ests = [(c2 - c1) / (i2 - i1) for (i1, c1), (i2, c2) in combinations(pts, 2) if i2 != i1]
    rowh = statistics.median(ests) if ests else 70 * h / 1754
    y0 = statistics.median(c - i * rowh for i, c in pts) if pts else 265 * h / 1754
    return y0, rowh


def _parse_rows(img: Image.Image, boxes, doc_type) -> dict:
    w, h = img.size
    labels = ROW_LABELS[doc_type]
    order = ROW_ORDER[doc_type]
    found = _find_labels(boxes, labels, 0.35 * w)
    y0, rowh = _geometry(found, order, h)
    x_start = (max(b.x1 for b in found.values()) + 12) if found else 0.385 * w

    def row_text(i):
        cy = y0 + i * rowh
        bs = [b for b in boxes if b.x0 >= x_start - 8 and abs(b.cy - cy) < 0.45 * rowh]
        return " ".join(b.text for b in sorted(bs, key=lambda b: b.x0)).strip()

    fields = {}
    for key in labels:
        if key == "address2":
            continue
        i = order.index(key)
        if key in ID_FIELDS:
            cy = y0 + i * rowh
            fields[key] = ocr.read_strip(img, x_start, cy - 0.5 * rowh, w - 20, cy + 0.5 * rowh)
        elif key == "address":
            fields[key] = (row_text(i) + " " + row_text(i + 1)).strip()
        else:
            fields[key] = row_text(i)
    return {k: (v or None) for k, v in fields.items()}


def _parse_card(img: Image.Image, boxes) -> dict:
    w, _ = img.size
    cand = [b for b in boxes if b.x0 > 0.25 * w]
    found = _find_labels(cand, CARD_LABELS, w)
    fields = {}
    for key, lab in found.items():
        below = [b for b in cand if b.y0 >= lab.y1 - 3 and abs(b.x0 - lab.x0) < 0.05 * w and b is not lab]
        below.sort(key=lambda b: b.y0)
        fields[key] = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", below[0].text.strip()) if below else None
    return fields


def _date(s: str | None) -> str | None:
    if not s:
        return None
    m = re.search(r"(\d{4})\D{0,2}(\d{2})\D{0,2}(\d{2})", s.upper().replace("O", "0"))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def parse_document(img: Image.Image) -> dict:
    """Returns {doc_type, sharpness, blurry, fields, corrections}."""
    sharp = ocr.sharpness(img)
    out = {"doc_type": None, "sharpness": round(sharp, 1), "blurry": sharp < BLUR_LIMIT, "fields": {}, "corrections": []}
    if out["blurry"]:
        return out  # do not read what we cannot read reliably: ask for a better photo
    boxes = ocr.read_full(img)
    skew = ocr.estimate_skew(boxes)
    if abs(skew) > 1.5:  # tilted photo: straighten it and read again
        img = ocr.deskew(img, skew)
        boxes = ocr.read_full(img)
        out["deskewed_deg"] = round(skew, 1)
    doc_type = classify(boxes, img.size[1])
    out["doc_type"] = doc_type
    if doc_type in ROW_LABELS:
        f = _parse_rows(img, boxes, doc_type)
    elif doc_type == "signatory_id":
        f = _parse_card(img, boxes)
    else:
        return out

    if doc_type == "gst_certificate":
        raw = f.get("gstin")
        g, status = repair_gstin(raw)
        f["gstin_raw"] = clean(raw)
        f["gstin"], f["gstin_status"] = g, status
        if status == "corrected":
            out["corrections"].append({"field": "gstin", "read_as": clean(raw), "corrected_to": g})
        f["date"] = _date(f.get("date"))
    elif doc_type == "udyam_certificate":
        raw = f.get("udyam_number")
        u, status = repair_udyam(raw)
        f["udyam_raw"] = raw
        f["udyam_number"], f["udyam_status"] = u, status
        if status == "corrected":
            out["corrections"].append({"field": "udyam_number", "read_as": raw, "corrected_to": u})
        f["date"] = _date(f.get("date"))
    elif doc_type == "address_proof":
        f["bill_date"] = _date(f.get("bill_date"))
    elif doc_type == "signatory_id":
        f["valid_till"] = _date(f.get("valid_till"))
    out["fields"] = f
    return out
