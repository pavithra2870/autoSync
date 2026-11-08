"""OCR helpers (RapidOCR, fully local). One engine, guarded by a lock."""
import math
import threading
from dataclasses import dataclass

import numpy as np
from PIL import Image

_engine = None
_lock = threading.Lock()


@dataclass
class Box:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float = 1.0
    angle: float = 0.0  # tilt of this text line in degrees (positive = slopes down to the right)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _run(arr: np.ndarray):
    with _lock:
        res, _ = _get_engine()(arr)
    return res or []


def read_full(img: Image.Image, binarise: bool = True, cut: int = 150) -> list[Box]:
    """Whole-page OCR. Binarising first removes pale watermarks/stamps but keeps dark print."""
    g = img.convert("L")
    if binarise:
        g = g.point(lambda p: 0 if p < cut else 255)
    out = []
    for pts, text, conf in _run(np.asarray(g.convert("RGB"))):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        angle = math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
        out.append(Box(text, min(xs), min(ys), max(xs), max(ys), float(conf), angle))
    return out


def estimate_skew(boxes: list[Box]) -> float:
    """Median tilt of the longer text lines. A phone photo taken at an angle shows up here."""
    angles = [b.angle for b in boxes if len(b.text) >= 6 and abs(b.angle) < 30]
    return float(np.median(angles)) if len(angles) >= 3 else 0.0


def deskew(img: Image.Image, angle: float) -> Image.Image:
    return img.convert("RGB").rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(252, 252, 250))


def read_strip(img: Image.Image, x0: float, y0: float, x1: float, y1: float, scale: int = 3, cut: int = 150) -> str:
    """OCR one row of a form. Upscale and binarise first: that removes the pale watermark and
    makes monospaced IDs (where a full-page pass often slips) readable."""
    w, h = img.size
    box = (max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1)))
    if box[2] - box[0] < 5 or box[3] - box[1] < 5:
        return ""
    g = img.convert("L").crop(box)
    g = g.resize((g.width * scale, g.height * scale), Image.LANCZOS).point(lambda p: 0 if p < cut else 255)
    # white border helps the detector
    canvas = Image.new("L", (g.width + 40, g.height + 40), 255)
    canvas.paste(g, (20, 20))
    boxes = _run(np.asarray(canvas.convert("RGB")))
    boxes.sort(key=lambda b: min(p[0] for p in b[0]))
    return " ".join(b[1] for b in boxes).strip()


def sharpness(img: Image.Image) -> float:
    """Variance of the Laplacian on a fixed-size greyscale copy. Low = blurry."""
    w, h = img.size
    g = np.asarray(img.convert("L").resize((1000, max(1, int(1000 * h / w)))), dtype=np.float64)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())
