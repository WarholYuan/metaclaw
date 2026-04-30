# Changelog

All notable changes to the MetaClaw installer wrapper are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- GitHub Actions CI: shellcheck, syntax checks, node tests on Node 18/20/22, npm pack dry-run, bats tests
- Gitleaks secret scanning workflow
- Dependabot config for npm and github-actions
- Bats integration tests for `scripts/install.sh`
- Node tests for `npm/bin/metaclaw-install.js`
- Issue templates (bug report, feature request) and PR template
- `CONTRIBUTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CHANGELOG.md`
- `.editorconfig` for consistent editor settings
- `package.json` lint and test scripts (`lint:sh`, `lint:js`, `test:bats`)

### Changed

- `.gitignore` extended to ignore `.env`, `*.env.local`, `node_modules/`, `*.tgz`
- `RELEASE_CHECKLIST.md` now includes a SemVer bump step

## [0.1.1] - 2026-04-29

### Fixed

- Expose `metaclaw` binary in npm package bin entries
- Support `--` argument separator when invoked via `npx`

### Changed

- Target installer repository moved to `WarholYuan/metaclaw-installer`
- npm scope set to `@mianhuatang913/metaclaw`

### Added

- `RELEASE_CHECKLIST.md` covering secret rotation, GitHub push, and npm publish

## [0.1.0] - 2026-04-29

### Added

- Initial public installer release: `scripts/install.sh` with curl/npm entry points
- npm wrapper at `npm/bin/metaclaw-install.js`
- `README.md` and `INSTALL.md` for user-facing install documentation
- Workspace separation: source under `~/.metaclaw/src`, runtime data under `~/.metaclaw/workspace`

[Unreleased]: https://github.com/WarholYuan/metaclaw-installer/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/WarholYuan/metaclaw-installer/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/WarholYuan/metaclaw-installer/releases/tag/v0.1.0
