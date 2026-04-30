#!/usr/bin/env node
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const script = path.resolve(__dirname, '../../scripts/install.sh');
const args = process.argv.slice(2);
if (args[0] === '--') args.shift();
const result = spawnSync('bash', [script, ...args], {
  stdio: 'inherit',
  env: process.env,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
