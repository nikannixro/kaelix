<#
.SYNOPSIS
    Kaelix installer for Windows.

.DESCRIPTION
    Installs Kaelix into %LOCALAPPDATA%\kaelix with its own virtualenv and a
    kaelix.cmd launcher on PATH. Runs as a normal user; no elevation is needed
    unless optional system dependencies have to be installed via winget.

    Safe to re-run: an existing install is updated in place.

.PARAMETER Uninstall
    Remove Kaelix from this computer.

.PARAMETER SkipDependencies
    Do not attempt to install mkvtoolnix/ffmpeg; only warn if missing.

.PARAMETER Quiet
    No prompts and no trailing pause.

.EXAMPLE
    irm https://raw.githubusercontent.com/nikannixro/kaelix/main/install.ps1 | iex

.EXAMPLE
    .\install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$SkipDependencies,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
try {
    [Net.ServicePointManager]::SecurityProtocol =
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

# --- Configuration -----------------------------------------------------------

$RepoUrl       = 'https://github.com/nikannixro/kaelix.git'
$DefaultBranch = 'main'

$AppBase = if ($env:KAELIX_APP_DIR) { $env:KAELIX_APP_DIR }
           else { Join-Path $env:LOCALAPPDATA 'kaelix' }
$AppDir  = Join-Path $AppBase 'app'
$VenvDir = Join-Path $AppBase 'venv'
$LogDir  = Join-Path $AppBase 'logs'
$BinDir  = Join-Path $env:LOCALAPPDATA 'Programs\kaelix\bin'
$Launcher = Join-Path $BinDir 'kaelix.cmd'

$script:LogFile = $null

# Optional runtime tools. Kaelix reports these itself and accepts explicit
# paths, so a missing one must never block installation.
$OptionalTools = @(
    @{ Command = 'mkvmerge';    Package = 'MoritzBunkus.MKVToolNix'; Label = 'MKVToolNix' }
    @{ Command = 'mkvpropedit'; Package = 'MoritzBunkus.MKVToolNix'; Label = 'MKVToolNix' }
    @{ Command = 'ffprobe';     Package = 'Gyan.FFmpeg';             Label = 'FFmpeg' }
)

# --- Output ------------------------------------------------------------------

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    if (-not $script:LogFile) { return }
    $line = '[{0}] [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Add-Content -LiteralPath $script:LogFile -Value $line -ErrorAction SilentlyContinue
}

function Write-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host '==> ' -ForegroundColor Cyan -NoNewline
    Write-Host $Message
    Write-Log $Message 'STEP'
}

function Write-Item { param([string]$Message) Write-Host "    $Message" -ForegroundColor DarkGray; Write-Log $Message }
function Write-Ok   { param([string]$Message) Write-Host '    + ' -ForegroundColor Green -NoNewline; Write-Host $Message; Write-Log $Message 'OK' }
function Write-Warn { param([string]$Message) Write-Host '    ! ' -ForegroundColor Yellow -NoNewline; Write-Host $Message; Write-Log $Message 'WARN' }

function Stop-WithError {
    param([string]$Message)
    Write-Host ''
    Write-Host '    x ' -ForegroundColor Red -NoNewline
    Write-Host $Message -ForegroundColor Red
    Write-Host ''
    Write-Log $Message 'FAIL'
    exit 1
}

function Show-Banner {
    Write-Host ''
    foreach ($line in @(
        '   ##  ##   #####   #####  ##      ##  ##  ##'
        '   ## ##   ##   ## ##      ##      ##   ####  '
        '   ####    ####### #####   ##      ##    ##   '
        '   ## ##   ##   ## ##      ##      ##   ####  '
        '   ##  ##  ##   ##  #####  ######  ##  ##  ##'
    )) { Write-Host $line -ForegroundColor Cyan }
    Write-Host ''
    Write-Host '   MKV metadata, subtitles, and batch renaming' -ForegroundColor DarkGray
    Write-Host ''
}

# --- Helpers -----------------------------------------------------------------

function Test-Command {
    param([string]$Name)
    [bool](Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $identity).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ';'
}

function Invoke-Step {
    <#
      Run a native command, logging its output. Returns $true on exit code 0.
      Native stderr is captured rather than surfaced as a PowerShell error.
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [string]$WorkingDirectory
    )
    $stdout = New-TemporaryFile
    $stderr = New-TemporaryFile
    try {
        $params = @{
            FilePath               = $FilePath
            ArgumentList           = $Arguments
            NoNewWindow            = $true
            Wait                   = $true
            PassThru               = $true
            RedirectStandardOutput = $stdout
            RedirectStandardError  = $stderr
        }
        if ($WorkingDirectory) { $params.WorkingDirectory = $WorkingDirectory }
        Write-Log ("RUN {0} {1}" -f $FilePath, ($Arguments -join ' '))
        $proc = Start-Process @params
        foreach ($file in @($stdout, $stderr)) {
            $text = (Get-Content -LiteralPath $file -Raw -ErrorAction SilentlyContinue)
            if ($text) { Write-Log $text.Trim() }
        }
        return ($proc.ExitCode -eq 0)
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

# --- Environment -------------------------------------------------------------

function Show-Environment {
    Write-Step 'Environment'

    $os = try {
        (Get-CimInstance Win32_OperatingSystem).Caption.Trim()
    } catch { 'Windows' }
    $build = [Environment]::OSVersion.Version.ToString()

    $arch = switch ($env:PROCESSOR_ARCHITECTURE) {
        'AMD64' { 'x86_64' }
        'ARM64' { 'arm64' }
        'x86'   { 'x86' }
        default { $env:PROCESSOR_ARCHITECTURE }
    }

    Write-Item "Operating system:  $os (build $build)"
    Write-Item "Architecture:      $arch"
    Write-Item "PowerShell:        $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition))"
    Write-Item "Administrator:     $(if (Test-Administrator) { 'yes' } else { 'no (not required)' })"
    Write-Item "Install location:  $AppBase"
    Write-Item "Python env:        $VenvDir"

    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Stop-WithError "PowerShell 5.1 or newer is required (found $($PSVersionTable.PSVersion))."
    }
}

# --- Dependencies ------------------------------------------------------------

function Resolve-Python {
    <#
      Return the path to a Python 3.12+ interpreter, or $null.

      Get-Command can match several entries for one name (a real install plus
      the Windows Store alias), so every match is collected and probed. The
      Store stub is a 0-byte file and is skipped.
    #>
    $candidates = [System.Collections.Generic.List[string]]::new()

    if (Test-Command 'py') {
        foreach ($v in '3.14', '3.13', '3.12') {
            $found = & py "-$v" -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $found) { $candidates.Add($found.Trim()) }
        }
    }
    foreach ($name in 'python3', 'python') {
        foreach ($cmd in @(Get-Command $name -CommandType Application -ErrorAction SilentlyContinue)) {
            if ($cmd.Source) { $candidates.Add($cmd.Source) }
        }
    }

    # Prefer a real interpreter over a .cmd/.bat forwarder: `python3.cmd` works
    # for probing but a venv built from it records a less predictable base.
    $ordered = @(
        @($candidates | Where-Object { $_ -like '*.exe' })
        @($candidates | Where-Object { $_ -notlike '*.exe' })
    )

    foreach ($exe in $ordered) {
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { continue }
        if ((Get-Item -LiteralPath $exe).Length -eq 0) { continue }   # Store alias stub
        & $exe -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $exe }
    }
    return $null
}

function Install-WithWinget {
    param([string]$PackageId, [string]$Label)

    if (-not (Test-Command 'winget')) {
        Write-Warn "$Label is missing and winget is unavailable - install $Label manually."
        return $false
    }
    Write-Item "Installing $Label via winget..."
    $args = @(
        'install', '--id', $PackageId, '--exact', '--source', 'winget',
        '--accept-package-agreements', '--accept-source-agreements',
        '--disable-interactivity'
    )
    $null = Invoke-Step -FilePath 'winget' -Arguments $args
    Update-SessionPath
    return $true
}

function Install-Dependencies {
    Write-Step 'Checking dependencies'

    if (-not (Test-Command 'git')) {
        if ($SkipDependencies) { Stop-WithError 'git is required. Install it and re-run.' }
        $null = Install-WithWinget -PackageId 'Git.Git' -Label 'Git'
        if (-not (Test-Command 'git')) {
            Stop-WithError 'git is still unavailable. Install Git, open a new terminal, and re-run.'
        }
    }
    Write-Ok "git $((& git --version) -replace '^git version ', '')"

    $python = Resolve-Python
    if (-not $python) {
        if ($SkipDependencies) { Stop-WithError 'Python 3.12+ is required. Install it and re-run.' }
        $null = Install-WithWinget -PackageId 'Python.Python.3.12' -Label 'Python 3.12'
        $python = Resolve-Python
        if (-not $python) {
            Stop-WithError 'Python 3.12+ is still unavailable. Install it, open a new terminal, and re-run.'
        }
    }
    # No embedded quotes: PowerShell strips them when passing args to a
    # native executable, which would corrupt the expression.
    $pyVersion = (& $python -c 'import sys; print(sys.version.split()[0])').Trim()
    Write-Ok "python $pyVersion ($python)"

    foreach ($tool in $OptionalTools | Group-Object { $_.Package }) {
        $first = $tool.Group[0]
        $missing = @($tool.Group | Where-Object { -not (Test-Command $_.Command) })
        if (-not $missing) {
            Write-Ok $first.Label
            continue
        }
        if ($SkipDependencies) {
            Write-Warn "$($first.Label) not found - install it before running Kaelix."
            continue
        }
        $null = Install-WithWinget -PackageId $first.Package -Label $first.Label
        $stillMissing = @($tool.Group | Where-Object { -not (Test-Command $_.Command) })
        if ($stillMissing) {
            Write-Warn "$($first.Label) still not on PATH - open a new terminal, or install it manually."
        } else {
            Write-Ok $first.Label
        }
    }

    return $python
}

# --- Install -----------------------------------------------------------------

function Sync-Repository {
    Write-Step 'Fetching Kaelix'

    $gitDir = Join-Path $AppDir '.git'
    if (Test-Path -LiteralPath $gitDir) {
        $remote = (& git -C $AppDir remote get-url origin 2>$null)
        if ($remote -and $remote.Trim() -ne $RepoUrl) {
            Write-Warn 'Existing clone points elsewhere; replacing it.'
            Remove-Item -LiteralPath $AppDir -Recurse -Force
        }
    }

    if (Test-Path -LiteralPath (Join-Path $AppDir '.git')) {
        Write-Item 'Updating existing clone'
        if (-not (Invoke-Step 'git' @('-C', $AppDir, 'fetch', '--tags', '--force', '--quiet', 'origin'))) {
            Stop-WithError 'Could not reach GitHub. Check your network and retry.'
        }
        if (-not (Invoke-Step 'git' @('-C', $AppDir, 'checkout', '--force', '--quiet', "origin/$DefaultBranch"))) {
            Stop-WithError "Could not check out $DefaultBranch."
        }
        Write-Ok "Updated to latest $DefaultBranch"
    } else {
        Write-Item "Cloning $RepoUrl"
        if (Test-Path -LiteralPath $AppDir) { Remove-Item -LiteralPath $AppDir -Recurse -Force }
        $parent = Split-Path -Parent $AppDir
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        if (-not (Invoke-Step 'git' @('clone', '--quiet', '--depth', '1', '--branch', $DefaultBranch, $RepoUrl, $AppDir))) {
            Stop-WithError 'Clone failed. Check your network and retry.'
        }
        # Full tag history is what --upgrade compares against.
        $null = Invoke-Step 'git' @('-C', $AppDir, 'fetch', '--tags', '--quiet', '--unshallow')
        Write-Ok "Cloned into $AppDir"
    }
}

function Install-Venv {
    param([Parameter(Mandatory)][string]$Python)

    Write-Step 'Setting up the Python environment'
    $venvPython = Join-Path $VenvDir 'Scripts\python.exe'

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Item 'Creating virtualenv'
        if (-not (Invoke-Step $Python @('-m', 'venv', $VenvDir))) {
            Stop-WithError 'Could not create the virtualenv.'
        }
        Write-Ok 'Virtualenv created'
    } else {
        Write-Ok 'Virtualenv already present'
    }

    Write-Item 'Installing Kaelix and its dependencies'
    if (-not (Invoke-Step $venvPython @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip'))) {
        Write-Warn 'Could not upgrade pip; continuing.'
    }
    if (-not (Invoke-Step $venvPython @('-m', 'pip', 'install', '--quiet', '--upgrade', $AppDir))) {
        Stop-WithError "pip install failed. See $($script:LogFile)."
    }
    Write-Ok 'Installed into the virtualenv'
}

function Install-Launcher {
    Write-Step 'Installing the kaelix command'

    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    $venvExe = Join-Path $VenvDir 'Scripts\kaelix.exe'

    # A .cmd shim (not a hardlink) so KAELIX_APP_DIR survives upgrades.
    # `& exit /b` sits on the same line as the call: cmd.exe has already read
    # that line, so it never reads past it. Without this, `kaelix --uninstall`
    # deletes this very file and cmd then reports "The batch file cannot be
    # found." while trying to fetch the next line. `exit /b` with no argument
    # preserves the exit code.
    $shim = @(
        '@echo off'
        'setlocal'
        "if not defined KAELIX_APP_DIR set ""KAELIX_APP_DIR=$AppBase"""
        """$venvExe"" %* & exit /b"
    ) -join "`r`n"
    Set-Content -LiteralPath $Launcher -Value $shim -Encoding ASCII
    Write-Ok "Created $Launcher"

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @(($userPath -split ';') | Where-Object { $_ })
    if ($entries -notcontains $BinDir) {
        [Environment]::SetEnvironmentVariable(
            'Path', (@($entries + $BinDir) -join ';'), 'User')
        Write-Ok "Added $BinDir to your user PATH"
        Write-Item 'Open a new terminal for the PATH change to take effect.'
    } else {
        Write-Ok "$BinDir already on your user PATH"
    }
    Update-SessionPath
}

function Invoke-Capture {
    <#
      Run a native command and return @{ ExitCode; Output }. Native stderr is
      redirected to a file rather than PowerShell's error stream, which under
      $ErrorActionPreference='Stop' would otherwise throw NativeCommandError.
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments
    )
    $stdout = New-TemporaryFile
    $stderr = New-TemporaryFile
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
            -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $text = @(
            (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue)
            (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue)
        ) -join ''
        return @{ ExitCode = $proc.ExitCode; Output = ($text -replace '\s+$', '') }
    } finally {
        Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
    }
}

function Test-Installation {
    Write-Step 'Verifying'
    $venvExe = Join-Path $VenvDir 'Scripts\kaelix.exe'
    if (-not (Test-Path -LiteralPath $venvExe)) {
        Stop-WithError "Install finished but $venvExe is missing. See $($script:LogFile)."
    }
    $result = Invoke-Capture -FilePath $venvExe -Arguments @('--version')
    if ($result.ExitCode -ne 0 -or -not $result.Output) {
        Write-Log $result.Output 'FAIL'
        Stop-WithError "Install finished but 'kaelix --version' failed. See $($script:LogFile)."
    }
    Write-Ok (($result.Output -split "`r?`n")[0])
}

# --- Entry points ------------------------------------------------------------

function Initialize-Logging {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $script:LogFile = Join-Path $LogDir ('install-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}

function Invoke-Install {
    Show-Banner
    Initialize-Logging
    Show-Environment
    $python = Install-Dependencies
    Sync-Repository
    Install-Venv -Python $python
    Install-Launcher
    Test-Installation

    Write-Host ''
    Write-Host '  Kaelix is installed.' -ForegroundColor Green -NoNewline
    Write-Host " Run " -NoNewline
    Write-Host 'kaelix' -ForegroundColor Cyan -NoNewline
    Write-Host ' to start.'
    Write-Host ''
}

function Invoke-Uninstall {
    Show-Banner
    # No Initialize-Logging here: the log directory lives inside $AppBase, and
    # creating it would recreate the very tree we are about to delete.
    Write-Step 'Uninstalling Kaelix'

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @(($userPath -split ';') | Where-Object { $_ -and $_ -ne $BinDir })
    if (($userPath -split ';') -contains $BinDir) {
        [Environment]::SetEnvironmentVariable(
            'Path', ($entries -join ';'), 'User')
        Write-Ok "Removed $BinDir from your PATH"
    }

    # $BinDir's parent (Programs\kaelix) is ours alone, so the whole tree goes.
    $launcherRoot = Split-Path -Parent $BinDir
    $found = $false
    foreach ($target in @($launcherRoot, $AppBase)) {
        if (-not (Test-Path -LiteralPath $target)) { continue }
        $found = $true
        try {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
            Write-Ok "Removed $target"
        } catch {
            Write-Warn "Could not fully remove $target"
        }
    }
    if (-not $found) {
        Write-Item "Nothing installed at $AppBase"
    }

    Write-Host ''
    Write-Host '  Kaelix has been uninstalled.' -ForegroundColor Green
    Write-Host ''
}

if ($Uninstall) { Invoke-Uninstall } else { Invoke-Install }

if (-not $Quiet -and $Host.Name -eq 'ConsoleHost') {
    Write-Host '  Press any key to close...' -ForegroundColor DarkGray
    try { $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown') } catch { }
}
