# 统一消息网关（Gateway 抽象层）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MetaClaw 的 `metaclaw/metaclaw/` 目录下新增 `gateway/` 模块，提供 `Gateway` 单例，让定时任务、子代理等任意代码都能通过 `Gateway().send_text(platform, session_id, text)` 向任意已运行的平台 channel 发送消息，同时对现有 channel 代码零改动。

**Architecture:** 新增 `gateway/` 模块（4 个文件），Gateway 作为单例维护 `{platform -> channel}` 注册表。`ChannelManager._run_channel()` 在 channel 启动后调用 `Gateway().register()`，停止时调用 `Gateway().unregister()`。`Gateway.send()` 内部构造 `Reply` 和最小化 `Context`，直接调用目标 channel 的 `send()` 方法。

**Tech Stack:** Python 3.7+，threading.RLock，现有 `bridge.reply.Reply` 和 `bridge.context.Context`，现有 `common.singleton` 装饰器，pytest

---

## 文件改动清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `metaclaw/metaclaw/gateway/__init__.py` | 导出 Gateway 和 OutboundMessage |
| 新建 | `metaclaw/metaclaw/gateway/message.py` | OutboundMessage 数据类 |
| 新建 | `metaclaw/metaclaw/gateway/exceptions.py` | GatewayError、PlatformNotRegisteredError |
| 新建 | `metaclaw/metaclaw/gateway/gateway.py` | Gateway 单例核心逻辑 |
| 新建 | `metaclaw/metaclaw/tests/test_gateway.py` | 全量测试 |
| 微改 | `metaclaw/metaclaw/app.py` | `_run_channel` 启动后注册，`stop` 后注销（共 +8 行） |

---

## Task 1：新建 gateway/exceptions.py

**Files:**
- Create: `metaclaw/metaclaw/gateway/exceptions.py`

- [ ] **Step 1: 创建异常文件**

```python
# metaclaw/metaclaw/gateway/exceptions.py


class GatewayError(Exception):
    """统一网关基础异常"""


class PlatformNotRegisteredError(GatewayError):
    """目标平台尚未注册到 Gateway"""

    def __init__(self, platform: str):
        self.platform = platform
        super().__init__(f"Platform '{platform}' is not registered in Gateway")
```

- [ ] **Step 2: 提交**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
git add gateway/exceptions.py
git commit -m "feat(gateway): add gateway exception types"
```

---

## Task 2：新建 gateway/message.py

**Files:**
- Create: `metaclaw/metaclaw/gateway/message.py`

- [ ] **Step 1: 创建 OutboundMessage 数据类**

```python
# metaclaw/metaclaw/gateway/message.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from bridge.reply import ReplyType


@dataclass
class OutboundMessage:
    """发往某平台某会话的出站消息。"""
    platform: str           # 目标平台，如 "feishu" / "weixin" / "terminal"
    session_id: str         # 接收方 ID（用户 ID 或群 ID）
    content: str            # 消息正文
    reply_type: ReplyType = ReplyType.TEXT
    extra: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: 提交**

```bash
git add gateway/message.py
git commit -m "feat(gateway): add OutboundMessage dataclass"
```

---

## Task 3：新建 gateway/gateway.py

**Files:**
- Create: `metaclaw/metaclaw/gateway/gateway.py`

- [ ] **Step 1: 写失败测试（先跑，确认 import 报错）**

```bash
# 在 tests/ 目录下临时运行，预期 ImportError
python -c "from gateway.gateway import Gateway; print('ok')"
```

预期输出：`ModuleNotFoundError: No module named 'gateway'`

- [ ] **Step 2: 创建 gateway/gateway.py**

```python
# metaclaw/metaclaw/gateway/gateway.py
import threading
from typing import Dict, Optional

from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.singleton import singleton

from gateway.exceptions import PlatformNotRegisteredError
from gateway.message import OutboundMessage


@singleton
class Gateway:
    """统一消息网关单例。

    channel 启动后通过 register() 注册；停止时通过 unregister() 注销。
    其他模块通过 send() / send_text() 向任意已注册平台发送消息。
    """

    def __init__(self):
        self._channels: Dict[str, object] = {}  # platform -> channel instance
        self._lock = threading.RLock()

    def register(self, platform: str, channel) -> None:
        """注册一个已启动的 channel。"""
        with self._lock:
            self._channels[platform] = channel
        logger.info(f"[Gateway] Platform '{platform}' registered")

    def unregister(self, platform: str) -> None:
        """注销一个 channel（channel 停止时调用）。"""
        with self._lock:
            removed = self._channels.pop(platform, None)
        if removed is not None:
            logger.info(f"[Gateway] Platform '{platform}' unregistered")

    def list_platforms(self) -> list:
        """返回当前已注册的平台名称列表。"""
        with self._lock:
            return list(self._channels.keys())

    def send(self, msg: OutboundMessage) -> bool:
        """发送出站消息到指定平台。

        Returns:
            True  — 调用 channel.send() 成功
            False — 平台未注册或发送异常
        """
        with self._lock:
            channel = self._channels.get(msg.platform)

        if channel is None:
            raise PlatformNotRegisteredError(msg.platform)

        reply = Reply(msg.reply_type, msg.content)
        context = Context(ContextType.TEXT, msg.content)
        context["session_id"] = msg.session_id
        context["receiver"] = msg.session_id
        context["channel_type"] = msg.platform

        try:
            channel.send(reply, context)
            logger.debug(f"[Gateway] Sent to {msg.platform}/{msg.session_id}: {msg.content[:50]}")
            return True
        except Exception as e:
            logger.error(f"[Gateway] Failed to send to {msg.platform}/{msg.session_id}: {e}")
            return False

    def send_text(self, platform: str, session_id: str, text: str) -> bool:
        """快捷方法：发送纯文本消息。"""
        return self.send(OutboundMessage(
            platform=platform,
            session_id=session_id,
            content=text,
            reply_type=ReplyType.TEXT,
        ))
```

- [ ] **Step 3: 验证 import 成功**

```bash
python -c "from gateway.gateway import Gateway; print('ok')"
```

预期输出：`ok`

- [ ] **Step 4: 提交**

```bash
git add gateway/gateway.py
git commit -m "feat(gateway): implement Gateway singleton with register/send/send_text"
```

---

## Task 4：新建 gateway/\_\_init\_\_.py

**Files:**
- Create: `metaclaw/metaclaw/gateway/__init__.py`

- [ ] **Step 1: 创建 \_\_init\_\_.py**

```python
# metaclaw/metaclaw/gateway/__init__.py
from gateway.gateway import Gateway
from gateway.message import OutboundMessage
from gateway.exceptions import GatewayError, PlatformNotRegisteredError

__all__ = ["Gateway", "OutboundMessage", "GatewayError", "PlatformNotRegisteredError"]
```

- [ ] **Step 2: 验证顶层 import**

```bash
python -c "from gateway import Gateway, OutboundMessage; print('ok')"
```

预期输出：`ok`

- [ ] **Step 3: 提交**

```bash
git add gateway/__init__.py
git commit -m "feat(gateway): export public API from gateway package"
```

---

## Task 5：编写测试 test_gateway.py

**Files:**
- Create: `metaclaw/metaclaw/tests/test_gateway.py`

- [ ] **Step 1: 写测试文件**

```python
# metaclaw/metaclaw/tests/test_gateway.py
import threading
import pytest

from bridge.reply import Reply, ReplyType
from bridge.context import Context
from gateway.gateway import Gateway
from gateway.message import OutboundMessage
from gateway.exceptions import PlatformNotRegisteredError


# ── 每个测试用独立的 Gateway 实例（绕过单例） ──────────────────────────────

@pytest.fixture
def gw():
    """返回一个未注册任何 channel 的新 Gateway 实例。"""
    g = Gateway.__wrapped__()  # 调用被 singleton 装饰前的原始类
    yield g


class FakeChannel:
    """最小化 channel mock，记录 send() 调用。"""

    def __init__(self):
        self.sent = []

    def send(self, reply: Reply, context: Context):
        self.sent.append((reply.type, reply.content, context.get("session_id")))


# ── 测试 ──────────────────────────────────────────────────────────────────

def test_register_and_list(gw):
    ch = FakeChannel()
    gw.register("feishu", ch)
    assert "feishu" in gw.list_platforms()


def test_unregister(gw):
    ch = FakeChannel()
    gw.register("feishu", ch)
    gw.unregister("feishu")
    assert "feishu" not in gw.list_platforms()


def test_unregister_nonexistent_is_noop(gw):
    # 不应抛异常
    gw.unregister("nonexistent")


def test_send_text_success(gw):
    ch = FakeChannel()
    gw.register("feishu", ch)

    result = gw.send_text("feishu", "user_001", "hello")

    assert result is True
    assert len(ch.sent) == 1
    reply_type, content, session_id = ch.sent[0]
    assert reply_type == ReplyType.TEXT
    assert content == "hello"
    assert session_id == "user_001"


def test_send_raises_when_platform_not_registered(gw):
    with pytest.raises(PlatformNotRegisteredError) as exc_info:
        gw.send_text("weixin", "user_002", "hi")
    assert exc_info.value.platform == "weixin"


def test_send_returns_false_when_channel_raises(gw):
    class BrokenChannel:
        def send(self, reply, context):
            raise RuntimeError("network error")

    gw.register("dingtalk", BrokenChannel())
    result = gw.send_text("dingtalk", "user_003", "test")
    assert result is False


def test_send_outbound_message_with_image_url(gw):
    ch = FakeChannel()
    gw.register("terminal", ch)

    msg = OutboundMessage(
        platform="terminal",
        session_id="user_004",
        content="https://example.com/img.png",
        reply_type=ReplyType.IMAGE_URL,
    )
    result = gw.send(msg)

    assert result is True
    reply_type, content, session_id = ch.sent[0]
    assert reply_type == ReplyType.IMAGE_URL
    assert content == "https://example.com/img.png"


def test_thread_safety(gw):
    """并发 register/send 不应产生竞争条件。"""
    ch = FakeChannel()
    errors = []

    def worker(i):
        try:
            gw.register(f"platform_{i}", ch)
            gw.send_text(f"platform_{i}", f"user_{i}", f"msg_{i}")
            gw.unregister(f"platform_{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread safety errors: {errors}"
```

> **注意：** `Gateway.__wrapped__` 的获取方式依赖 `singleton` 装饰器的实现。`singleton` 返回 `get_instance` 闭包，原始类保存在闭包变量中。如果 `__wrapped__` 不可用，在 fixture 中改用以下方式直接构造：
> ```python
> from gateway import gateway as gw_module
> g = object.__new__(gw_module.Gateway.__class__)  # fallback
> ```
> 更简单的方式：直接在 fixture 中 `import gateway.gateway as m; g = m.Gateway.__wrapped__()`，或在 `gateway.py` 中给原始类加 `__wrapped__` 属性：在 `singleton` 装饰器返回 `get_instance` 前加 `get_instance.__wrapped__ = cls`。

- [ ] **Step 2: 更新 singleton 装饰器，暴露 \_\_wrapped\_\_**

打开 `metaclaw/metaclaw/common/singleton.py`，在 `return get_instance` 前加一行：

```python
def singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    get_instance.__wrapped__ = cls   # ← 新增这一行，方便测试绕过单例
    return get_instance
```

- [ ] **Step 3: 运行测试，预期全部通过**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_gateway.py -v
```

预期输出（示例）：
```
tests/test_gateway.py::test_register_and_list PASSED
tests/test_gateway.py::test_unregister PASSED
tests/test_gateway.py::test_unregister_nonexistent_is_noop PASSED
tests/test_gateway.py::test_send_text_success PASSED
tests/test_gateway.py::test_send_raises_when_platform_not_registered PASSED
tests/test_gateway.py::test_send_returns_false_when_channel_raises PASSED
tests/test_gateway.py::test_send_outbound_message_with_image_url PASSED
tests/test_gateway.py::test_thread_safety PASSED
8 passed in ...
```

- [ ] **Step 4: 提交**

```bash
git add tests/test_gateway.py common/singleton.py
git commit -m "test(gateway): add full test suite for Gateway; expose __wrapped__ on singleton"
```

---

## Task 6：将 Gateway 注册接入 ChannelManager（app.py 微改）

**Files:**
- Modify: `metaclaw/metaclaw/app.py`（`_run_channel` 方法和 `ChannelManager.stop` 方法）

- [ ] **Step 1: 找到 `_run_channel` 方法（约第 160 行）**

当前代码：

```python
    def _run_channel(self, name: str, channel):
        try:
            channel.startup()
        except Exception as e:
            logger.error(f"[ChannelManager] Channel '{name}' startup error: {e}")
            logger.exception(e)
```

改为：

```python
    def _run_channel(self, name: str, channel):
        try:
            channel.startup()
            # 启动成功后注册到统一网关
            try:
                from gateway.gateway import Gateway
                Gateway().register(name, channel)
            except Exception as gw_err:
                logger.warning(f"[ChannelManager] Gateway register failed for '{name}': {gw_err}")
        except Exception as e:
            logger.error(f"[ChannelManager] Channel '{name}' startup error: {e}")
            logger.exception(e)
```

- [ ] **Step 2: 找到 `stop` 方法中执行 `ch.stop()` 后的位置**

在 `stop` 方法的 `for name, ch, th in to_stop:` 循环的最后（`logger.info` 打印停止成功后），加注销逻辑：

```python
        for name, ch, th in to_stop:
            # ... 现有代码 ...
            # 已有代码结尾处加：
            try:
                from gateway.gateway import Gateway
                Gateway().unregister(name)
            except Exception as gw_err:
                logger.warning(f"[ChannelManager] Gateway unregister failed for '{name}': {gw_err}")
```

> **注意：** `try/except` 包裹 Gateway 调用，确保 Gateway 模块未加载时不影响现有 channel 生命周期。

- [ ] **Step 3: 验证应用启动正常**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
python -c "
import sys
sys.argv = ['app']
from config import load_config
load_config()
from gateway.gateway import Gateway
print('Gateway platforms before start:', Gateway().list_platforms())
print('Integration check OK')
"
```

预期输出：
```
Gateway platforms before start: []
Integration check OK
```

- [ ] **Step 4: 提交**

```bash
git add app.py
git commit -m "feat(gateway): register/unregister channels in ChannelManager lifecycle"
```

---

## Task 7：集成验证（端到端冒烟测试）

**Files:**
- 无新增文件，验证整体集成

- [ ] **Step 1: 运行全部 gateway 相关测试**

```bash
cd /Users/mianhuatang/MetaClaw/metaclaw/metaclaw
pytest tests/test_gateway.py -v
```

预期：8 passed

- [ ] **Step 2: 运行现有测试，确认零回归**

```bash
pytest tests/ -v --ignore=tests/test_gateway.py 2>&1 | tail -20
```

预期：现有测试通过率与改动前一致（忽略已知 skip/xfail）

- [ ] **Step 3: 手动验证 Gateway 在 terminal channel 下可用**

```bash
python -c "
from config import load_config
load_config()

# 模拟 channel 注册
from gateway.gateway import Gateway

class MockTerminal:
    def send(self, reply, context):
        print(f'[MockTerminal] Received: {reply.content} -> {context[\"session_id\"]}')

Gateway().register('terminal', MockTerminal())
Gateway().send_text('terminal', 'test_user', '统一网关测试消息')
print('Gateway platforms:', Gateway().list_platforms())
"
```

预期输出：
```
[MockTerminal] Received: 统一网关测试消息 -> test_user
Gateway platforms: ['terminal']
```

- [ ] **Step 4: 最终提交**

```bash
git add .
git commit -m "feat: complete unified gateway (H) - Gateway singleton with platform registration"
```

---

## 自检结果

**Spec 覆盖：**
- ✅ 新增 `gateway/` 模块（4 文件）
- ✅ `Gateway` 单例，提供 `register / unregister / send / send_text / list_platforms`
- ✅ `OutboundMessage` 统一出站消息模型
- ✅ `PlatformNotRegisteredError` 错误类型
- ✅ `ChannelManager._run_channel` 启动后注册
- ✅ `ChannelManager.stop` 停止后注销
- ✅ 线程安全（RLock）
- ✅ 现有 channel 代码零改动
- ✅ `singleton.__wrapped__` 暴露，支持测试绕过单例

**类型一致性：**
- `OutboundMessage.reply_type` 类型为 `ReplyType`，在 Task 2 定义，Task 3 和 Task 5 均正确使用
- `Gateway.send()` 接收 `OutboundMessage`，`send_text()` 内部构造 `OutboundMessage` 再调用 `send()`，签名一致
- `singleton.__wrapped__` 在 Task 5 fixture 中使用，在 Task 5 Step 2 中添加

**Placeholder 扫描：** 无 TBD / TODO / "类似 Task N" 等模糊描述
