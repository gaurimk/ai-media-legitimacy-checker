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
    content_snapshot: str = Field(
        default="",
        description=(
            "A short (under 110 characters) plain-language snapshot of what the submitted content "
            "says or shows, written so it can appear on a public awareness poster. Remove or "
            "generalise personal details (names, phone numbers, account numbers, addresses) and "
            "never include web addresses -- write 'a suspicious link' instead."
        ),
    )
    consequences: List[str] = Field(
        default_factory=list,
        description=(
            "Only for 'scam' or 'likely_fake' verdicts: 2-3 very short (under 5 words each) "
            "real-world consequences of trusting THIS specific content, e.g. 'Money lost' or "
            "'Passwords stolen'. Leave empty for 'legitimate' and 'uncertain' verdicts."
        ),
    )
    awareness_tips: List[str] = Field(
        default_factory=list,
        description=(
            "2-3 short, practical awareness tips specific to THIS content -- what to look for "
            "in similar messages/media and what to do -- useful to anyone who receives something "
            "like it. Provide these for every verdict, including 'legitimate' ones. Each tip "
            "must be under 12 words."
        ),
    )


class AnalyzeResponse(BaseModel):
    verdict: VerdictResult
    session_id: Optional[str] = Field(
        default=None,
        description="Chat session id for follow-up questions about this result.",
    )
    warning_image_url: Optional[str] = Field(
        default=None,
        description="Unused; posters are fetched separately via /api/poster.",
    )


class UsageStatus(BaseModel):
    month: str
    spent_inr: float
    cap_inr: float
    remaining_inr: float


class FeedbackRequest(BaseModel):
    helpful: bool = Field(description="Whether the person found the verdict's explanation clear and useful.")
    message: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional free-text detail on what would have made this better.",
    )
    verdict_label: Optional[VerdictLabel] = Field(
        default=None, description="The verdict label this feedback refers to, if any."
    )


class FeedbackResponse(BaseModel):
    status: str = "recorded"


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=1000)


class ChatModelOutput(BaseModel):
    reply: str = Field(description="Short plain-language reply, 1-4 sentences.")
    recheck: bool = Field(
        default=False,
        description=(
            "True only if the person gave NEW information about who sent the content, how it "
            "arrived, or where it was found that could change the verdict."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    verdict: Optional[VerdictResult] = None
    turns_left: int