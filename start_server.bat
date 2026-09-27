@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Starting SonicSentinel AI Server...
echo   URL: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================================

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
if %ERRORLEVEL% NEQ 0 (
    "C:\Python314\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
)
pause

