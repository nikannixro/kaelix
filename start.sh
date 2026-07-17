#!/usr/bin/env bash
# ============================================================================
# Kaelix — Unix/macOS Installer and Launcher
# https://github.com/nikannixro/kaelix
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/nikannixro/kaelix.git"
REPO_NAME="kaelix"

# --- Colors -------------------------------------------------------------------

RED='\033[1;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
GRAY='\033[0;37m'
NC='\033[0m'

# --- Output helpers -----------------------------------------------------------

banner() {
    echo ""
    echo -e "${CYAN}  _  __           _    _       ${NC}"
    echo -e "${CYAN} | |/ /___   __ _| | _| |_ ___ ${NC}"
    echo -e "${CYAN} | ' // _ \ / _\` | |/ / __/ _ \\${NC}"
    echo -e "${CYAN} | . \  __/ (_| |   <| ||  __/${NC}"
    echo -e "${CYAN} |_|\_\___|\__,_|_|\_\\__\___|${NC}"
    echo ""
    echo -e "${GRAY}  Automated MKV Metadata Editor${NC}"
    echo -e "${GRAY}  ─────────────────────────────${NC}"
    echo ""
}

step() {
    local num=$1 total=$2
    shift 2
    echo -ne "  ${GRAY}[${NC}${YELLOW}${num}/${total}${NC}${GRAY}]${NC} "
    echo "$*"
}

ok()    { echo -e "       ${GREEN}$*${NC}"; }
fail()  { echo -e "       ${RED}$*${NC}"; }
info()  { echo -e "       ${YELLOW}$*${NC}"; }
has()   { command -v "$1" >/dev/null 2>&1; }

# --- OS and distro detection -------------------------------------------------

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
            fail "Unsupported operating system: $(uname -s). Use start.ps1 for Windows."
            exit 1
            ;;
    esac
}

detect_distro() {
    if [ ! -f /etc/os-release ]; then
        fail "Cannot detect Linux distribution."
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
        fail "Unsupported distribution: ${PRETTY_NAME:-$ID}"
        exit 1
    fi
}

# --- Root check ---------------------------------------------------------------

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        fail "Please run as root or with sudo."
        exit 1
    fi
}

# --- Dependency installation --------------------------------------------------

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
    apt update -y -qq
    apt install -y -qq git python3 python3-pip mkvtoolnix ffmpeg
    ok "System dependencies installed."
}

install_deps_arch() {
    info "Installing dependencies (pacman)..."
    pacman -Sy --noconfirm --quiet git python python-pip mkvtoolnix ffmpeg
    ok "System dependencies installed."
}

install_deps_macos() {
    info "Installing dependencies (brew)..."
    if ! has brew; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install git python mkvtoolnix ffmpeg -q
    ok "System dependencies installed."
}

# --- Repository management ----------------------------------------------------

manage_repo() {
    local target_dir
    target_dir="$(pwd)/${REPO_NAME}"

    if [ -d "$target_dir/.git" ]; then
        local remote
        remote="$(git -C "$target_dir" remote get-url origin 2>/dev/null || echo "")"
        if [ "$remote" = "$REPO_URL" ] || [ "$remote" = "${REPO_URL%.git}.git" ]; then
            update_repo "$target_dir"
        else
            fail "Directory exists but is not the correct repository."
            exit 1
        fi
    else
        clone_repo "$target_dir"
    fi

    cd "$target_dir"
}

clone_repo() {
    info "Cloning repository..."
    git clone "$REPO_URL" 2>/dev/null
    ok "Repository cloned."
}

update_repo() {
    local target_dir="$1"
    info "Checking for updates..."

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

# --- Python dependencies and app launch --------------------------------------

install_python_deps() {
    info "Installing Python dependencies..."
    if has pip3; then
        pip3 install -r requirements.txt --break-system-packages -q 2>/dev/null || \
        pip3 install -r requirements.txt -q
    elif has pip; then
        pip install -r requirements.txt --break-system-packages -q 2>/dev/null || \
        pip install -r requirements.txt -q
    fi
    ok "Dependencies installed."
}

run_app() {
    echo ""
    echo -e "  ${CYAN}Launching Kaelix...${NC}"
    echo -e "  ${GRAY}───────────────────${NC}"
    echo ""
    if has python3; then
        python3 -m src.main
    elif has python; then
        python -m src.main
    fi
}

# --- Entry point --------------------------------------------------------------

main() {
    banner
    detect_os
    check_root
    install_deps
    manage_repo
    install_python_deps
    run_app
}

main "$@"
