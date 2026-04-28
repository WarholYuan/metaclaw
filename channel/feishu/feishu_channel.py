"""
飞书通道接入

支持两种事件接收模式:
1. webhook模式: 通过HTTP服务器接收事件(需要公网IP)
2. websocket模式: 通过长连接接收事件(本地开发友好)

通过配置项 feishu_event_mode 选择模式: "webhook" 或 "websocket"

@author Saboteur7
@Date 2023/11/19
"""

import importlib.util
import json
import logging
import os
import re
import ssl
import threading
import time
# -*- coding=utf-8 -*-
import uuid

import requests
import web

from bridge.context import Context
from bridge.context import ContextType
from bridge.bridge import Bridge
from bridge.reply import Reply, ReplyType
from channel.chat_channel import ChatChannel, check_prefix
from channel.feishu.feishu_message import FeishuMessage
from common import utils
from common.expired_dict import ExpiredDict
from common.log import logger
from common.session_cancel import clear_cancel, request_cancel
from common.session_tmp import get_session_tmp_dir
from common.singleton import singleton
from config import conf

# Suppress verbose logs from Lark SDK
logging.getLogger("Lark").setLevel(logging.WARNING)

URL_VERIFICATION = "url_verification"
ABORT_KEYWORDS = ("停止", "取消", "abort", "cancel", "别做了")
NEW_SESSION_COMMANDS = ("/new", "／new")

# Lazy-check for lark_oapi SDK availability without importing it at module level.
# The full `import lark_oapi` pulls in 10k+ files and takes 4-10s, so we defer
# the actual import to _startup_websocket() where it is needed.
LARK_SDK_AVAILABLE = importlib.util.find_spec("lark_oapi") is not None
lark = None  # will be populated on first use via _ensure_lark_imported()


def _ensure_lark_imported():
    """Import lark_oapi on first use (takes 4-10s due to 10k+ source files)."""
    global lark
    if lark is None:
        import lark_oapi as _lark
        lark = _lark
    return lark


@singleton
class FeiShuChanel(ChatChannel):
    feishu_app_id = conf().get('feishu_app_id')
    feishu_app_secret = conf().get('feishu_app_secret')
    feishu_token = conf().get('feishu_token')
    feishu_event_mode = conf().get('feishu_event_mode', 'websocket')  # webhook 或 websocket

    def __init__(self):
        super().__init__()
        # 历史消息id暂存，用于幂等控制
        self.receivedMsgs = ExpiredDict(60 * 60 * 7.1)
        self._http_server = None
        self._ws_client = None
        self._ws_thread = None
        self._bot_open_id = None  # cached bot open_id for @-mention matching
        self._stream_states = {}
        self._feishu_session_states = {}
        logger.debug("[FeiShu] app_id={}, app_secret={}, verification_token={}, event_mode={}".format(
            self.feishu_app_id, self.feishu_app_secret, self.feishu_token, self.feishu_event_mode))
        # 无需群校验和前缀
        conf()["group_name_white_list"] = ["ALL_GROUP"]
        conf()["single_chat_prefix"] = [""]

        # 验证配置
        if self.feishu_event_mode == 'websocket' and not LARK_SDK_AVAILABLE:
            logger.error("[FeiShu] websocket mode requires lark_oapi. Please install: pip install lark-oapi")
            raise Exception("lark_oapi not installed")

    def startup(self):
        self.feishu_app_id = conf().get('feishu_app_id')
        self.feishu_app_secret = conf().get('feishu_app_secret')
        self.feishu_token = conf().get('feishu_token')
        self.feishu_event_mode = conf().get('feishu_event_mode', 'websocket')
        self._fetch_bot_open_id()
        if self.feishu_event_mode == 'websocket':
            self._startup_websocket()
        else:
            self._startup_webhook()

    def _fetch_bot_open_id(self):
        """Fetch the bot's own open_id via API so we can match @-mentions without feishu_bot_name."""
        try:
            access_token = self.fetch_access_token()
            if not access_token:
                logger.warning("[FeiShu] Cannot fetch bot info: no access_token")
                return
            headers = {"Authorization": "Bearer " + access_token}
            resp = requests.get("https://open.feishu.cn/open-apis/bot/v3/info/", headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    self._bot_open_id = data.get("bot", {}).get("open_id")
                    logger.info(f"[FeiShu] Bot open_id fetched: {self._bot_open_id}")
                else:
                    logger.warning(f"[FeiShu] Fetch bot info failed: code={data.get('code')}, msg={data.get('msg')}")
        except Exception as e:
            logger.warning(f"[FeiShu] Fetch bot open_id error: {e}")

    def _fetch_user_name(self, open_id: str) -> str:
        """通过飞书 Contact API 获取用户昵称，失败时返回 open_id。"""
        try:
            access_token = self.fetch_access_token()
            if not access_token:
                return open_id
            headers = {"Authorization": "Bearer " + access_token}
            url = f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}?user_id_type=open_id"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    name = data.get("data", {}).get("user", {}).get("name", "")
                    if name:
                        logger.info(f"[FeiShu] Fetched name for {open_id}: {name}")
                        return name
        except Exception as e:
            logger.warning(f"[FeiShu] Fetch user name error for {open_id}: {e}")
        return open_id

    def stop(self):
        import ctypes
        logger.info("[FeiShu] stop() called")
        ws_client = self._ws_client
        self._ws_client = None
        ws_thread = self._ws_thread
        self._ws_thread = None
        # Interrupt the ws thread first so its blocking start() unblocks
        if ws_thread and ws_thread.is_alive():
            try:
                tid = ws_thread.ident
                if tid:
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_ulong(tid), ctypes.py_object(SystemExit)
                    )
                    if res == 1:
                        logger.info("[FeiShu] Interrupted ws thread via ctypes")
                    elif res > 1:
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(tid), None)
            except Exception as e:
                logger.warning(f"[FeiShu] Error interrupting ws thread: {e}")
        # lark.ws.Client has no stop() method; thread interruption above is sufficient
        if self._http_server:
            try:
                self._http_server.stop()
                logger.info("[FeiShu] HTTP server stopped")
            except Exception as e:
                logger.warning(f"[FeiShu] Error stopping HTTP server: {e}")
            self._http_server = None
        logger.info("[FeiShu] stop() completed")

    def _startup_webhook(self):
        """启动HTTP服务器接收事件(webhook模式)"""
        logger.debug("[FeiShu] Starting in webhook mode...")
        urls = (
            '/', 'channel.feishu.feishu_channel.FeishuController'
        )
        app = web.application(urls, globals(), autoreload=False)
        port = conf().get("feishu_port", 9891)
        func = web.httpserver.StaticMiddleware(app.wsgifunc())
        func = web.httpserver.LogMiddleware(func)
        server = web.httpserver.WSGIServer(("0.0.0.0", port), func)
        self._http_server = server
        try:
            server.start()
        except (KeyboardInterrupt, SystemExit):
            server.stop()

    def _startup_websocket(self):
        """启动长连接接收事件(websocket模式)"""
        _ensure_lark_imported()
        logger.debug("[FeiShu] Starting in websocket mode...")

        # 创建事件处理器
        def handle_message_event(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
            """处理接收消息事件 v2.0"""
            try:
                event_dict = json.loads(lark.JSON.marshal(data))
                event = event_dict.get("event", {})
                msg = event.get("message", {})

                # Skip group messages that don't @-mention the bot (reduce log noise)
                if msg.get("chat_type") == "group" and not msg.get("mentions") and msg.get("message_type") == "text":
                    return

                logger.debug(f"[FeiShu] websocket receive event: {lark.JSON.marshal(data, indent=2)}")

                # 处理消息
                self._handle_message_event(event)

            except Exception as e:
                logger.error(f"[FeiShu] websocket handle message error: {e}", exc_info=True)

        def handle_message_read_event(data) -> None:
            """Ignore read-receipt events if the app subscribed to them."""
            logger.debug("[FeiShu] websocket message read event ignored")

        # 构建事件分发器
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message_event) \
            .register_p2_im_message_message_read_v1(handle_message_read_event) \
            .build()

        def start_client_with_retry():
            """Run ws client in this thread with its own event loop to avoid conflicts."""
            import asyncio
            import ssl as ssl_module
            original_create_default_context = ssl_module.create_default_context

            def create_unverified_context(*args, **kwargs):
                context = original_create_default_context(*args, **kwargs)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                return context

            # lark_oapi.ws.client captures the event loop at module-import time as a module-
            # level global variable.  When a previous ws thread is force-killed via ctypes its
            # loop may still be marked as "running", which causes the next ws_client.start()
            # call (in this new thread) to raise "This event loop is already running".
            # Fix: replace the module-level loop with a brand-new, idle loop before starting.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                import lark_oapi.ws.client as _lark_ws_client_mod
                _lark_ws_client_mod.loop = loop
            except Exception:
                pass

            startup_error = None
            for attempt in range(2):
                try:
                    if attempt == 1:
                        logger.warning("[FeiShu] Retrying with SSL verification disabled...")
                        ssl_module.create_default_context = create_unverified_context
                        ssl_module._create_unverified_context = create_unverified_context

                    ws_client = lark.ws.Client(
                        self.feishu_app_id,
                        self.feishu_app_secret,
                        event_handler=event_handler,
                        log_level=lark.LogLevel.WARNING
                    )
                    self._ws_client = ws_client
                    logger.debug("[FeiShu] Websocket client starting...")
                    ws_client.start()
                    break

                except (SystemExit, KeyboardInterrupt):
                    logger.info("[FeiShu] Websocket thread received stop signal")
                    break
                except Exception as e:
                    error_msg = str(e)
                    is_ssl_error = ("CERTIFICATE_VERIFY_FAILED" in error_msg
                                    or "certificate verify failed" in error_msg.lower())
                    if is_ssl_error and attempt == 0:
                        logger.warning(f"[FeiShu] SSL error: {error_msg}, retrying...")
                        continue
                    logger.error(f"[FeiShu] Websocket client error: {e}", exc_info=True)
                    startup_error = error_msg
                    ssl_module.create_default_context = original_create_default_context
                    break
            if startup_error:
                self.report_startup_error(startup_error)
            try:
                loop.close()
            except Exception:
                pass
            logger.info("[FeiShu] Websocket thread exited")

        ws_thread = threading.Thread(target=start_client_with_retry, daemon=True)
        self._ws_thread = ws_thread
        ws_thread.start()
        logger.info("[FeiShu] ✅ Websocket thread started, ready to receive messages")
        ws_thread.join()

    def _is_mention_bot(self, mentions: list) -> bool:
        """Check whether any mention in the list refers to this bot.

        Priority:
        1. Match by open_id (obtained from /bot/v3/info at startup, no config needed)
        2. Fallback to feishu_bot_name config for backward compatibility
        3. If neither is available, assume the first mention is the bot (Feishu only
           delivers group messages that @-mention the bot, so this is usually correct)
        """
        if self._bot_open_id:
            return any(
                m.get("id", {}).get("open_id") == self._bot_open_id
                for m in mentions
            )
        bot_name = conf().get("feishu_bot_name")
        if bot_name:
            return any(m.get("name") == bot_name for m in mentions)
        # Feishu event subscription only delivers messages that @-mention the bot,
        # so reaching here means the bot was indeed mentioned.
        return True

    def _get_session_id(self, feishu_msg: FeishuMessage, chat_id: str, is_group: bool) -> str:
        if is_group:
            if conf().get("group_shared_session", True):
                return chat_id
            return f"{feishu_msg.from_user_id}:{chat_id}"
        return feishu_msg.from_user_id

    def _is_abort_message(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        return any(keyword in normalized for keyword in ABORT_KEYWORDS)

    def _is_new_session_message(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        return normalized in NEW_SESSION_COMMANDS

    def _handle_new_session_message(self, session_id: str, feishu_msg: FeishuMessage, receive_id_type: str):
        request_cancel(session_id)
        self.cancel_session(session_id)
        self._feishu_session_states.pop(session_id, None)

        for stream_id, stream_state in list(self._stream_states.items()):
            context = stream_state.get("context") or {}
            if context.get("session_id") == session_id:
                self._stream_states.pop(stream_id, None)

        try:
            agent_bridge = Bridge().get_agent_bridge()
            agent_bridge.clear_session(session_id)
        except Exception as e:
            logger.warning(f"[FeiShu] clear agent session failed, session_id={session_id}, error={e}")

        try:
            from agent.memory.conversation_store import get_conversation_store
            get_conversation_store().clear_context(session_id)
        except Exception as e:
            logger.warning(f"[FeiShu] clear conversation context failed, session_id={session_id}, error={e}")

        context = self._compose_context(
            ContextType.TEXT,
            "/new",
            isgroup=feishu_msg.is_group,
            msg=feishu_msg,
            receive_id_type=receive_id_type,
            no_need_at=True
        )
        if context:
            self._send_status_card("已清空当前对话上下文。下一条消息会从新的上下文开始。", context, title="已新建会话", template="green")
        logger.info(f"[FeiShu] new session requested, session_id={session_id}")

    def _handle_abort_message(self, session_id: str, feishu_msg: FeishuMessage, receive_id_type: str):
        request_cancel(session_id)
        state = self._feishu_session_states.get(session_id)
        if state:
            state["cancel_requested"] = True
            stream_state = self._stream_states.get(state.get("stream_id"))
            if stream_state:
                stream_state["status"] = "已请求取消"
                stream_state["disabled"] = True
                stream_state["override_answer"] = "已收到取消请求。正在停止可取消的后续任务。"
                if stream_state.get("message_id"):
                    self._update_stream_card(
                        stream_state["message_id"],
                        stream_state,
                        stream_state.get("access_token")
                    )
        self.cancel_session(session_id)
        context = self._compose_context(
            ContextType.TEXT,
            "cancel",
            isgroup=feishu_msg.is_group,
            msg=feishu_msg,
            receive_id_type=receive_id_type,
            no_need_at=True
        )
        if context:
            self._send_status_card("已取消当前会话中排队的任务。", context, title="已取消")
        logger.info(f"[FeiShu] abort requested, session_id={session_id}")

    def _get_context_timeout_seconds(self, context: Context):
        if context.get("channel_type") == self.channel_type:
            return conf().get("feishu_request_timeout_seconds", 1800)
        return None

    def _on_context_timeout(self, context: Context):
        session_id = context.get("session_id")
        state_ref = self._feishu_session_states.get(session_id)
        stream_state = self._stream_states.get(state_ref.get("stream_id")) if state_ref else None
        timeout_seconds = conf().get("feishu_request_timeout_seconds", 1800)
        message = f"任务执行超过 {timeout_seconds} 秒，已停止等待并释放当前会话队列。你可以重新发送问题。"
        if stream_state:
            stream_state["status"] = "已超时"
            stream_state["phase"] = "timeout"
            stream_state["disabled"] = True
            stream_state["override_answer"] = message
            if stream_state.get("message_id"):
                self._update_stream_card(
                    stream_state["message_id"],
                    stream_state,
                    stream_state.get("access_token")
                )
            else:
                stream_state["message_id"] = self._send_stream_card(
                    stream_state,
                    context,
                    stream_state.get("access_token")
                )
        else:
            self._send_status_card(message, context, title="处理超时", template="yellow")
        if session_id in self._feishu_session_states:
            self._feishu_session_states[session_id]["status"] = "timeout"
        logger.warning(f"[FeiShu] context timeout, session_id={session_id}")

    def _handle_message_event(self, event: dict):
        """
        处理消息事件的核心逻辑
        webhook和websocket模式共用此方法
        """
        if not event.get("message") or not event.get("sender"):
            logger.warning(f"[FeiShu] invalid message, event={event}")
            return

        msg = event.get("message")

        # 幂等判断
        msg_id = msg.get("message_id")
        if self.receivedMsgs.get(msg_id):
            logger.warning(f"[FeiShu] repeat msg filtered, msg_id={msg_id}")
            return
        self.receivedMsgs[msg_id] = True

        # Filter out stale messages from before channel startup (offline backlog)
        import time as _time
        create_time_ms = msg.get("create_time")
        if create_time_ms:
            msg_age_s = _time.time() - int(create_time_ms) / 1000
            if msg_age_s > 60:
                logger.warning(f"[FeiShu] stale msg filtered (age={msg_age_s:.0f}s), msg_id={msg_id}")
                return

        is_group = False
        chat_type = msg.get("chat_type")

        if chat_type == "group":
            if not msg.get("mentions") and msg.get("message_type") == "text":
                # 群聊中未@不响应
                return
            if msg.get("mentions") and msg.get("message_type") == "text":
                if not self._is_mention_bot(msg.get("mentions")):
                    return
            # 群聊
            is_group = True
            receive_id_type = "chat_id"
        elif chat_type == "p2p":
            receive_id_type = "open_id"
        else:
            logger.warning("[FeiShu] message ignore")
            return

        # 构造飞书消息对象
        feishu_msg = FeishuMessage(event, is_group=is_group, access_token=self.fetch_access_token())
        if not feishu_msg:
            return

        # 注册用户并检查权限
        from common.user_manager import UserManager, PERMISSION_BLOCKED
        user_mgr = UserManager()
        sender_open_id = feishu_msg.from_user_id
        # 新用户或昵称未设置时，通过飞书 API 获取真实昵称
        existing = user_mgr._users.get(sender_open_id)
        needs_name = existing is None or existing.get("name") == sender_open_id
        display_name = self._fetch_user_name(sender_open_id) if needs_name else sender_open_id
        user_mgr.register(sender_open_id, name=display_name)
        if user_mgr.get_permission(sender_open_id) == PERMISSION_BLOCKED:
            context = self._compose_context(
                ContextType.TEXT, "blocked",
                isgroup=feishu_msg.is_group, msg=feishu_msg,
                receive_id_type=receive_id_type, no_need_at=True
            )
            if context:
                self._send_status_card("你没有使用权限，请联系管理员。", context, title="无权限", template="red")
            return

        # 处理文件缓存逻辑
        from channel.file_cache import get_file_cache
        file_cache = get_file_cache()

        session_id = self._get_session_id(feishu_msg, msg.get("chat_id"), is_group)

        if feishu_msg.ctype == ContextType.TEXT and self._is_new_session_message(feishu_msg.content):
            self._handle_new_session_message(session_id, feishu_msg, receive_id_type)
            return

        if feishu_msg.ctype == ContextType.TEXT and self._is_abort_message(feishu_msg.content):
            self._handle_abort_message(session_id, feishu_msg, receive_id_type)
            return

        session_state = self._feishu_session_states.get(session_id)
        if session_state and session_state.get("status") == "running":
            context = self._compose_context(
                ContextType.TEXT,
                "busy",
                isgroup=feishu_msg.is_group,
                msg=feishu_msg,
                receive_id_type=receive_id_type,
                no_need_at=True
            )
            if context:
                self._send_status_card(
                    "当前会话已有任务在执行。请等待当前回复完成，或发送“停止”取消后再重新提问。",
                    context,
                    title="正在处理上一条"
                )
            return

        # 如果是单张图片消息，缓存起来
        if feishu_msg.ctype == ContextType.IMAGE:
            if hasattr(feishu_msg, 'image_path') and feishu_msg.image_path:
                file_cache.add(session_id, feishu_msg.image_path, file_type='image')
                logger.info(f"[FeiShu] Image cached for session {session_id}, waiting for user query...")
            # 单张图片不直接处理，等待用户提问
            return

        # 如果是文本消息，检查是否有缓存的文件
        if feishu_msg.ctype == ContextType.TEXT:
            cached_files = file_cache.get(session_id)
            if cached_files:
                # 将缓存的文件附加到文本消息中
                file_refs = []
                for file_info in cached_files:
                    file_path = file_info['path']
                    file_type = file_info['type']
                    if file_type == 'image':
                        file_refs.append(f"[图片: {file_path}]")
                    elif file_type == 'video':
                        file_refs.append(f"[视频: {file_path}]")
                    else:
                        file_refs.append(f"[文件: {file_path}]")

                feishu_msg.content = feishu_msg.content + "\n" + "\n".join(file_refs)
                logger.info(f"[FeiShu] Attached {len(cached_files)} cached file(s) to user query")
                # 清除缓存
                file_cache.clear(session_id)

        context = self._compose_context(
            feishu_msg.ctype,
            feishu_msg.content,
            isgroup=is_group,
            msg=feishu_msg,
            receive_id_type=receive_id_type,
            no_need_at=True
        )
        if context:
            context["on_event"] = self._make_stream_callback(context)
            context["allowed_skills"] = user_mgr.get_allowed_skills(feishu_msg.from_user_id)
            context["allowed_tools"] = user_mgr.get_allowed_tools(feishu_msg.from_user_id)
            self.produce(context)
        logger.debug(f"[FeiShu] query={feishu_msg.content}, type={feishu_msg.ctype}")

    def _make_stream_callback(self, context: Context):
        stream_id = uuid.uuid4().hex
        session_id = context.get("session_id")
        context["feishu_stream_id"] = stream_id
        clear_cancel(session_id)
        self._stream_states[stream_id] = {
            "message_id": None,
            "question": context.content,
            "committed": "",
            "current": "",
            "reasoning": "",
            "tools": [],
            "status": "已收到，正在处理",
            "phase": "received",
            "started_at": time.time(),
            "last_update_time": 0,
            "last_update_len": 0,
            "context": context,
            "access_token": context.get("msg").access_token if context.get("msg") else self.fetch_access_token(),
        }
        if session_id:
            self._feishu_session_states[session_id] = {
                "status": "running",
                "stream_id": stream_id,
                "cancel_requested": False,
                "started_at": time.time(),
            }

        self._stream_states[stream_id]["message_id"] = self._send_stream_card(
            self._stream_states[stream_id],
            context,
            self._stream_states[stream_id]["access_token"]
        )
        self._schedule_stream_heartbeat(stream_id)

        def _ensure_stream_message(state: dict):
            if state.get("message_id"):
                return
            message_id = self._send_stream_card(
                state,
                state["context"],
                state["access_token"]
            )
            state["message_id"] = message_id

        def _push_stream(state: dict, force: bool = False):
            if state.get("disabled"):
                return
            content = self._render_stream_markdown(state)
            now = time.time()
            if not force and now - state["last_update_time"] < 0.5:
                return
            if not force and len(content) - state["last_update_len"] < 80:
                return
            _ensure_stream_message(state)
            if not state.get("message_id"):
                return
            if self._update_stream_card(state["message_id"], state, state["access_token"]):
                state["last_update_time"] = now
                state["last_update_len"] = len(content)
            else:
                state["disabled"] = True

        def on_event(event: dict):
            state = self._stream_states.get(stream_id)
            if not state:
                return

            event_type = event.get("type")
            data = event.get("data", {})

            if event_type == "turn_start":
                state["status"] = "正在理解问题"
                state["phase"] = "thinking"
                state["current"] = ""
                _push_stream(state, force=True)
            elif event_type == "reasoning_update":
                delta = data.get("delta", "")
                if delta:
                    state["reasoning"] += delta
                    _push_stream(state)
            elif event_type == "message_update":
                delta = data.get("delta", "")
                if delta:
                    state["status"] = "正在回复"
                    state["phase"] = "answering"
                    state["current"] += delta
                    _push_stream(state)
            elif event_type == "message_end":
                tool_calls = data.get("tool_calls", [])
                if tool_calls and state["current"].strip():
                    state["committed"] += state["current"].strip() + "\n\n---\n\n"
                    state["current"] = ""
                    state["status"] = "准备使用工具"
                    state["phase"] = "tooling"
                else:
                    state["status"] = "整理最终回复"
                    state["phase"] = "finalizing"
                _push_stream(state, force=True)
            elif event_type == "tool_execution_start":
                tool_name = data.get("tool_name", "unknown")
                tool_label = self._format_tool_action_for_user(tool_name)
                state["status"] = tool_label
                state["phase"] = "tooling"
                state["tools"].append({
                    "name": tool_name,
                    "label": tool_label,
                    "status": "running",
                    "arguments": data.get("arguments") or {},
                    "started_at": time.time(),
                })
                _push_stream(state, force=True)
            elif event_type == "tool_execution_end":
                tool_name = data.get("tool_name", "unknown")
                for tool in reversed(state["tools"]):
                    if tool.get("name") == tool_name and tool.get("status") == "running":
                        tool["status"] = data.get("status", "done")
                        tool["execution_time"] = data.get("execution_time", 0)
                        tool["result"] = data.get("result")
                        break
                state["status"] = "工具处理完成，正在整理回复"
                state["phase"] = "answering"
                _push_stream(state, force=True)
            elif event_type == "agent_end":
                state["status"] = "已完成"
                state["phase"] = "done"
                state["done"] = True
                if session_id in self._feishu_session_states:
                    self._feishu_session_states[session_id]["status"] = "done"
                _push_stream(state, force=True)
            elif event_type == "error":
                state["status"] = "处理失败"
                state["phase"] = "error"
                state["done"] = True
                state["override_answer"] = "处理失败，可以直接重试；如果连续失败，请发送“停止”后再问一次。"
                _push_stream(state, force=True)

        return on_event

    def _send_text_message(self, content: str, context: Context, access_token: str = None):
        return self._send_message("text", {"text": content}, context, access_token=access_token)

    def _truncate_card_text(self, text: str, limit: int = 1800) -> str:
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        remaining = len(text) - limit
        return text[:limit].rstrip() + f"\n\n... 内容较长，已收起后续 {remaining} 字。"

    def _normalize_card_markdown(self, text: str, limit: int = None) -> str:
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            return ""
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = self._soften_oversized_code_blocks(text)
        text = self._soften_oversized_quotes(text)
        if limit:
            text = self._truncate_card_text(text, limit)
        return text

    def _soften_oversized_code_blocks(self, text: str) -> str:
        max_code_chars = 1200

        def replace(match):
            fence = match.group(1)
            lang = match.group(2) or ""
            body = match.group(3) or ""
            if len(body) <= max_code_chars:
                return match.group(0)
            short = body[:max_code_chars].rstrip()
            return f"{fence}{lang}\n{short}\n... 代码较长，已收起。\n{fence}"

        return re.sub(r"(`{3,})([^\n`]*)\n([\s\S]*?)\n\1", replace, text)

    def _soften_oversized_quotes(self, text: str) -> str:
        lines = text.split("\n")
        result = []
        quote_count = 0
        skipped = 0
        for line in lines:
            if line.startswith(">"):
                quote_count += 1
                if quote_count > 8:
                    skipped += 1
                    continue
            else:
                if skipped:
                    result.append(f"> ... 已收起 {skipped} 行引用。")
                quote_count = 0
                skipped = 0
            result.append(line)
        if skipped:
            result.append(f"> ... 已收起 {skipped} 行引用。")
        return "\n".join(result)

    def _format_question_preview(self, question: str) -> str:
        limit = conf().get("feishu_question_preview_chars", 360)
        preview = self._normalize_card_markdown(question, limit)
        preview = re.sub(r"\n{2,}", "\n", preview).strip()
        return preview or "（无文本内容）"

    def _format_answer_for_card(self, answer: str) -> str:
        limit = conf().get("feishu_answer_card_chars", 4200)
        notice_threshold = conf().get("feishu_long_answer_notice_threshold", 3600)
        normalized = self._normalize_card_markdown(answer, limit)
        if answer and len(answer) > notice_threshold and "内容较长" not in normalized:
            normalized += "\n\n提示：回复内容较长，已优先展示关键部分。"
        return normalized

    def _normalize_final_answer_markdown(self, text: str) -> str:
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text

    def _split_answer_for_cards(self, answer: str) -> list:
        text = self._normalize_final_answer_markdown(answer)
        if not text:
            return [""]
        limit = conf().get("feishu_answer_card_chars", 3600)
        if len(text) <= limit:
            return [text]

        chunks = []
        current = []
        current_len = 0
        fence = None

        def flush_chunk():
            nonlocal current, current_len
            if not current:
                return
            chunk = "\n".join(current).rstrip()
            if fence and not chunk.endswith(fence):
                chunk = f"{chunk}\n{fence}"
            if chunk:
                chunks.append(chunk)
            current = [fence] if fence else []
            current_len = len(fence) + 1 if fence else 0

        def append_line(line: str):
            nonlocal current_len
            if len(line) > limit:
                start = 0
                while start < len(line):
                    segment = line[start:start + limit - 200]
                    if current_len + len(segment) + 1 > limit and current:
                        flush_chunk()
                    current.append(segment)
                    current_len += len(segment) + 1
                    start += len(segment)
                return
            if current_len + len(line) + 1 > limit and current:
                flush_chunk()
            current.append(line)
            current_len += len(line) + 1

        for line in text.split("\n"):
            stripped = line.strip()
            fence_match = re.match(r"^(`{3,}|~{3,})", stripped)
            append_line(line)
            if fence_match:
                marker = fence_match.group(1)
                if fence is None:
                    fence = marker
                elif marker.startswith(fence[0]):
                    fence = None

        if current:
            chunks.append("\n".join(current).rstrip())
        return chunks

    def _build_continuation_card(self, chunk: str, index: int, total: int) -> dict:
        title = "回复完成" if index == total else "正在回复"
        suffix = f"\n\n（第 {index}/{total} 张）" if total > 1 else ""
        return self._build_simple_card(chunk + suffix, title=title, template="green" if index == total else "grey")

    def _send_status_card(self, content: str, context: Context, title: str = "状态更新", template: str = "grey"):
        access_token = context.get("msg").access_token if context.get("msg") else self.fetch_access_token()
        return self._send_message(
            "interactive",
            json.dumps(self._build_simple_card(content, title=title, template=template), ensure_ascii=False),
            context,
            access_token=access_token
        )

    def _send_answer_continuation_cards(self, chunks: list, context: Context, access_token: str = None):
        total = len(chunks)
        for index, chunk in enumerate(chunks[1:], start=2):
            self._send_message(
                "interactive",
                json.dumps(self._build_continuation_card(chunk, index, total), ensure_ascii=False),
                context,
                access_token=access_token
            )
            time.sleep(0.2)

    def _send_paginated_answer_cards(self, answer: str, context: Context, access_token: str = None) -> bool:
        chunks = self._split_answer_for_cards(answer)
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            self._send_message(
                "interactive",
                json.dumps(self._build_continuation_card(chunk, index, total), ensure_ascii=False),
                context,
                access_token=access_token
            )
            time.sleep(0.2)
        return True

    def _format_tool_args(self, args: dict) -> str:
        if not args:
            return ""
        try:
            rendered = json.dumps(args, ensure_ascii=False)
        except Exception:
            rendered = str(args)
        return self._truncate_card_text(rendered, 180)

    def _format_tool_name_for_user(self, tool_name: str) -> str:
        labels = {
            "read": "读取文件",
            "write": "写入文件",
            "edit": "编辑文件",
            "bash": "执行命令",
            "ls": "查看目录",
            "web_search": "搜索资料",
            "web_fetch": "读取网页",
            "browser": "操作浏览器",
            "memory": "查询记忆",
            "scheduler": "处理日程任务",
            "send": "发送文件",
        }
        return labels.get(tool_name, tool_name)

    def _format_tool_action_for_user(self, tool_name: str) -> str:
        labels = {
            "read": "正在查看项目文件",
            "open": "正在查看项目文件",
            "write": "正在写入文件",
            "edit": "正在修改文件",
            "bash": "正在运行命令",
            "exec": "正在运行命令",
            "command": "正在运行命令",
            "ls": "正在查看目录",
            "grep": "正在搜索文本",
            "glob": "正在查找文件",
            "web_search": "正在搜索资料",
            "web_fetch": "正在读取网页",
            "browser": "正在操作浏览器",
            "memory": "正在查询记忆",
            "scheduler": "正在处理日程任务",
            "send": "正在发送文件",
        }
        normalized = (tool_name or "").replace("-", "_").lower()
        for key, label in labels.items():
            if normalized == key or normalized.startswith(f"{key}_"):
                return label
        return f"正在使用工具：{tool_name or '未知工具'}"

    def _redact_inline_secrets(self, text: str) -> str:
        if not text:
            return ""
        redacted = re.sub(
            r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)(\s*[=:]\s*|\s+)[^\s&]+",
            r"\1\2[已隐藏]",
            text,
        )
        return self._truncate_card_text(redacted, 160)

    def _extract_tool_detail_for_user(self, tool: dict) -> str:
        args = tool.get("arguments") or {}
        if not isinstance(args, dict):
            return ""
        raw_name = tool.get("name", "unknown")
        normalized = (raw_name or "").replace("-", "_").lower()

        def first_text(*keys):
            for key in keys:
                value = args.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        if normalized.startswith(("read", "open", "write", "edit")):
            path = first_text("file_path", "path", "file")
            return os.path.basename(path) if path else ""
        if normalized.startswith(("ls", "glob")):
            return first_text("path", "pattern", "glob")
        if normalized.startswith("grep"):
            pattern = first_text("pattern", "query", "q")
            target = first_text("path", "glob")
            return f"{pattern} / {target}" if pattern and target else pattern or target
        if normalized.startswith(("bash", "exec", "command")):
            return self._redact_inline_secrets(first_text("description", "command", "cmd", "script"))
        if normalized.startswith("web_search"):
            return first_text("query", "q")
        if normalized.startswith(("web_fetch", "browser")):
            return self._redact_inline_secrets(first_text("url", "href"))
        return self._truncate_card_text(first_text("description", "query", "name", "target"), 160)

    def _should_expand_card_details(self, state: dict, elapsed: int) -> bool:
        if state.get("force_detail"):
            return True
        if state.get("tools"):
            return True
        if state.get("phase") in ("tooling", "error"):
            return True
        threshold = conf().get("feishu_detail_expand_threshold_seconds", 10)
        return elapsed >= threshold

    def _format_elapsed_for_user(self, elapsed: int) -> str:
        if elapsed < 60:
            return f"{elapsed}s"
        return f"{elapsed // 60}m {elapsed % 60}s"

    def _get_progress_hint(self, state: dict, elapsed: int) -> str:
        phase = state.get("phase")
        if phase == "received":
            return "收到，我正在处理这条消息。"
        if phase == "thinking":
            if elapsed >= 30:
                return "任务较长，我还在分析上下文，会继续更新进度。"
            if elapsed >= 10:
                return "还在处理，正在整理上下文和可用信息。"
            return "正在理解问题，马上给你结果。"
        if phase == "tooling":
            if elapsed >= 30:
                return "任务较长，正在等待工具结果。"
            return "正在调用工具处理这件事。"
        if phase == "finalizing":
            return "结果已基本完成，正在整理成可读回复。"
        return "正在生成回复。"

    def _render_stream_markdown(self, state: dict, override_answer: str = None) -> str:
        elapsed = int(time.time() - state.get("started_at", time.time()))
        status = state.get("status") or "处理中"
        lines = [f"状态：{status} · {self._format_elapsed_for_user(elapsed)}"]

        tools = state.get("tools") or []
        if tools:
            lines.append(f"\n{self._format_compact_tool_summary(tools)}")

        reasoning = self._normalize_card_markdown(state.get("reasoning", ""), 700)
        if reasoning:
            lines.append(f"\n**思考摘要**\n{reasoning}")

        answer = override_answer
        if answer is None:
            answer = (state.get("committed") or "") + (state.get("current") or "")
        if state.get("final_answer_card"):
            answer = self._normalize_final_answer_markdown(answer)
        else:
            answer = self._format_answer_for_card(answer)
        if answer:
            lines.append(f"\n**回复**\n{answer}")
        elif not reasoning and not tools:
            lines.append(f"\n{self._get_progress_hint(state, elapsed)}")

        return self._truncate_card_text("\n".join(lines), 7800)

    def _get_stream_card_header(self, state: dict) -> tuple:
        phase = state.get("phase")
        if phase == "error":
            return "处理失败", "red"
        if phase == "timeout":
            return "处理超时", "yellow"
        if phase == "received":
            return "已收到", "grey"
        if phase == "thinking":
            return "正在理解", "grey"
        if state.get("disabled") and state.get("status") == "已请求取消":
            return "正在取消", "grey"
        if state.get("status") == "已取消":
            return "已取消", "grey"
        if state.get("done") or phase == "done":
            return "回复完成", "green"
        if phase == "tooling":
            return "正在使用工具", "grey"
        if phase in ("answering", "finalizing"):
            return "正在回复", "grey"
        return "正在回复", "grey"

    def _card_text_element(self, content: str) -> dict:
        return {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": content or "（空内容）"
            }
        }

    def _card_note_element(self, content: str) -> dict:
        return {
            "tag": "note",
            "elements": [
                {
                    "tag": "lark_md",
                    "content": content or "（空内容）"
                }
            ]
        }

    def _split_markdown_blocks(self, text: str) -> list:
        lines = (text or "").split("\n")
        blocks = []
        buf = []
        i = 0

        def flush_text():
            nonlocal buf
            if buf:
                content = "\n".join(buf).strip()
                if content:
                    blocks.append(("text", content))
                buf = []

        while i < len(lines):
            line = lines[i]
            fence_match = re.match(r"^(`{3,}|~{3,})([^\n`]*)\s*$", line.strip())
            if fence_match:
                flush_text()
                fence = fence_match.group(1)
                lang = (fence_match.group(2) or "").strip()
                code_lines = []
                i += 1
                while i < len(lines):
                    if lines[i].strip().startswith(fence):
                        break
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(("code", {"lang": lang, "code": "\n".join(code_lines)}))
                if i < len(lines):
                    i += 1
                continue

            if self._is_markdown_table_at(lines, i):
                flush_text()
                table_lines = [lines[i]]
                i += 1
                while i < len(lines) and self._looks_like_table_row(lines[i]) and lines[i].strip():
                    table_lines.append(lines[i])
                    i += 1
                blocks.append(("table", table_lines))
                continue

            buf.append(line)
            i += 1

        flush_text()
        return blocks

    def _normalize_table_line(self, line: str) -> str:
        return (line or "").replace("｜", "|")

    def _looks_like_table_row(self, line: str) -> bool:
        normalized = self._normalize_table_line(line).strip()
        if "|" not in normalized:
            return False
        cells = [cell.strip() for cell in normalized.strip("|").split("|")]
        return len(cells) >= 2 and any(cells)

    def _is_table_separator_row(self, line: str) -> bool:
        normalized = self._normalize_table_line(line).strip()
        if "|" not in normalized:
            return False
        cells = [cell.strip() for cell in normalized.strip("|").split("|")]
        if len(cells) < 2:
            return False
        return all(re.match(r"^:?-{3,}:?$", cell or "") for cell in cells)

    def _is_markdown_table_at(self, lines: list, index: int) -> bool:
        if index >= len(lines) or not self._looks_like_table_row(lines[index]):
            return False
        if index + 1 >= len(lines):
            return False
        return self._is_table_separator_row(lines[index + 1]) or self._looks_like_table_row(lines[index + 1])

    def _split_card_text_chunks(self, text: str, limit: int = 1400) -> list:
        text = (text or "").strip()
        if not text:
            return []
        chunks = []
        current = []
        current_len = 0
        for paragraph in re.split(r"\n{2,}", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > limit:
                if current:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0
                for start in range(0, len(paragraph), limit):
                    chunks.append(paragraph[start:start + limit])
                continue
            extra = len(paragraph) + (2 if current else 0)
            if current and current_len + extra > limit:
                chunks.append("\n\n".join(current))
                current = [paragraph]
                current_len = len(paragraph)
            else:
                current.append(paragraph)
                current_len += extra
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    def _format_code_block_for_card(self, code: str, lang: str = "") -> str:
        code = (code or "").rstrip()
        limit = 1800
        if len(code) > limit:
            code = code[:limit].rstrip() + "\n... 代码较长，已收起。"
        lang = re.sub(r"[^A-Za-z0-9_+.#-]", "", lang or "")[:24]
        return f"```{lang}\n{code or ' '}\n```"

    def _parse_table_row(self, line: str) -> list:
        return [cell.strip() for cell in self._normalize_table_line(line).strip().strip("|").split("|")]

    def _strip_inline_markdown(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
        text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def _format_markdown_table_for_card(self, table_lines: list) -> str:
        rows = [self._parse_table_row(line) for line in table_lines if self._looks_like_table_row(line)]
        rows = [row for row in rows if not all(self._is_table_separator_cell(cell) for cell in row)]
        if not rows:
            return ""

        has_header = len(table_lines) > 1 and self._is_table_separator_row(table_lines[1])
        headers = [self._strip_inline_markdown(cell) for cell in rows[0]] if has_header else []
        data_rows = rows[1:] if has_header else rows
        rendered = []
        for raw_row in data_rows[:12]:
            row = [self._strip_inline_markdown(cell) for cell in raw_row]
            if headers:
                row += [""] * (len(headers) - len(row))
                row = row[:len(headers)]
            if not any(row):
                continue

            first = row[0] or "项目"
            if len(row) <= 2:
                rendered.append(f"- **{first}**：{row[1] if len(row) > 1 else ''}".rstrip("："))
                continue

            details = []
            for idx, value in enumerate(row[1:], start=1):
                if not value:
                    continue
                label = headers[idx] if idx < len(headers) and headers[idx] else f"列{idx + 1}"
                details.append(f"{label}：{value}")
            rendered.append(f"- **{first}**")
            rendered.extend(f"  - {item}" for item in details)

        if len(data_rows) > 12:
            rendered.append(f"- ... 已收起 {len(data_rows) - 12} 行")
        return "\n".join(rendered) if rendered else "\n".join(table_lines)

    def _is_table_separator_cell(self, cell: str) -> bool:
        return bool(re.match(r"^:?-{3,}:?$", (cell or "").strip()))

    def _format_card_text_block(self, text: str) -> str:
        lines = []
        for line in (text or "").split("\n"):
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
            if heading:
                title = self._strip_inline_markdown(heading.group(1))
                lines.append(f"**{title}**")
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    def _build_markdown_elements(self, text: str, limit: int = None, heading: str = None) -> list:
        normalized = self._normalize_card_markdown(text, limit)
        elements = []
        if heading:
            elements.append(self._card_text_element(f"**{heading}**"))
        if not normalized:
            elements.append(self._card_text_element("（空内容）"))
            return elements

        for block_type, payload in self._split_markdown_blocks(normalized):
            if block_type == "code":
                elements.append(self._card_text_element(
                    self._format_code_block_for_card(payload.get("code", ""), payload.get("lang", ""))
                ))
            elif block_type == "table":
                elements.append(self._card_text_element(self._format_markdown_table_for_card(payload)))
            else:
                for chunk in self._split_card_text_chunks(payload):
                    elements.append(self._card_text_element(self._format_card_text_block(chunk)))
        return elements

    def _format_tool_status_for_user(self, status_text: str) -> str:
        labels = {
            "running": "进行中",
            "success": "完成",
            "done": "完成",
            "failed": "失败",
            "error": "失败",
        }
        return labels.get(status_text or "", status_text or "未知")

    def _format_compact_tool_summary(self, tools: list) -> str:
        if not tools:
            return ""

        running = 0
        done = 0
        failed = 0
        for tool in tools:
            status = tool.get("status", "running")
            if status in ("failed", "error"):
                failed += 1
            elif status == "running":
                running += 1
            else:
                done += 1

        parts = [f"{len(tools)} 项"]
        if running:
            parts.append(f"进行中 {running}")
        if done:
            parts.append(f"完成 {done}")
        if failed:
            parts.append(f"失败 {failed}")

        active_tool = None
        for tool in reversed(tools):
            if tool.get("status", "running") == "running":
                active_tool = tool
                break
        if active_tool is None:
            active_tool = tools[-1]

        active_name = active_tool.get("label") or self._format_tool_action_for_user(active_tool.get("name", "unknown"))
        active_status = self._format_tool_status_for_user(active_tool.get("status", "running"))
        current = f"当前：{active_name}" if active_status == "进行中" else f"最近：{active_name} {active_status}"
        return f"**工具**：{' · '.join(parts)} · {current}"

    def _should_show_reasoning_summary(self, state: dict, elapsed: int, reasoning: str) -> bool:
        if not reasoning:
            return False
        if state.get("phase") in ("error", "timeout") or state.get("status") == "已取消":
            return True
        if state.get("done"):
            threshold = conf().get("feishu_detail_expand_threshold_seconds", 10)
            return elapsed >= threshold and bool(state.get("tools"))
        return False

    def _build_stream_card(self, content) -> dict:
        if isinstance(content, dict):
            return self._build_stream_state_card(content)
        return self._build_simple_card(content or "收到，我正在处理这条消息。")

    def _build_simple_card(self, content: str, title: str = "MetaClaw 回复", template: str = "grey") -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": template,
                "title": {"tag": "plain_text", "content": title}
            },
            "elements": self._build_markdown_elements(
                content or "（空内容）",
                conf().get("feishu_answer_card_chars", 3600)
            )
        }

    def _build_stream_state_card(self, state: dict) -> dict:
        question = self._format_question_preview(state.get("question", ""))
        elapsed = int(time.time() - state.get("started_at", time.time()))
        status = state.get("status") or "处理中"
        title, template = self._get_stream_card_header(state)

        answer = state.get("override_answer")
        if answer is None:
            answer = (state.get("committed") or "") + (state.get("current") or "")
        answer = self._format_answer_for_card(answer)
        answer_block = answer or self._get_progress_hint(state, elapsed)

        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**回复这条消息**\n> {question}"
                }
            },
            {"tag": "hr"},
        ]
        elements.extend(self._build_markdown_elements(
            answer_block,
            conf().get("feishu_answer_card_chars", 3600),
            heading="正文"
        ))

        tools = state.get("tools") or []
        reasoning_limit = conf().get("feishu_reasoning_summary_chars", 260)
        reasoning = self._normalize_card_markdown(state.get("reasoning", ""), reasoning_limit)
        bottom_sections = []
        if tools:
            bottom_sections.append(self._format_compact_tool_summary(tools))
        meta_lines = [f"**状态**：{status} · {self._format_elapsed_for_user(elapsed)}"]
        bottom_sections.append("\n".join(meta_lines))
        if self._should_show_reasoning_summary(state, elapsed, reasoning):
            bottom_sections.append(f"**思考摘要**\n{reasoning}")

        elements.extend([
            {"tag": "hr"},
            self._card_note_element(
                self._truncate_card_text(
                    "\n\n".join(bottom_sections),
                    conf().get("feishu_footer_card_chars", 900)
                )
            )
        ])

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": template,
                "title": {"tag": "plain_text", "content": title}
            },
            "elements": elements
        }

    def _send_stream_card(self, content, context: Context, access_token: str = None):
        return self._send_message(
            "interactive",
            json.dumps(self._build_stream_card(content), ensure_ascii=False),
            context,
            access_token=access_token
        )

    def _schedule_stream_heartbeat(self, stream_id: str):
        interval = conf().get("feishu_heartbeat_interval_seconds", 20)
        if not interval or interval <= 0:
            return

        def heartbeat():
            state = self._stream_states.get(stream_id)
            if not state or state.get("done") or state.get("disabled"):
                return
            if state.get("message_id"):
                self._update_stream_card(
                    state["message_id"],
                    state,
                    state.get("access_token")
                )
            self._schedule_stream_heartbeat(stream_id)

        timer = threading.Timer(interval, heartbeat)
        timer.daemon = True
        timer.start()

    def _update_stream_card(self, message_id: str, content, access_token: str = None) -> bool:
        return self._update_message(
            message_id,
            self._build_stream_card(content),
            access_token=access_token,
            msg_type="interactive"
        )

    def _send_message(self, msg_type: str, content, context: Context, access_token: str = None, force_new: bool = False):
        msg = context.get("msg")
        is_group = context.get("isgroup", False)
        access_token = access_token or (msg.access_token if msg else self.fetch_access_token())
        headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        content_json = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        can_reply = not force_new and is_group and msg and hasattr(msg, 'msg_id') and msg.msg_id

        if can_reply:
            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg.msg_id}/reply"
            data = {"msg_type": msg_type, "content": content_json}
            res = requests.post(url=url, headers=headers, json=data, timeout=(5, 10))
        else:
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            params = {"receive_id_type": context.get("receive_id_type") or "open_id"}
            data = {
                "receive_id": context.get("receiver"),
                "msg_type": msg_type,
                "content": content_json
            }
            res = requests.post(url=url, headers=headers, params=params, json=data, timeout=(5, 10))

        res = res.json()
        if res.get("code") == 0:
            data = res.get("data") or {}
            message_id = data.get("message_id")
            logger.info(f"[FeiShu] send message success, msg_type={msg_type}, message_id={message_id}")
            return message_id
        logger.error(f"[FeiShu] send message failed, code={res.get('code')}, msg={res.get('msg')}")
        return None

    def _update_message(self, message_id: str, content: str, access_token: str = None, msg_type: str = "text") -> bool:
        access_token = access_token or self.fetch_access_token()
        headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        content_payload = {"text": content} if msg_type == "text" else content
        data = {
            "msg_type": msg_type,
            "content": json.dumps(content_payload, ensure_ascii=False),
        }
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        try:
            res = requests.patch(url=url, headers=headers, json=data, timeout=(5, 10)).json()
        except Exception as e:
            logger.warning(f"[FeiShu] update message error: {e}")
            return False
        if res.get("code") == 0:
            logger.debug(f"[FeiShu] update message success, message_id={message_id}")
            return True
        logger.warning(f"[FeiShu] update message failed, code={res.get('code')}, msg={res.get('msg')}")
        return False

    def send_card(self, card_data: dict, context: Context):
        access_token = context.get("msg").access_token if context.get("msg") else self.fetch_access_token()
        return self._send_message("interactive", json.dumps(card_data, ensure_ascii=False), context, access_token=access_token)

    def update_card(self, message_id: str, card_data: dict, access_token: str = None) -> bool:
        return self._update_message(message_id, card_data, access_token=access_token, msg_type="interactive")

    def _finalize_stream_reply(self, context: Context, answer: str, continuation: bool = True) -> bool:
        stream_id = context.get("feishu_stream_id")
        if not stream_id:
            return False
        state = self._stream_states.pop(stream_id, None)
        session_id = context.get("session_id")
        session_state = self._feishu_session_states.get(session_id) if session_id else None
        if session_state:
            session_state["status"] = "done"
        if session_state and session_state.get("cancel_requested"):
            if state and state.get("message_id"):
                state["status"] = "已取消"
                state["phase"] = "done"
                state["done"] = True
                state["override_answer"] = "任务已取消，已丢弃迟到回复。"
                self._update_stream_card(
                    state["message_id"],
                    state,
                    state.get("access_token")
                )
            session_state["status"] = "cancelled"
            logger.info(f"[FeiShu] drop cancelled reply, session_id={session_id}")
            return True
        if not state or not state.get("message_id"):
            return False

        chunks = self._split_answer_for_cards(answer or "")
        state["status"] = "已完成"
        state["phase"] = "done"
        state["done"] = True
        state["final_answer_card"] = True
        if continuation and len(chunks) > 1:
            state["override_answer"] = (
                f"{chunks[0]}\n\n"
                f"（完整回复分 {len(chunks)} 张卡片展示，下面继续。）"
            )
        else:
            state["override_answer"] = chunks[0]
        if self._update_stream_card(state["message_id"], state, state.get("access_token")):
            if continuation and len(chunks) > 1:
                self._send_answer_continuation_cards(chunks, context, state.get("access_token"))
            return True
        logger.warning("[FeiShu] stream card final update failed, fallback to regular send")
        return False

    def send(self, reply: Reply, context: Context):
        if reply.type == ReplyType.TEXT and self._finalize_stream_reply(context, reply.content):
            return

        msg = context.get("msg")
        is_group = context["isgroup"]
        if msg:
            access_token = msg.access_token
        else:
            access_token = self.fetch_access_token()
        headers = {
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        }
        if reply.type == ReplyType.TEXT:
            self._send_paginated_answer_cards(reply.content, context, access_token)
            return
        if context.get("feishu_stream_id") and not getattr(reply, "text_content", None):
            self._finalize_stream_reply(context, "结果已生成，正在发送附件。", continuation=False)
        msg_type = "text"
        logger.debug(f"[FeiShu] sending reply, type={context.type}, content={str(reply.content)[:100]}...")
        reply_content = reply.content
        content_key = "text"
        if reply.type == ReplyType.IMAGE_URL:
            # 图片上传
            reply_content = self._upload_image_url(reply.content, access_token)
            if not reply_content:
                logger.warning("[FeiShu] upload image failed")
                return
            msg_type = "image"
            content_key = "image_key"
        elif reply.type == ReplyType.FILE:
            # 如果有附加的文本内容，先发送文本
            if hasattr(reply, 'text_content') and reply.text_content:
                logger.info(f"[FeiShu] Sending text before file: {reply.text_content[:50]}...")
                text_reply = Reply(ReplyType.TEXT, reply.text_content)
                self._send(text_reply, context)
                time.sleep(0.3)  # 短暂延迟，确保文本先到达

            # 判断是否为视频文件
            file_path = reply.content
            if file_path.startswith("file://"):
                file_path = file_path[7:]

            is_video = file_path.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.flv'))

            if is_video:
                # 视频上传（包含duration信息）
                upload_data = self._upload_video_url(reply.content, access_token)
                if not upload_data or not upload_data.get('file_key'):
                    logger.warning("[FeiShu] upload video failed")
                    return

                # 视频使用 media 类型（根据官方文档）
                # 错误码 230055 说明：上传 mp4 时必须使用 msg_type="media"
                msg_type = "media"
                reply_content = upload_data  # 完整的上传响应数据（包含file_key和duration）
                logger.info(
                    f"[FeiShu] Sending video: file_key={upload_data.get('file_key')}, duration={upload_data.get('duration')}ms")
                content_key = None  # 直接序列化整个对象
            else:
                # 其他文件使用 file 类型
                file_key = self._upload_file_url(reply.content, access_token)
                if not file_key:
                    logger.warning("[FeiShu] upload file failed")
                    return
                reply_content = file_key
                msg_type = "file"
                content_key = "file_key"
        elif reply.type == ReplyType.CARD:
            msg_type = "interactive"
            content_key = None

        # Check if we can reply to an existing message (need msg_id)
        can_reply = is_group and msg and hasattr(msg, 'msg_id') and msg.msg_id

        # Build content JSON
        content_json = json.dumps(reply_content, ensure_ascii=False) if content_key is None else json.dumps({content_key: reply_content}, ensure_ascii=False)
        logger.debug(f"[FeiShu] Sending message: msg_type={msg_type}, content={content_json[:200]}")

        if can_reply:
            # 群聊中回复已有消息
            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{msg.msg_id}/reply"
            data = {
                "msg_type": msg_type,
                "content": content_json
            }
            res = requests.post(url=url, headers=headers, json=data, timeout=(5, 10))
        else:
            # 发送新消息（私聊或群聊中无msg_id的情况，如定时任务）
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            params = {"receive_id_type": context.get("receive_id_type") or "open_id"}
            data = {
                "receive_id": context.get("receiver"),
                "msg_type": msg_type,
                "content": content_json
            }
            res = requests.post(url=url, headers=headers, params=params, json=data, timeout=(5, 10))
        res = res.json()
        if res.get("code") == 0:
            logger.info(f"[FeiShu] send message success")
        else:
            logger.error(f"[FeiShu] send message failed, code={res.get('code')}, msg={res.get('msg')}")

    def fetch_access_token(self) -> str:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        headers = {
            "Content-Type": "application/json"
        }
        req_body = {
            "app_id": self.feishu_app_id,
            "app_secret": self.feishu_app_secret
        }
        data = bytes(json.dumps(req_body), encoding='utf8')
        response = requests.post(url=url, data=data, headers=headers)
        if response.status_code == 200:
            res = response.json()
            if res.get("code") != 0:
                logger.error(f"[FeiShu] get tenant_access_token error, code={res.get('code')}, msg={res.get('msg')}")
                return ""
            else:
                return res.get("tenant_access_token")
        else:
            logger.error(f"[FeiShu] fetch token error, res={response}")

    def _upload_image_url(self, img_url, access_token):
        logger.debug(f"[FeiShu] start process image, img_url={img_url}")

        # Check if it's a local file path (file:// protocol)
        if img_url.startswith("file://"):
            local_path = img_url[7:]  # Remove "file://" prefix
            logger.info(f"[FeiShu] uploading local file: {local_path}")

            if not os.path.exists(local_path):
                logger.error(f"[FeiShu] local file not found: {local_path}")
                return None

            # Upload directly from local file
            upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
            data = {'image_type': 'message'}
            headers = {'Authorization': f'Bearer {access_token}'}

            with open(local_path, "rb") as file:
                upload_response = requests.post(upload_url, files={"image": file}, data=data, headers=headers)
                logger.info(f"[FeiShu] upload file, res={upload_response.content}")

                response_data = upload_response.json()
                if response_data.get("code") == 0:
                    return response_data.get("data").get("image_key")
                else:
                    logger.error(f"[FeiShu] upload failed: {response_data}")
                    return None

        # Original logic for HTTP URLs
        response = requests.get(img_url)
        suffix = utils.get_path_suffix(img_url)
        temp_name = str(uuid.uuid4()) + "." + suffix
        if response.status_code == 200:
            # 将图片内容保存为临时文件
            with open(temp_name, "wb") as file:
                file.write(response.content)

        # upload
        upload_url = "https://open.feishu.cn/open-apis/im/v1/images"
        data = {
            'image_type': 'message'
        }
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        with open(temp_name, "rb") as file:
            upload_response = requests.post(upload_url, files={"image": file}, data=data, headers=headers)
            logger.info(f"[FeiShu] upload file, res={upload_response.content}")
            os.remove(temp_name)
            return upload_response.json().get("data").get("image_key")

    def _get_video_duration(self, file_path: str) -> int:
        """
        获取视频时长（毫秒）
        
        Args:
            file_path: 视频文件路径
        
        Returns:
            视频时长（毫秒），如果获取失败返回0
        """
        try:
            import subprocess

            # 使用 ffprobe 获取视频时长
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                duration_seconds = float(result.stdout.strip())
                duration_ms = int(duration_seconds * 1000)
                logger.info(f"[FeiShu] Video duration: {duration_seconds:.2f}s ({duration_ms}ms)")
                return duration_ms
            else:
                logger.warning(f"[FeiShu] Failed to get video duration via ffprobe: {result.stderr}")
                return 0
        except FileNotFoundError:
            logger.warning("[FeiShu] ffprobe not found, video duration will be 0. Install ffmpeg to fix this.")
            return 0
        except Exception as e:
            logger.warning(f"[FeiShu] Failed to get video duration: {e}")
            return 0

    def _upload_video_url(self, video_url, access_token):
        """
        Upload video to Feishu and return video info (file_key and duration)
        Supports:
        - file:// URLs for local files
        - http(s):// URLs (download then upload)
        
        Returns:
            dict with 'file_key' and 'duration' (milliseconds), or None if failed
        """
        local_path = None
        temp_file = None

        try:
            # For file:// URLs (local files), upload directly
            if video_url.startswith("file://"):
                local_path = video_url[7:]  # Remove file:// prefix
                if not os.path.exists(local_path):
                    logger.error(f"[FeiShu] local video file not found: {local_path}")
                    return None
            else:
                # For HTTP URLs, download first
                logger.info(f"[FeiShu] Downloading video from URL: {video_url}")
                response = requests.get(video_url, timeout=(5, 60))
                if response.status_code != 200:
                    logger.error(f"[FeiShu] download video failed, status={response.status_code}")
                    return None

                # Save to temp file
                import uuid
                file_name = os.path.basename(video_url) or "video.mp4"
                temp_file = str(uuid.uuid4()) + "_" + file_name

                with open(temp_file, "wb") as file:
                    file.write(response.content)

                logger.info(f"[FeiShu] Video downloaded, size={len(response.content)} bytes")
                local_path = temp_file

            # Get video duration
            duration = self._get_video_duration(local_path)

            # Upload to Feishu
            file_name = os.path.basename(local_path)
            file_ext = os.path.splitext(file_name)[1].lower()
            file_type_map = {'.mp4': 'mp4'}
            file_type = file_type_map.get(file_ext, 'mp4')

            upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
            data = {
                'file_type': file_type,
                'file_name': file_name
            }
            # Add duration only if available (required for video/audio)
            if duration:
                data['duration'] = duration  # Must be int, not string

            headers = {'Authorization': f'Bearer {access_token}'}

            logger.info(f"[FeiShu] Uploading video: file_name={file_name}, duration={duration}ms")

            with open(local_path, "rb") as file:
                upload_response = requests.post(
                    upload_url,
                    files={"file": file},
                    data=data,
                    headers=headers,
                    timeout=(5, 60)
                )
                logger.info(
                    f"[FeiShu] upload video response, status={upload_response.status_code}, res={upload_response.content}")

                response_data = upload_response.json()
                if response_data.get("code") == 0:
                    # Add duration to the response data (API doesn't return it)
                    upload_data = response_data.get("data")
                    upload_data['duration'] = duration  # Add our calculated duration
                    logger.info(
                        f"[FeiShu] Upload complete: file_key={upload_data.get('file_key')}, duration={duration}ms")
                    return upload_data
                else:
                    logger.error(f"[FeiShu] upload video failed: {response_data}")
                    return None

        except Exception as e:
            logger.error(f"[FeiShu] upload video exception: {e}")
            return None

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"[FeiShu] Failed to remove temp file {temp_file}: {e}")

    def _upload_file_url(self, file_url, access_token):
        """
        Upload file to Feishu
        Supports both local files (file://) and HTTP URLs
        """
        logger.debug(f"[FeiShu] start process file, file_url={file_url}")

        # Check if it's a local file path (file:// protocol)
        if file_url.startswith("file://"):
            local_path = file_url[7:]  # Remove "file://" prefix
            logger.info(f"[FeiShu] uploading local file: {local_path}")

            if not os.path.exists(local_path):
                logger.error(f"[FeiShu] local file not found: {local_path}")
                return None

            # Get file info
            file_name = os.path.basename(local_path)
            file_ext = os.path.splitext(file_name)[1].lower()

            # Determine file type for Feishu API
            # Feishu supports: opus, mp4, pdf, doc, xls, ppt, stream (other types)
            file_type_map = {
                '.opus': 'opus',
                '.mp4': 'mp4',
                '.pdf': 'pdf',
                '.doc': 'doc', '.docx': 'doc',
                '.xls': 'xls', '.xlsx': 'xls',
                '.ppt': 'ppt', '.pptx': 'ppt',
            }
            file_type = file_type_map.get(file_ext, 'stream')  # Default to stream for other types

            # Upload file to Feishu
            upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
            data = {'file_type': file_type, 'file_name': file_name}
            headers = {'Authorization': f'Bearer {access_token}'}

            try:
                with open(local_path, "rb") as file:
                    upload_response = requests.post(
                        upload_url,
                        files={"file": file},
                        data=data,
                        headers=headers,
                        timeout=(5, 30)  # 5s connect, 30s read timeout
                    )
                    logger.info(
                        f"[FeiShu] upload file response, status={upload_response.status_code}, res={upload_response.content}")

                    response_data = upload_response.json()
                    if response_data.get("code") == 0:
                        return response_data.get("data").get("file_key")
                    else:
                        logger.error(f"[FeiShu] upload file failed: {response_data}")
                        return None
            except Exception as e:
                logger.error(f"[FeiShu] upload file exception: {e}")
                return None

        # For HTTP URLs, download first then upload
        try:
            response = requests.get(file_url, timeout=(5, 30))
            if response.status_code != 200:
                logger.error(f"[FeiShu] download file failed, status={response.status_code}")
                return None

            # Save to temp file
            import uuid
            file_name = os.path.basename(file_url)
            temp_name = str(uuid.uuid4()) + "_" + file_name

            with open(temp_name, "wb") as file:
                file.write(response.content)

            # Upload
            file_ext = os.path.splitext(file_name)[1].lower()
            file_type_map = {
                '.opus': 'opus', '.mp4': 'mp4', '.pdf': 'pdf',
                '.doc': 'doc', '.docx': 'doc',
                '.xls': 'xls', '.xlsx': 'xls',
                '.ppt': 'ppt', '.pptx': 'ppt',
            }
            file_type = file_type_map.get(file_ext, 'stream')

            upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
            data = {'file_type': file_type, 'file_name': file_name}
            headers = {'Authorization': f'Bearer {access_token}'}

            with open(temp_name, "rb") as file:
                upload_response = requests.post(upload_url, files={"file": file}, data=data, headers=headers)
                logger.info(f"[FeiShu] upload file, res={upload_response.content}")

                response_data = upload_response.json()
                os.remove(temp_name)  # Clean up temp file

                if response_data.get("code") == 0:
                    return response_data.get("data").get("file_key")
                else:
                    logger.error(f"[FeiShu] upload file failed: {response_data}")
                    return None
        except Exception as e:
            logger.error(f"[FeiShu] upload file from URL exception: {e}")
            return None

    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content)
        context.kwargs = kwargs
        if "channel_type" not in context:
            context["channel_type"] = self.channel_type
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype

        cmsg = context["msg"]

        # Set session_id based on chat type
        if cmsg.is_group:
            # Group chat: check if group_shared_session is enabled
            if conf().get("group_shared_session", True):
                # All users in the group share the same session context
                context["session_id"] = cmsg.other_user_id  # group_id
            else:
                # Each user has their own session within the group
                # This ensures:
                # - Same user in different groups have separate conversation histories
                # - Same user in private chat and group chat have separate histories
                context["session_id"] = f"{cmsg.from_user_id}:{cmsg.other_user_id}"
        else:
            # Private chat: use user_id only
            context["session_id"] = cmsg.from_user_id

        context["receiver"] = cmsg.other_user_id

        if ctype == ContextType.TEXT:
            # 1.文本请求
            # 图片生成处理
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix"))
            if img_match_prefix:
                content = content.replace(img_match_prefix, "", 1)
                context.type = ContextType.IMAGE_CREATE
            else:
                context.type = ContextType.TEXT
            context.content = content.strip()

        elif context.type == ContextType.VOICE:
            # 2.语音请求
            if "desire_rtype" not in context and conf().get("voice_reply_voice"):
                context["desire_rtype"] = ReplyType.VOICE

        session_id = context.get("session_id")
        if session_id:
            context["session_tmp_dir"] = get_session_tmp_dir(session_id)
        return context


class FeishuController:
    """
    HTTP服务器控制器，用于webhook模式
    """
    # 类常量
    FAILED_MSG = '{"success": false}'
    SUCCESS_MSG = '{"success": true}'
    MESSAGE_RECEIVE_TYPE = "im.message.receive_v1"

    def GET(self):
        return "Feishu service start success!"

    def POST(self):
        try:
            channel = FeiShuChanel()

            request = json.loads(web.data().decode("utf-8"))
            logger.debug(f"[FeiShu] receive request: {request}")

            # 1.事件订阅回调验证
            if request.get("type") == URL_VERIFICATION:
                varify_res = {"challenge": request.get("challenge")}
                return json.dumps(varify_res)

            # 2.消息接收处理
            # token 校验
            header = request.get("header")
            if not header or header.get("token") != channel.feishu_token:
                return self.FAILED_MSG

            # 处理消息事件
            event = request.get("event")
            if header.get("event_type") == self.MESSAGE_RECEIVE_TYPE and event:
                channel._handle_message_event(event)

            return self.SUCCESS_MSG

        except Exception as e:
            logger.error(e)
            return self.FAILED_MSG
