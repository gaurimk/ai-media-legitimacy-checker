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
    follow_up_question: str = Field(
        default="",
        description=(
            "ONLY when the label is 'uncertain' AND one missing fact about who sent the content, "
            "how it arrived, or where it was found would change the verdict: ONE short question "
            "(under 15 words). Otherwise an empty string. Never ask for OTPs, passwords, PINs, "
            "account numbers or other personal data."
        ),
    )
    follow_up_options: List[str] = Field(
        default_factory=list,
        description=(
            "2-4 short answers (under 4 words each) the person can tap in reply to the follow-up "
            "question, e.g. 'Unknown number'. Empty when follow_up_question is empty."
        ),
    )

class AnalyzeResponse(BaseModel):
    verdict: VerdictResult
    warning_image_url: Optional[str] = Field(
        default=None,
        description="Relative URL to a downloadable AI-generated warning poster. Only set for 'scam' and 'likely_fake' verdicts, and only if the budget allows.",
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