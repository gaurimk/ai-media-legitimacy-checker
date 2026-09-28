"""An awareness graphic is generated for EVERY verdict (not just scams)."""
import pytest
from fastapi.testclient import TestClient

from app import gemini_client, main
from app.config import settings
from app.prompts import build_image_prompt
from app.schemas import VerdictLabel, VerdictResult


def _verdict(label, **kwargs):
    return VerdictResult(label=label, confidence=0.8, summary="Summary of what was checked.", **kwargs)


# --- prompt content ---------------------------------------------------------


@pytest.mark.parametrize(
    "label,headline",
    [
        (VerdictLabel.SCAM, "SCAM ALERT"),
        (VerdictLabel.LIKELY_FAKE, "LIKELY FAKE"),
        (VerdictLabel.UNCERTAIN, "NOT CONFIRMED"),
        (VerdictLabel.LEGITIMATE, "LOOKS GENUINE"),
    ],
)
def test_image_prompt_headline_follows_verdict(label, headline):
    assert headline in build_image_prompt(_verdict(label))


def test_image_prompt_uses_awareness_tips_for_legitimate_content():
    prompt = build_image_prompt(
        _verdict(VerdictLabel.LEGITIMATE, awareness_tips=["Check the sender's official website"])
    )
    assert "Check the sender's official website" in prompt
    assert "green" in prompt.lower()


def test_image_prompt_combines_red_flags_and_tips():
    prompt = build_image_prompt(
        _verdict(VerdictLabel.SCAM, red_flags=["Upfront fee"], awareness_tips=["Never share your OTP"])
    )
    assert "Upfront fee" in prompt and "Never share your OTP" in prompt


def test_image_prompt_has_default_point_when_nothing_supplied():
    prompt = build_image_prompt(_verdict(VerdictLabel.LEGITIMATE))
    assert "official source" in prompt.lower()


# --- endpoint: image is produced for a legitimate verdict too -----------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "VERDICT_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(main.budget_guard, "ensure_budget_available", lambda amount: None)
    monkeypatch.setattr(main.budget_guard, "record_spend_inr", lambda amount: None)
    return TestClient(main.app)


def _patch_gemini(monkeypatch, verdict, image_calls):
    monkeypatch.setattr(
        main.gemini_client,
        "analyze_content",
        lambda **kwargs: gemini_client.AnalysisOutcome(verdict=verdict, estimated_cost_inr=1.0),
    )

    def fake_image(v, *, image_size="4K"):
        image_calls.append(image_size)
        return gemini_client.ImageOutcome(png_bytes=b"png-bytes", estimated_cost_inr=20.0)

    monkeypatch.setattr(main.gemini_client, "generate_verdict_image", fake_image)


@pytest.mark.parametrize("label", list(VerdictLabel))
def test_endpoint_returns_awareness_image_for_every_verdict(client, monkeypatch, tmp_path, label):
    image_calls = []
    _patch_gemini(monkeypatch, _verdict(label), image_calls)

    response = client.post("/api/analyze", data={"text": "some forwarded message"})

    assert response.status_code == 200
    url = response.json()["warning_image_url"]
    assert url and url.startswith("/static/verdicts/")
    assert len(list(tmp_path.glob("*.png"))) == 1
    assert image_calls == [settings.image_size]


def test_endpoint_still_returns_verdict_when_image_generation_fails(client, monkeypatch):
    monkeypatch.setattr(
        main.gemini_client,
        "analyze_content",
        lambda **kwargs: gemini_client.AnalysisOutcome(verdict=_verdict(VerdictLabel.LEGITIMATE), estimated_cost_inr=1.0),
    )

    def boom(*args, **kwargs):
        raise gemini_client.GeminiClientError("image model unavailable")

    monkeypatch.setattr(main.gemini_client, "generate_verdict_image", boom)

    response = client.post("/api/analyze", data={"text": "hello"})
    assert response.status_code == 200
    assert response.json()["warning_image_url"] is None
    assert response.json()["verdict"]["label"] == "legitimate"


def test_invalid_image_size_falls_back_to_4k():
    from app.config import Settings

    assert Settings(image_size="8k-nonsense").image_size == "4K"
    assert Settings(image_size="2K").image_size == "2K"