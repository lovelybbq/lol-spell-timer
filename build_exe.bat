@echo off
echo ==========================================
echo      Spell Timer Build System
echo ==========================================

:: 0. RUN SETUP
echo.
echo [Step 0] Running Setup to verify dependencies...
:: Run setup.bat to create venv and install libraries if missing
call setup.bat

:: If setup.bat failed (or was closed) - stop the build
if %errorlevel% neq 0 (
    echo [ERROR] Setup failed! Aborting build.
    pause
    exit /b
)

:: 1. ACTIVATE VENV
:: Activate the environment to ensure we use the installed libraries
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
)

:: 2. UPDATE ASSETS
echo.
echo [1/3] Checking for Asset Updates...
python download_assets.py

:: Check if asset download failed
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Asset download failed! Aborting build.
    pause
    exit /b
)

:: 3. CLEANUP
echo.
echo [2/3] Cleaning up old build files...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

:: 4. BUILD EXE
echo.
echo [3/3] Building EXE with PyInstaller...
echo Using Icon: ico\icon.ico
echo Name: Spell Timer

:: --noconsole: No black window
:: --onefile: Single .exe file
:: --add-data: Include assets and ico folders inside exe
:: --hidden-import: Ensure libraries are included

pyinstaller --noconsole --onefile --name "Spell Timer" ^
 --icon "ico\icon.ico" ^
 --add-data "assets;assets" ^
 --add-data "ico;ico" ^
 --hidden-import=requests ^
 --hidden-import=pystray ^
 --hidden-import=PIL ^
 --hidden-import=urllib3 ^
 main.py

echo.
if %errorlevel% equ 0 (
    echo ==========================================
    echo [SUCCESS] Build Complete!
    echo File located at: dist\Spell Timer.exe
    echo ==========================================
) else (
    echo [ERROR] Build Failed!
    echo Make sure you have created the "ico" folder and put "icon.ico" inside it!
)
pause