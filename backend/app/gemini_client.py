"""
Thin wrapper around the Gemini API (via the `google-genai` SDK's Interactions
API) for the two jobs this app needs:

1. analyze_content()      -- multimodal reasoning + web grounding, returns a
                              schema-validated VerdictResult.
2. generate_verdict_image() -- a 4K shareable warning graphic for fake/scam
                              verdicts, using a model chosen for accurate
                              text rendering.

Network calls only happen inside this module, which keeps the rest of the
app (and the unit tests in backend/tests/) easy to test with a mocked client.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from . import pricing
from .config import settings
from .prompts import ANALYSIS_SYSTEM_INSTRUCTION, build_analysis_prompt, build_image_prompt
from .schemas import VerdictResult

logger = logging.getLogger(__name__)

_client = None  # lazily created singleton; see get_client()


class GeminiClientError(RuntimeError):
    """Raised for any failure talking to, or parsing a response from, Gemini."""


def get_client():
    """
    Returns a cached `google.genai.Client`.

    Imported lazily so the rest of the app (and the test suite) can run
    without the `google-genai` package being importable in every context.
    """
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise GeminiClientError(
                "GEMINI_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and add your key from https://aistudio.google.com/apikey."
            )
        from google import genai  # local import, see docstring above

        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _media_block(data: bytes, mime_type: str) -> dict:
    kind = "video" if mime_type.startswith("video/") else "image"
    return {
        "type": kind,
        "mime_type": mime_type,
        "data": base64.b64encode(data).decode("ascii"),
    }


@dataclass
class AnalysisOutcome:
    verdict: VerdictResult
    estimated_cost_inr: float


def analyze_content(
    *,
    text: Optional[str],
    media_bytes: Optional[bytes],
    media_mime_type: Optional[str],
    note: Optional[str],
) -> AnalysisOutcome:
    """
    Sends the submission to the analysis model with Google Search + URL
    Context grounding enabled, and asks for a Structured Output that matches
    VerdictResult's JSON schema.
    """
    client = get_client()

    prompt_text = build_analysis_prompt(user_text=text, note=note)
    input_blocks = [_text_block(prompt_text)]
    if media_bytes and media_mime_type:
        input_blocks.append(_media_block(media_bytes, media_mime_type))

    try:
        interaction = client.interactions.create(
            model=settings.analysis_model,
            system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
            input=input_blocks,
            tools=[{"type": "google_search"}, {"type": "url_context"}],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": VerdictResult.model_json_schema(),
            },
        )
    except Exception as exc:  # pragma: no cover - depends on live network/SDK errors
        raise GeminiClientError(f"Gemini analysis request failed: {exc}") from exc

    return AnalysisOutcome(
        verdict=_parse_verdict(interaction),
        estimated_cost_inr=_estimate_text_cost_inr(interaction),
    )


def _parse_verdict(interaction) -> VerdictResult:
    raw_json = getattr(interaction, "output_text", None)
    if not raw_json:
        raise GeminiClientError("The analysis model returned an empty response.")
    try:
        return VerdictResult.model_validate_json(raw_json)
    except ValidationError as exc:
        raise GeminiClientError(
            f"The model's response did not match the expected verdict format: {exc}"
        ) from exc


def _estimate_text_cost_inr(interaction) -> float:
    usage = getattr(interaction, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cost_usd = pricing.estimate_text_cost_usd(settings.analysis_model, input_tokens, output_tokens)
    return pricing.usd_to_inr(cost_usd)


@dataclass
class ImageOutcome:
    png_bytes: bytes
    estimated_cost_inr: float


def generate_verdict_image(verdict: VerdictResult, *, image_size: str = "4K") -> ImageOutcome:
    """
    Renders a shareable warning graphic for a fake/scam verdict.

    image_size must be one of "1K", "2K", "4K" (uppercase 'K' is required by
    the API). Defaults to 4K per the project brief.
    """
    client = get_client()
    prompt = build_image_prompt(verdict)

    try:
        interaction = client.interactions.create(
            model=settings.image_model,
            input=prompt,
            response_format={
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": "3:4",
                "image_size": image_size,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on live network/SDK errors
        raise GeminiClientError(f"Gemini image generation request failed: {exc}") from exc

    output_image = getattr(interaction, "output_image", None)
    image_data = getattr(output_image, "data", None) if output_image else None
    if not image_data:
        raise GeminiClientError("The image model did not return an image.")

    cost_usd = pricing.estimate_image_cost_usd(settings.image_model, image_size)
    return ImageOutcome(
        png_bytes=base64.b64decode(image_data),
        estimated_cost_inr=pricing.usd_to_inr(cost_usd),
    )
