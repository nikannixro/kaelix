@echo off
setlocal enabledelayedexpansion
title Movies Metadata Organizer - Windows Installer

set "REPO_URL=https://github.com/nikannixro/movies-metadata-organizer.git"
set "REPO_NAME=movies-metadata-organizer"

echo ============================================================
echo  Movies Metadata Organizer - Windows Installer
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: Check Windows
:: ---------------------------------------------------------------
if not "%OS%"=="Windows_NT" (
    echo ERROR: This script requires Windows.
    echo Use use.sh for Linux, macOS, or WSL.
    exit /b 1
)

:: ---------------------------------------------------------------
:: Check winget
:: ---------------------------------------------------------------
echo [1/6] Checking for winget...
where winget >nul 2>&1
if errorlevel 1 (
    echo ERROR: winget is not installed.
    echo Install "App Installer" from the Microsoft Store and try again.
    exit /b 1
)
echo      winget found.
echo.

:: ---------------------------------------------------------------
:: Install Git
:: ---------------------------------------------------------------
echo [2/6] Checking for Git...
where git >nul 2>&1
if errorlevel 1 (
    echo      Installing Git...
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Failed to install Git.
        exit /b 1
    )
    echo      Git installed.
) else (
    echo      Git found.
)
echo.

:: ---------------------------------------------------------------
:: Install Python
:: ---------------------------------------------------------------
echo [3/6] Checking for Python...
where python >nul 2>&1
if errorlevel 1 (
    echo      Installing Python...
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Failed to install Python.
        exit /b 1
    )
    echo      Python installed.
) else (
    echo      Python found.
)
echo.

:: ---------------------------------------------------------------
:: Install MKVToolNix
:: ---------------------------------------------------------------
echo [4/6] Checking for MKVToolNix...
where mkvmerge >nul 2>&1
if errorlevel 1 (
    echo      Installing MKVToolNix...
    winget install --id MoritzBunkus.MKVToolNix -e --source winget --installer-type portable --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Failed to install MKVToolNix.
        exit /b 1
    )
    echo      MKVToolNix installed.
) else (
    echo      MKVToolNix found.
)
echo.

:: ---------------------------------------------------------------
:: Install ffmpeg
:: ---------------------------------------------------------------
echo [5/6] Checking for ffmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo      Installing ffmpeg...
    winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ERROR: Failed to install ffmpeg.
        exit /b 1
    )
    echo      ffmpeg installed.
) else (
    echo      ffmpeg found.
)
echo.

:: ---------------------------------------------------------------
:: Clone or update repository
:: ---------------------------------------------------------------
echo [6/6] Setting up repository...
if exist "%REPO_NAME%\.git" (
    cd "%REPO_NAME%"
    git fetch origin --quiet 2>nul
    for /f "tokens=*" %%i in ('git remote get-url origin') do set "REMOTE_URL=%%i"
    if "!REMOTE_URL!"=="%REPO_URL%" (
        for /f "tokens=*" %%i in ('git rev-parse HEAD') do set "LOCAL=%%i"
        for /f "tokens=*" %%i in ('git rev-parse origin/main 2^>nul') do set "REMOTE=%%i"
        if not "!LOCAL!"=="!REMOTE!" git pull --quiet 2>nul
    )
) else (
    echo      Cloning repository...
    git clone %REPO_URL%
    if errorlevel 1 (
        echo ERROR: Failed to clone repository.
        exit /b 1
    )
    cd "%REPO_NAME%"
    echo      Repository cloned.
)
echo.

:: ---------------------------------------------------------------
:: Install Python dependencies
:: ---------------------------------------------------------------
echo Installing Python dependencies...
pip install -r requirements.txt --break-system-packages 2>nul || pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies.
    exit /b 1
)
echo Python dependencies installed.
echo.

:: ---------------------------------------------------------------
:: Launch application
:: ---------------------------------------------------------------
echo Starting Movies Metadata Organizer...
python -m src.main
