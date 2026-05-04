# Architecture

This document explains how MetaClaw is packaged, installed, and updated. For end-user install instructions see [README.md](README.md) and [INSTALL.md](INSTALL.md).

## Repository Model

MetaClaw is now published as a single repository:

```text
MetaClaw repository
├── scripts/install.sh              # curl installer
├── npm/bin/metaclaw-install.js     # npx entry point
├── tests/                          # installer integration tests
├── skills/                         # development skills, not npm payload
└── metaclaw/metaclaw/              # Python application source
```

The npm package is published as `@mianhuatang913/metaclaw`. The package stays small: it ships the bootstrapper that retrieves this repository, prepares a Python virtual environment, installs the bundled Python application, and creates local CLI shims.

This keeps the end-user install command small while the public GitHub repository remains complete and cloneable without extra private dependencies.

## Install Flow

Both `curl | bash` and `npx @mianhuatang913/metaclaw` end up running `scripts/install.sh`.

```text
User
 |
 |-- curl --> raw.githubusercontent.com/.../install.sh --> bash
 |
 |-- npx  --> npm/bin/metaclaw-install.js --> bash
 |
 v
scripts/install.sh
 |
 |-- parse flags and environment overrides
 |-- check git and python3
 |-- clone or update MetaClaw source
 |-- verify bundled Python application source
 |-- create Python virtual environment
 |-- pip install -e the application
 |-- create workspace config
 |-- optionally install browser support
 |-- save install.env
 |-- create metaclaw and metaclaw-update shims
 v
~/.metaclaw/ and ~/.local/bin/
```

Installed layout:

```text
~/.metaclaw/
├── src/        # source checkout
├── venv/       # Python virtual environment
├── workspace/  # config, runtime data, user state
└── install.env # saved install settings

~/.local/bin/
├── metaclaw
└── metaclaw-update
```

## Key Files

| File | Purpose |
|---|---|
| `scripts/install.sh` | Main installer used by curl, npm, updater, and smoke tests. |
| `npm/bin/metaclaw-install.js` | Node entry point for `npx`; resolves the bash script path and forwards arguments. |
| `package.json` | npm metadata. The `files` field keeps the published package intentionally small. |
| `metaclaw/metaclaw/` | Python application source installed into the virtual environment. |
| `tests/install.bats` | End-to-end installer tests using temporary HOME and stubbed external commands. |

## Update Flow

The installer creates `~/.local/bin/metaclaw-update`, which:

1. Sources `~/.metaclaw/install.env` to recover the original install settings.
2. Re-runs `scripts/install.sh` with those settings.
3. Updates the source checkout and re-runs `pip install -e`.

User workspace data under `~/.metaclaw/workspace/` is preserved by the updater. If `config.json` already exists there, the installer leaves it unchanged.

## Skills

The root `skills/` directory contains development skills used while building MetaClaw. They are not part of the npm payload because `package.json#files` does not include `skills/`.

Runtime skills that belong to the Python application live under the bundled application source.

## Testing Strategy

These layers are covered locally and in CI:

1. Static checks: `bash -n`, `node --check`, `shellcheck`, `npm pack --dry-run`.
2. Node tests: `node --test` for npm entry points.
3. Installer integration tests: `bats tests/install.bats`.
4. Python tests: `pytest metaclaw/metaclaw/tests`.
5. Fresh install smoke tests from a temporary HOME on Linux and macOS.

## Security Boundary

- No secrets belong in the repository. `.gitignore` excludes `.claude/`, `config.json`, `.env`, runtime logs, and local data.
- The installer does not require credentials. It only clones public source and runs `pip install`.
- Application secrets such as API keys and Feishu tokens are configured by the user after install in `~/.metaclaw/workspace/config.json`.
- Secret scanning runs in CI on every push, pull request, and weekly schedule.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.
