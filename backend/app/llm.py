"""Thin local-Ollama client. Every caller must cope with None (LLM off / slow / bad output)."""
import json
import re
import threading
import time
import unicodedata

import httpx

from .config import LLM_MODE, LLM_MODEL, LLM_TIMEOUT, OLLAMA_URL

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "mr": "Marathi", "te": "Telugu",
    "bn": "Bengali", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi",
}

_avail = {"ok": False, "at": 0.0, "good_at": 0.0}
_lock = threading.Lock()  # one local model: serialise calls so a slow GPU is not thrashed


def available() -> bool:
    if LLM_MODE == "off":
        return False
    if time.time() - _avail["at"] < 20:
        return _avail["ok"]
    ok = False
    try:
        # a model that is busy generating can be slow to answer even a tag listing: give it time
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=6)
        names = [m["name"] for m in r.json().get("models", [])]
        ok = any(n == LLM_MODEL or n.split(":")[0] == LLM_MODEL.split(":")[0] and LLM_MODEL in n for n in names)
        if ok:
            _avail["good_at"] = time.time()
    except Exception:
        # transient timeout while it was healthy a moment ago: keep trusting it (a real failure in chat() resets this)
        ok = time.time() - _avail["good_at"] < 90
    _avail.update(ok=ok, at=time.time())
    return ok


def chat(system: str, user: str, json_mode: bool = False, temperature: float = 0.2, num_predict: int = 400) -> str | None:
    if not available():
        return None
    body = {
        "model": LLM_MODEL, "stream": False, "keep_alive": "30m",
        "options": {"temperature": temperature, "num_ctx": 2048, "num_predict": num_predict},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if json_mode:
        body["format"] = "json"
    try:
        with _lock:
            r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=LLM_TIMEOUT)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception:
        _avail.update(ok=False, at=time.time(), good_at=0.0)
        return None


def chat_json(system: str, user: str, **kw) -> dict | None:
    out = chat(system, user, json_mode=True, **kw)
    if not out:
        return None
    try:
        data = json.loads(out)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def warm() -> None:
    """Load the model into memory so the first real chat does not wait ~40 s."""
    threading.Thread(target=lambda: chat("Reply OK.", "OK", num_predict=2), daemon=True).start()


def ascii_digits(text: str) -> str:
    """Convert Devanagari/Tamil/Bengali/... digits to 0-9 so numbers can be compared."""
    return "".join(str(unicodedata.digit(c)) if c.isdigit() and not c.isascii() else c for c in text)


# ---------------------------------------------------------------------------------------------
# Advisor tasks
# ---------------------------------------------------------------------------------------------
EXTRACT_SYSTEM = """You help a telecom company understand a small business owner. The owner may write in \
Hindi, Tamil, Marathi, Telugu, Bengali, Gujarati, Kannada, Malayalam, Punjabi, English, or a mix.
Read the message and return ONLY a JSON object with these keys. Use null when the message does not say. Never guess.
{"business_type": short English noun phrase like "bakery" or "dental clinic" or null,
 "city": English spelling of the city or null,
 "employees": integer, number of people working there, or null,
 "sites": integer, number of shops/offices/units, or null,
 "current_internet": one of "business_broadband","home_broadband","mobile_hotspot","leased_line","mixed_per_site","none", or null,
 "has_gstin": true/false/null (do they have GST registration),
 "has_udyam": true/false/null,
 "monthly_spend": integer rupees per month on phone and internet, or null,
 "needs": array of zero or more of "uptime" (internet keeps going down),"bills" (too many bills or helplines),
   "cctv","whatsapp","pos","security","backup","phone","website","iot","fleet",
 "wants_human": true only if they ask to talk to a person}
Write numbers with normal digits 0-9."""


def extract_profile(text: str, asked_slot: str | None) -> dict | None:
    ctx = f"The owner was just asked about: {asked_slot}.\n" if asked_slot else ""
    return chat_json(EXTRACT_SYSTEM, f"{ctx}Owner's message: {text}", temperature=0, num_predict=200)


def write_explanation(lang: str, facts: dict) -> str | None:
    language = LANG_NAMES.get(lang, "English")
    system = (
        f"You are a friendly telecom advisor. Write exactly two short sentences in {language} telling a small "
        "business owner why the plan below fits them. Use simple everyday words, no jargon. Use ONLY the facts "
        "given. Do not mention any price, number or product name that is not in the facts. "
        "Reply with the two sentences only: no greeting, no preface, no list."
    )
    out = chat(system, json.dumps(facts, ensure_ascii=False), temperature=0.3, num_predict=160)
    if not out:
        return None
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if lines and lines[0].endswith(":"):
        lines = lines[1:]
    return " ".join(lines).strip('" ') or None


def explanation_is_safe(text: str, allowed_numbers: set[int], bundle_names: set[str], all_names: set[str]) -> bool:
    """Guard: the LLM may not invent prices or name products that are not in the bundle."""
    t = ascii_digits(text)
    for m in re.findall(r"\d[\d,]*", t):
        n = int(m.replace(",", ""))
        if n >= 100 and n not in allowed_numbers:
            return False
    low = t.lower()
    for name in all_names - bundle_names:
        if name.lower() in low:
            return False
    return True


def translate_strings(lang: str, strings: dict[str, str]) -> dict[str, str] | None:
    language = LANG_NAMES.get(lang, lang)
    system = (
        f"Translate UI strings from English to {language} for small business owners in India. Keep placeholders "
        "such as {n}, {name}, {id}, {date}, {spend}, {unit}, {status}, {total}, {items} EXACTLY unchanged. "
        "Keep brand and technical terms (Accel Business, GST, GSTIN, Udyam, UPI, WhatsApp, CCTV, POS, IVR, Wi-Fi, "
        "ISP, SMS, KYC, IP, GPS, SD-WAN) in Latin letters and keep the rupee sign. Return ONLY a JSON object with "
        "exactly the same keys."
    )
    return chat_json(system, json.dumps(strings, ensure_ascii=False), temperature=0, num_predict=1200)
