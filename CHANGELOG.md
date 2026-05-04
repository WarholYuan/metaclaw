# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## 0.2.0 (2026-05-01)


### Features

* add CI, tests, and engineering infrastructure ([4bf74c4](https://github.com/WarholYuan/MetaClaw/commit/4bf74c45a672998a534dcdd46a91bf0a11b54bf1))
* add interactive configuration wizard ([fda4bf1](https://github.com/WarholYuan/MetaClaw/commit/fda4bf1692f6b1a5cdd3759e7489a736e713f556))
* add lark-cli skill for Feishu operations ([10b0b94](https://github.com/WarholYuan/MetaClaw/commit/10b0b949f843f4cae7df2a385050f41869e49fd4))
* add uninstall command ([67a9c1e](https://github.com/WarholYuan/MetaClaw/commit/67a9c1e240ef527af68ea9da1daa59553be3246e))
* add update check to metaclaw-update shim ([4af29d1](https://github.com/WarholYuan/MetaClaw/commit/4af29d1e21adbe7b0126ee6ade261ad0e7321903))
* **installer:** add colored output, progress steps, and error handling ([30b74c8](https://github.com/WarholYuan/MetaClaw/commit/30b74c8e0aef5558335ba8b1e2e17d6eb1803b0d))
* **metadoctor:** integrate health monitoring daemon submodule ([660628a](https://github.com/WarholYuan/MetaClaw/commit/660628abaa5123a18393d5736047d3aac95bf902))
* upgrade web-access skill to v2.5 with CDP support ([b8cf0dc](https://github.com/WarholYuan/MetaClaw/commit/b8cf0dc13103c506973e27582ddce617770db767))
* workspace config isolation and CI smoke test ([d936fbf](https://github.com/WarholYuan/MetaClaw/commit/d936fbf9046870b1c265c8c9b114a57c2b79919a))


### Bug Fixes

* expose metaclaw npx bin ([5277f17](https://github.com/WarholYuan/MetaClaw/commit/5277f170eba0187abcc06762166f68e8d255b8db))
* **feishu:** restore display name and bump metaclaw pointer ([c29408d](https://github.com/WarholYuan/MetaClaw/commit/c29408d2100c2177123e6db3c4e017168a7be02a))
* shellcheck SC1087 and bats PATH isolation ([b87b0f5](https://github.com/WarholYuan/MetaClaw/commit/b87b0f5a6341ea7ec61833d9fcc1f1d26085374d))
* support npx argument separator ([0e8cffb](https://github.com/WarholYuan/MetaClaw/commit/0e8cffb6ba9959fca556b9c4053c245a8eae4921))
* **web-access:** restore strict find-url arg validation ([a5bd2ee](https://github.com/WarholYuan/MetaClaw/commit/a5bd2eeee2644f87cc639b96e8626ed2b44cffcb))


### Code Refactoring

* **web-access:** migrate from CDP proxy to metaclaw browser tool ([7ed6d0d](https://github.com/WarholYuan/MetaClaw/commit/7ed6d0d9bf18c6a0408bd5f69e465f30d866b791))


### Documentation

* add implementation plan for personalized welcome dashboard ([5a7ed88](https://github.com/WarholYuan/MetaClaw/commit/5a7ed887ea0e7c1f01058d305b7f497ffe14b8b7))
* add knowledge base index and market analysis ([64a3fc9](https://github.com/WarholYuan/MetaClaw/commit/64a3fc9aed18923a02c4b522987aa1cdc5c12afe))
* add knowledge entries, dream diary, and unified-gateway plan ([0c4c8fa](https://github.com/WarholYuan/MetaClaw/commit/0c4c8faff019d07bbae6be93b6809633f11602bb))
* add personalized welcome dashboard design spec ([f1f6880](https://github.com/WarholYuan/MetaClaw/commit/f1f6880224196877e774a798a168835ba74c0b20))
* add release checklist ([3f2a58a](https://github.com/WarholYuan/MetaClaw/commit/3f2a58a1c8b6c5cc3181e5185f9ecaa3b9ee8bb9))


### CI/CD

* add automated release workflow ([1643539](https://github.com/WarholYuan/MetaClaw/commit/16435398c7d90d7a6c7fbf0078c36c432da1d3fd))
* add macOS to fresh-install smoke test matrix ([e8615a6](https://github.com/WarholYuan/MetaClaw/commit/e8615a69dd8b78d59f4bad46d5907e7d67392031))


### Chores

* add .gitignore with .worktrees ([b973f22](https://github.com/WarholYuan/MetaClaw/commit/b973f2267fd3acba6df1135cc0c972dad5340567))
* add husky pre-commit hooks and ignore coverage ([698af12](https://github.com/WarholYuan/MetaClaw/commit/698af12c914e47ce1b3ba42a6188bd6f4b20e17a))
* add standard-version for automated releases ([f1f1ac4](https://github.com/WarholYuan/MetaClaw/commit/f1f1ac42e8380d0d5d065ee052686fdba4760078))
* add test coverage reporting ([ecc17b1](https://github.com/WarholYuan/MetaClaw/commit/ecc17b1ad10a4d004384ea4e7621588a7624b944))
* **config:** tighten ignores and refresh AGENT/MEMORY content ([c3b2774](https://github.com/WarholYuan/MetaClaw/commit/c3b27741d822fb3f7992388b7a2eecd4f1091ac5))
* enhance pre-commit hooks ([febacb4](https://github.com/WarholYuan/MetaClaw/commit/febacb4a45326ad198a94bf4888cf3099aace79d))
* initial commit before sandbox feature development ([1c057d6](https://github.com/WarholYuan/MetaClaw/commit/1c057d639e71dc27dec19792dcefed0105a4875b))
* prepare public installer release ([7b30044](https://github.com/WarholYuan/MetaClaw/commit/7b300442103e702a025182791c8bee1e817a404e))
* rollback metaclaw submodule to pre-sandbox version (ee35ae3) ([8a0494c](https://github.com/WarholYuan/MetaClaw/commit/8a0494c3bd29484f809eeea8929850c1385ec4e4))
* separate local workspace from public source ([d1a5096](https://github.com/WarholYuan/MetaClaw/commit/d1a5096c540fe4b8518f21cc4b9f435c6d96bf8f))
* target installer repo and npm scope ([4c1e860](https://github.com/WarholYuan/MetaClaw/commit/4c1e8600d67bdc0e2846d363cf1a4a7207767192))
* update .gitignore and core configs ([f2c22b4](https://github.com/WarholYuan/MetaClaw/commit/f2c22b4fb45eb3bf39f745a5a857f097de692b45))
* update metaclaw submodule to latest ([6c43b24](https://github.com/WarholYuan/MetaClaw/commit/6c43b249d8fdd4f5625bf4f424d50ff28529d467))

## [0.1.1] - 2026-04-29

### Fixed

- Expose `metaclaw` binary in npm package bin entries
- Support `--` argument separator when invoked via `npx`

### Changed

- Target installer repository moved to `WarholYuan/MetaClaw`
- npm scope set to `@mianhuatang913/metaclaw`

### Added

- `RELEASE_CHECKLIST.md` covering secret rotation, GitHub push, and npm publish

## [0.1.0] - 2026-04-29

### Added

- Initial public installer release: `scripts/install.sh` with curl/npm entry points
- npm wrapper at `npm/bin/metaclaw-install.js`
- `README.md` and `INSTALL.md` for user-facing install documentation
- Workspace separation: source under `~/.metaclaw/src`, runtime data under `~/.metaclaw/workspace`

[Unreleased]: https://github.com/WarholYuan/MetaClaw/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/WarholYuan/MetaClaw/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/WarholYuan/MetaClaw/releases/tag/v0.1.0
