# Contributing to MetaClaw

Thanks for considering a contribution. MetaClaw is a new personal AI agent project with a Python application core and a small release installer for `curl` and `npm` users.

This repository owns the public install path, release workflow, installer tests, documentation, and the application source component used by the installer.

## Repo Layout

```text
.
├── scripts/install.sh          # core installer
├── npm/bin/metaclaw-install.js # npm/npx entry point
├── tests/install.bats          # installer integration tests
├── npm/bin/*.test.mjs          # node:test unit tests
├── skills/                     # development skills, not part of npm payload
├── metaclaw/                   # MetaClaw application source and workspace assets
└── .github/                    # CI, release workflow, issue/PR templates
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full install and update flow.

## Local Development

### Prerequisites

- Node.js >= 18
- Bash >= 4
- `bats-core` for shell tests: `brew install bats-core` on macOS or `apt install bats` on Debian/Ubuntu
- `shellcheck` for shell linting: `brew install shellcheck` or `apt install shellcheck`
- Python supported by the application test matrix

### Run Tests

```bash
npm test
npm run test:bats
npm run lint:sh
npm run lint:js
bash -n scripts/install.sh
npm pack --dry-run
python -m pytest metaclaw/metaclaw/tests -q
```

### Try the Installer Locally

The installer touches `~/.metaclaw/` and `~/.local/bin/`. To test without polluting your home directory:

```bash
HOME=$(mktemp -d) bash scripts/install.sh --branch main --no-shims
```

## Pull Request Workflow

1. Fork and clone the repo.
2. Create a feature branch: `git checkout -b feat/your-feature`.
3. Keep changes focused; avoid unrelated cleanup.
4. Run the relevant tests above.
5. Update `CHANGELOG.md` under `[Unreleased]` if the change is user-facing.
6. Push and open a PR using the PR template.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new user-facing feature
- `fix:` bug fix
- `chore:` tooling, config, build
- `docs:` documentation only
- `refactor:` code restructure with no behavior change
- `test:` test-only changes
- `ci:` CI config changes

Breaking changes: append `!` after the type, such as `feat!:`, or include `BREAKING CHANGE:` in the commit body.

## Versioning

This project uses [SemVer](https://semver.org/) for the published installer package and release tags:

- MAJOR: breaking change to install path, env vars, shim contracts, or release behavior
- MINOR: new feature, new flag, or new supported install surface
- PATCH: bug fix, doc update, or internal maintenance

Application-core versioning may evolve separately while MetaClaw is young. Release notes should call out both installer and application-impacting changes when they differ.

## Reporting Bugs

Use the [bug report template](https://github.com/WarholYuan/MetaClaw/issues/new?template=bug_report.yml). Include OS, shell, install method, and full command output.

## Reporting Security Issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## Code of Conduct

Be respectful. Disagreements about technical direction are welcome; personal attacks are not.
