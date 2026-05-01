# Architecture

This document explains how the MetaClaw installer wrapper is structured and what it does at install time. For end-user install instructions see [`README.md`](README.md) and [`INSTALL.md`](INSTALL.md).

## Two-Repo Model

```
┌──────────────────────────────────────────┐
│ metaclaw-installer (this repo)           │
│   scripts/install.sh                     │
│   npm/bin/metaclaw-install.js            │
│   metaclaw/  ──► submodule               │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ WarholYuan/metaclaw (upstream app)       │
│   Python application: channels, plugins, │
│   bridges, agents, CLI                   │
└──────────────────────────────────────────┘
```

The installer repo is published to npm as `@mianhuatang913/metaclaw` and to GitHub as `WarholYuan/metaclaw-installer`. The application repo is pulled in as a git submodule at `metaclaw/metaclaw/`.

This split keeps installer changes (bash, packaging, CLI shims) decoupled from application changes (Python features, channel integrations).

## Install Flow

Both `curl | bash` and `npx @mianhuatang913/metaclaw` end up running `scripts/install.sh`.

```
User
 │
 ├── curl ──► raw.githubusercontent.com/.../install.sh ──► bash
 │                                                          │
 ├── npx ──► npm/bin/metaclaw-install.js ──► spawn bash ────┤
 │                                                          │
 │                                                          ▼
 │                                                   scripts/install.sh
 │                                                          │
 │                                                          ▼
 │                              ┌──────────────────────────────────┐
 │                              │ 1. Parse flags / env overrides   │
 │                              │ 2. Check git, python3 present    │
 │                              │ 3. Clone or update source        │
 │                              │ 4. Update submodule              │
 │                              │ 5. Create Python venv            │
 │                              │ 6. pip install -e the app        │
 │                              │ 7. Create workspace config       │
 │                              │ 8. (Optional) install browser    │
 │                              │ 9. Save install.env              │
 │                              │ 10. Create CLI shims             │
 │                              └──────────────────────────────────┘
 │                                                          │
 ▼                                                          ▼
~/.metaclaw/                                       ~/.local/bin/
├── src/        (source checkout w/ submodule)     ├── metaclaw
├── venv/       (Python virtualenv)                └── metaclaw-update
├── workspace/  (config, runtime data, user state)
└── install.env (saved install settings)
```

## Key Files

| File | Purpose |
|---|---|
| `scripts/install.sh` | The installer. ~175 lines of bash. All logic lives here. |
| `npm/bin/metaclaw-install.js` | ~17-line Node wrapper that resolves the bash script path and spawns it with inherited stdio. Strips a leading `--` from argv (npx convention). |
| `package.json` | npm metadata. The `files` field controls what gets shipped — only `npm/bin/`, `scripts/`, and the two README files. |
| `metaclaw/` (submodule) | Pinned at a specific commit of `WarholYuan/metaclaw`. Updated via `git submodule update`. |

## Update Flow

The installer creates `~/.local/bin/metaclaw-update` which:

1. Sources `~/.metaclaw/install.env` to recover the original install flags
2. Re-runs `scripts/install.sh` with those flags
3. The script's "update existing checkout" branch does `git fetch && git pull --ff-only && submodule update --init --recursive`, then re-runs `pip install -e`

User workspace data under `~/.metaclaw/workspace/` is preserved by the updater. If `config.json` already exists there, the installer leaves it unchanged.

## Skills

The `skills/` directory contains custom Claude skills used during MetaClaw development. They are **not** part of the installer payload — `package.json#files` does not include `skills/`, so they don't ship to npm. They are kept in the repo only for the project's own development workflow.

See `skills/skills_config.json` for the skill registry and each `skills/<name>/SKILL.md` for individual skill specs.

## Testing Strategy

Three layers, all run in CI:

1. **Static checks** — `bash -n`, `node --check`, `shellcheck`, `npm pack --dry-run`
2. **Unit tests** — `node --test` for JS (`npm/bin/*.test.mjs`), small `node --test` cases for skill utilities (`skills/web-access/tests/`)
3. **Integration tests** — `bats` for the bash installer (`tests/install.bats`), using stub `git`/`python3` binaries on PATH and a temporary `$HOME`

CI also runs a fresh-install smoke test from a temporary HOME and verifies the installed CLI starts.

## Security Boundary

- No secrets in this repo. `.gitignore` excludes `.claude/`, `config.json`, `.env`, `metaclaw/config.json`.
- The installer does not require any credentials. It only clones a public repo and runs `pip install`.
- Application-level secrets (API keys, Feishu tokens) are configured by the user post-install in `~/.metaclaw/workspace/config.json`.
- `gitleaks` runs in CI on every push and weekly to catch accidental secret commits.

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting.
