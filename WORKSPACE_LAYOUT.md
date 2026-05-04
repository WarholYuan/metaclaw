# Workspace and Source Layout

This repository is the public MetaClaw source and installer distribution. Runtime data is intentionally kept out of Git.

## Public Source Area

These paths are versioned and safe to publish:

```text
README.md
INSTALL.md
RELEASE_CHECKLIST.md
scripts/install.sh
npm/bin/metaclaw-install.js
package.json
skills/
metaclaw/metaclaw   # Bundled Python MetaClaw source
```

## Local Workspace Area

These paths are local runtime/user data and are ignored by Git:

```text
data/
knowledge/
memory/
reports/
logs/
tmp/
.claude/
metaclaw/config.json
metaclaw/data/
metaclaw/logs/
```

They may exist on your machine, but they are not part of the public release.

## User Install Layout

The installer creates the same separation on user machines:

```text
~/.metaclaw/src        # Git checkout / source code
~/.metaclaw/venv       # Python virtual environment
~/.metaclaw/workspace  # Runtime workspace and user data
~/.local/bin/metaclaw
~/.local/bin/metaclaw-update
```

## Rule

Do not commit runtime data, credentials, logs, local memory databases, screenshots, generated reports, or personal knowledge files.

If a file is reusable product documentation, put it in `docs/`.
If a file is a reusable skill, put it in `skills/`.
If a file is personal/runtime state, keep it under the local workspace paths above.
