#!/usr/bin/env bash
set -euo pipefail

# MetaClaw uninstaller
# Removes all installed files and data

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error() { echo -e "${RED}✖${NC}  $*" >&2; }
log_prompt() { echo -e "${CYAN}?${NC}  $*"; }

# Load install settings if available
if [[ -f "$HOME/.metaclaw/install.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.metaclaw/install.env"
fi

INSTALL_DIR="${METACLAW_INSTALL_DIR:-$HOME/.metaclaw/src}"
WORKSPACE_DIR="${METACLAW_WORKSPACE_DIR:-$HOME/.metaclaw/workspace}"
VENV_DIR="${METACLAW_VENV_DIR:-$HOME/.metaclaw/venv}"
BIN_DIR="${METACLAW_BIN_DIR:-$HOME/.local/bin}"

cat <<BANNER

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🗑️  MetaClaw Uninstaller
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This will remove the following:

  📁 Source code:    $INSTALL_DIR
  💾 Workspace data: $WORKSPACE_DIR
  🐍 Virtual env:    $VENV_DIR
  🔗 CLI commands:   $BIN_DIR/metaclaw
                    $BIN_DIR/metaclaw-update
  ⚙️  Settings:      $HOME/.metaclaw/install.env

BANNER

log_warn "Your workspace data (config, memory, skills) will be deleted!"
log_prompt "Do you want to backup workspace data before uninstalling?"
read -rp "[Y/n] (default: Y): " backup_choice

case "${backup_choice:-Y}" in
  [Yy]*)
    BACKUP_DIR="$HOME/.metaclaw-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    if [[ -d "$WORKSPACE_DIR" ]]; then
      cp -r "$WORKSPACE_DIR" "$BACKUP_DIR/"
      log_success "Workspace backed up to: $BACKUP_DIR/workspace"
    fi
    if [[ -f "$HOME/.metaclaw/install.env" ]]; then
      cp "$HOME/.metaclaw/install.env" "$BACKUP_DIR/"
    fi
    ;;
  *)
    log_info "Skipping backup"
    ;;
esac

log_prompt "Are you sure you want to uninstall MetaClaw?"
read -rp "Type 'yes' to confirm: " confirm

if [[ "$confirm" != "yes" ]]; then
  log_info "Uninstall cancelled."
  exit 0
fi

log_info "Uninstalling MetaClaw..."

# Remove CLI shims
if [[ -f "$BIN_DIR/metaclaw" ]]; then
  rm -f "$BIN_DIR/metaclaw"
  log_success "Removed $BIN_DIR/metaclaw"
fi

if [[ -f "$BIN_DIR/metaclaw-update" ]]; then
  rm -f "$BIN_DIR/metaclaw-update"
  log_success "Removed $BIN_DIR/metaclaw-update"
fi

# Remove virtual environment
if [[ -d "$VENV_DIR" ]]; then
  rm -rf "$VENV_DIR"
  log_success "Removed $VENV_DIR"
fi

# Remove source code
if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  log_success "Removed $INSTALL_DIR"
fi

# Remove workspace data
if [[ -d "$WORKSPACE_DIR" ]]; then
  rm -rf "$WORKSPACE_DIR"
  log_success "Removed $WORKSPACE_DIR"
fi

# Remove install.env
if [[ -f "$HOME/.metaclaw/install.env" ]]; then
  rm -f "$HOME/.metaclaw/install.env"
  log_success "Removed $HOME/.metaclaw/install.env"
fi

# Remove .metaclaw directory if empty
if [[ -d "$HOME/.metaclaw" ]] && [[ -z "$(ls -A "$HOME/.metaclaw" 2>/dev/null)" ]]; then
  rmdir "$HOME/.metaclaw"
  log_success "Removed empty $HOME/.metaclaw directory"
fi

cat <<DONE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ MetaClaw Uninstalled
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MetaClaw has been removed from your system.

DONE

if [[ -n "${BACKUP_DIR:-}" ]]; then
  log_info "Your data was backed up to:"
  log_info "  $BACKUP_DIR"
fi

log_info "To reinstall, run:"
log_info "  curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash"

echo ""
