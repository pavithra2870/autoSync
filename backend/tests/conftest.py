import os
import tempfile

# Tests get their own throw-away database so they never touch the demo data in backend/var.
os.environ.setdefault("VAR_DIR", tempfile.mkdtemp(prefix="airtel_test_"))
os.environ.setdefault("LLM_MODE", "off")
