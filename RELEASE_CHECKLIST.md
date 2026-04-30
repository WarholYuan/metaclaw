# MetaClaw 发布前后清单

这份清单用于把当前仓库发布到 GitHub，并让用户可以通过 `curl` 或 `npx` 安装和更新。

## 0. 版本号 bump 与 CHANGELOG

每次发布前先确定语义化版本（[SemVer](https://semver.org/)）：

- `feat:` 提交 → MINOR（0.1.x → 0.2.0）
- `fix:` / `chore:` / `docs:` 提交 → PATCH（0.1.0 → 0.1.1）
- `feat!:` 或 commit body 含 `BREAKING CHANGE:` → MAJOR（0.x → 1.0.0）

更新这两个文件：

1. `package.json` 的 `version` 字段
2. `CHANGELOG.md`：把 `[Unreleased]` section 的内容移到新版本号下，加日期，再开一个新的空 `[Unreleased]`

提交并打 tag：

```bash
git add package.json CHANGELOG.md
git commit -m "chore: release v$(node -p "require('./package.json').version")"
git tag "v$(node -p "require('./package.json').version")"
```

## 1. 必须先做：轮换密钥

这些密钥曾经出现在本地仓库历史里。虽然当前 Git 历史已经清理过，但安全上必须去对应平台后台重新生成/作废旧密钥。

必须轮换：

- OpenAI API Key
- Moonshot / Kimi API Key
- 飞书 `feishu_app_secret`
- 飞书 `feishu_token`
- 任何曾经写入 `config.json` 或 `.claude/settings*.json` 的 token/password

轮换后，只放在本地忽略文件或环境变量里，不要提交到 Git。

本地私密文件当前应保持被忽略：

```text
.claude/
config.json
metaclaw/config.json
logs/
tmp/
memory/long-term/
data/*.pkl
```

## 2. 确认 GitHub 仓库地址

当前安装器默认地址是：

```text
https://github.com/WarholYuan/metaclaw-installer.git
```

如果你的真实仓库不是这个地址，需要改这些文件：

```text
scripts/install.sh
README.md
INSTALL.md
package.json
```

搜索命令：

```bash
rg "WarholYuan/metaclaw-installer|@mianhuatang913/metaclaw"
```

## 3. 发布 GitHub

如果还没有 remote：

```bash
git remote add origin https://github.com/WarholYuan/metaclaw-installer.git
```

因为历史已经重写过，首次推送或覆盖旧仓库需要 force：

```bash
git push -u origin main --force
```

如果你已经有远端并且确认要覆盖：

```bash
git push origin main --force
```

推送后检查：

```bash
git status
```

应该显示 clean。

## 4. GitHub 发布后验证 curl 安装

在一个临时目录或测试机器上跑：

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash
```

安装成功后验证：

```bash
metaclaw help
metaclaw-update --help
```

如果提示找不到 `metaclaw`，把这个加入 shell 配置：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 5. 发布 npm 包

登录 npm：

```bash
npm login
```

确认包名还可用：

```bash
npm view @mianhuatang913/metaclaw
```

如果显示 404，说明未发布，可以继续。

发布：

```bash
npm publish --access public
```

发布后验证：

```bash
npx @mianhuatang913/metaclaw -- --help
```

真正安装测试：

```bash
npx @mianhuatang913/metaclaw
```

## 6. 用户安装命令

curl：

```bash
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/install.sh | bash
```

npm：

```bash
npx @mianhuatang913/metaclaw
```

GitHub npm 方式，适合 npm 包发布前测试：

```bash
npx github:WarholYuan/metaclaw-installer
```

## 7. 用户更新命令

安装器会创建：

```bash
metaclaw-update
```

用户以后更新直接跑：

```bash
metaclaw-update
```

也可以重复运行安装命令。安装器会：

- 拉取最新 GitHub 代码
- 更新 submodule
- 复用 Python venv
- 重新 `pip install -e`
- 保留用户 workspace 数据

## 8. 当前发布包结构

npm 包只包含安装器，不包含你的工作区数据：

```text
README.md
INSTALL.md
package.json
npm/bin/metaclaw-install.js
scripts/install.sh
```

用户机器上的安装结构：

```text
~/.metaclaw/src        # 源码 checkout
~/.metaclaw/venv       # Python 虚拟环境
~/.metaclaw/workspace  # 用户运行数据
~/.local/bin/metaclaw
~/.local/bin/metaclaw-update
```

## 9. 每次发布前自检命令

```bash
git status --short
bash -n scripts/install.sh
node --check npm/bin/metaclaw-install.js
npm pack --dry-run
node --test skills/web-access/tests/find-url.test.mjs
python3 -m pytest -q
```

密钥扫描：

```bash
git grep -n -E 'sk-[A-Za-z0-9]{20,}|api_key"\\s*:\\s*"[^"]+|app_secret"\\s*:\\s*"[^"]+|token"\\s*:\\s*"[^"]+|password"\\s*:\\s*"[^"]+'
```

如果命中真实密钥，不要发布。

## 10. 已知注意事项

- 当前根仓库使用 submodule 指向 `https://github.com/WarholYuan/metaclaw.git`。
- 如果你希望完全独立维护，后续可以把 submodule 改成你自己的 fork。
- 如果你修改了 submodule 指针，必须确认该 commit 已经 push 到对应远端，否则用户 clone 会失败。
- 历史已经重写过，如果旧远端已有内容，推送需要 `--force`。
- 强烈建议 GitHub 仓库开启 secret scanning / push protection。
