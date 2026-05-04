# MetaClaw

MetaClaw is a personal AI agent project with a Python application core, channel integrations, skills, memory, and a command-line workflow for local deployment.

This repository is the release and installation home for MetaClaw. It gives users a simple `curl` or `npm` entry point, creates an isolated Python environment, installs the MetaClaw CLI, and keeps runtime data outside the source checkout.

## Install

### curl

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash
```

### npm

After the npm package is published:

```bash
npx @mianhuatang913/metaclaw
```

Before npm publishing, install from GitHub:

```bash
npx github:WarholYuan/MetaClaw
```

## Update

Run the generated updater:

```bash
metaclaw-update
```

Or run the installer again:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash
```

The updater pulls the latest MetaClaw release source, updates the application component, and reinstalls the Python package into the existing virtual environment.

## Layout

```text
~/.metaclaw/src        # Source checkout
~/.metaclaw/venv       # Python virtual environment
~/.metaclaw/workspace  # Runtime workspace, config, and user data
~/.local/bin/metaclaw  # CLI shim
```

If `metaclaw` is not found after installation, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Common Commands

```bash
metaclaw help
metaclaw start
metaclaw stop
metaclaw status
metaclaw-update
```

## Custom Install

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/MetaClaw/main/scripts/install.sh | bash -s -- \
  --branch main \
  --dir "$HOME/.metaclaw/src" \
  --workspace "$HOME/.metaclaw/workspace" \
  --browser
```

See [INSTALL.md](INSTALL.md) for full options.
