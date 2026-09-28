"""
A small, file-backed feedback log.

No Gemini calls are involved here, so this never touches the budget guard --
it's just a lightweight, append-only record of whether people found a
verdict's explanation clear and useful, so prompt wording and clarifying
questions can be improved over time based on real signal rather than
guesswork.

Same caveat as budget_guard.py's usage.json: this is a local file, fine for
a single instance, not safe for multiple concurrent replicas without a real
database.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import settings

_LOCK = threading.Lock()


def _feedback_file() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "feedback.jsonl"


def record_feedback(
    *, helpful: bool, message: Optional[str], verdict_label: Optional[str]
) -> None:
    """Appends one JSON line per piece of feedback (never overwrites)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "helpful": helpful,
        "message": message,
        "verdict_label": verdict_label,
    }
    with _LOCK:
        with _feedback_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")