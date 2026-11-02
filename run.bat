@echo off
title ACADIA - Academic Identity Authenticated (SIH26263)
echo =====================================================================
echo           ACADIA - Academic Identity Authenticated
echo    Smart India Hackathon 2026 - Problem Statement: SIH26263
echo                         Team: Zenith_5
echo =====================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking / Seeding database...
python -m backend.scripts.generate_synthetic_data

echo.
echo [2/3] Starting ACADIA Backend API Server (Port 8000)...
start "ACADIA Backend (Port 8000)" cmd /k "cd /d "%~dp0" && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [3/3] Starting ACADIA Frontend Server (Port 5173)...
start "ACADIA Frontend (Port 5173)" cmd /k "cd /d "%~dp0Frontend" && npx vite --host 0.0.0.0 --port 5173"

echo.
echo =====================================================================
echo   ACADIA is live!
echo   -----------------------------------------------------------------
echo   * Web Dashboard:    http://localhost:5173
echo   * Backend REST API: http://localhost:8000
echo   * API Documentation:http://localhost:8000/docs
echo =====================================================================
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:5173

pause
