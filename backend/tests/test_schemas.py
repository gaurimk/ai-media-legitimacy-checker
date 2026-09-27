import pytest
from pydantic import ValidationError

from app.schemas import AnalyzeResponse, Source, VerdictLabel, VerdictResult


def test_verdict_result_accepts_valid_payload():
    verdict = VerdictResult.model_validate(
        {
            "label": "scam",
            "confidence": 0.92,
            "summary": "This message asks for an upfront fee to release a lottery prize, a classic advance-fee scam pattern.",
            "red_flags": ["Requests an upfront payment", "Creates false urgency"],
            "sources": [
                {
                    "title": "Reserve Bank of India consumer advisory",
                    "url": "https://www.rbi.org.in/",
                    "note": "Confirms RBI never asks citizens to pay a fee to claim a prize.",
                }
            ],
        }
    )
    assert verdict.label is VerdictLabel.SCAM
    assert 0.0 <= verdict.confidence <= 1.0
    assert len(verdict.sources) == 1
    assert isinstance(verdict.sources[0], Source)


def test_verdict_result_rejects_unknown_label():
    with pytest.raises(ValidationError):
        VerdictResult.model_validate(
            {
                "label": "definitely_a_scam",  # not a valid enum value
                "confidence": 0.5,
                "summary": "x",
            }
        )


def test_verdict_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        VerdictResult.model_validate(
            {
                "label": "uncertain",
                "confidence": 1.5,  # must be <= 1.0
                "summary": "x",
            }
        )


def test_verdict_result_defaults_empty_lists():
    verdict = VerdictResult.model_validate(
        {"label": "legitimate", "confidence": 0.8, "summary": "Matches the sender's official announcement."}
    )
    assert verdict.red_flags == []
    assert verdict.sources == []


def test_analyze_response_defaults_no_image():
    response = AnalyzeResponse(
        verdict=VerdictResult(label=VerdictLabel.LEGITIMATE, confidence=0.9, summary="Looks genuine.")
    )
    assert response.warning_image_url is None
