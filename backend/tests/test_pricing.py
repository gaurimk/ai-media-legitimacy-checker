from app import pricing


def test_estimate_text_cost_usd_known_model():
    cost = pricing.estimate_text_cost_usd("gemini-3.5-flash-lite", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.30 + 2.50


def test_estimate_text_cost_usd_unknown_model_returns_zero():
    assert pricing.estimate_text_cost_usd("not-a-real-model", 1_000, 1_000) == 0.0


def test_estimate_text_cost_usd_scales_with_tokens():
    half = pricing.estimate_text_cost_usd("gemini-3.5-flash-lite", 500_000, 0)
    full = pricing.estimate_text_cost_usd("gemini-3.5-flash-lite", 1_000_000, 0)
    assert full == half * 2


def test_estimate_image_cost_usd_known_size():
    assert pricing.estimate_image_cost_usd("gemini-3-pro-image", "4K") == 0.24


def test_estimate_image_cost_usd_unknown_size_returns_zero():
    assert pricing.estimate_image_cost_usd("gemini-3-pro-image", "8K") == 0.0


def test_usd_to_inr_uses_configured_rate(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "usd_to_inr_rate", 90.0)
    assert pricing.usd_to_inr(1.0) == 90.0
