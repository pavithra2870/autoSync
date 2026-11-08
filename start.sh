#!/usr/bin/env sh
# One-command start for macOS/Linux. Uses the venv in the project root (created on first run).
# Then serves everything on http://localhost:8000
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/frontend" || exit 1
[ -d node_modules ] || npm install
[ -d dist ] || npm run build

cd "$ROOT" || exit 1
if [ ! -f venv/bin/activate ]; then
  python3 -m venv venv && . venv/bin/activate && python -m pip install -r backend/requirements.txt
else
  . venv/bin/activate
fi
cd "$ROOT/backend" && python -m uvicorn app.main:app --port 8000
