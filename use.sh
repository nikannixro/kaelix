#!/usr/bin/env bash
# ============================================================================
# Movies Metadata Organizer — cross-platform startup script
# Supports: Linux, WSL, macOS, Windows (Git Bash)
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/nikannixro/movies-metadata-organizer.git"
REPO_DIR="movies-metadata-organizer"

# --- Helpers ----------------------------------------------------------------

info()  { printf "\033[1;34m=== %s ===\033[0m\n" "$*"; }
ok()    { printf "\033[1;32m--- %s ---\033[0m\n" "$*"; }
err()   { printf "\033[1;31mERROR: %s\033[0m\n" "$*" >&2; }
has()   { command -v "$1" >/dev/null 2>&1; }

# --- Detect OS --------------------------------------------------------------

detect_os() {
    case "$(uname -s)" in
        Linux*)
            if [ -n "${WSL_DISTRO_NAME:-}" ] && [ -f /proc/sys/fs/binfmt_misc/WSLInterop ]; then
                OS="wsl"
            else
                OS="linux"
            fi
            ;;
        Darwin*)               OS="macos" ;;
        MINGW*|MSYS*|CYGWIN*) OS="windows" ;;
        *)                     err "Unsupported OS: $(uname -s)"; exit 1 ;;
    esac
    info "Detected OS: $OS"
}

# --- Root check (Linux / WSL only) ------------------------------------------

check_root() {
    if [ "$OS" = "linux" ] || [ "$OS" = "wsl" ]; then
        if [ "$(id -u)" -ne 0 ]; then
            err "You are not running as root."
            err "Please run this script as root or using sudo."
            err "Installation cancelled."
            exit 1
        fi
    fi
}

# --- Install dependencies ---------------------------------------------------

install_deps_linux() {
    info "Installing system packages (apt)..."
    apt update
    apt upgrade -y
    apt install -y mkvtoolnix ffmpeg git-all python3-pip
    ok "System packages installed."
}

install_deps_macos() {
    if ! has brew; then
        err "Homebrew is not installed."
        err "Install it from https://brew.sh and re-run this script."
        exit 1
    fi
    info "Installing system packages (brew)..."
    brew install ffmpeg mkvtoolnix git python
    ok "System packages installed."
}

install_deps_windows() {
    info "Detected Windows (Git Bash / MSYS2)."
    local missing=0
    if ! has git; then
        err "Git is not installed."
        err "Install it: winget install --id Git.Git -e --source winget"
        missing=1
    fi
    if ! has python3 && ! has python; then
        err "Python 3 is not installed."
        err "Install it: winget install --id Python.Python.3.12 -e --source winget"
        missing=1
    fi
    if ! has pip3 && ! has pip; then
        err "pip is not installed."
        err "Install it: python -m ensurepip --upgrade"
        missing=1
    fi
    if [ "$missing" -eq 1 ]; then
        exit 1
    fi
    ok "Required tools found (git, python, pip)."
}

# --- Clone repo -------------------------------------------------------------

clone_repo() {
    if [ -d "$REPO_DIR/src" ]; then
        info "Repository already exists at ./$REPO_DIR — skipping clone."
    else
        info "Cloning repository..."
        git clone "$REPO_URL"
        ok "Repository cloned."
    fi
    cd "$REPO_DIR"
}

# --- Install Python deps + run ---------------------------------------------

setup_and_run() {
    info "Installing Python dependencies..."
    if has pip; then
        pip install -r requirements.txt
    elif has pip3; then
        pip3 install -r requirements.txt
    fi
    ok "Python dependencies installed."

    info "Starting Movies Metadata Organizer..."
    if has python; then
        python -m src.main
    elif has python3; then
        python3 -m src.main
    fi
}

# --- Main -------------------------------------------------------------------

main() {
    detect_os
    check_root

    case "$OS" in
        linux|wsl) install_deps_linux ;;
        macos)     install_deps_macos ;;
        windows)   install_deps_windows ;;
    esac

    clone_repo
    setup_and_run
}

main "$@"
