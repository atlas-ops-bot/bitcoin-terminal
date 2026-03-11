#!/usr/bin/env bash
# ============================================================================
# Bitcoin Terminal — One-line installer
# curl -sL https://raw.githubusercontent.com/CRTao/bitcoin-terminal/main/install.sh | bash
# ============================================================================
set -e

REPO_URL="https://github.com/CRTao/bitcoin-terminal.git"
INSTALL_DIR="$HOME/bitcoin-terminal"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

# ── Colors ─────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    BOLD="\033[1m"
    DIM="\033[2m"
    ORANGE="\033[38;5;208m"
    GREEN="\033[32m"
    RED="\033[31m"
    CYAN="\033[36m"
    RESET="\033[0m"
else
    BOLD="" DIM="" ORANGE="" GREEN="" RED="" CYAN="" RESET=""
fi

info()  { printf "${CYAN}[info]${RESET}  %s\n" "$*"; }
ok()    { printf "${GREEN}[  ok]${RESET}  %s\n" "$*"; }
warn()  { printf "${ORANGE}[warn]${RESET}  %s\n" "$*"; }
fail()  { printf "${RED}[fail]${RESET}  %s\n" "$*"; exit 1; }

# ── Banner ─────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}${ORANGE}"
cat << 'BANNER'

    ____  _ __              _          ______                    _             __
   / __ )(_) /________  ___(_)___     /_  __/__  _________ ___  (_)___  ____ _/ /
  / __  / / __/ ___/ _ \/ / / __ \     / / / _ \/ ___/ __ `__ \/ / __ \/ __ `/ /
 / /_/ / / /_/ /__/ /__/ / / / / /    / / /  __/ /  / / / / / / / / / / /_/ / /
/_____/_/\__/\___/\___/_/_/_/ /_/    /_/  \___/_/  /_/ /_/ /_/_/_/ /_/\__,_/_/

BANNER
printf "${RESET}"
printf "${DIM}  A modern terminal dashboard for Bitcoin Node monitoring${RESET}\n"
printf "${DIM}  https://github.com/CRTao/bitcoin-terminal${RESET}\n\n"

# ── Check: git ─────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    fail "git is not installed. Please install git first:
    macOS:  xcode-select --install
    Ubuntu: sudo apt install git
    Fedora: sudo dnf install git"
fi
ok "git found"

# ── Check: Python 3 ───────────────────────────────────────────────────
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" 2>/dev/null; then
                echo "$cmd"
                return
            fi
        fi
    done
}

PYTHON_CMD="$(find_python)"

if [[ -z "$PYTHON_CMD" ]]; then
    printf "${RED}[fail]${RESET}  Python 3 is not installed.\n"
    printf "\n  Install Python 3.8+ for your platform:\n"
    case "$(uname -s)" in
        Darwin)  printf "    brew install python3\n" ;;
        Linux)   printf "    sudo apt install python3 python3-venv python3-pip   # Debian/Ubuntu\n"
                 printf "    sudo dnf install python3 python3-pip                # Fedora\n" ;;
        *)       printf "    https://www.python.org/downloads/\n" ;;
    esac
    printf "\n"
    exit 1
fi

# ── Check: Python version ─────────────────────────────────────────────
PYTHON_VERSION="$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
PYTHON_OK="$("$PYTHON_CMD" -c "import sys; print(int(sys.version_info >= ($MIN_PYTHON_MAJOR,$MIN_PYTHON_MINOR)))")"

if [[ "$PYTHON_OK" != "1" ]]; then
    fail "Python >= $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR required (found $PYTHON_VERSION)"
fi
ok "Python $PYTHON_VERSION"

# ── Check: venv module ────────────────────────────────────────────────
if ! "$PYTHON_CMD" -m venv --help &>/dev/null; then
    warn "python3-venv not found, attempting to install..."
    case "$(uname -s)" in
        Linux)
            if command -v apt-get &>/dev/null; then
                PY_VER="$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
                sudo apt-get install -y "python${PY_VER}-venv" || fail "Could not install python3-venv. Run: sudo apt install python3-venv"
            else
                fail "python3-venv is missing. Install it with your package manager."
            fi
            ;;
        *)
            fail "python3-venv is missing. Install it with your package manager."
            ;;
    esac
fi

# ── Clone or update ───────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "Could not auto-update (you may have local changes)"
    ok "Updated"
else
    if [[ -d "$INSTALL_DIR" ]]; then
        fail "$INSTALL_DIR already exists but is not a git repo. Remove it or choose a different location."
    fi
    info "Cloning Bitcoin Terminal..."
    git clone "$REPO_URL" "$INSTALL_DIR" || fail "Failed to clone repository"
    cd "$INSTALL_DIR"
    ok "Cloned to $INSTALL_DIR"
fi

# ── Create virtual environment ────────────────────────────────────────
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    info "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$INSTALL_DIR/venv" || fail "Failed to create virtual environment"
    ok "Virtual environment created"
fi

# ── Activate & install ────────────────────────────────────────────────
# shellcheck disable=SC1091
source "$INSTALL_DIR/venv/bin/activate"

info "Installing dependencies (this may take a moment)..."
python -m pip install --upgrade pip --quiet 2>/dev/null
python -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet || fail "Failed to install dependencies"
ok "Dependencies installed"

# ── Make run.sh executable ────────────────────────────────────────────
chmod +x "$INSTALL_DIR/run.sh"

# ── Done ──────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}${GREEN}  ✓ Bitcoin Terminal installed successfully!${RESET}\n\n"

printf "  ${BOLD}To launch:${RESET}\n"
printf "    ${CYAN}cd ~/bitcoin-terminal && ./run.sh${RESET}\n\n"

printf "  ${BOLD}What happens next:${RESET}\n"
printf "    • The setup wizard will guide you through connecting to your node\n"
printf "    • It auto-detects your Bitcoin data directory\n"
printf "    • It finds RPC credentials from your .cookie or bitcoin.conf\n"
printf "    • No manual configuration needed in most cases\n\n"

printf "  ${BOLD}Requirements:${RESET}\n"
printf "    • A running Bitcoin Core node with ${CYAN}server=1${RESET} in bitcoin.conf\n"
printf "    • That's it — the wizard handles everything else\n\n"

printf "${DIM}  Tip: If your node doesn't have server=1, add it to bitcoin.conf and restart bitcoind${RESET}\n"
printf "${DIM}  Tip: Run ./run.sh --setup to re-run the setup wizard anytime${RESET}\n\n"

# ── Ask to launch now ─────────────────────────────────────────────────
printf "  ${BOLD}Launch Bitcoin Terminal now? [Y/n]${RESET} "
read -r answer
case "$answer" in
    [nN]*)
        printf "\n  ${DIM}Run later with: cd ~/bitcoin-terminal && ./run.sh${RESET}\n\n"
        ;;
    *)
        printf "\n"
        exec "$INSTALL_DIR/run.sh"
        ;;
esac
