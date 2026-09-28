import importlib
import json

import pytest


@pytest.fixture()
def feedback(tmp_path, monkeypatch):
    """
    Re-imports feedback with settings.data_dir pointed at a temp directory,
    so tests never touch the real backend/data/feedback.jsonl.
    """
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", tmp_path)

    from app import feedback as module

    importlib.reload(module)
    return module


def test_record_feedback_writes_one_json_line(feedback, tmp_path):
    feedback.record_feedback(helpful=True, message=None, verdict_label="scam")

    lines = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["helpful"] is True
    assert entry["message"] is None
    assert entry["verdict_label"] == "scam"
    assert "timestamp" in entry


def test_record_feedback_appends_rather_than_overwrites(feedback, tmp_path):
    feedback.record_feedback(helpful=True, message=None, verdict_label="legitimate")
    feedback.record_feedback(helpful=False, message="Too vague", verdict_label="uncertain")

    lines = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    second = json.loads(lines[1])
    assert second["helpful"] is False
    assert second["message"] == "Too vague"