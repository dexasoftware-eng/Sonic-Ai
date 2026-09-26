@echo off
setlocal
cd /d "%~dp0"
set PATH=C:\ProgramData\miniconda3;C:\ProgramData\miniconda3\Library\bin;C:\ProgramData\miniconda3\Library\mingw-w64\bin;C:\ProgramData\miniconda3\Library\usr\bin;C:\ProgramData\miniconda3\Scripts;%PATH%

echo ========================================================
echo   Starting SonicSentinel AI Server...
echo   URL: http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================================

"C:\ProgramData\miniconda3\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
