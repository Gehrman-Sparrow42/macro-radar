@echo off
title Yatirim Radari - Makro ve Portfoy Terminali
cd /d "%~dp0"
echo ===================================================
echo   YATIRIM RADARI - MAKRO VE PORTFOY TERMINALI
echo ===================================================
echo.
echo Terminal baslatiliyor: http://127.0.0.1:8501
echo.
python run.py --dashboard --port 8501
pause
