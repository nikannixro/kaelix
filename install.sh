#!/usr/bin/env bash
# ============================================================================
# Kaelix — Unix/macOS Installer (Unified)
# https://github.com/nikannixro/kaelix
# ============================================================================
set -euo pipefail

# --- Constants ----------------------------------------------------------------
REPO_URL="https://github.com/nikannixro/kaelix.git"
REPO_NAME="kaelix"
REQUIRED_DEPS=(git python3 python3-pip mkvtoolnix ffmpeg)
OPTIONAL_DEPS=(pipx uv)

# --- Colors & Output ----------------------------------------------------------
if [[ -t 1 ]]; then
    C_RED=$'\033[1;31m'
    C_GREEN=$'\033[1;32m'
    C_YELLOW=$'\033[1;33m'
    C_BLUE=$'\033[1;34m'
    C_GRAY=$'\033[0;37m'
    C_CYAN=$'\033[1;36m'
    C_BOLD=$'\033[1m'
    C_RESET=$'\033[0m'
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_GRAY=""; C_CYAN=""; C_BOLD=""; C_RESET=""
fi

LOG_DIR="${HOME}/.kaelix"
LOG_FILE="${LOG_DIR}/install_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "${LOG_DIR}" 2>/dev/null || true

log() {
    local level="$1"; shift
    local msg="$*"
    local ts; ts=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$ts] [$level] $msg" >> "${LOG_FILE}" 2>/dev/null || true
}

has() { command -v "$1" >/dev/null 2>&1; }

banner() {
    local width height max_len=41 banner_h=5 top_pad left_pad i
    width=$(tput cols 2>/dev/null || echo 80)
    height=$(tput lines 2>/dev/null || echo 24)
    top_pad=$(( (height - banner_h) / 2 ))
    left_pad=$(printf '%*s' $(( (width - max_len) / 2 )) '')
    for ((i=0; i<top_pad; i++)); do echo ""; done
    echo -e "${C_GREEN}${left_pad}=========================================${C_RESET}"
    echo -e "${C_GREEN}${left_pad}            K A E L I X${C_RESET}"
    echo -e "${C_GREEN}${left_pad}=========================================${C_RESET}"
    echo ""
}

step() { local n=$1 t=$2; shift 2; echo -ne "  ${C_GRAY}[${C_YELLOW}${n}/${t}${C_GRAY}]${C_RESET} "; echo "$*"; log "STEP" "$*"; }
ok()   { echo -e "       ${C_GREEN}✓ $*${C_RESET}"; log "OK" "$*"; }
fail() { echo -e "       ${C_RED}✗ $*${C_RESET}"; log "FAIL" "$*"; }
warn() { echo -e "       ${C_YELLOW}⚠ $*${C_RESET}"; log "WARN" "$*"; }
info() { echo -e "       ${C_CYAN}⟳ $*${C_RESET}"; log "INFO" "$*"; }
die()  { fail "$*"; exit 1; }

# --- Admin/Root check ---------------------------------------------------------
need_root() {
    if [[ $EUID -ne 0 ]]; then
        fail "This installer must run as root."
        echo -e "       ${C_YELLOW}Re-run with: sudo bash install.sh${C_RESET}"
        exit 1
    fi
}

# --- OS / Distro detection ----------------------------------------------------
OS=""; DISTRO=""; PKG_MGR=""

detect_os() {
    case "$(uname -s)" in
        Linux*)
            case "$(uname -o)" in
                GNU/Linux) OS="linux"; detect_distro ;;
                *) OS="wsl"; DISTRO="${WSL_DISTRO_NAME:-unknown}" ;;
            esac ;;
        Darwin*) OS="macos" ;;
        *) die "Unsupported OS: $(uname -s). Use install.ps1 for Windows." ;;
    esac
}

detect_distro() {
    [[ -f /etc/os-release ]] || die "Cannot detect Linux distribution."
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
        ubuntu)              DISTRO="ubuntu"; PKG_MGR="apt" ;;
        debian)              DISTRO="debian"; PKG_MGR="apt" ;;
        linuxmint|pop)       DISTRO="debian"; PKG_MGR="apt" ;;
        arch|manjaro|endeavouros|parch) DISTRO="arch"; PKG_MGR="pacman" ;;
        fedora)              DISTRO="fedora"; PKG_MGR="dnf" ;;
        centos|rhel|rocky|almalinux|ol|virtuozzo|amzn) DISTRO="rhel"; PKG_MGR="dnf" ;;
        opensuse*|sles)      DISTRO="opensuse"; PKG_MGR="zypper" ;;
        alpine)              DISTRO="alpine"; PKG_MGR="apk" ;;
        void)                DISTRO="void"; PKG_MGR="xbps" ;;
        nixos)               DISTRO="nixos"; PKG_MGR="nix" ;;
        *)
            case "${ID_LIKE:-}" in
                ubuntu|debian) DISTRO="debian"; PKG_MGR="apt" ;;
                arch)          DISTRO="arch"; PKG_MGR="pacman" ;;
                fedora|rhel)   DISTRO="rhel"; PKG_MGR="dnf" ;;
                suse)          DISTRO="opensuse"; PKG_MGR="zypper" ;;
                *)             DISTRO="unknown"; PKG_MGR="" ;;
            esac ;;
    esac
    ok "Detected: ${PRETTY_NAME:-$DISTRO} (pkg: ${PKG_MGR:-unknown})"
}

# --- Package Manager Abstraction ---------------------------------------------
pkg_update() {
    case "$PKG_MGR" in
        apt)    apt-get update -y -qq ;;
        dnf)    dnf makecache -y ;;
        yum)    yum makecache -y ;;
        pacman) pacman -Sy --noconfirm ;;
        zypper) zypper refresh ;;
        apk)    apk update ;;
        xbps)   xbps-install -Sy ;;
        nix)    return 0 ;;
        *) return 1 ;;
    esac
}

pkg_install() {
    case "$PKG_MGR" in
        apt)    apt-get install -y -qq "$@" ;;
        dnf)    dnf install -y "$@" ;;
        yum)    yum install -y "$@" ;;
        pacman) pacman -S --noconfirm "$@" ;;
        zypper) zypper install -y "$@" ;;
        apk)    apk add "$@" ;;
        xbps)   xbps-install -Sy "$@" ;;
        nix)    nix-env -i "$@" ;;
        *) return 1 ;;
    esac
}

# --- Dependency detection & install ------------------------------------------
install_deps() {
    case "$OS" in
        linux)  install_deps_linux ;;
        macos)  install_deps_macos ;;
    esac
}

install_deps_linux() {
    if [[ -z "$PKG_MGR" ]]; then
        install_deps_fallback
        return
    fi

    info "Updating package index..."
    pkg_update || warn "Package update had issues (continuing)."

    info "Installing: ${REQUIRED_DEPS[*]}"
    pkg_install "${REQUIRED_DEPS[@]}" || die "Failed to install system dependencies."

    # Optional: pipx/uv for isolated python tools
    for opt in "${OPTIONAL_DEPS[@]}"; do
        if ! has "$opt"; then
            info "Installing optional: $opt"
            pkg_install "$opt" 2>/dev/null || warn "Optional $opt not available via $PKG_MGR"
        fi
    done

    ok "System dependencies installed."
}

install_deps_macos() {
    if ! has brew; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)"
    fi
    info "Installing: ${REQUIRED_DEPS[*]}"
    brew install "${REQUIRED_DEPS[@]}" -q
    ok "System dependencies installed."
}

install_deps_fallback() {
    warn "Unknown distro ($DISTRO), trying fallback package managers..."
    local managers=(apt-get dnf yum pacman zypper apk xbps-install nix-env snap flatpak)
    for mgr in "${managers[@]}"; do
        if has "$mgr"; then
            info "Trying $mgr..."
            case "$mgr" in
                apt-get) apt-get update -y -qq && apt-get install -y -qq "${REQUIRED_DEPS[@]}" ;;
                dnf)     dnf install -y "${REQUIRED_DEPS[@]}" ;;
                yum)     yum install -y "${REQUIRED_DEPS[@]}" ;;
                pacman)  pacman -Sy --noconfirm "${REQUIRED_DEPS[@]}" ;;
                zypper)  zypper install -y "${REQUIRED_DEPS[@]}" ;;
                apk)     apk add "${REQUIRED_DEPS[@]}" ;;
                xbps-install) xbps-install -Sy "${REQUIRED_DEPS[@]}" ;;
                nix-env) nix-env -i "${REQUIRED_DEPS[@]}" ;;
                snap)    snap install python3 --classic 2>/dev/null; snap install ffmpeg 2>/dev/null ;;
                flatpak) flatpak install -y flathub org.python.Platform 2>/dev/null ;;
            esac && { ok "Dependencies installed via $mgr"; return; }
        fi
    done
    die "No supported package manager found. Install manually: ${REQUIRED_DEPS[*]}"
}

# --- Download with progress bar (Ollama-style) -------------------------------
download() {
    local url="$1" out="$2" max="${3:-3}" attempt=1 total=0 read=0 bar_w=40 pct=0
    info "Downloading: $url"
    while (( attempt <= max )); do
        if has curl; then
            if curl -fL --progress-bar -o "$out" "$url" 2>&1; then
                ok "Download complete."
                return 0
            fi
        elif has wget; then
            if wget --show-progress -O "$out" "$url" 2>&1; then
                ok "Download complete."
                return 0
            fi
        fi
        warn "Download failed (attempt $attempt/$max). Retrying in $((attempt*2))s..."
        sleep $((attempt * 2))
        ((attempt++))
    done
    die "Download failed after $max attempts: $url"
}

# --- Repository management ---------------------------------------------------
manage_repo() {
    local target_dir="$(pwd)/${REPO_NAME}"
    if [[ -d "$target_dir/.git" ]]; then
        local remote
        remote=$(git -C "$target_dir" remote get-url origin 2>/dev/null || echo "")
        if [[ "$remote" == "$REPO_URL" || "$remote" == "${REPO_URL%.git}.git" ]]; then
            update_repo "$target_dir"
        else
            warn "Directory exists but is wrong repo. Re-cloning..."
            rm -rf "$target_dir"
            clone_repo "$target_dir"
        fi
    else
        clone_repo "$target_dir"
    fi
    cd "$target_dir"
}

clone_repo() {
    info "Cloning repository..."
    git clone "$REPO_URL" "$1" 2>/dev/null || die "Clone failed."
    ok "Repository cloned."
}

update_repo() {
    info "Checking for updates..."
    git -C "$1" fetch origin --quiet 2>/dev/null
    local local_hash remote_hash
    local_hash=$(git -C "$1" rev-parse HEAD)
    remote_hash=$(git -C "$1" rev-parse origin/main 2>/dev/null || git -C "$1" rev-parse origin/master 2>/dev/null || echo "$local_hash")
    if [[ "$local_hash" == "$remote_hash" ]]; then
        ok "Already up to date."
    else
        info "Updates available. Pulling..."
        git -C "$1" pull --quiet 2>/dev/null
        ok "Updated to latest version."
    fi
}

# --- Python package install --------------------------------------------------
install_python() {
    info "Installing Python package (editable)..."
    if has pipx; then
        pipx install --force -e . || pipx install --force .
    elif has pip3; then
        pip3 install --user -e . -q 2>/dev/null || pip3 install --user -e .
    elif has pip; then
        pip install --user -e . -q 2>/dev/null || pip install --user -e .
    else
        die "No pip/pipx found."
    fi
    ok "Kaelix installed."
}

# --- Uninstall ---------------------------------------------------------------
uninstall() {
    info "Uninstalling Kaelix..."
    has pipx && pipx uninstall kaelix 2>/dev/null || true
    has pip3 && pip3 uninstall -y kaelix 2>/dev/null || true
    has pip && pip uninstall -y kaelix 2>/dev/null || true
    local target_dir="$(pwd)/${REPO_NAME}"
    [[ -d "$target_dir" ]] && rm -rf "$target_dir" && ok "Removed $target_dir"
    [[ -d "$HOME/.kaelix" ]] && rm -rf "$HOME/.kaelix" && ok "Removed ~/.kaelix"
    ok "Kaelix uninstalled."
}

# --- Non-interactive mode ----------------------------------------------------
NONINTERACTIVE="${KAELIX_NONINTERACTIVE:-0}"

prompt_or_default() {
    local var="$1" prompt="$2" default="$3"
    if [[ "$NONINTERACTIVE" == "1" ]]; then
        printf -v "$var" '%s' "$default"
    else
        read -rp "$prompt" "$var"
        printf -v "$var" '%s' "${!var:-$default}"
    fi
}

# --- Main --------------------------------------------------------------------
main() {
    case "${1:-}" in
        -u|--uninstall) banner; need_root; uninstall; exit 0 ;;
        -h|--help)
            echo "Usage: install.sh [OPTIONS]"
            echo "  -u, --uninstall    Uninstall Kaelix"
            echo "  -h, --help         Show help"
            echo "Env: KAELIX_NONINTERACTIVE=1"
            exit 0 ;;
    esac

    banner
    need_root
    detect_os
    step 1 4 "Installing system dependencies"
    install_deps
    step 2 4 "Setting up repository"
    manage_repo
    step 3 4 "Installing Python package"
    install_python
    step 4 4 "Verifying installation"
    has kaelix && ok "kaelix command available" || warn "Add ~/.local/bin to PATH if 'kaelix' not found"
    echo ""
    ok "Installation complete. Run 'kaelix' to start."
}

main "$@"