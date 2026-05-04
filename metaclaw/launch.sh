#!/bin/bash
# MetaClaw launch wrapper — ensures full user PATH is available
# even when started from macOS launchd (which has a minimal PATH).

# Load nvm (Node.js version manager)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Homebrew
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)" || true

# User local bins
export PATH="$HOME/.local/bin:$HOME/.local/node/bin:/usr/local/bin:$PATH"

exec python3 "$HOME/MetaClaw/metaclaw/metaclaw/app.py"
