"""Translate the UI/advisor strings into the other Indian languages with the local model and cache them
in app/i18n_cache/<lang>.json (committed, so nothing is translated at demo time).

    python scripts/warm_i18n.py            # all missing languages
    python scripts/warm_i18n.py ta te      # just these
Hindi is hand-written. Machine translations should be reviewed by a native speaker before production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import i18n  # noqa: E402

langs = sys.argv[1:] or ["ta", "mr", "te", "bn", "gu", "kn", "ml", "pa"]
for lang in langs:
    i18n.translate_language(lang)
    print(f"{lang}: {i18n.translation_coverage(lang):.0%} translated", flush=True)
