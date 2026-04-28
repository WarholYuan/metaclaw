# 飞书会话 tmp 目录隔离设计

**日期**：2026-04-28  
**状态**：待实现

---

## 背景

当前 `tmp/` 目录下所有飞书会话的临时文件（音频、图片、视频、agent 中间产物）全部混在一起，存在以下问题：

- 不同用户/群聊的文件互相干扰，存在数据泄漏风险
- Agent 执行任务产生的中间文件无法追踪归属
- 没有自动清理机制，文件长期堆积

---

## 目标

1. 每个飞书会话（私聊用户或群聊）有独立的 `tmp/<hash>/` 子目录
2. 所有临时文件（媒体上传、agent 产物）统一写入该目录
3. 会话结束（`/new` 命令或超时）时自动清理对应目录

---

## 方案：Context 注入 `session_tmp_dir`

在 `_compose_context` 时注入 `session_tmp_dir` 字段，整个请求链路统一从 context 取路径。

---

## 设计细节

### 1. `common/session_tmp.py`（新文件）

提供两个公共函数：

```python
import hashlib, os, shutil

def _session_dir(session_id: str) -> str:
    h = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return os.path.join("tmp", h)

def get_session_tmp_dir(session_id: str) -> str:
    """创建并返回会话专属 tmp 目录路径。"""
    path = _session_dir(session_id)
    os.makedirs(path, exist_ok=True)
    return path

def cleanup_session_tmp(session_id: str):
    """删除会话 tmp 目录及其所有内容。"""
    path = _session_dir(session_id)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
```

**目录命名**：`tmp/<session_id 的前8位 sha256>/`，避免飞书 open_id 中的特殊字符（如 `:`），同时保持可追踪性。

### 2. `feishu_channel.py` — `_compose_context` 注入

在 `_compose_context` 方法末尾，基于 `context["session_id"]` 创建目录并注入：

```python
from common.session_tmp import get_session_tmp_dir
context["session_tmp_dir"] = get_session_tmp_dir(context["session_id"])
```

### 3. `feishu_channel.py` — 媒体上传改动

`_upload_image_url`、`_upload_video_url`、`_upload_file_url` 三个方法增加可选参数 `tmp_dir: str = None`：

- 下载/生成临时文件时，路径改为 `os.path.join(tmp_dir, filename)` 而非当前目录
- 调用方从 context 传入 `context.get("session_tmp_dir")` 或 fallback 到 `"tmp"`

### 4. `feishu_channel.py` — 清理时机

在两处调用 `cleanup_session_tmp(session_id)`：

| 触发点 | 位置 |
|---|---|
| 用户发送 `/new` | `_handle_new_session_message` 末尾 |
| 请求超时 | `_on_context_timeout` 末尾 |

### 5. Agent 工具集成

**`agent/tools/bash.py`**：
- 若 context 有 `session_tmp_dir`，将其作为 bash 命令的 `cwd`（工作目录）
- agent 在 bash 中产生的相对路径文件自动落入会话目录

**`agent/tools/write.py`**：
- 若 `file_path` 是相对路径，且 context 有 `session_tmp_dir`，以 `session_tmp_dir` 为基准解析

**其他工具**（`read`、`edit` 等）：不改动，操作用户指定路径，不强制重定向。

---

## 兼容性

- `session_tmp_dir` 不存在时（非飞书 channel 或旧代码路径），工具行为完全不变
- bash 的 `cwd` 只影响相对路径命令，绝对路径不受影响
- 现有 `tmp/` 目录下已有文件不受影响

---

## 涉及文件清单

| 文件 | 变更类型 |
|---|---|
| `common/session_tmp.py` | 新增 |
| `channel/feishu/feishu_channel.py` | 修改（`_compose_context`、3个上传方法、2个清理点） |
| `agent/tools/bash.py` | 修改（注入 `cwd`） |
| `agent/tools/write.py` | 修改（相对路径基准） |

---

## 不在范围内

- 非飞书 channel（微信、钉钉等）的隔离
- 手动/外部清理机制
- `tmp_dir` 可配置化（config.json）
