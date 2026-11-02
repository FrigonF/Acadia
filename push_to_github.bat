@echo off
title ACADIA - Git Push to GitHub
echo =====================================================================
echo                ACADIA - Push to GitHub Repository
echo              Target: https://github.com/FrigonF/Acadia
echo =====================================================================
echo.
cd /d "%~dp0"

echo Running: git push -u origin main
echo.
echo If prompted, sign in via your browser or paste your GitHub Personal Access Token.
echo.
git push -u origin main

echo.
echo =====================================================================
if %errorlevel% equ 0 (
    echo SUCCESS: Repository successfully pushed to GitHub!
) else (
    echo Error pushing to GitHub. Please check your GitHub permissions.
)
echo =====================================================================
pause
