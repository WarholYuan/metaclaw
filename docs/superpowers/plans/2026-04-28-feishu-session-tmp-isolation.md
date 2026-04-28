# Feishu Session Tmp Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为每个飞书会话创建独立的 `tmp/<hash>/` 子目录，所有临时文件（媒体上传 + agent 中间产物）隔离存储，会话结束时自动清理。

**Architecture:** 在 `_compose_context` 中基于 `session_id` 创建会话 tmp 目录并注入 `context["session_tmp_dir"]`；三个媒体上传方法接收 `tmp_dir` 参数将临时文件写入会话目录；在 `agent_reply` 中将 `session_tmp_dir` 设为 bash/write 工具的 `cwd`，让 agent 产物也落入会话目录；`/new` 命令和超时回调中清理目录。

**Tech Stack:** Python stdlib (`hashlib`, `os`, `shutil`), 无新依赖

---

## 文件清单

| 文件 | 操作 | 职责 |
|---|---|---|
| `common/session_tmp.py` | **新建** | 提供 `get_session_tmp_dir` / `cleanup_session_tmp` 两个公共函数 |
| `tests/test_session_tmp.py` | **新建** | 单元测试 session_tmp 模块 |
| `channel/feishu/feishu_channel.py` | **修改** | `_compose_context` 注入、三个上传方法加 `tmp_dir`、两处清理调用 |
| `bridge/agent_bridge.py` | **修改** | `agent_reply` 中将 `session_tmp_dir` 注入 bash/write 工具 `cwd` |

---

## Task 1: 新建 `common/session_tmp.py`

**Files:**
- Create: `common/session_tmp.py`
- Test: `tests/test_session_tmp.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_session_tmp.py
import os
import shutil
import pytest


def test_get_session_tmp_dir_creates_dir():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_001"
    path = get_session_tmp_dir(session_id)
    try:
        assert os.path.isdir(path)
        assert path.startswith("tmp" + os.sep)
        assert len(os.path.basename(path)) == 8  # sha256前8位
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_same_id_same_path():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_002"
    path1 = get_session_tmp_dir(session_id)
    path2 = get_session_tmp_dir(session_id)
    try:
        assert path1 == path2
    finally:
        cleanup_session_tmp(session_id)


def test_get_session_tmp_dir_different_ids_different_paths():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    path1 = get_session_tmp_dir("user:group_a")
    path2 = get_session_tmp_dir("user:group_b")
    try:
        assert path1 != path2
    finally:
        cleanup_session_tmp("user:group_a")
        cleanup_session_tmp("user:group_b")


def test_cleanup_session_tmp_removes_dir():
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "test_user_003"
    path = get_session_tmp_dir(session_id)
    assert os.path.isdir(path)
    cleanup_session_tmp(session_id)
    assert not os.path.exists(path)


def test_cleanup_session_tmp_nonexistent_is_noop():
    from common.session_tmp import cleanup_session_tmp
    # 不存在的 session，不应抛异常
    cleanup_session_tmp("nonexistent_session_xyz")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_session_tmp.py -v
```

Expected: `ModuleNotFoundError: No module named 'common.session_tmp'`

- [ ] **Step 3: 实现 `common/session_tmp.py`**

```python
import hashlib
import os
import shutil


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

- [ ] **Step 4: 运行测试，确认全部通过**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_session_tmp.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add common/session_tmp.py tests/test_session_tmp.py
git commit -m "feat: add session_tmp utility for per-session tmp dir isolation"
```

---

## Task 2: `feishu_channel.py` — `_compose_context` 注入 `session_tmp_dir`

**Files:**
- Modify: `channel/feishu/feishu_channel.py:1971-2015`

**上下文：** `_compose_context` 末尾（第2015行，`return context` 之前），`context["session_id"]` 此时已设置完毕。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_session_tmp.py  — 追加到文件末尾
def test_session_tmp_dir_no_special_chars():
    """session_id 含冒号（飞书群聊格式）时，目录名应无特殊字符"""
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "ou_abc123:oc_xyz789"
    path = get_session_tmp_dir(session_id)
    try:
        dir_name = os.path.basename(path)
        assert ":" not in dir_name
        assert "/" not in dir_name
    finally:
        cleanup_session_tmp(session_id)
```

- [ ] **Step 2: 运行测试，确认通过（验证 hash 无特殊字符）**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_session_tmp.py::test_session_tmp_dir_no_special_chars -v
```

Expected: PASS

- [ ] **Step 3: 在 `feishu_channel.py` 顶部添加 import**

在文件现有 `from common.xxx` 导入区域找到合适位置添加：

```python
from common.session_tmp import get_session_tmp_dir
```

具体位置：在文件中找到其他 `from common.` 开头的 import，插入其后。

- [ ] **Step 4: 在 `_compose_context` 末尾注入 `session_tmp_dir`**

定位到 `_compose_context` 方法的最后（`return context` 前，约第2015行），在 `return context` 之前插入：

```python
        context["session_tmp_dir"] = get_session_tmp_dir(context["session_id"])
```

修改后该方法末尾应如下：

```python
        elif context.type == ContextType.VOICE:
            # 2.语音请求
            if "desire_rtype" not in context and conf().get("voice_reply_voice"):
                context["desire_rtype"] = ReplyType.VOICE

        context["session_tmp_dir"] = get_session_tmp_dir(context["session_id"])
        return context
```

- [ ] **Step 5: 运行现有测试，确认无回归**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/ -v --ignore=tests/test_process_update.py --ignore=tests/test_release_packaging.py 2>&1 | tail -20
```

Expected: 无新失败

- [ ] **Step 6: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add channel/feishu/feishu_channel.py tests/test_session_tmp.py
git commit -m "feat: inject session_tmp_dir into feishu context"
```

---

## Task 3: `feishu_channel.py` — 媒体上传方法使用 `tmp_dir`

**Files:**
- Modify: `channel/feishu/feishu_channel.py`（三个方法 + 三处调用点）

**背景：** 三个上传方法（`_upload_image_url`, `_upload_video_url`, `_upload_file_url`）目前将临时文件写入当前工作目录。需改为写入 `tmp_dir` 参数指定目录；调用点从 context 传入 `session_tmp_dir`。

### 3a: `_upload_image_url`

- [ ] **Step 1: 修改 `_upload_image_url` 签名和临时文件路径**

将方法签名从：
```python
    def _upload_image_url(self, img_url, access_token):
```
改为：
```python
    def _upload_image_url(self, img_url, access_token, tmp_dir=None):
```

将 HTTP URL 下载分支中的临时文件生成（约第1713行）：
```python
        temp_name = str(uuid.uuid4()) + "." + suffix
        if response.status_code == 200:
            # 将图片内容保存为临时文件
            with open(temp_name, "wb") as file:
                file.write(response.content)
```
改为：
```python
        _dir = tmp_dir or "tmp"
        os.makedirs(_dir, exist_ok=True)
        temp_name = os.path.join(_dir, str(uuid.uuid4()) + "." + suffix)
        if response.status_code == 200:
            # 将图片内容保存为临时文件
            with open(temp_name, "wb") as file:
                file.write(response.content)
```

### 3b: `_upload_video_url`

- [ ] **Step 2: 修改 `_upload_video_url` 签名和临时文件路径**

将方法签名从：
```python
    def _upload_video_url(self, video_url, access_token):
```
改为：
```python
    def _upload_video_url(self, video_url, access_token, tmp_dir=None):
```

将 HTTP URL 下载分支中的临时文件生成（约第1802行）：
```python
                file_name = os.path.basename(video_url) or "video.mp4"
                temp_file = str(uuid.uuid4()) + "_" + file_name

                with open(temp_file, "wb") as file:
```
改为：
```python
                file_name = os.path.basename(video_url) or "video.mp4"
                _dir = tmp_dir or "tmp"
                os.makedirs(_dir, exist_ok=True)
                temp_file = os.path.join(_dir, str(uuid.uuid4()) + "_" + file_name)

                with open(temp_file, "wb") as file:
```

### 3c: `_upload_file_url`

- [ ] **Step 3: 修改 `_upload_file_url` 签名和临时文件路径**

将方法签名从：
```python
    def _upload_file_url(self, file_url, access_token):
```
改为：
```python
    def _upload_file_url(self, file_url, access_token, tmp_dir=None):
```

将 HTTP URL 下载分支中的临时文件生成（约第1936行）：
```python
            file_name = os.path.basename(file_url)
            temp_name = str(uuid.uuid4()) + "_" + file_name

            with open(temp_name, "wb") as file:
```
改为：
```python
            file_name = os.path.basename(file_url)
            _dir = tmp_dir or "tmp"
            os.makedirs(_dir, exist_ok=True)
            temp_name = os.path.join(_dir, str(uuid.uuid4()) + "_" + file_name)

            with open(temp_name, "wb") as file:
```

### 3d: 更新三处调用点

- [ ] **Step 4: 更新 `_send` 方法中对三个上传方法的调用**

定位到约第1582、1605、1619行，将 context 中的 `session_tmp_dir` 传入：

```python
        if reply.type == ReplyType.IMAGE_URL:
            # 图片上传
            reply_content = self._upload_image_url(reply.content, access_token, tmp_dir=context.get("session_tmp_dir"))
```

```python
            if is_video:
                # 视频上传（包含duration信息）
                upload_data = self._upload_video_url(reply.content, access_token, tmp_dir=context.get("session_tmp_dir"))
```

```python
            else:
                # 其他文件使用 file 类型
                file_key = self._upload_file_url(reply.content, access_token, tmp_dir=context.get("session_tmp_dir"))
```

- [ ] **Step 5: 运行测试，确认无回归**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/ -v --ignore=tests/test_process_update.py --ignore=tests/test_release_packaging.py 2>&1 | tail -20
```

Expected: 无新失败

- [ ] **Step 6: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add channel/feishu/feishu_channel.py
git commit -m "feat: route media upload tmp files into session tmp dir"
```

---

## Task 4: `feishu_channel.py` — 清理调用（`/new` 和超时）

**Files:**
- Modify: `channel/feishu/feishu_channel.py:333-365`（`_handle_new_session_message`）
- Modify: `channel/feishu/feishu_channel.py:401-428`（`_on_context_timeout`）

- [ ] **Step 1: 在 `feishu_channel.py` 顶部补充 import**

找到 Task 2 中已添加的 import 行，改为同时导入两个函数：

```python
from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
```

- [ ] **Step 2: 在 `_handle_new_session_message` 末尾调用清理**

定位到该方法末尾（约第365行的 `logger.info(...)` 之后），追加：

```python
        cleanup_session_tmp(session_id)
```

修改后末尾应如下：

```python
        if context:
            self._send_status_card("已清空当前对话上下文。下一条消息会从新的上下文开始。", context, title="已新建会话", template="green")
        logger.info(f"[FeiShu] new session requested, session_id={session_id}")
        cleanup_session_tmp(session_id)
```

- [ ] **Step 3: 在 `_on_context_timeout` 末尾调用清理**

定位到该方法末尾（约第428行的 `logger.warning(...)` 之后），追加：

```python
        cleanup_session_tmp(session_id)
```

修改后末尾应如下：

```python
        if session_id in self._feishu_session_states:
            self._feishu_session_states[session_id]["status"] = "timeout"
        logger.warning(f"[FeiShu] context timeout, session_id={session_id}")
        cleanup_session_tmp(session_id)
```

- [ ] **Step 4: 运行测试，确认无回归**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/ -v --ignore=tests/test_process_update.py --ignore=tests/test_release_packaging.py 2>&1 | tail -20
```

Expected: 无新失败

- [ ] **Step 5: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add channel/feishu/feishu_channel.py
git commit -m "feat: cleanup session tmp dir on /new and context timeout"
```

---

## Task 5: `agent_bridge.py` — 将 `session_tmp_dir` 注入工具 `cwd`

**Files:**
- Modify: `bridge/agent_bridge.py`（`agent_reply` 方法）

**背景：** `Bash` 和 `Write` 工具都有 `self.cwd` 属性（已被 `workspace_dir` 机制使用）。在 `agent_reply` 中，每次调用前将 `session_tmp_dir` 赋给具有 `cwd` 属性的工具，覆盖默认工作目录。这样 bash/write 工具产生的相对路径文件自动落入会话 tmp 目录。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_session_tmp.py — 追加到文件末尾
def test_session_tmp_dir_is_subdir_of_tmp():
    """确认路径格式正确：tmp/<8位hash>"""
    from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
    session_id = "ou_feishu_user_123"
    path = get_session_tmp_dir(session_id)
    try:
        parts = path.replace("\\", "/").split("/")
        assert parts[0] == "tmp"
        assert len(parts) == 2
        assert len(parts[1]) == 8
        assert all(c in "0123456789abcdef" for c in parts[1])
    finally:
        cleanup_session_tmp(session_id)
```

- [ ] **Step 2: 运行测试，确认通过**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_session_tmp.py::test_session_tmp_dir_is_subdir_of_tmp -v
```

Expected: PASS

- [ ] **Step 3: 在 `agent_reply` 中注入 `session_tmp_dir` 到工具 `cwd`**

定位到 `agent_bridge.py` 中的 `agent_reply` 方法。找到 `agent = self.get_agent(session_id=session_id)` 这行（约第382行），在其**之后**插入以下代码块：

```python
            # Inject session_tmp_dir into tool cwd so agent artifacts land in session dir
            session_tmp_dir = context.get("session_tmp_dir") if context else None
            if session_tmp_dir and agent.tools:
                for tool in agent.tools:
                    if hasattr(tool, 'cwd'):
                        tool.cwd = session_tmp_dir
                        if not os.path.exists(session_tmp_dir):
                            os.makedirs(session_tmp_dir, exist_ok=True)
```

同时确认文件顶部已有 `import os`（查看现有 import）。如没有则添加。

- [ ] **Step 4: 运行测试，确认无回归**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/ -v --ignore=tests/test_process_update.py --ignore=tests/test_release_packaging.py 2>&1 | tail -20
```

Expected: 无新失败

- [ ] **Step 5: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add bridge/agent_bridge.py tests/test_session_tmp.py
git commit -m "feat: inject session_tmp_dir as tool cwd in agent_reply"
```

---

## Task 6: 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/ -v --ignore=tests/test_process_update.py --ignore=tests/test_release_packaging.py
```

Expected: 全部通过，包含 `tests/test_session_tmp.py` 的 7 个测试

- [ ] **Step 2: 手动验证 session_tmp 隔离行为**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
python3 -c "
from common.session_tmp import get_session_tmp_dir, cleanup_session_tmp
import os

# 验证两个不同会话目录隔离
p1 = get_session_tmp_dir('ou_user1')
p2 = get_session_tmp_dir('ou_user2')
p3 = get_session_tmp_dir('ou_user1:oc_group')
print('user1 dir:', p1)
print('user2 dir:', p2)
print('user1+group dir:', p3)
assert p1 != p2
assert p1 != p3

# 验证清理
open(os.path.join(p1, 'test.txt'), 'w').write('hello')
cleanup_session_tmp('ou_user1')
assert not os.path.exists(p1)

# 清理其他
cleanup_session_tmp('ou_user2')
cleanup_session_tmp('ou_user1:oc_group')
print('All checks passed.')
"
```

Expected: 打印三个不同路径，最后输出 `All checks passed.`

- [ ] **Step 3: 提交最终**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add -A
git commit -m "test: integration verification for session tmp isolation" --allow-empty
```
