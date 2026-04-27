---
name: web-access
description:
  联网操作统一策略调度 skill。覆盖搜索、网页抓取、登录后操作、社交媒体抓取、动态页面渲染、批量调研等所有网络任务。
  触发场景：(1) 用户要求搜索信息或查看网页内容，(2) 访问需要登录/交互的网站，(3) 抓取小红书/微博/推特等社交媒体，(4) 读取动态渲染页面，(5) 批量调研多个目标，(6) 任何需要浏览器的网络任务。
  核心能力：工具自动选择（web_fetch / browser / curl / vision）、浏览哲学（目标驱动）、站点经验复用、并行分治策略。
metadata:
  author: metaclaw
  version: "1.0.0"
  requires:
    bins: ["node"]
---

# web-access Skill

## 浏览哲学

**像人一样思考，兼顾高效与适应性完成任务。**

执行任务时不预先规划所有步骤，而是带着目标进入，边看边判断，遇到阻碍就解决，发现内容不够就深入——全程围绕「我要达成什么」做决策。

**① 拿到请求** — 明确用户要做什么，定义成功标准。这是后续所有判断的锚点。

**② 选择起点** — 根据任务性质选一个最可能直达的方式。需要操作页面、登录态、反爬平台（小红书、微信公众号等）→ 直接 browser；已知 URL 且内容静态 → web_fetch。

**③ 过程校验** — 每一步结果都是证据。对照成功标准更新判断：路径在推进吗？方向错了立即调整，不在同一方式上反复重试。遇到弹窗、登录墙，判断是否真的挡住了目标。

**④ 完成判断** — 确认达成成功标准后停止，不为了"完整"而浪费代价。

## 联网工具选择

**一手信息优于二手信息**。搜索引擎是发现入口，多次搜索无质改善时升级到一手来源。

| 场景 | 工具 |
|------|------|
| URL 已知，定向提取页面特定信息 | **web_fetch** |
| URL 已知，需要原始 HTML（meta、JSON-LD 等） | **bash + curl** |
| 非公开内容，反爬平台（小红书、微信公众号等） | **browser** |
| 需要登录态、交互操作、自由导航探索 | **browser** |
| 截图/图片/视频内容需要识别分析 | **vision** |

**Jina AI 预处理**（可选）：在 URL 前加 `https://r.jina.ai/http://` 或 `https://r.jina.ai/https://` 可将网页转为 Markdown，大幅节省 token 但可能有信息损耗。限 20 RPM。适合文章、博客、文档等以正文为核心的页面。

进入 browser 层后，`browser action="evaluate"` 就是你的眼睛和手：
- **看**：用 `evaluate` 查询 DOM，发现链接、按钮、表单、文本内容
- **做**：用 `click` 点击、`fill` 填表、`scroll` 滚动、`press` 按键——像人一样自然导航
- **读**：用 `evaluate` 提取文字内容；图片/视频承载核心信息时，提取媒体 URL 用 vision 分析或 browser screenshot

浏览网页时，**先了解页面结构，再决定下一步动作**。不需要提前规划所有步骤。

## browser 操作指南

metaclaw 的 `browser` 工具是原生 CDP，直接操控浏览器。

### 基本流程

```
1. browser navigate → 打开目标页面
2. browser snapshot → 查看页面结构（获取元素 ref）
3. browser click / fill / scroll → 交互操作
4. browser screenshot → 捕获视觉状态（配合 vision 分析）
5. browser evaluate → 执行 JS 提取数据、操控 DOM
```

### 三种点击方式

| 方式 | 用法 | 适用场景 |
|------|------|---------|
| JS click | `browser action="click" ref=N` | 简单快速，覆盖大多数场景 |
| 真实鼠标 | `browser action="click" ref=N`（browser 内部已处理） | 触发文件对话框、绕过反自动化检测 |
| JS eval | `evaluate` 中执行 `el.click()` | 精确控制、需要前置逻辑时 |

### 页面内导航

- **在当前 tab 点击跳转**：直接用 `click`，适合连续操作（翻页、展开、进入详情）
- **新开 tab 访问**：用 `browser action="navigate" url=...` 打开完整 URL

**站点内交互产生的链接是可靠的**：手动构造的 URL 可能缺失隐式必要参数。

### 媒体资源提取

判断内容在图片里时，用 `evaluate` 从 DOM 直接拿图片 URL，再定向读取——比全页截图精准得多。

```javascript
// 提取页面所有图片 URL
Array.from(document.images).map(img => img.src)

// 提取视频 URL
Array.from(document.querySelectorAll('video')).map(v => v.src || v.currentSrc)
```

### 技术事实

- 页面中存在大量已加载但未展示的内容——轮播非当前帧、折叠区块、懒加载占位等。以数据结构为单位思考，eval 可直接触达。
- DOM 中存在选择器不可跨越的边界（Shadow DOM、iframe）。eval 递归遍历可一次穿透所有层级。
- `/scroll` 到底部会触发懒加载。提取图片 URL 前若未滚动，部分图片可能尚未加载。
- 公开资源可直接 `web_fetch` 下载；需要登录态的才需要在浏览器内 navigate + screenshot。
- 短时间内密集打开大量页面可能触发反爬风控。
- 平台返回的"内容不存在"等提示可能是访问方式问题（URL 缺失参数、触发反爬），而非内容本身问题。

### 视频内容获取

通过 `evaluate` 操控 `<video>` 元素（获取时长、seek 到任意时间点、播放/暂停），配合 `screenshot` + `vision` 采帧分析。

```javascript
// seek 到第 30 秒并暂停
const v = document.querySelector('video');
v.currentTime = 30;
v.pause();
'done';
```

### 登录判断

用户日常 Chrome 天然携带登录态。判断核心：**目标内容拿到了吗？**

打开页面后先尝试获取内容。只有当确认目标无法获取且判断登录能解决时，才告知用户登录。

## 并行调研：分治策略

任务包含多个**独立**调研目标时（如同时调研 N 个项目），合理分治并行处理，而非串行。

**分治判断标准：**

| 适合分治 | 不适合分治 |
|----------|-----------|
| 目标相互独立，结果互不依赖 | 目标有依赖关系 |
| 每个子任务量大（多页抓取、多轮搜索） | 简单单页查询 |
| 需要 browser 或长时间运行的任务 | 几次 web_fetch 就能完成 |

**实现方式**：
1. 将大任务拆分为独立子任务列表
2. 对不互相依赖的子任务，用多个 `browser` 会话或 web_fetch 并行获取
3. 主 agent 只接收摘要结果，原始抓取内容不进入主上下文

## 信息核实类任务

核实的目标是**一手来源**，而非更多二手报道。

| 信息类型 | 一手来源 |
|----------|---------|
| 政策/法规 | 发布机构官网 |
| 企业公告 | 公司官方新闻页 |
| 学术声明 | 原始论文/机构官网 |
| 工具能力/用法 | 官方文档、源码 |

找不到官网时：权威媒体原创报道可作为次级依据，但需声明"未找到官方原文，以下来自[媒体名]报道"。

## 站点经验

按域名存储在 `references/site-patterns/` 下。文件格式：

```markdown
---
domain: example.com
aliases: [示例]
updated: 2026-04-27
---
## 平台特征
架构、反爬行为、登录需求、内容加载方式

## 有效模式
已验证的 URL 模式、操作策略、选择器

## 已知陷阱
什么会失败以及为什么
```

**操作流程**：
1. 确定目标网站后，检查 `references/site-patterns/` 是否有匹配站点，有则读取获取先验知识
2. CDP 操作成功后发现新模式，主动写入对应的站点经验文件
3. 只写经过验证的事实，不写未确认的猜测

## 本地 Chrome 资源检索

用户指向**本人访问过的页面**或**组织内部系统**时，检索本地 Chrome 书签/历史：

```bash
node "<base_dir>/scripts/find-url.mjs" [关键词...] [--only bookmarks|history] [--limit N] [--since 1d|7h|YYYY-MM-DD] [--sort recent|visits]
```

参数说明：
- 关键词空格分词、多词 AND，匹配 title + url
- `--only` 限定数据源，默认两者都查
- `--limit N` 条数上限，默认 20
- `--since` 时间窗（仅历史）：`1d`、`7h`、`YYYY-MM-DD`
- `--sort recent|visits` 历史排序，默认 recent

示例：
```bash
node "<base_dir>/scripts/find-url.mjs" 财务小智
node "<base_dir>/scripts/find-url.mjs" agent skills --since 7d
node "<base_dir>/scripts/find-url.mjs" --since 7d --only history --sort visits
```

⚠️ **使用前提醒**：通过浏览器自动化操作社交平台（如小红书）存在账号被平台限流或封禁的风险。建议使用小号。
