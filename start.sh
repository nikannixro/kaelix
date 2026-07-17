#!/usr/bin/env bash
# ============================================================================
# Kaelix — Unix/macOS installer and launcher
# Supported: Ubuntu, Debian, Linux Mint, Arch Linux, WSL, macOS
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/nikannixro/kaelix.git"
REPO_NAME="kaelix"

# --- Output helpers ---------------------------------------------------------

info()  { printf "\033[1;34m=== %s ===\033[0m\n" "$*"; }
ok()    { printf "\033[1;32m--- %s ---\033[0m\n" "$*"; }
warn()  { printf "\033[1;33mWARNING: %s\033[0m\n" "$*" >&2; }
err()   { printf "\033[1;31mERROR: %s\033[0m\n" "$*" >&2; }
has()   { command -v "$1" >/dev/null 2>&1; }

# --- OS and distro detection -----------------------------------------------

detect_os() {
    OS=""
    DISTRO=""

    case "$(uname -s)" in
        Linux*)
            case "$(uname -o)" in
                GNU/Linux)
                    OS="linux"
                    detect_distro
                    ;;
                *)
                    OS="wsl"
                    DISTRO="${WSL_DISTRO_NAME:-unknown}"
                    ;;
            esac
            ;;
        Darwin*)
            OS="macos"
            ;;
        *)
            err "Unsupported operating system: $(uname -s). Use start.ps1 for Windows."
            exit 1
            ;;
    esac

    info "Detected OS: ${OS}${DISTRO:+ ($DISTRO)}"
}

detect_distro() {
    if [ ! -f /etc/os-release ]; then
        err "Cannot detect Linux distribution (/etc/os-release not found)."
        err "Unsupported operating system."
        exit 1
    fi

    # shellcheck disable=SC1091
    . /etc/os-release

    case "${ID:-}" in
        ubuntu)              DISTRO="ubuntu" ;;
        debian)              DISTRO="debian" ;;
        linuxmint)           DISTRO="linuxmint" ;;
        arch|manjaro|endeavouros) DISTRO="arch" ;;
        fedora|centos|rhel|rocky|alma) DISTRO="unsupported" ;;
        *)
            case "${ID_LIKE:-}" in
                ubuntu|debian) DISTRO="debian" ;;
                arch)          DISTRO="arch" ;;
                *)             DISTRO="unsupported" ;;
            esac
            ;;
    esac

    if [ "$DISTRO" = "unsupported" ]; then
        err "Unsupported operating system: ${PRETTY_NAME:-$ID}"
        exit 1
    fi
}

# --- Root check (apt/pacman require root) -----------------------------------

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        err "You are not running as root."
        err "Please run this script as root or using sudo."
        err "Installation cancelled."
        exit 1
    fi
}

# --- Dependency installation ------------------------------------------------

install_deps() {
    case "$DISTRO" in
        ubuntu|debian|linuxmint) install_deps_debian ;;
        arch)                    install_deps_arch ;;
    esac
    if [ "$OS" = "macos" ]; then
        install_deps_macos
    fi
}

install_deps_debian() {
    info "Installing dependencies (apt)..."
    apt update -y
    apt install -y git python3 python3-pip mkvtoolnix ffmpeg
    ok "All system dependencies installed."
}

install_deps_arch() {
    info "Installing dependencies (pacman)..."
    pacman -Sy --noconfirm git python python-pip mkvtoolnix ffmpeg
    ok "All system dependencies installed."
}

install_deps_macos() {
    info "Installing dependencies (brew)..."
    if ! has brew; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install git python mkvtoolnix ffmpeg
    ok "All system dependencies installed."
}

# --- Repository management --------------------------------------------------

manage_repo() {
    local target_dir
    target_dir="$(pwd)/${REPO_NAME}"

    if [ -d "$target_dir/.git" ]; then
        local remote
        remote="$(git -C "$target_dir" remote get-url origin 2>/dev/null || echo "")"
        if [ "$remote" = "$REPO_URL" ] || [ "$remote" = "${REPO_URL%.git}.git" ]; then
            update_repo "$target_dir"
        else
            err "Directory exists but is not the correct repository."
            err "Expected: $REPO_URL"
            err "Found:    $remote"
            exit 1
        fi
    else
        clone_repo "$target_dir"
    fi

    cd "$target_dir"
}

clone_repo() {
    local target_dir="$1"
    info "Cloning repository..."
    git clone "$REPO_URL"
    ok "Repository cloned."
}

update_repo() {
    local target_dir="$1"
    info "Repository found. Checking for updates..."

    git -C "$target_dir" fetch origin --quiet 2>/dev/null

    local local_hash remote_hash
    local_hash="$(git -C "$target_dir" rev-parse HEAD)"
    remote_hash="$(git -C "$target_dir" rev-parse origin/main 2>/dev/null || \
                   git -C "$target_dir" rev-parse origin/master 2>/dev/null || \
                   echo "$local_hash")"

    if [ "$local_hash" = "$remote_hash" ]; then
        ok "Already up to date."
    else
        info "Updates available. Pulling..."
        git -C "$target_dir" pull --quiet 2>/dev/null
        ok "Updated to latest version."
    fi
}

# --- Python dependencies and app launch -------------------------------------

install_python_deps() {
    info "Installing Python dependencies..."
    if has pip3; then
        pip3 install -r requirements.txt --break-system-packages 2>/dev/null || \
        pip3 install -r requirements.txt
    elif has pip; then
        pip install -r requirements.txt --break-system-packages 2>/dev/null || \
        pip install -r requirements.txt
    fi
    ok "Python dependencies installed."
}

run_app() {
    info "Starting Kaelix..."
    if has python3; then
        python3 -m src.main
    elif has python; then
        python -m src.main
    fi
}

# --- Entry point ------------------------------------------------------------

main() {
    detect_os
    check_root
    install_deps
    manage_repo
    install_python_deps
    run_app
}

main "$@"
