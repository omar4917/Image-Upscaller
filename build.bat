@echo off
cd /d "%~dp0"

:: Ensure virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment and install pyinstaller and other dependencies
echo Installing/checking dependencies and PyInstaller...
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install pyinstaller

:: Build application with PyInstaller
echo Building standalone executable with PyInstaller...
venv\Scripts\pyinstaller --clean --onefile --noconsole --collect-all customtkinter --name "AIMediaStudio" app.py

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo Build successful! Executable is at dist/AIMediaStudio.exe
    echo ===================================================
) else (
    echo.
    echo Build failed with error code %errorlevel%
)
pause
