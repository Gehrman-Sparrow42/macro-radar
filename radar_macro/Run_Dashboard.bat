@echo off
cd /d "%~dp0"
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" run.py --dashboard
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py --dashboard
) else (
    python run.py --dashboard
)
