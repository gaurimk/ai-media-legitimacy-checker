import json, os, threading
from datetime import datetime, timezone
from . import config as c
from .schemas import UsageStatus

_lock = threading.Lock()

def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")

def _load() -> dict:
    try:
        with open(c.USAGE_FILE) as f:
            d = json.load(f)
        if d.get("month") == _month():
            return d
    except (OSError, ValueError):
        pass
    return {"month": _month(), "spent_inr": 0.0}

def status() -> UsageStatus:
    d = _load()
    return UsageStatus(month=d["month"], spent_inr=round(d["spent_inr"], 2), cap_inr=c.CAP_INR,
                       remaining_inr=round(max(c.CAP_INR - d["spent_inr"], 0), 2))

def can_spend(amount: float) -> bool:
    with _lock:
        return _load()["spent_inr"] + amount <= c.CAP_INR

def record(amount: float) -> None:
    with _lock:
        d = _load()
        d["spent_inr"] += amount
        tmp = c.USAGE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, c.USAGE_FILE)