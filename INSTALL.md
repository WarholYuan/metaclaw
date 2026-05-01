# Install MetaClaw

MetaClaw is a Python application. The npm package is only a thin installer wrapper so users can install it with either `curl` or `npm`.

## curl

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash
```

Custom repo, branch, and install paths:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash -s -- \
  --repo https://github.com/WarholYuan/metaclaw-installer.git \
  --branch main \
  --dir "$HOME/.metaclaw/src" \
  --workspace "$HOME/.metaclaw/workspace"
```

Install browser support too:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash -s -- --browser
```

## npm

From npm after publishing:

```bash
npx @mianhuatang913/metaclaw
```

From GitHub before npm publishing:

```bash
npx github:WarholYuan/metaclaw-installer
```

Pass installer options after `--`:

```bash
npx @mianhuatang913/metaclaw -- --branch main --browser
```

## Updates

Users can update by running either installer command again:

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash
```

or:

```bash
npx @mianhuatang913/metaclaw
```

The installer also creates a local update command:

```bash
metaclaw-update
```

`metaclaw-update` reuses the saved install settings from `~/.metaclaw/install.env`, pulls the latest Git commit, updates submodules, and reinstalls the Python package into the existing virtual environment.

## After Installation

```bash
metaclaw help
metaclaw start
```

The installer keeps source code and runtime data separate:

```text
~/.metaclaw/src        # Git checkout / source code
~/.metaclaw/venv       # Python virtual environment
~/.metaclaw/workspace  # Agent workspace, config, and runtime data
~/.local/bin/metaclaw  # CLI shim
```

If `metaclaw` is not found after installation, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## What the Installer Does

1. Clones or updates the GitHub repo.
2. Updates submodules.
3. Creates or reuses the Python virtual environment.
4. Installs MetaClaw with `pip install -e`.
5. Creates `metaclaw` and `metaclaw-update` shims in `~/.local/bin`.
6. Writes `config.json` into the workspace and keeps runtime data outside the source checkout.

## Publisher Checklist

Before publishing, replace `WarholYuan/metaclaw-installer` in these files if your GitHub repo path is different:

- `scripts/install.sh`
- `INSTALL.md`
- `package.json`

Publish npm package:

```bash
npm publish --access public
```
