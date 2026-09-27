import importlib

import pytest


@pytest.fixture()
def budget_guard(tmp_path, monkeypatch):
    """
    Re-imports budget_guard with settings.data_dir pointed at a temp
    directory, so tests never touch the real backend/data/usage.json.
    """
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", tmp_path)
    monkeypatch.setattr(config.settings, "monthly_budget_inr", 100.0)

    from app import budget_guard as module

    importlib.reload(module)
    return module


def test_fresh_month_has_zero_spend(budget_guard):
    status = budget_guard.get_budget_status()
    assert status.spent_inr == 0.0
    assert status.cap_inr == 100.0
    assert status.remaining_inr == 100.0


def test_record_spend_accumulates(budget_guard):
    budget_guard.record_spend_inr(10.0)
    budget_guard.record_spend_inr(5.5)
    assert budget_guard.get_month_spend_inr() == pytest.approx(15.5)


def test_ensure_budget_available_passes_under_cap(budget_guard):
    budget_guard.record_spend_inr(50.0)
    # Should not raise: 50 + 40 = 90, under the 100 cap.
    budget_guard.ensure_budget_available(40.0)


def test_ensure_budget_available_raises_over_cap(budget_guard):
    budget_guard.record_spend_inr(95.0)
    with pytest.raises(budget_guard.BudgetExceededError):
        budget_guard.ensure_budget_available(10.0)


def test_record_spend_ignores_non_positive_amounts(budget_guard):
    budget_guard.record_spend_inr(0.0)
    budget_guard.record_spend_inr(-5.0)
    assert budget_guard.get_month_spend_inr() == 0.0
