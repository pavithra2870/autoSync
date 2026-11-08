@echo off
REM One-command start for Windows. Uses the venv in the project root (created on first run).
REM Then serves everything on http://localhost:8000
cd /d "%~dp0frontend"
if not exist node_modules call npm install
if not exist dist call npm run build

cd /d "%~dp0"
if not exist venv\Scripts\activate.bat (
  python -m venv venv
  call venv\Scripts\activate.bat
  python -m pip install -r backend\requirements.txt
) else (
  call venv\Scripts\activate.bat
)
cd /d "%~dp0backend"
python -m uvicorn app.main:app --port 8000
