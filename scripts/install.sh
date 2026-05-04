#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging helpers
log_info() { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error() { echo -e "${RED}✖${NC}  $*" >&2; }

DEFAULT_REPO_URL="https://github.com/WarholYuan/MetaClaw.git"
REPO_URL="${METACLAW_REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${METACLAW_BRANCH:-main}"
INSTALL_DIR="${METACLAW_INSTALL_DIR:-$HOME/.metaclaw/src}"
WORKSPACE_DIR="${METACLAW_WORKSPACE_DIR:-$HOME/.metaclaw/workspace}"
VENV_DIR="${METACLAW_VENV_DIR:-$HOME/.metaclaw/venv}"
BIN_DIR="${METACLAW_BIN_DIR:-$HOME/.local/bin}"
INSTALL_BROWSER="${METACLAW_INSTALL_BROWSER:-0}"
DEV_INSTALL="${METACLAW_DEV_INSTALL:-0}"
CREATE_SHIMS="${METACLAW_CREATE_SHIMS:-1}"

# Error handling
cleanup_on_error() {
  local exit_code=$?
  if [ $exit_code -ne 0 ]; then
    log_error "Installation failed with exit code $exit_code"
    log_info "If you need help, please open an issue at:"
    log_info "  https://github.com/WarholYuan/MetaClaw/issues"
    log_info "Include the following information:"
    log_info "  OS: $(uname -s)"
    log_info "  Shell: $SHELL"
    log_info "  Python: $(python3 --version 2>/dev/null || echo 'not found')"
    log_info "  Git: $(git --version 2>/dev/null || echo 'not found')"
  fi
}
trap cleanup_on_error EXIT

usage() {
  cat <<USAGE
MetaClaw installer

Usage:
  install.sh [options]

Options:
  --repo URL          Git repository URL. Default: $DEFAULT_REPO_URL
  --branch NAME       Git branch/tag to install. Default: main
  --dir PATH          Source checkout directory. Default: ~/.metaclaw/src
  --workspace PATH    Runtime workspace directory. Default: ~/.metaclaw/workspace
  --venv PATH         Python virtualenv directory. Default: ~/.metaclaw/venv
  --bin-dir PATH      Directory for metaclaw/metaclaw-update shims. Default: ~/.local/bin
  --browser           Install browser tool after CLI installation
  --dev               Install Python package with dev extras
  --no-shims          Do not create shell command shims
  -h, --help          Show this help

Environment overrides:
  METACLAW_REPO_URL, METACLAW_BRANCH, METACLAW_INSTALL_DIR,
  METACLAW_WORKSPACE_DIR, METACLAW_VENV_DIR, METACLAW_BIN_DIR,
  METACLAW_INSTALL_BROWSER, METACLAW_DEV_INSTALL, METACLAW_CREATE_SHIMS
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO_URL="${2:?--repo requires a URL}"; shift 2 ;;
    --branch) BRANCH="${2:?--branch requires a name}"; shift 2 ;;
    --dir) INSTALL_DIR="${2:?--dir requires a path}"; shift 2 ;;
    --workspace) WORKSPACE_DIR="${2:?--workspace requires a path}"; shift 2 ;;
    --venv) VENV_DIR="${2:?--venv requires a path}"; shift 2 ;;
    --bin-dir) BIN_DIR="${2:?--bin-dir requires a path}"; shift 2 ;;
    --browser) INSTALL_BROWSER=1; shift ;;
    --dev) DEV_INSTALL=1; shift ;;
    --no-shims) CREATE_SHIMS=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "Missing required command: $1"
    log_info "Please install $1 and try again."
    exit 1
  fi
}

log_info "Checking prerequisites..."
need_cmd git
need_cmd python3
log_success "git and python3 are available"

log_info "Preparing directories..."
mkdir -p "$(dirname "$INSTALL_DIR")" "$WORKSPACE_DIR" "$HOME/.metaclaw"
log_success "Directories ready"

STEP=0
TOTAL_STEPS=7

step() {
  STEP=$((STEP + 1))
  log_info "[$STEP/$TOTAL_STEPS] $*"
}

step "Checking source code..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
  log_info "Updating MetaClaw source in $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch --tags origin
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
  log_success "Source updated"
else
  if [[ -e "$INSTALL_DIR" ]]; then
    log_error "Install directory exists but is not a git checkout: $INSTALL_DIR"
    log_info "Remove it or use --dir to choose a different location"
    exit 1
  fi
  log_info "Cloning MetaClaw from $REPO_URL to $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
  log_success "Source cloned"
fi

step "Checking bundled application source..."
if [[ -f "$INSTALL_DIR/.gitmodules" ]]; then
  git -C "$INSTALL_DIR" submodule update --init --recursive
  log_success "Submodules updated"
elif [[ -f "$INSTALL_DIR/metaclaw/metaclaw/pyproject.toml" || -f "$INSTALL_DIR/pyproject.toml" ]]; then
  log_success "Bundled application source found"
else
  log_error "Could not find bundled MetaClaw Python source."
  exit 1
fi

step "Locating Python project..."
PROJECT_DIR="$INSTALL_DIR/metaclaw/metaclaw"
if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    PROJECT_DIR="$INSTALL_DIR"
  else
    log_error "Could not find MetaClaw Python project under $INSTALL_DIR"
    exit 1
  fi
fi
log_success "Found project at $PROJECT_DIR"

step "Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
log_success "Virtual environment created at $VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log_info "Installing Python dependencies..."
python -m pip install --upgrade pip setuptools wheel
if [[ "$DEV_INSTALL" == "1" ]]; then
  # shellcheck disable=SC1087
  python -m pip install -e "$PROJECT_DIR[dev]"
else
  python -m pip install -e "$PROJECT_DIR"
fi
log_success "Python dependencies installed"

step "Configuring workspace..."
CONFIG_FILE="$WORKSPACE_DIR/config.json"
LEGACY_CONFIG_FILE="$PROJECT_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ -f "$LEGACY_CONFIG_FILE" ]]; then
    cp "$LEGACY_CONFIG_FILE" "$CONFIG_FILE"
    log_success "Migrated legacy config to workspace"
  elif [[ -f "$PROJECT_DIR/config-template.json" ]]; then
    cp "$PROJECT_DIR/config-template.json" "$CONFIG_FILE"
    log_success "Created config from template"
  fi
else
  log_success "Config already exists in workspace"
fi
export METACLAW_CONFIG_FILE="$CONFIG_FILE"

step "Installing optional components..."
if [[ "$INSTALL_BROWSER" == "1" ]]; then
  log_info "Installing browser tool..."
  metaclaw install-browser
  log_success "Browser tool installed"
fi

step "Saving installation settings..."
write_install_env() {
  : > "$HOME/.metaclaw/install.env"
  write_install_env_var() {
    local key="$1"
    local value="$2"
    printf '%s=%q\n' "$key" "$value" >> "$HOME/.metaclaw/install.env"
  }

  write_install_env_var METACLAW_REPO_URL "$REPO_URL"
  write_install_env_var METACLAW_BRANCH "$BRANCH"
  write_install_env_var METACLAW_INSTALL_DIR "$INSTALL_DIR"
  write_install_env_var METACLAW_WORKSPACE_DIR "$WORKSPACE_DIR"
  write_install_env_var METACLAW_VENV_DIR "$VENV_DIR"
  write_install_env_var METACLAW_BIN_DIR "$BIN_DIR"
  write_install_env_var METACLAW_INSTALL_BROWSER "$INSTALL_BROWSER"
  write_install_env_var METACLAW_DEV_INSTALL "$DEV_INSTALL"
  write_install_env_var METACLAW_CREATE_SHIMS "$CREATE_SHIMS"
}
write_install_env
log_success "Settings saved"

step "Creating CLI commands..."
if [[ "$CREATE_SHIMS" == "1" ]]; then
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/metaclaw" <<SHIM
#!/usr/bin/env bash
export METACLAW_CONFIG_FILE="$CONFIG_FILE"
exec "$VENV_DIR/bin/metaclaw" "\$@"
SHIM
  chmod +x "$BIN_DIR/metaclaw"

  cat > "$BIN_DIR/metaclaw-update" <<'SHIM'
#!/usr/bin/env bash
set -euo pipefail
if [[ -f "$HOME/.metaclaw/install.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.metaclaw/install.env"
fi

# Check for updates before running (skip in test environments)
if [[ "${METACLAW_SKIP_UPDATE_CHECK:-0}" != "1" ]]; then
  LATEST_TAG=$(git ls-remote --tags "${METACLAW_REPO_URL:-https://github.com/WarholYuan/MetaClaw.git}" 2>/dev/null | tail -1 | sed 's/.*refs\/tags\///' || echo "")
  CURRENT_VERSION="0.2.0"  # Will be replaced during release

  if [[ -n "${LATEST_TAG:-}" && "$LATEST_TAG" != "v$CURRENT_VERSION" ]]; then
    echo -e "\033[1;33m⚠  New version available: $LATEST_TAG (current: v$CURRENT_VERSION)\033[0m"
    echo "   Run this command to update:"
    echo ""
  fi
fi

exec bash "$INSTALL_DIR/scripts/install.sh" "$@"
SHIM
  chmod +x "$BIN_DIR/metaclaw-update"
  log_success "CLI commands created in $BIN_DIR"
else
  log_warn "Skipped CLI shim creation (--no-shims)"
fi

log_success "Installation complete!"

cat <<DONE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ MetaClaw installed successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Source:    $INSTALL_DIR
📦 Project:   $PROJECT_DIR
💾 Workspace: $WORKSPACE_DIR
🐍 Venv:      $VENV_DIR
🔗 Bin dir:   $BIN_DIR

🚀 Quick start:
  metaclaw help      # Show help
  metaclaw start     # Start MetaClaw
  metaclaw-update    # Update to latest

⚙️  Configuration:
  $CONFIG_FILE

💡 Tip: If 'metaclaw' is not found, add to your shell profile:
  export PATH="$BIN_DIR:\$PATH"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DONE
