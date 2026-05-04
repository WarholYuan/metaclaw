# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅        |
| < 0.2   | ❌        |

Only the latest 0.2.x is supported. When 1.0 ships, this table will be updated.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Use one of these channels:

1. **GitHub Security Advisories (preferred)** — Open a private advisory at:
   https://github.com/WarholYuan/MetaClaw/security/advisories/new

2. **Email** — Contact the maintainer via the email listed on their GitHub profile.

Include:

- Description of the issue and potential impact
- Steps to reproduce
- Affected versions
- Any suggested fix or mitigation

You should receive an acknowledgement within 7 days. We aim to publish a fix within 30 days for high-severity issues.

## Scope

In scope:

- `scripts/install.sh` — bash injection, path traversal, privilege escalation
- `npm/bin/metaclaw-install.js` — argument injection, prototype pollution
- The npm package contents (anything in `package.json#files`)
- Generated CLI shims under `~/.local/bin/`
- MetaClaw application code and configuration handling in this repository

Out of scope (report upstream):

- Vulnerabilities in third-party dependencies pulled by `pip install` → upstream maintainers
- User misconfiguration of `config.json`

## Hardening Notes

The installer is designed to:

- Run with the user's existing shell privileges, not as root
- Refuse to overwrite a non-git directory at `$INSTALL_DIR`
- Validate required commands (`git`, `python3`) before any filesystem changes
- Use `set -euo pipefail` so failures abort early
- Save the original install flags to `~/.metaclaw/install.env` for reproducible updates

If you find a way to bypass any of these, please report it.

## Secret Rotation After a Leak

If credentials were accidentally committed to this repo, see step 1 of [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for the rotation procedure: rotate the secret at the provider first, **then** scrub git history.
