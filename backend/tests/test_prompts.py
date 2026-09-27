from app.prompts import build_analysis_prompt, build_image_prompt
from app.schemas import VerdictLabel, VerdictResult


def test_build_analysis_prompt_includes_text():
    prompt = build_analysis_prompt(user_text="Click here to claim your prize!", note=None)
    assert "Click here to claim your prize!" in prompt


def test_build_analysis_prompt_includes_note_when_given():
    prompt = build_analysis_prompt(user_text="Some message", note="My aunt received this on WhatsApp.")
    assert "My aunt received this on WhatsApp." in prompt


def test_build_analysis_prompt_handles_media_only_submission():
    prompt = build_analysis_prompt(user_text=None, note=None)
    assert "attached" in prompt.lower()


def test_build_image_prompt_uses_scam_headline():
    verdict = VerdictResult(
        label=VerdictLabel.SCAM,
        confidence=0.95,
        summary="Asks for an upfront fee to release a fake lottery prize.",
        red_flags=["Upfront payment request", "Fake urgency", "Unofficial sender"],
    )
    prompt = build_image_prompt(verdict)
    assert "SCAM ALERT" in prompt
    assert "Upfront payment request" in prompt


def test_build_image_prompt_uses_likely_fake_headline():
    verdict = VerdictResult(label=VerdictLabel.LIKELY_FAKE, confidence=0.6, summary="Could not confirm the claim.")
    prompt = build_image_prompt(verdict)
    assert "LIKELY FAKE" in prompt
    # No red flags supplied -- should fall back to a generic explanation, not crash.
    assert "Unverified claims found" in prompt or "could not be verified" in prompt.lower()
