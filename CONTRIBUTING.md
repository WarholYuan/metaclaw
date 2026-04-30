# Contributing to MetaClaw Installer

Thanks for considering a contribution. This repo is the **installer wrapper** for MetaClaw — a thin layer that clones the application source, sets up a Python venv, and exposes CLI shims. The application itself lives in the [`WarholYuan/metaclaw`](https://github.com/WarholYuan/metaclaw) repo as a git submodule.

## Repo Layout

```
.
├── scripts/install.sh          # core installer (bash)
├── npm/bin/metaclaw-install.js # npm/npx entry point (Node)
├── tests/install.bats          # bats integration tests
├── npm/bin/*.test.mjs          # node:test unit tests
├── skills/                     # custom Claude skills (not part of installer)
├── metaclaw/                   # git submodule → MetaClaw application
└── .github/                    # CI, issue/PR templates, dependabot
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full installer flow.

## Local Development

### Prerequisites

- Node.js >= 18
- Bash >= 4
- `bats-core` for shell tests: `brew install bats-core` (macOS) or `apt install bats` (Debian/Ubuntu)
- `shellcheck` for shell linting: `brew install shellcheck` or `apt install shellcheck`

### Run Tests

```bash
npm test                    # node tests (find-url + npm bin)
npm run test:bats           # bats integration tests
npm run lint:sh             # shellcheck on install.sh
npm run lint:js             # node --check on npm bin
bash -n scripts/install.sh  # bash syntax check
npm pack --dry-run          # verify packed file list
```

### Try the Installer Locally

The installer touches `~/.metaclaw/` and `~/.local/bin/`. To test without polluting your home dir:

```bash
HOME=$(mktemp -d) bash scripts/install.sh --branch main --no-shims
```

## Pull Request Workflow

1. Fork and clone the repo
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes, keeping them minimal and surgical (no unrelated cleanup)
4. Run all the test commands above
5. Update `CHANGELOG.md` under the `[Unreleased]` section if your change is user-facing
6. Push and open a PR using the PR template

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new user-facing feature
- `fix:` bug fix
- `chore:` tooling, config, build
- `docs:` documentation only
- `refactor:` code restructure with no behavior change
- `test:` test-only changes
- `ci:` CI config changes

Breaking changes: append `!` after the type (e.g., `feat!:`) or include `BREAKING CHANGE:` in the commit body.

## Versioning

This project uses [SemVer](https://semver.org/):

- **MAJOR** (1.x → 2.0): breaking change to install path, env vars, shim contracts
- **MINOR** (0.1 → 0.2): new feature, new flag
- **PATCH** (0.1.0 → 0.1.1): bug fix, doc update, internal change

The maintainer bumps the version at release time per [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md). Contributors should not bump versions in PRs.

## Reporting Bugs

Use the [bug report template](https://github.com/WarholYuan/metaclaw-installer/issues/new?template=bug_report.yml). Include OS, shell, install method (curl/npx), and the full command output.

## Reporting Security Issues

Do **not** open a public issue. See [`SECURITY.md`](SECURITY.md).

## Code of Conduct

Be respectful. Disagreements about technical direction are welcome; personal attacks are not.
