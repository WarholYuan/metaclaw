#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_URL="https://github.com/WarholYuan/metaclaw-installer.git"
REPO_URL="${METACLAW_REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${METACLAW_BRANCH:-main}"
INSTALL_DIR="${METACLAW_INSTALL_DIR:-$HOME/.metaclaw/src}"
WORKSPACE_DIR="${METACLAW_WORKSPACE_DIR:-$HOME/.metaclaw/workspace}"
VENV_DIR="${METACLAW_VENV_DIR:-$HOME/.metaclaw/venv}"
BIN_DIR="${METACLAW_BIN_DIR:-$HOME/.local/bin}"
INSTALL_BROWSER="${METACLAW_INSTALL_BROWSER:-0}"
DEV_INSTALL="${METACLAW_DEV_INSTALL:-0}"
CREATE_SHIMS="${METACLAW_CREATE_SHIMS:-1}"

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
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd python3

mkdir -p "$(dirname "$INSTALL_DIR")" "$WORKSPACE_DIR" "$HOME/.metaclaw"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating MetaClaw source in $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch --tags origin
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  if [[ -e "$INSTALL_DIR" ]]; then
    echo "Install directory exists but is not a git checkout: $INSTALL_DIR" >&2
    exit 1
  fi
  echo "Cloning MetaClaw from $REPO_URL to $INSTALL_DIR"
  git clone --recursive --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

if [[ -f "$INSTALL_DIR/.gitmodules" ]]; then
  git -C "$INSTALL_DIR" submodule update --init --recursive
else
  echo "No .gitmodules found. The repository must include the MetaClaw Python source or a valid submodule mapping." >&2
  exit 1
fi

PROJECT_DIR="$INSTALL_DIR/metaclaw/metaclaw"
if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]]; then
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    PROJECT_DIR="$INSTALL_DIR"
  else
    echo "Could not find MetaClaw Python project under $INSTALL_DIR" >&2
    exit 1
  fi
fi

echo "Creating virtual environment: $VENV_DIR"
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
if [[ "$DEV_INSTALL" == "1" ]]; then
  # shellcheck disable=SC1087
  python -m pip install -e "$PROJECT_DIR[dev]"
else
  python -m pip install -e "$PROJECT_DIR"
fi

CONFIG_FILE="$WORKSPACE_DIR/config.json"
LEGACY_CONFIG_FILE="$PROJECT_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
  if [[ -f "$LEGACY_CONFIG_FILE" ]]; then
    cp "$LEGACY_CONFIG_FILE" "$CONFIG_FILE"
  elif [[ -f "$PROJECT_DIR/config-template.json" ]]; then
    cp "$PROJECT_DIR/config-template.json" "$CONFIG_FILE"
  fi
fi
export METACLAW_CONFIG_FILE="$CONFIG_FILE"

if [[ "$INSTALL_BROWSER" == "1" ]]; then
  metaclaw install-browser
fi

cat > "$HOME/.metaclaw/install.env" <<ENV
METACLAW_REPO_URL='$REPO_URL'
METACLAW_BRANCH='$BRANCH'
METACLAW_INSTALL_DIR='$INSTALL_DIR'
METACLAW_WORKSPACE_DIR='$WORKSPACE_DIR'
METACLAW_VENV_DIR='$VENV_DIR'
METACLAW_BIN_DIR='$BIN_DIR'
METACLAW_INSTALL_BROWSER='$INSTALL_BROWSER'
METACLAW_DEV_INSTALL='$DEV_INSTALL'
METACLAW_CREATE_SHIMS='$CREATE_SHIMS'
ENV

if [[ "$CREATE_SHIMS" == "1" ]]; then
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/metaclaw" <<SHIM
#!/usr/bin/env bash
export METACLAW_CONFIG_FILE="$CONFIG_FILE"
exec "$VENV_DIR/bin/metaclaw" "\$@"
SHIM
  chmod +x "$BIN_DIR/metaclaw"

  cat > "$BIN_DIR/metaclaw-update" <<SHIM
#!/usr/bin/env bash
set -euo pipefail
if [[ -f "\$HOME/.metaclaw/install.env" ]]; then
  # shellcheck disable=SC1091
  source "\$HOME/.metaclaw/install.env"
fi
exec bash "$INSTALL_DIR/scripts/install.sh" "\$@"
SHIM
  chmod +x "$BIN_DIR/metaclaw-update"
fi

cat <<DONE

MetaClaw installed.

Source:    $INSTALL_DIR
Project:   $PROJECT_DIR
Workspace: $WORKSPACE_DIR
Venv:      $VENV_DIR
Bin dir:   $BIN_DIR

Next steps:
  metaclaw help
  metaclaw start
  metaclaw-update

To configure runtime data/workspace, edit:
  $CONFIG_FILE

If 'metaclaw' is not found, add this to your shell profile:
  export PATH="$BIN_DIR:\$PATH"

DONE
