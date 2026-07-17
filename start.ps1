#Requires -RunAsAdministrator
# ============================================================================
# Kaelix — Windows installer and launcher
# ============================================================================
$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/nikannixro/kaelix.git"
$REPO_NAME = "kaelix"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Kaelix - Windows Installer" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --- Helper functions --------------------------------------------------------

function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host "[$Step] $Message" -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host "      $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

# --- Check Windows -----------------------------------------------------------

if ($env:OS -ne "Windows_NT") {
    Write-Error "This script requires Windows. Use start.sh for Linux, macOS, or WSL."
}

# --- Check winget ------------------------------------------------------------

Write-Step "1/6" "Checking for winget..."
if (-not (Test-Command "winget")) {
    Write-Error "winget is not installed. Install 'App Installer' from the Microsoft Store and try again."
}
Write-Success "winget found."
Write-Host ""

# --- Install Git -------------------------------------------------------------

Write-Step "2/6" "Checking for Git..."
if (-not (Test-Command "git")) {
    Write-Host "      Installing Git..." -ForegroundColor Gray
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install Git." }
    Write-Success "Git installed."
} else {
    Write-Success "Git found."
}
Write-Host ""

# --- Install Python ----------------------------------------------------------

Write-Step "3/6" "Checking for Python..."
if (-not (Test-Command "python")) {
    Write-Host "      Installing Python..." -ForegroundColor Gray
    winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install Python." }
    Write-Success "Python installed."
} else {
    Write-Success "Python found."
}
Write-Host ""

# --- Install MKVToolNix ------------------------------------------------------

Write-Step "4/6" "Checking for MKVToolNix..."
if (-not (Test-Command "mkvmerge")) {
    Write-Host "      Installing MKVToolNix..." -ForegroundColor Gray
    winget install --id MoritzBunkus.MKVToolNix -e --source winget --installer-type portable --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install MKVToolNix." }
    Write-Success "MKVToolNix installed."
} else {
    Write-Success "MKVToolNix found."
}
Write-Host ""

# --- Install ffmpeg ----------------------------------------------------------

Write-Step "5/6" "Checking for ffmpeg..."
if (-not (Test-Command "ffmpeg")) {
    Write-Host "      Installing ffmpeg..." -ForegroundColor Gray
    winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install ffmpeg." }
    Write-Success "ffmpeg installed."
} else {
    Write-Success "ffmpeg found."
}
Write-Host ""

# --- Clone or update repository ----------------------------------------------

Write-Step "6/6" "Setting up repository..."
$targetDir = Join-Path (Get-Location) $REPO_NAME

if (Test-Path (Join-Path $targetDir ".git")) {
    Write-Host "      Repository found. Checking for updates..." -ForegroundColor Gray
    Set-Location $targetDir
    git fetch origin --quiet 2>$null
    $remoteUrl = git remote get-url origin
    if ($remoteUrl -eq $REPO_URL) {
        $localHash = git rev-parse HEAD
        $remoteHash = git rev-parse origin/main 2>$null
        if (-not $remoteHash) { $remoteHash = git rev-parse origin/master 2>$null }
        if (-not $remoteHash) { $remoteHash = $localHash }
        if ($localHash -eq $remoteHash) {
            Write-Success "Already up to date."
        } else {
            Write-Host "      Updates available. Pulling..." -ForegroundColor Gray
            git pull --quiet 2>$null
            Write-Success "Updated to latest version."
        }
    } else {
        Write-Host "      Repository exists but is not the correct remote. Cloning fresh..." -ForegroundColor Gray
        Set-Location (Split-Path $targetDir -Parent)
        git clone $REPO_URL
        Set-Location $REPO_NAME
    }
} else {
    Write-Host "      Cloning repository..." -ForegroundColor Gray
    git clone $REPO_URL
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to clone repository." }
    Set-Location $REPO_NAME
    Write-Success "Repository cloned."
}
Write-Host ""

# --- Install Python dependencies ---------------------------------------------

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to install Python dependencies." }
Write-Success "Python dependencies installed."
Write-Host ""

# --- Launch application ------------------------------------------------------

Write-Host "Starting Kaelix..." -ForegroundColor Yellow
python -m src.main
