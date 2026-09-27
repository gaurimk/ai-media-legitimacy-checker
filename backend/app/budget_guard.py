"""
A small, file-backed monthly spend tracker.

IMPORTANT (see docs/ARCHITECTURE.md): this is a *soft*, best-effort guard
based on estimated token/image costs computed after each Gemini call. It is
not connected to Google's own billing system, so it cannot hard-stop calls
made outside this app, and its estimates depend on the pricing constants in
pricing.py staying up to date. Pair it with a real billing alert in Google
AI Studio / Cloud Console for the fixed Rs 2,500 cap described in the brief.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from .config import settings
from .schemas import UsageStatus

_LOCK = threading.Lock()


class BudgetExceededError(Exception):
    """Raised when a request would push this month's estimated spend over the cap."""


def _usage_file() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "usage.json"


def _current_month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load() -> Dict[str, float]:
    path = _usage_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupted or unreadable usage file should never crash the app;
        # start counting from zero again rather than blocking every request.
        return {}


def _save(data: Dict[str, float]) -> None:
    _usage_file().write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_month_spend_inr() -> float:
    return float(_load().get(_current_month_key(), 0.0))


def get_budget_status() -> UsageStatus:
    spent = get_month_spend_inr()
    cap = settings.monthly_budget_inr
    return UsageStatus(
        month=_current_month_key(),
        spent_inr=round(spent, 2),
        cap_inr=cap,
        remaining_inr=round(max(cap - spent, 0.0), 2),
    )


def ensure_budget_available(estimated_cost_inr: float) -> None:
    """Raise BudgetExceededError if adding this call would exceed the cap."""
    with _LOCK:
        spent = get_month_spend_inr()
        if spent + estimated_cost_inr > settings.monthly_budget_inr:
            raise BudgetExceededError(
                f"This request (~Rs {estimated_cost_inr:.2f} estimated) would push this "
                f"month's spend over the Rs {settings.monthly_budget_inr:.2f} cap "
                f"(Rs {spent:.2f} already used this month). Increase MONTHLY_BUDGET_INR "
                "only after the budget-increase request described in the README has been approved."
            )


def record_spend_inr(amount_inr: float) -> None:
    if amount_inr <= 0:
        return
    with _LOCK:
        data = _load()
        key = _current_month_key()
        data[key] = float(data.get(key, 0.0)) + amount_inr
        _save(data)
