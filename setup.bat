@echo off
echo ==========================================
echo      LoL Tracker First Time Setup
echo ==========================================

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH!
    echo Please install Python from python.org and try again.
    pause
    exit /b
)

:: 2. Check/Create Virtual Environment (venv)
if not exist "venv" (
    echo [INFO] Virtual environment not found. Creating 'venv'...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b
    )
    echo [OK] venv created.
) else (
    echo [INFO] venv already exists. Using it.
)

:: 3. Activate venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

:: 4. Check for requirements.txt
if not exist "requirements.txt" (
    echo.
    echo [ERROR] "requirements.txt" not found!
    echo Please make sure this file exists in the same folder.
    pause
    exit /b
)

:: 5. Install dependencies from file
echo [INFO] Installing dependencies from requirements.txt...
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ==========================================
    echo [SUCCESS] Setup complete!
    echo ==========================================
    echo Now you can run:
    echo  - download_assets.py
    echo  - build_exe.bat
) else (
    echo.
    echo [ERROR] Failed to install dependencies.
)

pause