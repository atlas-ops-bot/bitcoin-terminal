#!/usr/bin/env bash
# ============================================================================
# Bitcoin Terminal - Launcher
# Handles first-time setup automatically: Python check, venv, dependencies.
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

# --- Colors ---------------------------------------------------------------
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

# --- Banner ----------------------------------------------------------------
printf "\n"
printf "${BOLD}${ORANGE}"
cat << 'EOF'
  ₿  Bitcoin Terminal
EOF
printf "${RESET}"
printf "${DIM}  A modern TUI for Bitcoin Node monitoring${RESET}\n"
printf "${DIM}  v0.1.0${RESET}\n\n"

# --- Locate Python 3 ------------------------------------------------------
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            # Verify it's actually Python 3
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

# --- Check Python version --------------------------------------------------
PYTHON_VERSION="$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
PYTHON_OK="$("$PYTHON_CMD" -c "import sys; print(int(sys.version_info >= ($MIN_PYTHON_MAJOR,$MIN_PYTHON_MINOR)))")"

if [[ "$PYTHON_OK" != "1" ]]; then
    fail "Python >= $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR required (found $PYTHON_VERSION)"
fi

ok "Python $PYTHON_VERSION"

# --- Ensure venv exists ----------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment..."

    # Make sure the venv module is available (some distros strip it out)
    if ! "$PYTHON_CMD" -m venv --help &>/dev/null; then
        warn "python3-venv not found. Attempting to install it..."
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

    "$PYTHON_CMD" -m venv "$VENV_DIR" || fail "Failed to create virtual environment"
    ok "Virtual environment created"
fi

# --- Activate venv ---------------------------------------------------------
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "Virtual environment activated"

# --- Upgrade pip (quietly) -------------------------------------------------
info "Checking pip..."
python -m pip install --upgrade pip --quiet 2>/dev/null || warn "Could not upgrade pip (continuing anyway)"
ok "pip ready"

# --- Install / verify dependencies ----------------------------------------
DEPS_INSTALLED=true
python -c "import textual, rich, dotenv, yaspin, pyfiglet, psutil" 2>/dev/null || DEPS_INSTALLED=false

if [[ "$DEPS_INSTALLED" == "false" ]]; then
    info "Installing dependencies (first run may take a moment)..."
    python -m pip install -r "$REQ_FILE" --quiet || fail "Dependency installation failed"
    ok "Dependencies installed"
else
    ok "Dependencies verified"
fi

# --- Launch ----------------------------------------------------------------
printf "\n${BOLD}  Launching Bitcoin Terminal...${RESET}\n\n"
exec python -m bitcoin_terminal "$@"
