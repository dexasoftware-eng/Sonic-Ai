@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Starting Detectra AI Server...
echo   URL: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================================

py -3.14 -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
if %ERRORLEVEL% NEQ 0 (
    python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
)
pause

