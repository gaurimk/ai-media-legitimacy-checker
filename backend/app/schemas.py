"""
Data models shared by the API layer and the Gemini client.

VerdictResult's JSON schema is sent to Gemini as a Structured Output
response_format, so the field descriptions below double as instructions
to the model -- keep them accurate and specific.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class VerdictLabel(str, Enum):
    LEGITIMATE = "legitimate"
    LIKELY_FAKE = "likely_fake"
    SCAM = "scam"
    UNCERTAIN = "uncertain"


class Source(BaseModel):
    title: str = Field(description="Short, human-readable name of the source (e.g. a news outlet or official page).")
    url: str = Field(description="Direct, working URL to the source used to verify or refute the claim.")
    note: str = Field(description="One short sentence on what this specific source confirms or refutes.")


class VerdictResult(BaseModel):
    label: VerdictLabel = Field(
        description=(
            "Overall verdict. Use 'uncertain' rather than guessing when the "
            "available evidence is not conclusive."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's confidence in the verdict, from 0.0 (no confidence) to 1.0 (certain).",
    )
    summary: str = Field(
        description=(
            "A short, plain-language explanation (2-4 sentences) that a "
            "non-technical person could understand in under a minute."
        )
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Concrete warning signs found in the content, if any (e.g. urgency, spoofed links, requests for money).",
    )
    sources: List[Source] = Field(
        default_factory=list,
        description="Real web sources actually used to reach this verdict. Never invent a source or URL.",
    )


class AnalyzeResponse(BaseModel):
    verdict: VerdictResult
    warning_image_url: Optional[str] = Field(
        default=None,
        description="Relative URL to a downloadable 4K warning graphic, present only for fake/scam verdicts.",
    )


class UsageStatus(BaseModel):
    month: str
    spent_inr: float
    cap_inr: float
    remaining_inr: float
