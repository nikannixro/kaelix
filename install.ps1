<# 
.SYNOPSIS
    Kaelix — Windows Installer (Unified)
    https://github.com/nikannixro/kaelix

.DESCRIPTION
    Installs Kaelix (MKV metadata tool) with all dependencies via winget.
    Supports: install, upgrade, uninstall, non-interactive mode.

.PARAMETER Uninstall
    Remove Kaelix completely.

.PARAMETER Quiet
    Suppress final pause prompt.

.PARAMETER NonInteractive
    Skip all prompts, use defaults.

.EXAMPLE
    irm https://kaelix.pages.dev/install.ps1 | iex

.EXAMPLE
    $env:KAELIX_NONINTERACTIVE=1; irm https://kaelix.pages.dev/install.ps1 | iex
#>

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

param(
    [switch]$Uninstall,
    [switch]$Quiet,
    [switch]$NonInteractive
)

# --- Constants ----------------------------------------------------------------
$REPO_URL   = "https://github.com/nikannixro/kaelix.git"
$REPO_NAME  = "kaelix"
$REQUIRED_DEPS = @(
    @{ Name="git";          Id="Git.Git";              Msg="Git" },
    @{ Name="python";       Id="Python.Python.3.12";   Msg="Python 3.12+" },
    @{ Name="mkvmerge";     Id="MoritzBunkus.MKVToolNix";Msg="MKVToolNix" },
    @{ Name="ffmpeg";       Id="Gyan.FFmpeg";          Msg="ffmpeg" }
)

# --- Admin detection (winutil pattern) ---------------------------------------
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Kaelix installer requires Administrator. Relaunching..." -ForegroundColor Yellow
    $argsList = @()
    $PSBoundParameters.GetEnumerator() | ForEach-Object {
        $argsList += if ($_.Value -is [switch] -and $_.Value) { "-$($_.Key)" }
        elseif ($_.Value) { "-$($_.Key) '$($_.Value)'" }
    }
    $script = if ($PSCommandPath) { "& { & `'$($PSCommandPath)`' $($argsList -join ' ') }" }
    else { "&([ScriptBlock]::Create((irm https://kaelix.pages.dev/install.ps1))) $($argsList -join ' ')" }
    $psh = if (Get-Command pwsh -EA SilentlyContinue) { "pwsh" } else { "powershell" }
    $proc = if (Get-Command wt.exe -EA SilentlyContinue) { "wt.exe" } else { $psh }
    if ($proc -eq "wt.exe") {
        Start-Process $proc -ArgumentList "$psh -ExecutionPolicy Bypass -NoProfile -Command `"$script`"" -Verb RunAs
    } else {
        Start-Process $proc -ArgumentList "-ExecutionPolicy Bypass -NoProfile -Command `"$script`"" -Verb RunAs
    }
    exit
}

# --- Logging ------------------------------------------------------------------
$LogDir = Join-Path $env:TEMP "kaelix"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "install_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

function Write-Log { param([string]$Msg, [string]$Level="INFO") 
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$ts] [$Level] $Msg" -EA SilentlyContinue
}

# --- Output helpers (consistent with bash) -----------------------------------
function Show-Banner {
    $w = try { $Host.UI.RawUI.WindowSize.Width } catch { 80 }
    $h = try { $Host.UI.RawUI.WindowSize.Height } catch { 24 }
    $banner = @("=========================================","            K A E L I X","=========================================")
    $max = ($banner | Measure-Object -Property Length -Maximum).Maximum
    $pad = [Math]::Max(0, [int](($w - $max)/2))
    $top = [Math]::Max(0, [int](($h - $banner.Count - 2)/2))
    1..$top | ForEach-Object { Write-Host "" }
    $banner | ForEach-Object { Write-Host (" " * $pad + $_) -ForegroundColor Green }
    Write-Host ""
}

function Write-Step { param([int]$N,[int]$T,[string]$Msg)
    Write-Host "  [" -NoNewline -ForegroundColor DarkGray
    Write-Host "$N/$T" -NoNewline -ForegroundColor Yellow
    Write-Host "] " -NoNewline -ForegroundColor DarkGray
    Write-Host $Msg
    Write-Log "STEP: $Msg"
}

function Write-OK   { param([string]$Msg) Write-Host "       ✓ $Msg" -ForegroundColor Green;  Write-Log "OK"   $Msg }
function Write-Fail { param([string]$Msg) Write-Host "       ✗ $Msg" -ForegroundColor Red;   Write-Log "FAIL" $Msg; exit 1 }
function Write-Warn { param([string]$Msg) Write-Host "       ⚠ $Msg" -ForegroundColor Yellow; Write-Log "WARN" $Msg }
function Write-Info { param([string]$Msg) Write-Host "       ⟳ $Msg" -ForegroundColor Cyan;  Write-Log "INFO" $Msg }

function Test-Cmd { param([string]$C) [bool](Get-Command $C -EA SilentlyContinue) }

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}

# --- Download with progress bar (Ollama pattern) ------------------------------
function Invoke-Download {
    param([string]$Url, [string]$OutFile, [int]$MaxRetries=3)
    for ($a=1; $a -le $MaxRetries; $a++) {
        try {
            Write-Log "Downloading: $Url (attempt $a/$MaxRetries)"
            $req = [Net.HttpWebRequest]::Create($Url)
            $req.AllowAutoRedirect = $true
            $req.Timeout = 300000
            $resp = $req.GetResponse()
            $total = $resp.ContentLength
            $stream = $resp.GetResponseStream()
            $fs = [IO.FileStream]::new($OutFile, [IO.FileMode]::Create)
            $buf = [byte[]]::new(65536)
            $read=0; $last=[DateTime]::MinValue; $barW=40
            try {
                while (($r = $stream.Read($buf,0,$buf.Length)) -gt 0) {
                    $fs.Write($buf,0,$r)
                    $read += $r
                    $now = [DateTime]::UtcNow
                    if (($now-$last).TotalMilliseconds -ge 250) {
                        if ($total -gt 0) {
                            $pct = [math]::Min(100.0, ($read/$total)*100)
                            $filled = [math]::Floor($barW*$pct/100)
                            $bar = ('█' * $filled) + ('░' * ($barW-$filled))
                            Write-Host -NoNewline "`r  $bar $($pct.ToString('0.0'))%"
                        } else {
                            $mb = [math]::Round($read/1MB,1)
                            Write-Host -NoNewline "`r  ${mb} MB downloaded..."
                        }
                        $last = $now
                    }
                }
                if ($total -gt 0) { Write-Host "`r  $($barW*'█') 100.0%" }
                else { $mb=[math]::Round($read/1MB,1); Write-Host "`r  ${mb} MB downloaded.     " }
                Write-Log "Download complete: $OutFile ($read bytes)"
                return $true
            } finally { $fs.Close(); $stream.Close(); $resp.Close() }
        } catch {
            Write-Log "Download failed: $($_.Exception.Message)" "ERROR"
            if ($a -eq $MaxRetries) { throw "Download failed after $MaxRetries attempts: $Url" }
            Start-Sleep -Seconds $a
        }
    }
}

# --- Uninstall ---------------------------------------------------------------
function Invoke-Uninstall {
    Write-Host ""; Write-Step 1 3 "Uninstalling Kaelix..."
    Write-Info "Removing Python package..."
    pip uninstall kaelix -y -q 2>$null
    Write-OK "Python package removed."
    $target = Join-Path (Get-Location) $REPO_NAME
    if (Test-Path $target) { Write-Info "Removing repo..."; Remove-Item -Recurse -Force $target -EA SilentlyContinue; Write-OK "Repo removed." }
    if (Test-Path $LogDir) { Write-Info "Removing logs..."; Remove-Item -Recurse -Force $LogDir -EA SilentlyContinue; Write-OK "Logs removed." }
    Write-Host ""; Write-OK "Kaelix uninstalled."
}

# --- Main Install ------------------------------------------------------------
function Invoke-Install {
    Show-Banner
    if ($env:OS -ne "Windows_NT") { Write-Fail "Windows only."; if (-not $Quiet) { Read-Host "Press Enter" }; exit 1 }

    $env:GIT_TERMINAL_PROMPT = "0"

    # --- Dependency checks ---
    Write-Step 1 ($REQUIRED_DEPS.Count + 2) "Checking dependencies..."
    foreach ($d in $REQUIRED_DEPS) {
        if (Test-Cmd $d.Name) { Write-OK "$($d.Msg) found." }
        elseif (-not $NonInteractive) {
            Write-Info "Installing $($d.Msg) via winget..."
            if (-not (Test-Cmd "winget")) { Write-Fail "winget not found. Install 'App Installer' from Microsoft Store." }
            winget install --id $d.Id -e --source winget --accept-package-agreements --accept-source-agreements 2>$null
            Refresh-Path
            if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335212) { Write-OK "$($d.Msg) installed." }
            else { Write-Fail "Failed to install $($d.Msg). Install manually." }
        } else {
            Write-Fail "$($d.Msg) not installed. Run without -NonInteractive or install manually."
        }
    }

    # --- Repository ---
    $step = $REQUIRED_DEPS.Count + 1
    $total = $REQUIRED_DEPS.Count + 2
    Write-Step $step $total "Setting up repository..."
    $target = Join-Path (Get-Location) $REPO_NAME
    if (Test-Path (Join-Path $target ".git")) {
        Write-Info "Repo exists. Checking updates..." -ForegroundColor Gray
        Push-Location $target
        git fetch origin --quiet 2>$null
        $remote = git remote get-url origin 2>$null
        if ($remote -and $remote.Trim() -eq $REPO_URL) {
            $local = git rev-parse HEAD 2>$null
            $rem = git rev-parse origin/main 2>$null; if (-not $rem) { $rem = git rev-parse origin/master 2>$null }
            if (-not $rem) { $rem = $local }
            if ($local -eq $rem) { Write-OK "Already up to date." }
            else { Write-Info "Pulling updates..."; git pull --quiet 2>$null; Write-OK "Updated." }
        } else {
            Write-Warn "Wrong remote. Re-cloning..."
            Pop-Location; Remove-Item -Recurse -Force $target -EA SilentlyContinue
            git clone $REPO_URL 2>$null
            Push-Location $REPO_NAME
        }
        Pop-Location
    } else {
        Write-Info "Cloning repository..."
        git clone $REPO_URL 2>$null
        if ($LASTEXITCODE -ne 0) { Write-Fail "Clone failed." }
        Write-OK "Repository cloned."
    }

    # --- Python deps + install ---
    $step++
    Write-Step $step $total "Installing Python package..."
    Push-Location $target
    pip install --user -r requirements.txt -q 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to install Python deps."; Pop-Location; if (-not $Quiet) { Read-Host "Press Enter" }; exit 1 }
    pip install --user -e . -q 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to register kaelix command."; Pop-Location; if (-not $Quiet) { Read-Host "Press Enter" }; exit 1 }
    Pop-Location
    Write-OK "Kaelix installed."

    # --- Done ---
    Write-Host ""
    Write-OK "Installation complete."
    Write-Host "  Type " -NoNewline -ForegroundColor Gray
    Write-Host '"kaelix"' -NoNewline -ForegroundColor Green
    Write-Host " to start." -ForegroundColor Gray
    Write-Host ""
}

# --- Entry point -------------------------------------------------------------
if ($Uninstall) { Invoke-Uninstall }
else { Invoke-Install }

if (-not $Quiet) {
    Write-Host "  Press any key to continue..." -ForegroundColor DarkGray
    try { $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") } catch { Read-Host "Press Enter" }
}
exit