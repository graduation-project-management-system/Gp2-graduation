@echo off
chcp 65001 >nul
title GP System — JUST

cd /d "%~dp0backend"

echo.
echo  ============================================================
echo   GP System - Jordan University of Science and Technology
echo  ============================================================
echo.

:: ── Check Python ──────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found!
    echo  Install from https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during install.
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo  [OK] Python %%v

:: ── Virtual environment ────────────────────────────────────────
set VENV_DIR=venv_new
if exist "%VENV_DIR%\Scripts\pip.exe" (
    echo  [1/4] Using existing virtual environment...
) else (
    echo  [1/4] Creating virtual environment...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause & exit /b 1
    )
)
call %VENV_DIR%\Scripts\activate.bat
echo  [2/4] Virtual environment activated.

:: ── Install dependencies ───────────────────────────────────────
echo  [3/4] Installing/verifying packages...
pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  ERROR: Failed to install packages.
    pause & exit /b 1
)
echo        Done.

:: ── Database setup ─────────────────────────────────────────────
echo  [4/4] Database setup...
python manage.py makemigrations accounts teams requests meetings grading notifications files chat --no-input 2>nul
python manage.py migrate --no-input
if errorlevel 1 (
    echo  ERROR: Migration failed.
    pause & exit /b 1
)
python manage.py seed_data

:: ── Launch ─────────────────────────────────────────────────────
echo.
echo  ============================================================
echo   SERVER RUNNING at http://127.0.0.1:8000
echo.
echo   LOGIN CREDENTIALS:
echo   Admin      : admin@just.edu.jo       / Admin@GP2025
echo   Supervisor : Hamza@just.edu.jo       / Hamza0*
echo   Student    : sadeen@cit.just.edu.jo  / Sadeen0*
echo.
echo   TESTS:
echo   pytest  ^> cd backend ^&^& python -m pytest tests/ -v
echo   cypress ^> npm run cy:open   (open GUI)
echo            npm run cy:run    (run all headless)
echo.
echo   Press Ctrl+C to stop the server.
echo  ============================================================
echo.

timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000

python manage.py runserver

pause
