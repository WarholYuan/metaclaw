# MetaClaw CLI API Documentation

## Overview

MetaClaw provides a command-line interface (CLI) for managing your AI agent instance.

## Installation

```bash
# Via curl
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash

# Via npm
npx @mianhuatang913/metaclaw

# Via Docker
docker-compose up -d
```

## Commands

### Core Commands

#### `metaclaw help`
Display help information.

```bash
metaclaw help
```

#### `metaclaw start`
Start the MetaClaw service.

```bash
metaclaw start
# Options:
#   --daemon    Run in background
#   --port      Specify port (default: 9899)
```

#### `metaclaw stop`
Stop the MetaClaw service.

```bash
metaclaw stop
```

#### `metaclaw restart`
Restart the MetaClaw service.

```bash
metaclaw restart
```

#### `metaclaw status`
Check service status.

```bash
metaclaw status
```

#### `metaclaw logs`
View service logs.

```bash
metaclaw logs
# Options:
#   --follow    Follow log output
#   --lines     Number of lines to show (default: 100)
```

### Update Commands

#### `metaclaw-update`
Update MetaClaw to the latest version.

```bash
metaclaw-update
# Options:
#   --force     Force update even if already latest
```

### Configuration Commands

#### `metaclaw setup`
Interactive configuration wizard.

```bash
metaclaw setup
# Steps:
# 1. Select channel (WeChat/Feishu/DingTalk/QQ/Terminal)
# 2. Select AI model
# 3. Enter API key
# 4. Enable/disable Agent mode
# 5. Set web console password
```

### Skill Management

#### `metaclaw skill list`
List installed skills.

```bash
metaclaw skill list
```

#### `metaclaw skill install`
Install a skill from the Skill Hub.

```bash
metaclaw skill install <skill-name>
```

#### `metaclaw skill remove`
Remove an installed skill.

```bash
metaclaw skill remove <skill-name>
```

### Knowledge Base

#### `metaclaw knowledge`
Manage knowledge base.

```bash
metaclaw knowledge import <file>
metaclaw knowledge search <query>
metaclaw knowledge export
```

## Configuration File

Location: `~/.metaclaw/workspace/config.json`

### Example Configuration

```json
{
  "channel_type": "weixin",
  "model": "MiniMax-M2.7",
  "minimax_api_key": "your-api-key",
  "agent": true,
  "agent_workspace": "~/metaclaw",
  "web_password": ""
}
```

### Supported Channels

| Channel | Value | Description |
|---------|-------|-------------|
| WeChat | `weixin` | Personal WeChat |
| Feishu | `feishu` | Feishu/Lark |
| DingTalk | `dingtalk` | DingTalk |
| QQ | `qq` | QQ |
| Terminal | `terminal` | Command line |

### Supported Models

| Model | Value | Provider |
|-------|-------|----------|
| MiniMax M2.7 | `MiniMax-M2.7` | MiniMax |
| DeepSeek V4 Pro | `deepseek-v4-pro` | DeepSeek |
| Claude Sonnet | `claude-sonnet-4-6` | Anthropic |
| GPT-5.4 | `gpt-5.4` | OpenAI |
| GLM-5.1 | `glm-5.1` | Zhipu AI |
| Kimi K2.6 | `kimi-k2.6` | Moonshot |
| Qwen 3.6+ | `qwen3.6-plus` | Alibaba |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `METACLAW_CONFIG_FILE` | Path to config file | `~/.metaclaw/workspace/config.json` |
| `METACLAW_REPO_URL` | Installer repository URL | `https://github.com/WarholYuan/metaclaw-installer.git` |
| `METACLAW_BRANCH` | Git branch to install | `main` |
| `METACLAW_INSTALL_DIR` | Source installation directory | `~/.metaclaw/src` |
| `METACLAW_WORKSPACE_DIR` | Workspace directory | `~/.metaclaw/workspace` |
| `METACLAW_VENV_DIR` | Python virtual environment | `~/.metaclaw/venv` |
| `METACLAW_BIN_DIR` | CLI binary directory | `~/.local/bin` |

## Docker Deployment

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Environment Variables for Docker

| Variable | Description |
|----------|-------------|
| `CHANNEL_TYPE` | Channel type (weixin/feishu/dingtalk/qq) |
| `MODEL` | AI model name |
| `API_KEY` | API key for selected model |
| `AGENT_MODE` | Enable agent mode (true/false) |

## Troubleshooting

### Common Issues

1. **Command not found**: Add `~/.local/bin` to PATH
2. **Permission denied**: Ensure scripts are executable
3. **Config not found**: Run `metaclaw setup` first
4. **Update failed**: Check network connection and try `metaclaw-update --force`

### Debug Mode

```bash
# Enable debug logging
export METACLAW_DEBUG=1
metaclaw start
```

## Security

### Script Verification

Verify install script integrity:

```bash
# Download script and checksum
curl -O https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh
curl -O https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh.sha256

# Verify
shasum -a 256 -c install.sh.sha256

# Install
bash install.sh
```

### API Key Security

- Never commit API keys to version control
- Use environment variables or config files
- Rotate keys regularly

## Support

- GitHub Issues: https://github.com/WarholYuan/metaclaw-installer/issues
- Documentation: https://docs.metaclaw.ai/
- Community: https://link-ai.tech/metaclaw/create

## License

MIT License - See LICENSE file for details.
