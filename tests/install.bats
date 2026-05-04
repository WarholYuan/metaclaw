#!/usr/bin/env bats

setup() {
  export ORIG_PATH="$PATH"
  export TEST_HOME="$(mktemp -d)"
  export HOME="$TEST_HOME"
  export SCRIPT="$BATS_TEST_DIRNAME/../scripts/install.sh"
  mkdir -p "$TEST_HOME/bin"
}

teardown() {
  export PATH="$ORIG_PATH"
  rm -rf "$TEST_HOME"
}

# Build a fake installed source tree with stub git/python so install.sh runs
# end-to-end without touching the network or installing anything real.
prep_stubs() {
  mkdir -p "$TEST_HOME/.metaclaw/src/.git"
  mkdir -p "$TEST_HOME/.metaclaw/src/metaclaw/metaclaw"
  touch "$TEST_HOME/.metaclaw/src/.gitmodules"
  printf '[project]\nname = "metaclaw"\n' \
    > "$TEST_HOME/.metaclaw/src/metaclaw/metaclaw/pyproject.toml"
  printf '{"model": "test-model"}\n' \
    > "$TEST_HOME/.metaclaw/src/metaclaw/metaclaw/config-template.json"

  cat > "$TEST_HOME/bin/git" <<'GIT'
#!/bin/sh
exit 0
GIT
  cat > "$TEST_HOME/bin/python3" <<'PY'
#!/bin/sh
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  printf '#!/bin/sh\n' > "$3/bin/activate"
fi
exit 0
PY
  cat > "$TEST_HOME/bin/python" <<'PY'
#!/bin/sh
exit 0
PY
  cat > "$TEST_HOME/bin/pip" <<'PY'
#!/bin/sh
exit 0
PY
  chmod +x "$TEST_HOME/bin/git" "$TEST_HOME/bin/python3" \
           "$TEST_HOME/bin/python" "$TEST_HOME/bin/pip"
  export PATH="$TEST_HOME/bin:$ORIG_PATH"
}

@test "--help prints usage and exits 0" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"MetaClaw installer"* ]]
  [[ "$output" == *"--branch"* ]]
}

@test "unknown option exits 2 with error" {
  run bash "$SCRIPT" --bogus
  [ "$status" -eq 2 ]
  [[ "$output" == *"Unknown option: --bogus"* ]]
}

@test "exits 1 when git is missing" {
  printf '#!/bin/sh\nexit 0\n' > "$TEST_HOME/bin/python3"
  chmod +x "$TEST_HOME/bin/python3"
  for cmd in bash sh mkdir dirname cat grep chmod; do
    ln -sf "$(command -v $cmd)" "$TEST_HOME/bin/$cmd" 2>/dev/null || true
  done
  export PATH="$TEST_HOME/bin"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Missing required command: git"* ]]
}

@test "exits 1 when python3 is missing" {
  printf '#!/bin/sh\nexit 0\n' > "$TEST_HOME/bin/git"
  chmod +x "$TEST_HOME/bin/git"
  for cmd in bash sh mkdir dirname cat grep chmod; do
    ln -sf "$(command -v $cmd)" "$TEST_HOME/bin/$cmd" 2>/dev/null || true
  done
  export PATH="$TEST_HOME/bin"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Missing required command: python3"* ]]
}

@test "--branch is persisted to install.env" {
  prep_stubs
  export METACLAW_CREATE_SHIMS=0

  run bash "$SCRIPT" --branch develop
  [ "$status" -eq 0 ]
  [ -f "$TEST_HOME/.metaclaw/install.env" ]
  grep -q "METACLAW_BRANCH=develop" "$TEST_HOME/.metaclaw/install.env"
}

@test "install.env safely persists shell-special values" {
  prep_stubs
  export METACLAW_CREATE_SHIMS=0

  run bash "$SCRIPT" --branch "feature/it's ready"
  [ "$status" -eq 0 ]

  # shellcheck disable=SC1091
  source "$TEST_HOME/.metaclaw/install.env"
  [ "$METACLAW_BRANCH" = "feature/it's ready" ]
}

@test "default options are persisted to install.env" {
  prep_stubs
  export METACLAW_CREATE_SHIMS=0

  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "METACLAW_BRANCH=main" "$TEST_HOME/.metaclaw/install.env"
  grep -q "METACLAW_INSTALL_BROWSER=0" "$TEST_HOME/.metaclaw/install.env"
  grep -q "METACLAW_DEV_INSTALL=0" "$TEST_HOME/.metaclaw/install.env"
}

@test "--no-shims prevents shim creation" {
  prep_stubs
  run bash "$SCRIPT" --no-shims
  [ "$status" -eq 0 ]
  [ ! -f "$TEST_HOME/.local/bin/metaclaw" ]
  [ ! -f "$TEST_HOME/.local/bin/metaclaw-update" ]
}

@test "config is created in workspace, not source checkout" {
  prep_stubs
  export METACLAW_CREATE_SHIMS=0

  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$TEST_HOME/.metaclaw/workspace/config.json" ]
  [ ! -f "$TEST_HOME/.metaclaw/src/metaclaw/metaclaw/config.json" ]
  grep -q "test-model" "$TEST_HOME/.metaclaw/workspace/config.json"
}

@test "existing project config is migrated to workspace config" {
  prep_stubs
  export METACLAW_CREATE_SHIMS=0
  printf '{"model": "legacy-model"}\n' \
    > "$TEST_HOME/.metaclaw/src/metaclaw/metaclaw/config.json"

  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$TEST_HOME/.metaclaw/workspace/config.json" ]
  grep -q "legacy-model" "$TEST_HOME/.metaclaw/workspace/config.json"
}

@test "shims are created with executable bit by default" {
  prep_stubs
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -x "$TEST_HOME/.local/bin/metaclaw" ]
  [ -x "$TEST_HOME/.local/bin/metaclaw-update" ]
  grep -q "exec.*venv/bin/metaclaw" "$TEST_HOME/.local/bin/metaclaw"
  grep -q "METACLAW_CONFIG_FILE=.*workspace/config.json" "$TEST_HOME/.local/bin/metaclaw"
  grep -q "install.sh" "$TEST_HOME/.local/bin/metaclaw-update"
}
