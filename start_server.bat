@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Starting SonicSentinel AI Server...
echo   URL: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

pause
