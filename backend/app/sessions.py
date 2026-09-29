import threading
import time
import uuid

from .config import settings
from .schemas import VerdictResult

_lock = threading.Lock()
_store: dict[str, dict] = {}


def _purge(now: float) -> None:
    for k in [k for k, s in _store.items() if now - s["t"] > settings.session_ttl_sec]:
        del _store[k]


def create(verdict: VerdictResult, text: str, kind: str) -> str:
    sid = uuid.uuid4().hex
    with _lock:
        _purge(time.time())
        _store[sid] = {"t": time.time(), "verdict": verdict, "text": text,
                       "kind": kind, "history": [], "turns": 0}
    return sid


def get(sid: str):
    with _lock:
        now = time.time()
        _purge(now)
        s = _store.get(sid)
        if s:
            s["t"] = now
        return s


def add_turn(sid: str, user: str, reply: str) -> None:
    with _lock:
        s = _store.get(sid)
        if s:
            s["history"] = (s["history"] + [("user", user), ("model", reply)])[-20:]
            s["turns"] += 1


def set_verdict(sid: str, verdict: VerdictResult) -> None:
    with _lock:
        s = _store.get(sid)
        if s:
            s["verdict"] = verdict