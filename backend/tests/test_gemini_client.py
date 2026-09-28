"""
These tests never touch the network: they replace gemini_client.get_client()
with a small fake object that mimics the shape of the google-genai SDK's
Interaction response, so we can test prompt-building, response-parsing and
cost-estimation logic on their own.
"""
import json
from types import SimpleNamespace

import pytest

from app import gemini_client
from app.schemas import VerdictLabel


VALID_VERDICT_JSON = json.dumps(
    {
        "label": "scam",
        "confidence": 0.9,
        "summary": "Asks for an upfront fee to release a lottery prize.",
        "red_flags": ["Requests an upfront payment"],
        "sources": [
            {
                "title": "Consumer protection advisory",
                "url": "https://example.gov/advisory",
                "note": "Confirms this is a known lottery scam pattern.",
            }
        ],
    }
)


class _FakeInteractions:
    def __init__(self, response):
        self._response = response
        self.last_call_kwargs = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.interactions = _FakeInteractions(response)


def _fake_text_response(output_text: str, input_tokens: int = 1000, output_tokens: int = 200):
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(output_text=output_text, usage=usage)


def test_analyze_content_parses_valid_verdict(monkeypatch):
    fake_client = _FakeClient(_fake_text_response(VALID_VERDICT_JSON))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    outcome = gemini_client.analyze_content(
        text="You won a lottery, pay Rs 500 to claim it.", media_bytes=None, media_mime_type=None, note=None
    )

    assert outcome.verdict.label is VerdictLabel.SCAM
    assert outcome.verdict.sources[0].url == "https://example.gov/advisory"
    assert outcome.estimated_cost_inr > 0

    # Both grounding tools should have been requested.
    tools = fake_client.interactions.last_call_kwargs["tools"]
    tool_types = {tool["type"] for tool in tools}
    assert tool_types == {"google_search", "url_context"}


def test_analyze_content_includes_media_block_when_provided(monkeypatch):
    fake_client = _FakeClient(_fake_text_response(VALID_VERDICT_JSON))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    gemini_client.analyze_content(
        text=None, media_bytes=b"fake-image-bytes", media_mime_type="image/png", note=None
    )

    input_blocks = fake_client.interactions.last_call_kwargs["input"]
    assert any(block["type"] == "image" for block in input_blocks)


def test_analyze_content_raises_on_empty_response(monkeypatch):
    fake_client = _FakeClient(_fake_text_response(""))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    with pytest.raises(gemini_client.GeminiClientError):
        gemini_client.analyze_content(text="hello", media_bytes=None, media_mime_type=None, note=None)


def test_analyze_content_raises_on_malformed_json(monkeypatch):
    fake_client = _FakeClient(_fake_text_response("{not valid json"))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    with pytest.raises(gemini_client.GeminiClientError):
        gemini_client.analyze_content(text="hello", media_bytes=None, media_mime_type=None, note=None)


def test_generate_verdict_image_decodes_base64(monkeypatch):
    import base64

    raw_png_bytes = b"not-a-real-png-but-good-enough-for-a-test"
    fake_response = SimpleNamespace(
        output_image=SimpleNamespace(data=base64.b64encode(raw_png_bytes).decode("ascii"))
    )
    fake_client = _FakeClient(fake_response)
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    from app.schemas import VerdictResult

    verdict = VerdictResult(label=VerdictLabel.SCAM, confidence=0.9, summary="Fake lottery scam.")
    outcome = gemini_client.generate_verdict_image(verdict, image_size="4K")

    assert outcome.png_bytes == raw_png_bytes
    assert outcome.estimated_cost_inr > 0

    call_kwargs = fake_client.interactions.last_call_kwargs
    assert call_kwargs["response_format"]["image_size"] == "4K"


def test_generate_verdict_image_raises_when_no_image_returned(monkeypatch):
    fake_client = _FakeClient(SimpleNamespace(output_image=None))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    from app.schemas import VerdictResult

    verdict = VerdictResult(label=VerdictLabel.SCAM, confidence=0.9, summary="Fake lottery scam.")
    with pytest.raises(gemini_client.GeminiClientError):
        gemini_client.generate_verdict_image(verdict)


# --- JSON repair + two-step fallback ---------------------------------------


class _SequencedInteractions:
    """Returns a different canned response for each successive create() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses[len(self.calls) - 1]


class _SequencedClient:
    def __init__(self, responses):
        self.interactions = _SequencedInteractions(responses)


def test_parse_repairs_trailing_comma(monkeypatch):
    broken = VALID_VERDICT_JSON.replace('"Requests an upfront payment"]', '"Requests an upfront payment",]')
    fake_client = _FakeClient(_fake_text_response(broken))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    outcome = gemini_client.analyze_content(text="hi", media_bytes=None, media_mime_type=None, note=None)
    assert outcome.verdict.label is VerdictLabel.SCAM


def test_parse_recovers_from_trailing_content_after_object(monkeypatch):
    fake_client = _FakeClient(_fake_text_response(VALID_VERDICT_JSON + "\n]\n}"))
    monkeypatch.setattr(gemini_client, "get_client", lambda: fake_client)

    outcome = gemini_client.analyze_content(text="hi", media_bytes=None, media_mime_type=None, note=None)
    assert outcome.verdict.label is VerdictLabel.SCAM


def test_falls_back_to_two_step_when_single_pass_is_unparseable(monkeypatch):
    citation = SimpleNamespace(url="https://example.gov/advisory", title="Consumer advisory")
    research = SimpleNamespace(
        output_text="Verdict: scam. Asks for an upfront fee.",
        usage=SimpleNamespace(input_tokens=1000, output_tokens=300),
        steps=[SimpleNamespace(content=[SimpleNamespace(annotations=[citation])])],
    )
    client = _SequencedClient(
        [
            _fake_text_response("{ this is not json at all"),  # 1: single pass, unusable
            research,  # 2: research with tools
            _fake_text_response(VALID_VERDICT_JSON),  # 3: format without tools
        ]
    )
    monkeypatch.setattr(gemini_client, "get_client", lambda: client)

    outcome = gemini_client.analyze_content(text="hi", media_bytes=None, media_mime_type=None, note=None)

    assert outcome.verdict.label is VerdictLabel.SCAM
    assert outcome.estimated_cost_inr > 0

    calls = client.interactions.calls
    assert len(calls) == 3
    assert "tools" in calls[1] and "response_format" not in calls[1]  # research: tools, no schema
    assert "tools" not in calls[2] and "response_format" in calls[2]  # format: schema, no tools
    assert "https://example.gov/advisory" in calls[2]["input"]  # real citation was passed along


def test_raises_when_fallback_also_fails(monkeypatch):
    client = _SequencedClient(
        [
            _fake_text_response("nope"),
            SimpleNamespace(output_text="findings", usage=None, steps=[]),
            _fake_text_response("still not json"),
        ]
    )
    monkeypatch.setattr(gemini_client, "get_client", lambda: client)

    with pytest.raises(gemini_client.GeminiClientError):
        gemini_client.analyze_content(text="hi", media_bytes=None, media_mime_type=None, note=None)


@pytest.mark.parametrize(
    "usage",
    [
        SimpleNamespace(input_tokens=100, output_tokens=50),
        SimpleNamespace(total_input_tokens=100, total_output_tokens=50),
        SimpleNamespace(prompt_tokens=100, completion_tokens=50),
    ],
)
def test_usage_tokens_read_from_any_known_field_name(usage):
    assert gemini_client._read_usage_tokens(usage) == (100, 50)