# 个性化仪表盘欢迎页实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Web UI 的静态欢迎页改造为基于历史对话的个性化仪表盘，支持一键回退到经典视图。

**Architecture:** 后端新增 `/api/welcome-summary` 端点，从 ConversationStore 读取统计数据并调用 LLM 生成个性化总结文案（5 分钟缓存）。前端保留经典视图 DOM，新增仪表盘视图容器，通过 localStorage 持久化视图偏好。

**Tech Stack:** Python (web.py), JavaScript (vanilla), Tailwind CSS, SQLite (ConversationStore)

---

## 文件结构

| 文件 | 变更 | 说明 |
|------|------|------|
| `metaclaw/metaclaw/channel/web/web_channel.py` | 修改 | 新增 `WelcomeSummaryHandler`、缓存函数、AI 总结函数、辅助统计函数；在 `urls` 中添加路由 |
| `metaclaw/metaclaw/channel/web/chat.html` | 修改 | 调整 `welcome-screen` 结构：添加视图切换按钮、仪表盘容器；保留经典视图内容 |
| `metaclaw/metaclaw/channel/web/static/js/console.js` | 修改 | 新增 i18n 词条、API 调用、视图切换、仪表盘渲染、骨架屏；修改 `newChat()` 和 `loadHistory()` |
| `metaclaw/metaclaw/tests/test_welcome_summary.py` | 创建 | 后端单元测试 |

---

## Task 1: 后端 — WelcomeSummaryHandler 与基础统计

**Files:**
- Modify: `metaclaw/metaclaw/channel/web/web_channel.py`
- Test: `metaclaw/metaclaw/tests/test_welcome_summary.py`

**Context:** 在 `HistoryHandler` 类之后（约第 1830 行之后）添加新代码。`urls` 路由表在文件约 598-629 行。

- [ ] **Step 1: 写失败测试**

创建 `metaclaw/metaclaw/tests/test_welcome_summary.py`：

```python
import json
import time
import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from channel.web.web_channel import _generate_welcome_summary, _welcome_summary_cache


class TestWelcomeSummary(unittest.TestCase):
    def tearDown(self):
        _welcome_summary_cache.clear()

    @patch('channel.web.web_channel.get_conversation_store')
    def test_generate_welcome_summary_returns_expected_structure(self, mock_get_store):
        """_generate_welcome_summary must return dict with greeting, summary, stats, recent_topics."""
        store = MagicMock()
        store.list_sessions.return_value = {
            "sessions": [
                {"session_id": "s1", "title": "Test Chat", "msg_count": 5,
                 "created_at": int(time.time()) - 3600, "last_active": int(time.time()) - 60},
            ],
            "total": 1,
        }
        store.load_history_page.return_value = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
            "has_more": False,
        }
        mock_get_store.return_value = store

        with patch('channel.web.web_channel._count_knowledge_docs', return_value=3):
            with patch('channel.web.web_channel._count_memory_entries', return_value=10):
                with patch('channel.web.web_channel._generate_ai_summary', return_value="Test summary"):
                    result = _generate_welcome_summary("s1")

        self.assertIn("greeting", result)
        self.assertIn("summary", result)
        self.assertIn("stats", result)
        self.assertIn("recent_topics", result)
        self.assertIn("generated_at", result)
        self.assertEqual(result["stats"]["conversation_count"], 1)
        self.assertEqual(result["stats"]["message_count"], 5)
        self.assertEqual(result["stats"]["knowledge_docs"], 3)
        self.assertEqual(result["stats"]["memory_entries"], 10)

    @patch('channel.web.web_channel.get_conversation_store')
    def test_cache_is_used_within_5_minutes(self, mock_get_store):
        """Second call within 5 minutes should return cached result without hitting store again."""
        store = MagicMock()
        store.list_sessions.return_value = {"sessions": [], "total": 0}
        mock_get_store.return_value = store

        with patch('channel.web.web_channel._count_knowledge_docs', return_value=0):
            with patch('channel.web.web_channel._count_memory_entries', return_value=0):
                with patch('channel.web.web_channel._generate_ai_summary', return_value="Cached"):
                    r1 = _generate_welcome_summary("s1")
                    r2 = _generate_welcome_summary("s1")

        self.assertEqual(r1["summary"], r2["summary"])
        # list_sessions should only be called once due to cache
        self.assertEqual(store.list_sessions.call_count, 1)

    @patch('channel.web.web_channel.get_conversation_store')
    def test_empty_history_fallback(self, mock_get_store):
        """When user has no history, greeting should be welcoming and stats should be zeros."""
        store = MagicMock()
        store.list_sessions.return_value = {"sessions": [], "total": 0}
        mock_get_store.return_value = store

        with patch('channel.web.web_channel._count_knowledge_docs', return_value=0):
            with patch('channel.web.web_channel._count_memory_entries', return_value=0):
                result = _generate_welcome_summary("s1")

        self.assertIn("欢迎", result["greeting"])
        self.assertEqual(result["stats"]["conversation_count"], 0)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd metaclaw/metaclaw
python -m pytest tests/test_welcome_summary.py -v
```

Expected: 3 FAILs with `ImportError` or `AttributeError` because `_generate_welcome_summary` does not exist yet.

- [ ] **Step 3: 在 web_channel.py 中新增 WelcomeSummaryHandler 和辅助函数**

在 `metaclaw/metaclaw/channel/web/web_channel.py` 中，`HistoryHandler` 类之后（约第 1830 行后）添加：

```python
# ========================================================================
# Welcome Summary — personalized dashboard data
# ========================================================================

_welcome_summary_cache = {}  # session_id -> {"timestamp": float, "data": dict}


class WelcomeSummaryHandler:
    def GET(self):
        _require_auth()
        web.header('Content-Type', 'application/json; charset=utf-8')
        web.header('Access-Control-Allow-Origin', '*')
        try:
            params = web.input(session_id='')
            session_id = params.session_id.strip()
            if not session_id:
                return json.dumps({"status": "error", "message": "session_id required"})

            result = _generate_welcome_summary(session_id)
            return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[WebChannel] Welcome summary API error: {e}")
            return json.dumps({"status": "error", "message": str(e)})


def _generate_welcome_summary(session_id: str) -> dict:
    """Generate personalized welcome summary with 5-minute caching."""
    global _welcome_summary_cache

    cached = _welcome_summary_cache.get(session_id)
    if cached and time.time() - cached["timestamp"] < 300:
        return cached["data"]

    from agent.memory import get_conversation_store
    store = get_conversation_store()

    sessions_result = store.list_sessions(channel_type="web", page=1, page_size=1000)
    all_sessions = sessions_result.get("sessions", [])

    total_conversations = len(all_sessions)
    total_messages = sum(s.get("msg_count", 0) for s in all_sessions)

    # Collect recent user messages for AI summary context
    recent_messages = []
    current_session = next((s for s in all_sessions if s["session_id"] == session_id), None)
    if current_session and current_session.get("msg_count", 0) > 0:
        try:
            history = store.load_history_page(session_id, page=1, page_size=20)
            for msg in history.get("messages", []):
                if msg.get("content") and msg.get("role") == "user":
                    recent_messages.append(msg["content"][:200])
        except Exception as e:
            logger.warning(f"[WelcomeSummary] Failed to load history: {e}")

    knowledge_count = _count_knowledge_docs()
    memory_count = _count_memory_entries()

    stats = {
        "conversation_count": total_conversations,
        "message_count": total_messages,
        "files_analyzed": 0,
        "tasks_completed": 0,
        "skills_used": 0,
        "memory_entries": memory_count,
        "knowledge_docs": knowledge_count,
        "usage_duration_minutes": 0,
    }

    summary_text = ""
    greeting = "欢迎使用 MetaClaw！"
    recent_topics = []

    if total_conversations > 0:
        greeting = "欢迎回来 👋"
        summary_text = _generate_ai_summary(stats, recent_messages)

        for s in all_sessions[:3]:
            title = s.get("title", "").strip()
            if title and title not in ("新对话", "New Chat", ""):
                recent_topics.append({
                    "id": s["session_id"],
                    "title": title,
                    "icon": "message",
                    "color": "primary",
                    "last_active": s.get("last_active", 0),
                })

    result = {
        "greeting": greeting,
        "summary": summary_text or "开始你的第一次对话吧！",
        "stats": stats,
        "recent_topics": recent_topics,
        "generated_at": int(time.time()),
    }

    _welcome_summary_cache[session_id] = {"timestamp": time.time(), "data": result}
    return result


def _generate_ai_summary(stats: dict, recent_messages: list) -> str:
    """Call the current LLM to generate a personalized welcome summary."""
    try:
        from bridge.bridge import Bridge
        from models.session_manager import Session
        bot = Bridge().get_bot("chat")

        messages_text = "\n".join(f"- {m}" for m in recent_messages[:5])
        prompt = (
            f"基于以下用户数据，生成一段简短的个性化欢迎文案（50字以内），"
            f"体现用户的使用成果和 AI 的价值，让用户有'获得感'。"
            f"只输出文案，不要加引号或额外说明。\n\n"
            f"统计数据：{stats['conversation_count']} 次对话，"
            f"{stats['message_count']} 条消息，"
            f"{stats['knowledge_docs']} 篇知识库文档，"
            f"{stats['memory_entries']} 条记忆。\n\n"
            f"最近对话摘要：\n{messages_text}\n"
        )

        session = Session("__welcome_summary__", system_prompt="")
        session.messages = [{"role": "user", "content": prompt}]

        result = bot.reply_text(session) or {}
        completion_tokens = result.get("completion_tokens", 0) or 0
        raw = (result.get("content") or "").strip()

        if completion_tokens > 0 and raw:
            import re
            summary = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip().strip('"\'')
            if summary:
                return summary
    except Exception as e:
        logger.warning(f"[WebChannel] AI summary generation failed: {e}")

    # Fallback
    if stats["conversation_count"] > 0:
        return (
            f"你已经进行了 {stats['conversation_count']} 次对话，"
            f"累计 {stats['message_count']} 条消息。继续探索更多可能吧！"
        )
    return ""


def _count_knowledge_docs() -> int:
    """Count markdown documents in the knowledge base (excluding index/log)."""
    try:
        from common.utils import expand_path
        kb_dir = os.path.join(expand_path(conf().get("agent_workspace", DEFAULT_AGENT_WORKSPACE)), "knowledge")
        if not os.path.isdir(kb_dir):
            return 0
        count = 0
        for root, _, files in os.walk(kb_dir):
            for f in files:
                if f.endswith(".md") and f not in ("index.md", "log.md"):
                    count += 1
        return count
    except Exception:
        return 0


def _count_memory_entries() -> int:
    """Count memory chunks in the long-term memory database."""
    try:
        from agent.memory import get_conversation_store
        store = get_conversation_store()
        conn = store._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM memory_chunks").fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
    except Exception:
        return 0
```

- [ ] **Step 4: 在 urls 路由表中注册新端点**

在 `metaclaw/metaclaw/channel/web/web_channel.py` 约 625 行的 `urls` 元组中，在 `'/api/history', 'HistoryHandler',` 之后添加：

```python
            '/api/welcome-summary', 'WelcomeSummaryHandler',
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd metaclaw/metaclaw
python -m pytest tests/test_welcome_summary.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add metaclaw/metaclaw/channel/web/web_channel.py metaclaw/metaclaw/tests/test_welcome_summary.py
git commit -m "feat(backend): add /api/welcome-summary endpoint with stats and AI summary"
```

---

## Task 2: 前端 — chat.html 结构调整

**Files:**
- Modify: `metaclaw/metaclaw/channel/web/chat.html`

**Context:** `welcome-screen` div 在约第 285-354 行。需要添加视图切换按钮和仪表盘容器。

- [ ] **Step 1: 修改 welcome-screen 结构**

将 `metaclaw/metaclaw/channel/web/chat.html` 中第 285-354 行的 `welcome-screen` 替换为：

```html
                        <!-- Welcome Screen -->
                        <div id="welcome-screen" class="flex flex-col items-center justify-center h-full px-6 pb-16 relative" style="padding-top: 6vh">
                            <!-- View Toggle Button -->
                            <button id="welcome-view-toggle"
                                    class="absolute top-4 right-4 p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300
                                           hover:bg-slate-100 dark:hover:bg-white/10 cursor-pointer transition-colors duration-150"
                                    title="切换视图">
                                <i class="fas fa-layer-group text-sm"></i>
                            </button>

                            <!-- Dashboard View (default) -->
                            <div id="welcome-dashboard" class="w-full max-w-2xl flex flex-col items-center">
                                <!-- Skeleton (shown while loading) -->
                                <div id="welcome-dashboard-skeleton" class="w-full flex flex-col items-center">
                                    <div class="w-20 h-20 rounded-2xl bg-slate-200 dark:bg-slate-700 mb-6 animate-pulse"></div>
                                    <div class="h-8 w-48 bg-slate-200 dark:bg-slate-700 rounded-lg mb-3 animate-pulse"></div>
                                    <div class="h-5 w-80 bg-slate-200 dark:bg-slate-700 rounded-lg mb-10 animate-pulse"></div>
                                    <div class="grid grid-cols-3 sm:grid-cols-4 gap-3 w-full">
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                        <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                                    </div>
                                </div>

                                <!-- Content (filled by JS) -->
                                <div id="welcome-dashboard-content" class="w-full flex flex-col items-center hidden">
                                    <img src="assets/logo-mark.svg" alt="MetaClaw" class="w-20 h-20 rounded-2xl mb-6 shadow-lg shadow-primary-500/20">
                                    <h1 id="welcome-greeting" class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-3 text-center"></h1>
                                    <p id="welcome-summary-text" class="text-base text-slate-500 dark:text-slate-400 text-center max-w-xl mb-10 leading-relaxed"></p>

                                    <!-- Stats Grid -->
                                    <div id="welcome-stats-grid" class="grid grid-cols-3 sm:grid-cols-4 gap-3 w-full mb-8">
                                        <!-- Filled by JS -->
                                    </div>

                                    <!-- Recent Topics -->
                                    <div id="welcome-recent-topics" class="w-full mb-6 hidden">
                                        <p class="text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-3 text-center" data-i18n="recent_topics_label">继续之前的对话</p>
                                        <div id="welcome-topics-list" class="flex flex-wrap justify-center gap-2">
                                            <!-- Filled by JS -->
                                        </div>
                                    </div>

                                    <!-- Quick Actions -->
                                    <div class="grid grid-cols-3 gap-3 w-full max-w-lg">
                                        <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                            <div class="flex items-center gap-2 mb-2">
                                                <div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center">
                                                    <i class="fas fa-folder-open text-blue-500 text-xs"></i>
                                                </div>
                                                <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_sys_title">系统管理</span>
                                            </div>
                                            <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_sys_text">查看工作空间里有哪些文件</p>
                                        </div>
                                        <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                            <div class="flex items-center gap-2 mb-2">
                                                <div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                                                    <i class="fas fa-code text-amber-500 text-xs"></i>
                                                </div>
                                                <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_code_title">编程助手</span>
                                            </div>
                                            <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_code_text">搜索AI资讯并生成可视化网页报告</p>
                                        </div>
                                        <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                            <div class="flex items-center gap-2 mb-2">
                                                <div class="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center">
                                                    <i class="fas fa-book text-violet-500 text-xs"></i>
                                                </div>
                                                <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_knowledge_title">知识库</span>
                                            </div>
                                            <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_knowledge_text">查看知识库当前文档情况</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Classic View -->
                            <div id="welcome-classic" class="w-full flex flex-col items-center hidden">
                                <img src="assets/logo-mark.svg" alt="MetaClaw" class="w-16 h-16 rounded-2xl mb-6 shadow-lg shadow-primary-500/20">
                                <h1 id="welcome-title" class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-3">今天想做什么？</h1>
                                <p id="welcome-subtitle" class="text-slate-500 dark:text-slate-400 text-center max-w-lg mb-10 leading-relaxed"
                                   data-i18n-html="welcome_subtitle">我可以帮你解答问题、管理计算机、创造和执行技能，并通过<br>长期记忆和知识库不断成长</p>

                                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full max-w-2xl">
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center">
                                                <i class="fas fa-folder-open text-blue-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_sys_title">系统管理</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_sys_text">查看工作空间里有哪些文件</p>
                                    </div>
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                                                <i class="fas fa-clock text-amber-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_task_title">定时任务</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_task_text">1分钟后提醒我检查服务器</p>
                                    </div>
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                                                <i class="fas fa-code text-amber-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_code_title">编程助手</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_code_text">搜索AI资讯并生成可视化网页报告</p>
                                    </div>
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center">
                                                <i class="fas fa-book text-violet-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_knowledge_title">知识库</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_knowledge_text">查看知识库当前文档情况</p>
                                    </div>
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-rose-50 dark:bg-rose-900/30 flex items-center justify-center">
                                                <i class="fas fa-puzzle-piece text-rose-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_skill_title">技能系统</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_skill_text">查看所有支持的工具和技能</p>
                                    </div>
                                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200" data-send="/help">
                                        <div class="flex items-center gap-2 mb-2">
                                            <div class="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                                                <i class="fas fa-terminal text-slate-500 text-xs"></i>
                                            </div>
                                            <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_web_title">指令中心</span>
                                        </div>
                                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_web_text">查看全部命令</p>
                                    </div>
                                </div>
                            </div>
                        </div>
```

- [ ] **Step 2: Commit**

```bash
git add metaclaw/metaclaw/channel/web/chat.html
git commit -m "feat(ui): add dashboard and classic view containers to welcome screen"
```

---

## Task 3: 前端 — console.js i18n 与 API 层

**Files:**
- Modify: `metaclaw/metaclaw/channel/web/static/js/console.js`

**Context:** i18n 对象 `I18N` 在文件开头（约第 13 行），`t()` 函数在第 191 行。

- [ ] **Step 1: 添加仪表盘相关 i18n 词条**

在 `metaclaw/metaclaw/channel/web/static/js/console.js` 的 `I18N.zh` 对象中，在 `welcome_subtitle` 之后添加：

```javascript
        welcome_greeting_new: '欢迎使用 MetaClaw！',
        welcome_greeting_return: '欢迎回来 👋',
        welcome_summary_empty: '开始你的第一次对话吧！',
        welcome_summary_fallback: '你已经进行了 {conversations} 次对话，累计 {messages} 条消息。继续探索更多可能吧！',
        recent_topics_label: '继续之前的对话',
        stat_label_messages: '对话消息',
        stat_label_files: '文件分析',
        stat_label_skills: '技能使用',
        stat_label_tasks: '任务完成',
        stat_label_memory: '记忆积累',
        stat_label_knowledge: '知识文档',
        view_toggle_dashboard: '切换仪表盘视图',
        view_toggle_classic: '切换经典视图',
```

在 `I18N.en` 对象中同样位置添加：

```javascript
        welcome_greeting_new: 'Welcome to MetaClaw!',
        welcome_greeting_return: 'Welcome back 👋',
        welcome_summary_empty: 'Start your first conversation!',
        welcome_summary_fallback: 'You\'ve had {conversations} conversations with {messages} messages. Keep exploring!',
        recent_topics_label: 'Continue previous conversations',
        stat_label_messages: 'Messages',
        stat_label_files: 'Files',
        stat_label_skills: 'Skills',
        stat_label_tasks: 'Tasks',
        stat_label_memory: 'Memories',
        stat_label_knowledge: 'Knowledge',
        view_toggle_dashboard: 'Switch to Dashboard',
        view_toggle_classic: 'Switch to Classic View',
```

- [ ] **Step 2: 添加视图偏好常量与 API 调用函数**

在 `metaclaw/metaclaw/channel/web/static/js/console.js` 中，在 `let sessionId = loadOrCreateSessionId();`（约第 509 行）之后添加：

```javascript
// ---- Welcome screen view preference ----
const WELCOME_VIEW_KEY = 'metaclaw_welcome_view';
let currentWelcomeView = localStorage.getItem(WELCOME_VIEW_KEY) || 'dashboard';

function saveWelcomeViewPreference(view) {
    localStorage.setItem(WELCOME_VIEW_KEY, view);
    currentWelcomeView = view;
}

function loadWelcomeViewPreference() {
    return localStorage.getItem(WELCOME_VIEW_KEY) || 'dashboard';
}

// ---- Welcome Summary API ----
let welcomeSummaryData = null;
let welcomeSummaryLoading = false;

async function fetchWelcomeSummary() {
    if (welcomeSummaryLoading) return;
    welcomeSummaryLoading = true;
    try {
        const resp = await fetch(`/api/welcome-summary?session_id=${encodeURIComponent(sessionId)}`);
        const data = await resp.json();
        if (data.status === 'success' && data.data) {
            welcomeSummaryData = data.data;
            renderDashboardWelcome();
        } else {
            console.warn('[WelcomeSummary] API error:', data.message);
            showDashboardFallback();
        }
    } catch (e) {
        console.warn('[WelcomeSummary] Fetch error:', e);
        showDashboardFallback();
    } finally {
        welcomeSummaryLoading = false;
    }
}

function showDashboardFallback() {
    const content = document.getElementById('welcome-dashboard-content');
    const skeleton = document.getElementById('welcome-dashboard-skeleton');
    if (skeleton) skeleton.classList.add('hidden');
    if (content) {
        content.classList.remove('hidden');
        const greeting = document.getElementById('welcome-greeting');
        const summary = document.getElementById('welcome-summary-text');
        if (greeting) greeting.textContent = t('welcome_greeting_new');
        if (summary) summary.textContent = t('welcome_summary_empty');
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add metaclaw/metaclaw/channel/web/static/js/console.js
git commit -m "feat(ui): add i18n keys and welcome summary API client"
```

---

## Task 4: 前端 — 仪表盘渲染与视图切换

**Files:**
- Modify: `metaclaw/metaclaw/channel/web/static/js/console.js`

**Context:** `newChat()` 函数约在第 1743 行。`loadHistory()` 函数约在第 1632 行。

- [ ] **Step 1: 添加仪表盘渲染函数**

在 `fetchWelcomeSummary()` 函数之后添加：

```javascript
function renderDashboardWelcome() {
    const skeleton = document.getElementById('welcome-dashboard-skeleton');
    const content = document.getElementById('welcome-dashboard-content');
    if (!content) return;

    if (skeleton) skeleton.classList.add('hidden');
    content.classList.remove('hidden');

    const data = welcomeSummaryData;
    if (!data) return;

    // Greeting
    const greetingEl = document.getElementById('welcome-greeting');
    if (greetingEl) greetingEl.textContent = data.greeting || t('welcome_greeting_return');

    // Summary
    const summaryEl = document.getElementById('welcome-summary-text');
    if (summaryEl) summaryEl.textContent = data.summary || t('welcome_summary_empty');

    // Stats Grid
    const statsGrid = document.getElementById('welcome-stats-grid');
    if (statsGrid && data.stats) {
        const s = data.stats;
        const statItems = [
            { icon: '💬', value: s.message_count || 0, label: t('stat_label_messages') },
            { icon: '📁', value: s.files_analyzed || 0, label: t('stat_label_files') },
            { icon: '⚡', value: s.skills_used || 0, label: t('stat_label_skills') },
            { icon: '✅', value: s.tasks_completed || 0, label: t('stat_label_tasks') },
            { icon: '🧠', value: s.memory_entries || 0, label: t('stat_label_memory') },
            { icon: '📚', value: s.knowledge_docs || 0, label: t('stat_label_knowledge') },
        ];
        statsGrid.innerHTML = statItems.map(item => `
            <div class="bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 text-center hover:border-primary-300 dark:hover:border-primary-600 transition-all duration-200">
                <div class="text-xl mb-1">${item.icon}</div>
                <div class="text-2xl font-bold text-primary-500">${item.value}</div>
                <div class="text-xs text-slate-500 dark:text-slate-400 mt-1">${item.label}</div>
            </div>
        `).join('');
    }

    // Recent Topics
    const topicsContainer = document.getElementById('welcome-recent-topics');
    const topicsList = document.getElementById('welcome-topics-list');
    if (topicsContainer && topicsList && data.recent_topics && data.recent_topics.length > 0) {
        topicsContainer.classList.remove('hidden');
        topicsList.innerHTML = data.recent_topics.map(topic => `
            <button class="px-3 py-1.5 rounded-full bg-slate-100 dark:bg-white/10 text-sm text-slate-600 dark:text-slate-300
                           hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:text-primary-600 dark:hover:text-primary-400
                           border border-slate-200 dark:border-white/10 transition-colors duration-150 cursor-pointer"
                    onclick="setInputValue(${JSON.stringify(topic.title).replace(/"/g, '&quot;')})">
                <i class="fas fa-message text-xs mr-1"></i>${escapeHtml(topic.title)}
            </button>
        `).join('');
    } else if (topicsContainer) {
        topicsContainer.classList.add('hidden');
    }
}

function setInputValue(text) {
    const input = document.getElementById('chat-input');
    if (input) {
        input.value = text;
        input.focus();
        input.dispatchEvent(new Event('input'));
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

- [ ] **Step 2: 添加视图切换函数**

继续在同一位置添加：

```javascript
function toggleWelcomeView() {
    const dashboard = document.getElementById('welcome-dashboard');
    const classic = document.getElementById('welcome-classic');
    const btn = document.getElementById('welcome-view-toggle');
    if (!dashboard || !classic) return;

    if (currentWelcomeView === 'dashboard') {
        // Switch to classic
        dashboard.classList.add('hidden');
        classic.classList.remove('hidden');
        saveWelcomeViewPreference('classic');
        if (btn) btn.title = t('view_toggle_dashboard');
    } else {
        // Switch to dashboard
        classic.classList.add('hidden');
        dashboard.classList.remove('hidden');
        saveWelcomeViewPreference('dashboard');
        if (btn) btn.title = t('view_toggle_classic');
        if (!welcomeSummaryData && !welcomeSummaryLoading) {
            fetchWelcomeSummary();
        }
    }
}

function applyWelcomeView() {
    const dashboard = document.getElementById('welcome-dashboard');
    const classic = document.getElementById('welcome-classic');
    const btn = document.getElementById('welcome-view-toggle');
    if (!dashboard || !classic) return;

    const view = loadWelcomeViewPreference();
    if (view === 'classic') {
        dashboard.classList.add('hidden');
        classic.classList.remove('hidden');
        if (btn) btn.title = t('view_toggle_dashboard');
    } else {
        classic.classList.add('hidden');
        dashboard.classList.remove('hidden');
        if (btn) btn.title = t('view_toggle_classic');
    }
}
```

- [ ] **Step 3: 绑定切换按钮事件**

在 `metaclaw/metaclaw/channel/web/static/js/console.js` 中，找到事件绑定区域（通常在 DOMContentLoaded 或初始化代码中）。如果没有统一的事件绑定区域，在文件末尾初始化代码附近添加：

```javascript
// Bind welcome view toggle
document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('welcome-view-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleWelcomeView);
    }
    applyWelcomeView();
});
```

如果文件末尾已有 `DOMContentLoaded` 监听器，将上述代码合并到其中。

- [ ] **Step 4: 修改 newChat() 函数以支持两种视图**

在 `metaclaw/metaclaw/channel/web/static/js/console.js` 中，找到 `newChat()` 函数（约第 1743 行）。将生成欢迎屏幕的代码段替换为：

```javascript
    // Build fresh welcome screen with both views
    const ws = document.createElement('div');
    ws.id = 'welcome-screen';
    ws.className = 'flex flex-col items-center justify-center h-full px-6 pb-16 relative';
    ws.style.paddingTop = '6vh';
    ws.innerHTML = `
        <button id="welcome-view-toggle"
                class="absolute top-4 right-4 p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300
                       hover:bg-slate-100 dark:hover:bg-white/10 cursor-pointer transition-colors duration-150"
                title="${t('view_toggle_classic')}">
            <i class="fas fa-layer-group text-sm"></i>
        </button>

        <!-- Dashboard View -->
        <div id="welcome-dashboard" class="w-full max-w-2xl flex flex-col items-center ${loadWelcomeViewPreference() === 'classic' ? 'hidden' : ''}">
            <div id="welcome-dashboard-skeleton" class="w-full flex flex-col items-center">
                <div class="w-20 h-20 rounded-2xl bg-slate-200 dark:bg-slate-700 mb-6 animate-pulse"></div>
                <div class="h-8 w-48 bg-slate-200 dark:bg-slate-700 rounded-lg mb-3 animate-pulse"></div>
                <div class="h-5 w-80 bg-slate-200 dark:bg-slate-700 rounded-lg mb-10 animate-pulse"></div>
                <div class="grid grid-cols-3 sm:grid-cols-4 gap-3 w-full">
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                    <div class="h-20 bg-slate-200 dark:bg-slate-700 rounded-xl animate-pulse"></div>
                </div>
            </div>
            <div id="welcome-dashboard-content" class="w-full flex flex-col items-center hidden">
                <img src="assets/logo-mark.svg" alt="MetaClaw" class="w-20 h-20 rounded-2xl mb-6 shadow-lg shadow-primary-500/20">
                <h1 id="welcome-greeting" class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-3 text-center"></h1>
                <p id="welcome-summary-text" class="text-base text-slate-500 dark:text-slate-400 text-center max-w-xl mb-10 leading-relaxed"></p>
                <div id="welcome-stats-grid" class="grid grid-cols-3 sm:grid-cols-4 gap-3 w-full mb-8"></div>
                <div id="welcome-recent-topics" class="w-full mb-6 hidden">
                    <p class="text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-3 text-center">${t('recent_topics_label')}</p>
                    <div id="welcome-topics-list" class="flex flex-wrap justify-center gap-2"></div>
                </div>
                <div class="grid grid-cols-3 gap-3 w-full max-w-lg">
                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                        <div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center"><i class="fas fa-folder-open text-blue-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_sys_title')}</span></div>
                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_sys_text')}</p>
                    </div>
                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                        <div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center"><i class="fas fa-code text-amber-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_code_title')}</span></div>
                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_code_text')}</p>
                    </div>
                    <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                        <div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center"><i class="fas fa-book text-violet-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_knowledge_title')}</span></div>
                        <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_knowledge_text')}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Classic View -->
        <div id="welcome-classic" class="w-full flex flex-col items-center ${loadWelcomeViewPreference() === 'dashboard' ? 'hidden' : ''}">
            <img src="assets/logo-mark.svg" alt="MetaClaw" class="w-16 h-16 rounded-2xl mb-6 shadow-lg shadow-primary-500/20">
            <h1 class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-3">${currentLang === 'zh' ? '今天想做什么？' : 'What should we work on?'}</h1>
            <p class="text-slate-500 dark:text-slate-400 text-center max-w-lg mb-10 leading-relaxed">${t('welcome_subtitle')}</p>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full max-w-2xl">
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center"><i class="fas fa-folder-open text-blue-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_sys_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_sys_text')}</p></div>
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center"><i class="fas fa-clock text-amber-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_task_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_task_text')}</p></div>
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center"><i class="fas fa-code text-amber-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_code_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_code_text')}</p></div>
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center"><i class="fas fa-book text-violet-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_knowledge_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_knowledge_text')}</p></div>
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-rose-50 dark:bg-rose-900/30 flex items-center justify-center"><i class="fas fa-puzzle-piece text-rose-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_skill_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_skill_text')}</p></div>
                <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200" data-send="/help"><div class="flex items-center gap-2 mb-2"><div class="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center"><i class="fas fa-terminal text-slate-500 text-xs"></i></div><span class="font-medium text-sm text-slate-700 dark:text-slate-200">${t('example_web_title')}</span></div><p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">${t('example_web_text')}</p></div>
            </div>
        </div>
    `;
    messagesDiv.appendChild(ws);

    // Bind toggle button
    const toggleBtn = ws.querySelector('#welcome-view-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleWelcomeView);
    }

    // Fetch welcome summary for dashboard view
    if (loadWelcomeViewPreference() === 'dashboard') {
        welcomeSummaryData = null;
        fetchWelcomeSummary();
    }

    // Re-bind example card clicks
    ws.querySelectorAll('.example-card').forEach(card => {
        card.addEventListener('click', () => {
            const sendText = card.dataset.send;
            if (sendText) {
                setInputValue(sendText);
                sendMessage();
            } else {
                const text = card.querySelector('p')?.textContent || '';
                if (text) {
                    setInputValue(text);
                    sendMessage();
                }
            }
        });
    });
```

替换原有的 `newChat()` 中创建 welcome screen 的代码块（从 `const ws = document.createElement('div');` 开始到 `ws.querySelectorAll('.example-card')` 事件绑定结束）。

- [ ] **Step 5: 修改 loadHistory() 以兼容两种视图**

在 `metaclaw/metaclaw/channel/web/static/js/console.js` 的 `loadHistory()` 函数中，将第 1640-1653 行的逻辑替换为：

```javascript
            if (data.status !== 'success' || data.messages.length === 0) {
                if (page === 1 && currentView === 'chat') {
                    document.body.classList.add('empty-chat');
                    const ws = document.getElementById('welcome-screen');
                    if (!ws) {
                        // No welcome screen exists, recreate it
                        newChat();
                    } else {
                        // Ensure correct view is shown
                        applyWelcomeView();
                        if (loadWelcomeViewPreference() === 'dashboard' && !welcomeSummaryData && !welcomeSummaryLoading) {
                            fetchWelcomeSummary();
                        }
                    }
                }
                return;
            }

            const prevScrollHeight = messagesDiv.scrollHeight;
            const isFirstLoad = page === 1;

            // On first load, remove the welcome screen if history exists
            if (isFirstLoad) {
                const ws = document.getElementById('welcome-screen');
                if (ws) ws.remove();
                document.body.classList.remove('empty-chat');
            }
```

- [ ] **Step 6: Commit**

```bash
git add metaclaw/metaclaw/channel/web/static/js/console.js
git commit -m "feat(ui): implement dashboard view rendering, view toggle, and newChat integration"
```

---

## Task 5: 集成测试与验证

**Files:**
- Modify: (修复测试中发现的任何问题)

- [ ] **Step 1: 运行后端测试**

```bash
cd metaclaw/metaclaw
python -m pytest tests/test_welcome_summary.py -v
```

Expected: 3 passed.

- [ ] **Step 2: 启动服务验证**

```bash
cd metaclaw/metaclaw
python app.py
```

在浏览器中打开 `http://127.0.0.1:9899`（或配置的 web_port）：

1. 首次加载应看到仪表盘骨架屏 → 数据加载后显示问候语、统计卡片、快捷入口
2. 点击右上角切换按钮应切换到经典视图（"今天想做什么？"+ 6 张卡片）
3. 再次点击切换按钮应回到仪表盘视图
4. 刷新页面应记住上次选择的视图
5. 发送一条消息后，欢迎屏应消失；点击"新对话"应重新显示欢迎屏

- [ ] **Step 3: 修复发现的问题**

根据验证结果修复：
- 如果 API 返回 404，检查 `urls` 路由是否正确注册
- 如果仪表盘不显示数据，检查 `fetchWelcomeSummary()` 的 console 输出
- 如果切换按钮不工作，检查事件绑定和 DOM ID

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: personalized welcome dashboard with AI summary and view toggle

- Add /api/welcome-summary endpoint with stats + AI-generated summary
- Implement dashboard view with greeting, stats grid, recent topics
- Support one-click toggle between dashboard and classic welcome views
- Cache AI summary for 5 minutes to reduce LLM calls
- Persist view preference in localStorage"
```

---

## 自审检查表

### Spec 覆盖检查

| 设计文档需求 | 对应任务 |
|-------------|---------|
| 后端 `/api/welcome-summary` 端点 | Task 1 |
| 5 分钟缓存 | Task 1 Step 3 (`_welcome_summary_cache`) |
| AI 总结生成 | Task 1 Step 3 (`_generate_ai_summary`) |
| 基础统计（对话数、消息数、知识库、记忆） | Task 1 Step 3 |
| 仪表盘视图（问候区+统计卡片+最近话题+快捷入口） | Task 2 + Task 4 |
| 经典视图保留 | Task 2 + Task 4 |
| 视图切换按钮 | Task 2 + Task 4 |
| localStorage 持久化 | Task 3 + Task 4 |
| 骨架屏加载状态 | Task 2 (HTML) + Task 4 (JS) |
| API 超时/失败降级 | Task 3 Step 2 (`showDashboardFallback`) |
| 无历史数据回退 | Task 1 Step 3 (greeting 和 summary fallback) |

### Placeholder 扫描

- [x] 无 "TBD"/"TODO"
- [x] 无 "implement later"
- [x] 所有步骤包含具体代码
- [x] 无模糊描述

### 类型一致性

- [x] `_generate_welcome_summary` 返回 `dict`（与测试一致）
- [x] `stats` 字段名在前后端一致
- [x] `recent_topics` 结构在前后端一致
- [x] `localStorage` key `metaclaw_welcome_view` 全局一致
