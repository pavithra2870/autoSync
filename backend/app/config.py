import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
VAR_DIR = Path(os.getenv("VAR_DIR", ROOT / "backend" / "var"))
VAR_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = VAR_DIR / "app.db"
I18N_CACHE_DIR = Path(__file__).resolve().parent / "i18n_cache"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# The case pack says to treat 2026-07-15 as "today" for date checks.
TODAY = date.fromisoformat(os.getenv("DEMO_TODAY", "2026-07-15"))
ADDRESS_PROOF_MAX_DAYS = 90

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:4b")
LLM_MODE = os.getenv("LLM_MODE", "auto")  # auto | off  (off = rules-only demo mode)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# Privacy: how long extracted KYC fields are kept (document images are never stored).
RETENTION_DAYS_ACTIVE = 90
RETENTION_DAYS_ABANDONED = 30
