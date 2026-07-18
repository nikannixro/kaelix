# Kaelix — Windows Installer
# https://github.com/nikannixro/kaelix
# ============================================================
$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- Auto-Elevation (WinUtil pattern) -----------------------------------------

if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argList = @()

    $PSBoundParameters.GetEnumerator() | ForEach-Object {
        $argList += if ($_.Value -is [switch] -and $_.Value) {
            "-$($_.Key)"
        } elseif ($_.Value -is [array]) {
            "-$($_.Key) $($_.Value -join ',')"
        } elseif ($_.Value) {
            "-$($_.Key) '$($_.Value)'"
        }
    }

    $script = if ($PSCommandPath) {
        "& { & `'$($PSCommandPath)`' $($argList -join ' ') }"
    } else {
        "&([ScriptBlock]::Create((irm https://raw.githubusercontent.com/nikannixro/kaelix/main/install.ps1))) $($argList -join ' ')"
    }

    $powershellCmd = if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        (Get-Command pwsh).Source
    } else {
        "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    }
    Start-Process $powershellCmd -ArgumentList "-ExecutionPolicy Bypass -NoProfile -Command `"$script`"" -Verb RunAs

    break
}

$REPO_URL = "https://github.com/nikannixro/kaelix.git"
$REPO_NAME = "kaelix"

# --- Banner -------------------------------------------------------------------

function Show-Banner {
    $width = 80
    $height = 24
    try {
        if ($Host.UI.RawUI.WindowSize.Width -gt 0) { $width = $Host.UI.RawUI.WindowSize.Width }
        if ($Host.UI.RawUI.WindowSize.Height -gt 0) { $height = $Host.UI.RawUI.WindowSize.Height }
    } catch { }

    $banner = @(
        "=========================================",
        "            K A E L I X",
        "========================================="
    )

    $maxLen = ($banner | Measure-Object -Property Length -Maximum).Maximum
    $bannerHeight = $banner.Count + 2
    $topPad = [Math]::Max(0, [int](($height - $bannerHeight) / 2))
    $leftPad = " " * [Math]::Max(0, [int](($width - $maxLen) / 2))

    for ($i = 0; $i -lt $topPad; $i++) { Write-Host "" }
    foreach ($line in $banner) {
        Write-Host "${leftPad}${line}" -ForegroundColor Green
    }
    Write-Host ""
}

# --- Helpers ------------------------------------------------------------------

function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Write-Step {
    param([int]$Num, [int]$Total, [string]$Message)
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host "$Num/$Total" -NoNewline -ForegroundColor Yellow
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $Message
}

function Write-OK {
    param([string]$Message)
    Write-Host "       " -NoNewline
    Write-Host $Message -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "       " -NoNewline
    Write-Host $Message -ForegroundColor Red
}

function Write-Installing {
    param([string]$Message)
    Write-Host "       " -NoNewline
    Write-Host $Message -ForegroundColor Yellow
}

# --- Preflight ----------------------------------------------------------------

Show-Banner

if ($env:OS -ne "Windows_NT") {
    Write-Fail "This script requires Windows."
    exit 1
}

$env:GIT_TERMINAL_PROMPT = "0"

# --- Dependency checks --------------------------------------------------------

$deps = @(
    @{ Name = "winget"; Id = "winget"; Install = $false; Message = "App Installer from Microsoft Store" },
    @{ Name = "git";    Id = "Git.Git"; Install = $true; Message = "Git" },
    @{ Name = "python"; Id = "Python.Python.3.12"; Install = $true; Message = "Python 3.12" },
    @{ Name = "mkvmerge"; Id = "MoritzBunkus.MKVToolNix"; Install = $true; Message = "MKVToolNix" },
    @{ Name = "ffmpeg"; Id = "Gyan.FFmpeg"; Install = $true; Message = "ffmpeg" }
)

$step = 0
$total = $deps.Count + 2

foreach ($dep in $deps) {
    $step++
    Write-Step $step $total "Checking for $($dep.Message)..."

    if (Test-Command $dep.Name) {
        Write-OK "$($dep.Name) found."
    } elseif ($dep.Install) {
        Write-Installing "Installing $($dep.Message)..."
        winget install --id $dep.Id -e --source winget --accept-package-agreements --accept-source-agreements 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-OK "$($dep.Message) installed."
        } else {
            Write-Fail "Failed to install $($dep.Message). Install manually and try again."
            exit 1
        }
    } else {
        Write-Fail "$($dep.Message) is not installed."
        Write-Host "       Install it from the Microsoft Store and try again." -ForegroundColor DarkGray
        exit 1
    }
}

# --- Repository ---------------------------------------------------------------

$step++
Write-Step $step $total "Setting up repository..."
$targetDir = Join-Path (Get-Location) $REPO_NAME

if (Test-Path (Join-Path $targetDir ".git")) {
    Write-Host "       Repository found. Checking for updates..." -ForegroundColor Gray
    Push-Location $targetDir

    $gitFetchHead = Join-Path ".git" "FETCH_HEAD"
    if (Test-Path $gitFetchHead) {
        try {
            $acl = Get-Acl $gitFetchHead
            $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $hasAccess = $acl.Access | Where-Object { $_.IdentityReference -eq $currentUser -and $_.FileSystemRights -match "Read" }
            if (-not $hasAccess) {
                Write-Host "       Fixing .git permissions..." -ForegroundColor Yellow
                icacls ".git" /grant "${currentUser}:(OI)(CI)F" /T /Q 2>$null
            }
        } catch { }
    }

    git fetch origin --quiet 2>$null
    $remoteUrl = git remote get-url origin 2>$null
    if ($remoteUrl -and $remoteUrl.Trim() -eq $REPO_URL) {
        $localHash = git rev-parse HEAD 2>$null
        $remoteHash = git rev-parse origin/main 2>$null
        if (-not $remoteHash) { $remoteHash = git rev-parse origin/master 2>$null }
        if (-not $remoteHash) { $remoteHash = $localHash }
        if ($localHash -eq $remoteHash) {
            Write-OK "Already up to date."
        } else {
            Write-Installing "Updates available. Pulling..."
            git pull --quiet 2>$null
            Write-OK "Updated to latest version."
        }
    } else {
        Write-Host "       Wrong remote. Cloning fresh..." -ForegroundColor Yellow
        Pop-Location
        Remove-Item -Recurse -Force $targetDir -ErrorAction SilentlyContinue
        git clone $REPO_URL
        Push-Location $REPO_NAME
    }
    Pop-Location
} else {
    Write-Installing "Cloning repository..."
    git clone $REPO_URL 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to clone repository."
        exit 1
    }
    Write-OK "Repository cloned."
}

# --- Python dependencies ------------------------------------------------------

$step++
Write-Step $step $total "Installing Python dependencies..."
Push-Location $targetDir
pip install -r requirements.txt -q 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to install Python dependencies."
    Pop-Location
    exit 1
}
Pop-Location
Write-OK "Dependencies installed."

# --- Register kaelix command --------------------------------------------------

$step++
Write-Step $step $total "Registering kaelix command..."
Push-Location $targetDir
pip install -e . -q 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to register kaelix command."
    Pop-Location
    exit 1
}
Pop-Location
Write-OK "Kaelix installed."

# --- Done ---------------------------------------------------------------------

Write-Host ""
Write-Host "  Installation complete." -ForegroundColor Green
Write-Host "  Type " -NoNewline -ForegroundColor Gray
Write-Host '"kaelix"' -NoNewline -ForegroundColor Green
Write-Host " to start." -ForegroundColor Gray
Write-Host ""
Write-Host "  Press any key to continue..." -ForegroundColor DarkGray
try {
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
exit
} catch {
    Read-Host "Press Enter to continue"
    exit
}
