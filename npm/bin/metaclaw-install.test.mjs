import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, writeFileSync, chmodSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const binPath = path.resolve(__dirname, 'metaclaw-install.js');
const realScript = path.resolve(__dirname, '../../scripts/install.sh');

function runWithStubScript(stubBody, args = []) {
  const dir = mkdtempSync(path.join(tmpdir(), 'metaclaw-bin-'));
  const fakeRoot = path.join(dir, 'root');
  const npmDir = path.join(fakeRoot, 'npm', 'bin');
  const scriptsDir = path.join(fakeRoot, 'scripts');
  const stubBin = path.join(npmDir, 'metaclaw-install.js');
  const stubScript = path.join(scriptsDir, 'install.sh');
  const realBin = `${binPath}`;

  spawnSync('mkdir', ['-p', npmDir, scriptsDir]);
  const binSrc = spawnSync('cat', [realBin]).stdout.toString();
  writeFileSync(stubBin, binSrc, { mode: 0o755 });
  writeFileSync(stubScript, stubBody, { mode: 0o755 });

  const result = spawnSync('node', [stubBin, ...args], {
    encoding: 'utf8',
  });
  rmSync(dir, { recursive: true, force: true });
  return result;
}

test('exits 0 and forwards args when script succeeds', () => {
  const stub = `#!/usr/bin/env bash
echo "args=$*"
exit 0
`;
  const result = runWithStubScript(stub, ['hello', 'world']);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /args=hello world/);
});

test('strips a single leading -- separator from argv', () => {
  const stub = `#!/usr/bin/env bash
echo "first=${'$'}1"
exit 0
`;
  const result = runWithStubScript(stub, ['--', '--help']);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /first=--help/);
});

test('does not strip -- when it is not the first arg', () => {
  const stub = `#!/usr/bin/env bash
echo "first=${'$'}1 second=${'$'}2"
exit 0
`;
  const result = runWithStubScript(stub, ['--branch', '--']);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /first=--branch second=--/);
});

test('forwards a non-zero exit code from the script', () => {
  const stub = `#!/usr/bin/env bash
exit 42
`;
  const result = runWithStubScript(stub, []);
  assert.equal(result.status, 42);
});

test('exits non-zero when bash is not found', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'metaclaw-bin-'));
  const result = spawnSync('node', [binPath], {
    encoding: 'utf8',
    env: { ...process.env, PATH: dir },
  });
  rmSync(dir, { recursive: true, force: true });
  assert.ok(result.status !== 0 || result.signal !== null, 'should fail when bash is missing');
});

test('resolves install.sh relative to the bin script', () => {
  const result = spawnSync('node', ['-e', `
    const path = require('node:path');
    const binDir = ${JSON.stringify(path.dirname(binPath))};
    const resolved = path.resolve(binDir, '../../scripts/install.sh');
    process.stdout.write(resolved);
  `], { encoding: 'utf8' });
  assert.equal(result.stdout, realScript);
});
