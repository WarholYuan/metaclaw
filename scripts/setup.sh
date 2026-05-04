#!/usr/bin/env bash
set -euo pipefail

# MetaClaw interactive setup wizard
# Helps users configure their first installation

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

CONFIG_FILE="${METACLAW_CONFIG_FILE:-$HOME/.metaclaw/workspace/config.json}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  log_error "Config file not found: $CONFIG_FILE"
  log_info "Please run the installer first:"
  log_info "  curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash"
  exit 1
fi

cat <<BANNER

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🤖 MetaClaw Configuration Wizard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This wizard will help you configure MetaClaw.
Press Ctrl+C at any time to cancel.

BANNER

# Read current config for reference
# shellcheck disable=SC2034
CURRENT_CONFIG=$(cat "$CONFIG_FILE")

# Helper to update JSON config
update_config() {
  local key="$1"
  local value="$2"
  local tmp_file="$CONFIG_FILE.tmp"
  
  # Use Python to safely update JSON
  python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['$key'] = $value
with open('$tmp_file', 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
" && mv "$tmp_file" "$CONFIG_FILE"
}

# Channel selection
log_prompt "Which channel do you want to use?"
echo ""
echo "  1) WeChat (微信) - Default"
echo "  2) Feishu (飞书)"
echo "  3) DingTalk (钉钉)"
echo "  4) QQ"
echo "  5) Terminal (命令行)"
echo ""
read -rp "Select [1-5] (default: 1): " channel_choice

case "${channel_choice:-1}" in
  1) update_config "channel_type" '"weixin"' ;;
  2) update_config "channel_type" '"feishu"' ;;
  3) update_config "channel_type" '"dingtalk"' ;;
  4) update_config "channel_type" '"qq"' ;;
  5) update_config "channel_type" '"terminal"' ;;
  *) update_config "channel_type" '"weixin"' ;;
esac

log_success "Channel configured"

# Model selection
log_prompt "Which AI model do you want to use?"
echo ""
echo "  1) MiniMax-M2.7 (Recommended)"
echo "  2) DeepSeek-V4-Pro"
echo "  3) Claude Sonnet 4.6"
echo "  4) GPT-5.4"
echo "  5) GLM-5.1"
echo "  6) Kimi K2.6"
echo "  7) Qwen 3.6-Plus"
echo ""
read -rp "Select [1-7] (default: 1): " model_choice

case "${model_choice:-1}" in
  1) update_config "model" '"MiniMax-M2.7"' ;;
  2) update_config "model" '"deepseek-v4-pro"' ;;
  3) update_config "model" '"claude-sonnet-4-6"' ;;
  4) update_config "model" '"gpt-5.4"' ;;
  5) update_config "model" '"glm-5.1"' ;;
  6) update_config "model" '"kimi-k2.6"' ;;
  7) update_config "model" '"qwen3.6-plus"' ;;
  *) update_config "model" '"MiniMax-M2.7"' ;;
esac

log_success "Model configured"

# API Key input
log_prompt "Enter your API Key for the selected model:"
read -rsp "API Key (input hidden): " api_key
echo ""

if [[ -n "$api_key" ]]; then
  # Determine which key to set based on model
  case "${model_choice:-1}" in
    1) update_config "minimax_api_key" "\"$api_key\"" ;;
    2) update_config "deepseek_api_key" "\"$api_key\"" ;;
    3) update_config "claude_api_key" "\"$api_key\"" ;;
    4) update_config "open_ai_api_key" "\"$api_key\"" ;;
    5) update_config "zhipu_ai_api_key" "\"$api_key\"" ;;
    6) update_config "moonshot_api_key" "\"$api_key\"" ;;
    7) update_config "dashscope_api_key" "\"$api_key\"" ;;
  esac
  log_success "API Key configured"
else
  log_warn "No API Key provided. You'll need to edit the config file manually."
fi

# Agent mode
log_prompt "Enable Agent mode? (advanced features: memory, skills, tools)"
read -rp "[Y/n] (default: Y): " agent_mode

case "${agent_mode:-Y}" in
  [Yy]*) 
    update_config "agent" "true"
    log_success "Agent mode enabled"
    ;;
  *)
    update_config "agent" "false"
    log_info "Agent mode disabled"
    ;;
esac

# Web console password
log_prompt "Set a password for the Web console? (optional)"
read -rp "Password (leave empty to skip): " web_password

if [[ -n "$web_password" ]]; then
  update_config "web_password" "\"$web_password\""
  log_success "Web console password set"
else
  log_info "No password set. Web console will be open."
fi

# Summary
cat <<SUMMARY

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ Configuration Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 Config file: $CONFIG_FILE

🚀 Next steps:
  metaclaw start     # Start MetaClaw
  metaclaw status    # Check status
  metaclaw logs      # View logs

🌐 Web console:
  http://localhost:9899/chat

💡 To reconfigure, run:
  metaclaw setup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUMMARY
