#!/usr/bin/env bash
#
# Kaelix installer for Linux and macOS.
#
#   bash <(curl -Ls https://raw.githubusercontent.com/nikannixro/kaelix/main/install.sh)
#
# Installs into a private per-user directory with its own virtualenv and
# creates a `kaelix` launcher on PATH. Safe to re-run; also handles upgrades.

set -euo pipefail

REPO_URL="https://github.com/nikannixro/kaelix.git"
DEFAULT_BRANCH="main"
BIN_DIR="${HOME}/.local/bin"

APP_BASE=""
APP_DIR=""
VENV_DIR=""
LOG_DIR=""
LOG_FILE=""

OS=""
DISTRO=""
ARCH=""
IS_WSL="no"
PYTHON=""

# --- Output -----------------------------------------------------------------

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'
else
    BOLD=''; DIM=''; RESET=''; RED=''; GREEN=''; YELLOW=''; CYAN=''
fi

log()   { [ -n "$LOG_FILE" ] && printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG_FILE" 2>/dev/null || true; }
say()   { printf '%s\n' "$*"; }
step()  { printf '\n%s==>%s %s%s%s\n' "$CYAN" "$RESET" "$BOLD" "$*" "$RESET"; log "STEP $*"; }
info()  { printf '    %s%s%s\n' "$DIM" "$*" "$RESET"; log "INFO $*"; }
ok()    { printf '    %s+%s %s\n' "$GREEN" "$RESET" "$*"; log "OK $*"; }
warn()  { printf '    %s!%s %s\n' "$YELLOW" "$RESET" "$*"; log "WARN $*"; }
die()   { printf '\n    %s x %s%s\n\n' "$RED" "$*" "$RESET" >&2; log "FAIL $*"; exit 1; }

banner() {
    printf '\n'
    printf '%s   ██  ██  █████  ███████ ██     ██ ██   ██%s\n' "$CYAN" "$RESET"
    printf '%s   ██ ██  ██   ██ ██      ██     ██  ██ ██ %s\n' "$CYAN" "$RESET"
    printf '%s   ████   ███████ █████   ██     ██   ███  %s\n' "$CYAN" "$RESET"
    printf '%s   ██ ██  ██   ██ ██      ██     ██  ██ ██ %s\n' "$CYAN" "$RESET"
    printf '%s   ██  ██ ██   ██ ███████ ██████ ██ ██   ██%s\n' "$CYAN" "$RESET"
    printf '\n   %sMKV metadata, subtitles, and batch renaming%s\n\n' "$DIM" "$RESET"
}

# --- Detection --------------------------------------------------------------

detect_platform() {
    case "$(uname -s)" in
        Linux*)  OS="linux" ;;
        Darwin*) OS="macos" ;;
        *) die "Unsupported OS: $(uname -s). Use install.ps1 on Windows." ;;
    esac

    case "$(uname -m)" in
        x86_64|amd64)   ARCH="x86_64" ;;
        arm64|aarch64)  ARCH="arm64" ;;
        armv7l|armhf)   ARCH="armv7" ;;
        *)              ARCH="$(uname -m)" ;;
    esac

    if [ "$OS" = "macos" ]; then
        DISTRO="macOS $(sw_vers -productVersion 2>/dev/null || echo '')"
    elif [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        DISTRO="$( . /etc/os-release && printf '%s' "${PRETTY_NAME:-${NAME:-Linux}}" )"
    else
        DISTRO="Linux"
    fi

    if grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
        IS_WSL="yes"
    fi
}

set_paths() {
    # create_log_dir=no during uninstall: the log directory lives inside
    # APP_BASE, so creating it would recreate the tree we are deleting.
    local create_log_dir="${1:-yes}"
    if [ -n "${KAELIX_APP_DIR:-}" ]; then
        APP_BASE="$KAELIX_APP_DIR"
    elif [ "$OS" = "macos" ]; then
        APP_BASE="${HOME}/Library/Application Support/kaelix"
    else
        APP_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/kaelix"
    fi
    APP_DIR="${APP_BASE}/app"
    VENV_DIR="${APP_BASE}/venv"
    LOG_DIR="${APP_BASE}/logs"
    if [ "$create_log_dir" = "yes" ]; then
        mkdir -p "$LOG_DIR"
        LOG_FILE="${LOG_DIR}/install-$(date '+%Y%m%d-%H%M%S').log"
    fi
}

show_environment() {
    step "Environment"
    info "Operating system:  ${DISTRO}$( [ "$IS_WSL" = "yes" ] && printf ' (WSL)' )"
    info "Architecture:      ${ARCH}"
    info "Shell:             ${SHELL:-unknown}"
    info "Install location:  ${APP_BASE}"
    info "Python env:        ${VENV_DIR}"
}

# --- Dependencies -----------------------------------------------------------

find_python() {
    for candidate in python3.14 python3.13 python3.12 python3 python; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            return 0
        fi
    done
    return 1
}

install_hint() {
    # Best-effort package-manager hint; we never install system packages here.
    if command -v apt-get >/dev/null 2>&1; then echo "sudo apt-get install -y $*"
    elif command -v dnf >/dev/null 2>&1;    then echo "sudo dnf install -y $*"
    elif command -v pacman >/dev/null 2>&1; then echo "sudo pacman -S --needed $*"
    elif command -v zypper >/dev/null 2>&1; then echo "sudo zypper install -y $*"
    elif command -v apk >/dev/null 2>&1;    then echo "sudo apk add $*"
    elif command -v brew >/dev/null 2>&1;   then echo "brew install $*"
    else echo "install: $*"
    fi
}

check_dependencies() {
    step "Checking dependencies"

    command -v git >/dev/null 2>&1 || die "git is required. Try: $(install_hint git)"
    ok "git $(git --version | awk '{print $3}')"

    find_python || die "Python 3.12+ is required. Try: $(install_hint python3)"
    ok "python $("$PYTHON" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') ($PYTHON)"

    if ! "$PYTHON" -c 'import venv' >/dev/null 2>&1; then
        die "The Python venv module is missing. Try: $(install_hint python3-venv)"
    fi

    # Runtime tools: warn only. Kaelix reports them itself and accepts
    # explicit paths, so a missing one must not block installation.
    for pair in "mkvmerge:mkvtoolnix" "mkvpropedit:mkvtoolnix" "ffprobe:ffmpeg"; do
        bin="${pair%%:*}"; pkg="${pair##*:}"
        if command -v "$bin" >/dev/null 2>&1; then
            ok "$bin"
        else
            warn "$bin not found - install before running: $(install_hint "$pkg")"
        fi
    done
}

# --- Install ----------------------------------------------------------------

sync_repo() {
    step "Fetching Kaelix"
    if [ -d "${APP_DIR}/.git" ]; then
        local remote
        remote="$(git -C "$APP_DIR" remote get-url origin 2>/dev/null || true)"
        if [ "$remote" != "$REPO_URL" ]; then
            warn "Existing clone points elsewhere; replacing it."
            rm -rf "$APP_DIR"
        fi
    fi

    if [ -d "${APP_DIR}/.git" ]; then
        info "Updating existing clone"
        git -C "$APP_DIR" fetch --tags --force --quiet origin \
            || die "Could not reach GitHub. Check your network and retry."
        git -C "$APP_DIR" checkout --quiet --force "origin/${DEFAULT_BRANCH}" 2>/dev/null \
            || git -C "$APP_DIR" checkout --quiet --force "$DEFAULT_BRANCH" \
            || die "Could not check out ${DEFAULT_BRANCH}."
        ok "Updated to latest ${DEFAULT_BRANCH}"
    else
        info "Cloning ${REPO_URL}"
        rm -rf "$APP_DIR"
        mkdir -p "$(dirname "$APP_DIR")"
        git clone --quiet --depth 1 --branch "$DEFAULT_BRANCH" "$REPO_URL" "$APP_DIR" \
            || die "Clone failed. Check your network and retry."
        # Full tag history is what --upgrade compares against.
        git -C "$APP_DIR" fetch --tags --quiet --unshallow 2>/dev/null || true
        ok "Cloned into ${APP_DIR}"
    fi
}

setup_venv() {
    step "Setting up the Python environment"
    if [ ! -x "${VENV_DIR}/bin/python" ]; then
        info "Creating virtualenv"
        "$PYTHON" -m venv "$VENV_DIR" || die "Could not create the virtualenv."
        ok "Virtualenv created"
    else
        ok "Virtualenv already present"
    fi

    info "Installing Kaelix and its dependencies"
    "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip >>"$LOG_FILE" 2>&1 \
        || warn "Could not upgrade pip; continuing."
    "${VENV_DIR}/bin/python" -m pip install --quiet --upgrade "$APP_DIR" >>"$LOG_FILE" 2>&1 \
        || die "pip install failed. See ${LOG_FILE}."
    ok "Installed into the virtualenv"
}

install_launcher() {
    step "Installing the kaelix command"
    mkdir -p "$BIN_DIR"
    local target="${BIN_DIR}/kaelix"
    # A wrapper (not a symlink) so KAELIX_APP_DIR overrides survive upgrades.
    cat >"$target" <<EOF
#!/usr/bin/env bash
# Generated by the Kaelix installer.
export KAELIX_APP_DIR="\${KAELIX_APP_DIR:-${APP_BASE}}"
exec "${VENV_DIR}/bin/kaelix" "\$@"
EOF
    chmod +x "$target"
    ok "Created ${target}"

    case ":${PATH}:" in
        *":${BIN_DIR}:"*) ;;
        *)
            warn "${BIN_DIR} is not on your PATH."
            case "$(basename "${SHELL:-bash}")" in
                zsh)  say "    Add: echo 'export PATH=\"${BIN_DIR}:\$PATH\"' >> ~/.zshrc" ;;
                fish) say "    Add: fish_add_path ${BIN_DIR}" ;;
                *)    say "    Add: echo 'export PATH=\"${BIN_DIR}:\$PATH\"' >> ~/.bashrc" ;;
            esac
            ;;
    esac
}

verify() {
    step "Verifying"
    local version
    version="$("${VENV_DIR}/bin/kaelix" --version 2>/dev/null || true)"
    [ -n "$version" ] || die "Install finished but 'kaelix --version' failed. See ${LOG_FILE}."
    ok "$version"
}

do_install() {
    banner
    detect_platform
    set_paths
    show_environment
    check_dependencies
    sync_repo
    setup_venv
    install_launcher
    verify
    printf '\n%s  Kaelix is installed.%s Run %skaelix%s to start.\n\n' \
        "$GREEN" "$RESET" "$BOLD" "$RESET"
}

do_uninstall() {
    banner
    detect_platform
    set_paths no
    step "Uninstalling Kaelix"
    local found="no"
    if [ -e "${BIN_DIR}/kaelix" ]; then
        found="yes"
        rm -f "${BIN_DIR}/kaelix" && ok "Removed ${BIN_DIR}/kaelix"
    fi
    if [ -d "$APP_BASE" ]; then
        found="yes"
        rm -rf "$APP_BASE" && ok "Removed ${APP_BASE}"
    fi
    [ "$found" = "yes" ] || info "Nothing installed at ${APP_BASE}"
    printf '\n%s  Kaelix has been uninstalled.%s\n\n' "$GREEN" "$RESET"
}

usage() {
    say "Kaelix installer"
    say ""
    say "Usage: install.sh [OPTION]"
    say ""
    say "  -u, --uninstall   Remove Kaelix from this computer"
    say "  -h, --help        Show this message"
    say ""
    say "Environment:"
    say "  KAELIX_APP_DIR    Override the install directory"
}

main() {
    case "${1:-}" in
        -u|--uninstall) do_uninstall ;;
        -h|--help)      usage ;;
        "")             do_install ;;
        *)              say "Unknown option: $1"; say ""; usage; exit 2 ;;
    esac
}

main "$@"
