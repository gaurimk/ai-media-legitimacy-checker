import pytest
from fastapi.testclient import TestClient

from app import config, main, sessions
from app.schemas import ChatModelOutput, VerdictResult

client = TestClient(main.app)
V = VerdictResult(label="uncertain", confidence=0.5, summary="s")
SCAM = VerdictResult(label="scam", confidence=0.9, summary="bad")


@pytest.fixture(autouse=True)
def tmp_usage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USAGE_FILE", str(tmp_path / "u.json"))


def post(sid, msg="hi"):
    return client.post("/api/chat", json={"session_id": sid, "message": msg})


def test_session_expiry(monkeypatch):
    sid = sessions.create(V, "hello", "text")
    assert sessions.get(sid)
    monkeypatch.setattr(config, "SESSION_TTL_SEC", -1)
    assert sessions.get(sid) is None


def test_unknown_session_is_410():
    assert post("nope").status_code == 410


def test_turn_cap(monkeypatch):
    async def fake_chat(v, h, m):
        return ChatModelOutput(reply="ok"), 0.1
    monkeypatch.setattr(main.g, "chat", fake_chat)
    monkeypatch.setattr(config, "CHAT_MAX_TURNS", 2)
    sid = sessions.create(V, "x", "text")
    assert post(sid).status_code == 200
    assert post(sid).status_code == 200
    assert post(sid).status_code == 429


def test_recheck_updates_verdict(monkeypatch):
    async def fake_chat(v, h, m):
        return ChatModelOutput(reply="Thanks", recheck=True), 0.1
    async def fake_analyze(text, blob):
        assert "unverified claim" in text
        return SCAM, 0.1
    monkeypatch.setattr(main.g, "chat", fake_chat)
    monkeypatch.setattr(main.g, "analyze", fake_analyze)
    sid = sessions.create(V, "x", "text")
    body = post(sid, "I got this from an unknown number").json()
    assert body["verdict"]["label"] == "scam"
    assert sessions.get(sid)["verdict"].label.value == "scam"