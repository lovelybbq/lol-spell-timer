@echo off
echo ==========================================
echo      Spell Timer Build System
echo ==========================================

:: 0. Activate venv
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
)

:: 1. UPDATE ASSETS
echo.
echo [1/3] Checking for Asset Updates...
python download_assets.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Asset download failed! Aborting build.
    pause
    exit /b
)

:: 2. CLEANUP
echo.
echo [2/3] Cleaning up old build files...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q *.spec 2>nul

:: 3. BUILD EXE
echo.
echo [3/3] Building EXE with PyInstaller...
echo Using Icon: ico\icon.ico
echo Name: Spell Timer

:: --icon: Path to the .ico file
:: --add-data "ico;ico": Include the ico folder inside the exe so the program can access it

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