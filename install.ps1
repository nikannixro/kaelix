<#
.SYNOPSIS
    Kaelix — Windows installer (Ollama-style banner, winutil-style elevation).
.DESCRIPTION
    Installs Kaelix into %LOCALAPPDATA%\kaelix with a private venv and a
    kaelix.cmd launcher. Idempotent; safe to re-run.
.PARAMETER Uninstall
    Remove Kaelix completely (app dir, venv, launcher).
.PARAMETER Quiet
    No pause at the end.
.PARAMETER NonInteractive
    No prompts; install missing deps via winget automatically.
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$Quiet,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

# --- Constants ----------------------------------------------------------------
$RepoUrl   = "https://github.com/nikannixro/kaelix.git"
$AppDir    = Join-Path $env:LOCALAPPDATA "kaelix"
$AppRepo   = Join-Path $AppDir "app"
$Venv      = Join-Path $AppDir "venv"
$Downloads = Join-Path $AppDir "downloads"
$LogDir    = Join-Path $AppDir "logs"
$LogFile   = Join-Path $LogDir ("install_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$BinDir    = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
$Launcher  = Join-Path $BinDir "kaelix.cmd"
$RequiredDeps = @(
    @{ Name = "git";      Id = "Git.Git";              Msg = "Git" },
    @{ Name = "python";   Id = "Python.Python.3.12";   Msg = "Python 3.12+" },
    @{ Name = "mkvmerge"; Id = "MoritzBunkus.MKVToolNix"; Msg = "MKVToolNix" },
    @{ Name = "ffprobe";  Id = "Gyan.FFmpeg";          Msg = "ffmpeg" }
)

# --- Logging + output ---------------------------------------------------------
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
function Write-Log { param([string]$Msg, [string]$Level = "INFO")
    Add-Content -Path $LogFile -Value ("[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Msg) -EA SilentlyContinue }
function Write-Step { param([int]$N, [int]$T, [string]$Msg)
    Write-Host "`n  [$N/$T] $Msg" -ForegroundColor White; Write-Log "STEP" $Msg }
function Write-OK   { param([string]$Msg) Write-Host "     ✓ $Msg" -ForegroundColor Green;  Write-Log "OK" $Msg }
function Write-Warn { param([string]$Msg) Write-Host "     ⚠ $Msg" -ForegroundColor Yellow; Write-Log "WARN" $Msg }
function Write-Fail { param([string]$Msg) Write-Host "     ✗ $Msg" -ForegroundColor Red; Write-Log "FAIL" $Msg; exit 1 }
function Write-Info { param([string]$Msg) Write-Host "     $Msg" -ForegroundColor DarkGray; Write-Log "INFO" $Msg }

function Show-Banner {
    Write-Host ""
    Write-Host "   ┌─────────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "   │            K A E L I X                   │" -ForegroundColor Green
    Write-Host "   │         the MKV metadata tool            │" -ForegroundColor Green
    Write-Host "   └─────────────────────────────────────────┘" -ForegroundColor Green
    Write-Host ""
}

function Test-Cmd { param([string]$C) [bool](Get-Command $C -EA SilentlyContinue) }

function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Invoke-Download {
    param([string]$Url, [string]$OutFile, [int]$MaxRetries = 3)
    for ($a = 1; $a -le $MaxRetries; $a++) {
        try {
            Write-Log "Downloading $Url (attempt $a/$MaxRetries)"
            $req = [Net.HttpWebRequest]::Create($Url); $req.AllowAutoRedirect = $true; $req.Timeout = 300000
            $resp = $req.GetResponse(); $total = $resp.ContentLength
            $stream = $resp.GetResponseStream(); $fs = [IO.FileStream]::new($OutFile, [IO.FileMode]::Create)
            $buf = [byte[]]::new(65536); $read = 0; $last = [DateTime]::MinValue; $barW = 40
            try {
                while (($r = $stream.Read($buf, 0, $buf.Length)) -gt 0) {
                    $fs.Write($buf, 0, $r); $read += $r
                    $now = [DateTime]::UtcNow
                    if (($now - $last).TotalMilliseconds -ge 250) {
                        if ($total -gt 0) {
                            $pct = [math]::Min(100.0, ($read / $total) * 100)
                            $filled = [math]::Floor($barW * $pct / 100)
                            Write-Host -NoNewline ("`r  " + ('█' * $filled) + ('░' * ($barW - $filled)) + (" {0,5:0.0}%" -f $pct))
                        } else { Write-Host -NoNewline ("`r  {0} MB downloaded..." -f [math]::Round($read / 1MB, 1)) }
                        $last = $now
                    }
                }
                if ($total -gt 0) { Write-Host ("`r  " + ('█' * $barW) + " 100.0%") }
                else { Write-Host ("`r  {0} MB downloaded.     " -f [math]::Round($read / 1MB, 1)) }
                Write-Log "Download complete: $OutFile ($read bytes)"
                return $true
            } finally { $fs.Close(); $stream.Close(); $resp.Close() }
        } catch {
            Write-Log "Download failed: $($_.Exception.Message)" "ERROR"
            if ($a -eq $MaxRetries) { Write-Fail "Download failed after $MaxRetries attempts: $Url" }
            Start-Sleep -Seconds $a
        }
    }
}

# --- Admin elevation (winutil pattern) ---------------------------------------
function Require-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        if ($NonInteractive) { Write-Fail "Admin required. Re-run from an elevated shell or without -NonInteractive." }
        Write-Warn "Kaelix installer needs Administrator to write to WindowsApps and install system deps via winget."
        Write-Info "Relaunching with elevation..."
        $args = @()
        $PSBoundParameters.GetEnumerator() | ForEach-Object {
            $args += if ($_.Value -is [switch] -and $_.Value) { "-$($_.Key)" }
                     elseif ($_.Value) { "-$($_.Key) '$($_.Value)'" }
        }
        $script = if ($PSCommandPath) { "& { & '$($PSCommandPath)' $($args -join ' ') }" }
                  else { "&([ScriptBlock]::Create((irm https://kaelix.pages.dev/install.ps1))) $($args -join ' ')" }
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"$script`"" -Verb RunAs
        exit
    }
}

# --- Arch + PowerShell check -------------------------------------------------
function Check-Environment {
    $arch = [Environment]::GetEnvironmentVariable("PROCESSOR_ARCHITECTURE")
    $arch = if ($arch -eq "AMD64") { "x86_64" } elseif ($arch -eq "ARM64") { "arm64" } else { $arch }
    if ($PSVersionTable.PSVersion.Major -lt 5 -or ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -lt 1)) {
        Write-Fail "PowerShell 5.1+ required. You are on $($PSVersionTable.PSVersion)."
    }
    Write-Info "Architecture: $arch"
    Write-Info "PowerShell: $($PSVersionTable.PSVersion)"
    return $arch
}

# --- Dependency checks -------------------------------------------------------
function Check-Dependencies {
    Write-Step 1 ($RequiredDeps.Count + 2) "Checking dependencies..."
    foreach ($d in $RequiredDeps) {
        if (Test-Cmd $d.Name) { Write-OK "$($d.Msg) found." }
        elseif (-not $NonInteractive) {
            Write-Info "Installing $($d.Msg) via winget..."
            if (-not (Test-Cmd "winget")) { Write-Fail "winget not found. Install 'App Installer' from Microsoft Store." }
            winget install --id $d.Id -e --source winget --accept-package-agreements --accept-source-agreements 2>$null
            Update-Path
            if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335212) { Write-OK "$($d.Msg) installed." }
            else { Write-Fail "Failed to install $($d.Msg). Install manually." }
        } else { Write-Fail "$($d.Msg) not installed. Run without -NonInteractive or install manually." }
    }
}

# --- Repo clone / refresh ----------------------------------------------------
function Manage-Repo {
    Write-Step ($RequiredDeps.Count + 1) ($RequiredDeps.Count + 2) "Setting up repository..."
    if (Test-Path (Join-Path $AppRepo ".git")) {
        Write-Info "Repo exists. Checking updates..."
        Push-Location $AppRepo
        git fetch origin --quiet 2>$null
        $remote = git remote get-url origin 2>$null
        if ($remote -and $remote.Trim() -eq $RepoUrl) {
            $local = git rev-parse HEAD 2>$null
            $rem = git rev-parse origin/main 2>$null; if (-not $rem) { $rem = git rev-parse origin/master 2>$null }
            if (-not $rem) { $rem = $local }
            if ($local -eq $rem) { Write-OK "Already up to date." }
            else { Write-Info "Pulling updates..."; git pull --quiet 2>$null; Write-OK "Updated." }
        } else {
            Write-Warn "Wrong remote. Re-cloning..."
            Pop-Location; Remove-Item -Recurse -Force $AppRepo -EA SilentlyContinue
            git clone $RepoUrl $AppRepo 2>$null
            Push-Location $AppRepo
        }
        Pop-Location
    } else {
        Write-Info "Cloning repository..."
        git clone $RepoUrl $AppRepo 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Fail "Clone failed." }
        Write-OK "Repository cloned."
    }
}

# --- Python venv -------------------------------------------------------------
function Setup-Venv {
    Write-Step ($RequiredDeps.Count + 2) ($RequiredDeps.Count + 2) "Setting up virtual environment..."
    if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
        Write-Info "Creating virtual environment..."
        python -m venv $Venv
        Write-OK "Virtual environment created."
    } else {
        Write-OK "Virtual environment already exists."
    }
    Write-Info "Installing Kaelix into the virtual environment..."
    & (Join-Path $Venv "Scripts\python.exe") -m pip install --quiet --upgrade pip
    & (Join-Path $Venv "Scripts\python.exe") -m pip install --quiet --upgrade $AppRepo
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to install Kaelix." }
    Write-OK "Kaelix installed in venv."
    # Write the app-dir marker so selfmanage can find it
    $marker = Join-Path $AppRepo ".kaelix-app"
    $AppRepo | Set-Content -Path $marker -Encoding ASCII
}

# --- Launcher ----------------------------------------------------------------
function Setup-Launcher {
    $venvExe = Join-Path $Venv "Scripts\kaelix.exe"
    $content = "@echo off`n`"$venvExe`" %*"
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    Set-Content -Path $Launcher -Value $content -Encoding ASCII
    Write-OK "Created launcher: $Launcher"
    # ensure WindowsApps is in user PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User") ?? ""
    if ($userPath -notlike "*$BinDir*") {
        Write-Warn "Adding $BinDir to your user PATH..."
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    }
}

# --- Uninstall ---------------------------------------------------------------
function Invoke-Uninstall {
    Write-Host ""; Write-Step 1 3 "Uninstalling Kaelix..."
    Write-Info "Removing Python package..."
    & (Join-Path $Venv "Scripts\python.exe") -m pip uninstall -y kaelix 2>$null
    Write-OK "Python package removed."
    if (Test-Path $Launcher) { Remove-Item -Force $Launcher; Write-OK "Launcher removed." }
    if (Test-Path $AppDir) { Write-Info "Removing app directory..."; Remove-Item -Recurse -Force $AppDir -EA SilentlyContinue; Write-OK "App directory removed." }
    Write-Host ""; Write-OK "Kaelix uninstalled."
}

# --- Entry point -------------------------------------------------------------
if ($Uninstall) { Require-Admin; Invoke-Uninstall }
else {
    Show-Banner
    Require-Admin
    Check-Environment
    Check-Dependencies
    Manage-Repo
    Setup-Venv
    Setup-Launcher
    Write-Host ""
    Write-OK "Installation complete."
    Write-Host "  Type 'kaelix' to start." -ForegroundColor Gray
    Write-Host ""
}
if (-not $Quiet) {
    Write-Host "  Press any key to continue..." -ForegroundColor DarkGray
    try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch { Read-Host "Press Enter" }
}