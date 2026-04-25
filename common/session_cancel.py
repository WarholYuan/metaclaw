import threading
from typing import Optional


class SessionCancelledError(Exception):
    """Raised when a running session has been cancelled by the user."""


_lock = threading.Lock()
_cancelled_sessions = set()


def request_cancel(session_id: Optional[str]) -> None:
    if not session_id:
        return
    with _lock:
        _cancelled_sessions.add(session_id)


def clear_cancel(session_id: Optional[str]) -> None:
    if not session_id:
        return
    with _lock:
        _cancelled_sessions.discard(session_id)


def is_cancelled(session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    with _lock:
        return session_id in _cancelled_sessions


def raise_if_cancelled(session_id: Optional[str]) -> None:
    if is_cancelled(session_id):
        raise SessionCancelledError("Session cancelled by user")
