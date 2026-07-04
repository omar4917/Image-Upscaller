@echo off
cd /d "%~dp0"

:: Check if python is in PATH
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python and try again.
    pause
    exit /b 1
)

:: Check if venv exists, if not create it
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Verify venv configuration
venv\Scripts\python.exe --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Virtual environment is broken or moved. Re-creating...
    rmdir /s /q venv
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to recreate virtual environment.
        pause
        exit /b 1
    )
)

:: Install/update dependencies
echo Checking and installing dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

:: Run application
echo Starting AI Media Studio...
venv\Scripts\python.exe app.py
if %errorlevel% neq 0 (
    echo Application exited with an error.
    pause
)
