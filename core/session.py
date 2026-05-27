import threading
from collections import OrderedDict

from core.logger import get_logger

logger = get_logger(__name__)

MAX_HISTORY_PER_SESSION = 30
MAX_SESSIONS = 100


class SessionManager:
    def __init__(self, max_sessions: int = MAX_SESSIONS):
        self._max_sessions = max_sessions
        self._sessions: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def _ensure_session(self, session_id: str) -> dict:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "history": [],
                "summary": None,
            }
            self._evict_if_needed()
            logger.debug(f"New session: {session_id[:8]}...")
        self._sessions.move_to_end(session_id)
        return self._sessions[session_id]

    def get_history(self, session_id: str) -> list[dict]:
        with self._lock:
            return self._ensure_session(session_id)["history"]

    def get_summary(self, session_id: str) -> str | None:
        with self._lock:
            return self._ensure_session(session_id).get("summary")

    def set_summary(self, session_id: str, summary: str) -> None:
        with self._lock:
            session = self._ensure_session(session_id)
            session["summary"] = summary

    def append(self, session_id: str, entry: dict) -> None:
        with self._lock:
            session = self._ensure_session(session_id)
            session["history"].append(entry)
            if len(session["history"]) > MAX_HISTORY_PER_SESSION:
                session["history"].pop(0)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    @property
    def active_sessions(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _evict_if_needed(self) -> None:
        while len(self._sessions) > self._max_sessions:
            evicted_key, _ = self._sessions.popitem(last=False)
            logger.info(f"Evicted session: {evicted_key[:8]}...")


sessions = SessionManager()
