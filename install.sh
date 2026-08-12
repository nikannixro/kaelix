#!/usr/bin/env bash
set -euo pipefail

# --- Constants ---------------------------------------------------------------
REPO_URL="https://github.com/nikannixro/kaelix.git"
REPO_NAME="kaelix"
INSTALL_LOG_DIR=""
INSTALL_LOG_FILE=""

# --- Colors (Ollama-style, disabled when not a TTY) --------------------------
if [[ -t 1 ]]; then
  C_RED=$'\033[1;31m'
  C_GREEN=$'\033[1;32m'
  C_YELLOW=$'\033[1;33m'
  C_CYAN=$'\033[1;36m'
  C_GRAY=$'\033[0;37m'
  C_BOLD=$'\033[1m'
  C_RESET=$'\033[0m'
else
  C_RED=""
  C_GREEN=""
  C_YELLOW=""
  C_CYAN=""
  C_GRAY=""
  C_BOLD=""
  C_RESET=""
fi

say()  { printf '%s\n' "$*"; }
info() { printf '  %s%s%s\n' "$C_GRAY" "$*" "$C_RESET"; }
ok()   { printf '  %s✓ %s%s\n' "$C_GREEN" "$*" "$C_RESET"; }
warn() { printf '  %s⚠ %s%s\n' "$C_YELLOW" "$*" "$C_RESET"; }
err()  { printf '  %s✗ %s%s\n' "$C_RED" "$*" "$C_RESET" >&2; }
die()  { err "$*"; exit 1; }
log()  { local ts; ts=$(date +"%Y-%m-%d %H:%M:%S"); echo "[$ts] $*" >> "$INSTALL_LOG_FILE" 2>/dev/null || true; }

banner() {
  say ""
  say "${C_GREEN}   ┌─────────────────────────────────────┐${C_RESET}"
  say "${C_GREEN}   │                                    │${C_RESET}"
  say "${C_GREEN}   │          K A E L I X               │${C_RESET}"
  say "${C_GREEN}   │        the MKV metadata tool      │${C_RESET}"
  say "${C_GREEN}   └─────────────────────────────────────┘${C_RESET}"
  say ""
}

# --- Detection ---------------------------------------------------------------
OS="linux"
ARCH="$(uname -m)"
DISTRO=""
PKG_MGR=""

detect_os() {
  case "$(uname -s)" in
    Linux*) OS="linux";;
    Darwin*) OS="macos";;
    *) die "Unsupported OS. Use install.ps1 on Windows." ;;
  esac
}

detect_distro() {
  [[ -f /etc/os-release ]] || { DISTRO="unknown"; return; }
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO="${PRETTY_NAME:-$ID:-unknown}"
  case "${ID:-}${ID_LIKE:-}" in
    *ubuntu*|*debian*) PKG_MGR="apt-get" ;;
    *arch*|*manjaro*)  PKG_MGR="pacman" ;;
    *fedora*)         PKG_MGR="dnf" ;;
    *rhel*|*centos*|*rocky*|*almalinux*) PKG_MGR="dnf" ;;
    *opensuse*|*suse*) PKG_MGR="zypper" ;;
    *alpine*)          PKG_MGR="apk" ;;
    *) PKG_MGR="" ;;
  esac
}

is_wsl() { [[ -f /proc/version ]] && grep -qi microsoft /proc/version; }

arch_human() {
  case "$ARCH" in
    x86_64|amd64) echo "x86_64" ;;
    arm64|aarch64) echo "arm64" ;;
    *) echo "$ARCH" ;;
  esac
}

# --- Dependencies ------------------------------------------------------------
REQUIRED_BINS=(git python3)

check_deps() {
  local missing=()
  for b in "${REQUIRED_BINS[@]}"; do
    command -v "$b" >/dev/null 2>&1 || missing+=("$b")
  done
  if (( ${#missing[@]} )); then
    die "Missing required tools: ${missing[*]}. Install them first (see README)."
  fi
  # Optional runtime binaries — warn, don't fail (path overrides exist).
  for b in mkvmerge mkvpropedit ffprobe; do
    command -v "$b" >/dev/null 2>&1 || warn "Optional: $b not on PATH (install MKVToolNix/ffmpeg or pass explicit paths)."
  done
}

# --- App dir (per-OS) --------------------------------------------------------
APP_DIR=""
setup_app_dir() {
  case "$OS" in
    macos) APP_DIR="$HOME/Library/Application Support/kaelix" ;;
    *)     APP_DIR="$HOME/.local/share/kaelix" ;;
  esac
  mkdir -p "$APP_DIR"/{app,venv,downloads,logs}
  INSTALL_LOG_DIR="$APP_DIR/logs"
  INSTALL_LOG_FILE="$INSTALL_LOG_DIR/install_$(date +%Y%m%d_%H%M%S).log"
  : > "$INSTALL_LOG_FILE" 2>/dev/null || true
}

# --- Repo clone / refresh ----------------------------------------------------
manage_repo() {
  local target="$APP_DIR/app"
  if [[ -d "$target/.git" ]]; then
    local remote
    remote=$(git -C "$target" remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote" == "$REPO_URL" || "$remote" == "${REPO_URL%.git}.git" ]]; then
      info "Checking for updates..."
      git -C "$target" fetch --quiet origin
      local local_hash remote_hash
      local_hash=$(git -C "$target" rev-parse HEAD)
      remote_hash=$(git -C "$target" rev-parse origin/main 2>/dev/null || git -C "$target" rev-parse origin/master 2>/dev/null || echo "$local_hash")
      if [[ "$local_hash" == "$remote_hash" ]]; then
        ok "Already up to date."
      else
        info "Pulling updates..."
        git -C "$target" pull --quiet
        ok "Updated to latest main."
      fi
    else
      warn "Wrong remote — re-cloning."
      rm -rf "$target"
      git clone "$REPO_URL" "$target"
      ok "Repository cloned."
    fi
  else
    info "Cloning repository..."
    git clone "$REPO_URL" "$target"
    ok "Repository cloned."
  fi
}

# --- Python venv -------------------------------------------------------------
setup_venv() {
  if [[ -x "$APP_DIR/venv/bin/python" ]]; then
    ok "Virtual environment already exists."
  else
    info "Creating virtual environment (python3 -m venv)..."
    python3 -m venv "$APP_DIR/venv"
    ok "Virtual environment created."
  fi
  "$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
  info "Installing Kaelix into the virtual environment (non-editable)..."
  "$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade "$APP_DIR/app"
  ok "Kaelix installed in venv."
  # Write the app-dir marker so selfmanage can find it
  echo "$APP_DIR/app" > "$APP_DIR/app/.kaelix-app"
}

# --- Global wrapper ----------------------------------------------------------
BIN_DIR="$HOME/.local/bin"
setup_wrapper() {
  mkdir -p "$BIN_DIR"
  local venv_bin="$APP_DIR/venv/bin/kaelix"
  if [[ -L "$BIN_DIR/kaelix" ]]; then
    rm -f "$BIN_DIR/kaelix"
  fi
  ln -s "$venv_bin" "$BIN_DIR/kaelix"
  ok "Created launcher: $BIN_DIR/kaelix"
  case ":$PATH:" in
    *":$BIN_DIR:"*) : ;;
    *)
      warn "Add $BIN_DIR to your PATH:"
      warn "    echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
      ;;
  esac
}

# --- Verify ------------------------------------------------------------------
verify_install() {
  if command -v kaelix >/dev/null 2>&1; then
    local v
    v=$("$BIN_DIR/kaelix" --version 2>/dev/null || echo "unknown")
    ok "Installed: $v"
  else
    warn "kaelix not on PATH yet — open a new shell or add $BIN_DIR."
  fi
}

# --- Uninstall ---------------------------------------------------------------
uninstall() {
  info "Uninstalling Kaelix..."
  rm -f "$BIN_DIR/kaelix"
  rm -rf "$APP_DIR"
  ok "Kaelix uninstalled."
}

# --- Main --------------------------------------------------------------------
main() {
  case "${1:-}" in
    -u|--uninstall) uninstall; exit 0 ;;
    -h|--help)
      say "Usage: install.sh [OPTIONS]"
      say "  -u, --uninstall   Uninstall Kaelix"
      say "  -h, --help        Show this help"
      exit 0 ;;
  esac

  banner
  detect_os
  detect_distro
  setup_app_dir
  log "Install start: OS=$OS ARCH=$(arch_human) DISTRO=$DISTRO"
  info "Detected: $OS $(arch_human)${DISTRO:+ ($DISTRO)}${is_wsl && echo ", WSL"}"
  info "Install location: $APP_DIR"
  check_deps
  manage_repo
  setup_venv
  setup_wrapper
  verify_install
  say ""
  ok "Installation complete. Run 'kaelix' to start."
  log "Install complete."
}

main "$@"