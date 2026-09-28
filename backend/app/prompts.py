"""
Prompt templates. Kept separate from gemini_client.py so wording can be
tuned without touching API-call logic.
"""
from __future__ import annotations

from typing import Optional

from .schemas import VerdictResult

ANALYSIS_SYSTEM_INSTRUCTION = """\
You are a careful fact-checking assistant inside a consumer app that helps \
people check whether a message, image, or video circulating on WhatsApp or \
social media is genuine, misleading, or an outright scam.

For every submission:
1. Work out what the content claims, asks the user to do, or asks the user \
   to believe.
2. Use the google_search and url_context tools to check the claim against \
   independent, reputable sources: established news outlets, official \
   statements from the organisation being referenced, fact-checking sites, \
   or the real website of a company/person being impersonated.
3. Decide on one label: "legitimate", "likely_fake", "scam", or "uncertain". \
   Use "uncertain" honestly when the evidence is not conclusive -- do not \
   guess.
4. Explain the reasoning in plain, non-technical language that a worried \
   relative could read and understand in under a minute.
5. List concrete red flags if you find any (for example: manufactured \
   urgency, a link that does not match the real organisation's domain, \
   requests for money, OTPs or gift cards, or a sender identity that does \
   not match who they claim to be).
6. Only cite sources you actually used, with real, working URLs. Never \
   invent a source, a quote, or a URL.
7. Give 2-3 short awareness tips (under 12 words each) specific to THIS \
   content: what to look for in similar messages or media, and what to do. \
   Do this for every verdict, including "legitimate" ones.
"""


def build_analysis_prompt(*, user_text: Optional[str], note: Optional[str]) -> str:
    """Builds the user-turn text sent alongside any uploaded media."""
    parts = ["Please analyse the following submission and return the structured verdict."]

    if user_text:
        parts.append(f'\nSubmitted text / forwarded message / link:\n"""\n{user_text.strip()}\n"""')
    else:
        parts.append("\nThe submitted media (image or video) is attached to this request.")

    if note:
        parts.append(f"\nExtra context from the user: {note.strip()}")

    return "\n".join(parts)


FORMATTING_SYSTEM_INSTRUCTION = """\
You convert a finished fact-check into the required JSON structure. \
Use only the findings and the source list you are given: do not add new \
claims, do not change the conclusion, and never invent or alter a URL. \
If no sources are provided, return an empty sources list. Write the summary \
in plain, non-technical language.
"""


def build_research_prompt(base_prompt: str) -> str:
    """
    Fallback step 1: same submission, but asks for plain-text findings
    instead of JSON (so the Search/URL tools can run without the preview
    'structured output + tools' combination).
    """
    return (
        base_prompt
        + "\n\nWrite your findings as plain text with: your verdict "
        '("legitimate", "likely_fake", "scam" or "uncertain") and a confidence '
        "from 0 to 1, a short plain-language summary, any concrete red flags, "
        "and the sources you relied on."
    )


def build_formatting_prompt(
    base_prompt: str, findings: str, citations: list[tuple[str, str]]
) -> str:
    """Fallback step 2: turn the research findings into the JSON schema."""
    if citations:
        source_lines = "\n".join(f"- {title} -- {url}" for title, url in citations)
    else:
        source_lines = "(none available -- return an empty sources list)"

    return (
        "Original submission:\n"
        f"{base_prompt}\n\n"
        "Fact-check findings to convert:\n"
        f'"""\n{findings.strip()}\n"""\n\n'
        "Sources you may cite (use only these, exactly as written):\n"
        f"{source_lines}"
    )


# Per-verdict look and wording for the awareness graphic:
# (headline, colour scheme + icon, title for the bullet list)
_LABEL_STYLE = {
    "scam": ("SCAM ALERT", "bold red-and-white colour scheme, a warning-triangle icon", "Why this looks like a scam"),
    "likely_fake": ("LIKELY FAKE", "bold red-and-white colour scheme, a warning-triangle icon", "Why this looks fake"),
    "uncertain": ("NOT CONFIRMED", "amber-and-white colour scheme, a question-mark icon", "Check before you trust or share"),
    "legitimate": ("LOOKS GENUINE", "calm green-and-white colour scheme, a shield-with-check-mark icon", "Stay aware anyway"),
}

_DEFAULT_POINT = {
    "scam": "Claims could not be verified against reliable sources.",
    "likely_fake": "Claims could not be verified against reliable sources.",
    "uncertain": "Claims could not be verified against reliable sources.",
    "legitimate": "Still confirm unexpected requests through the official source.",
}


def build_image_prompt(verdict: VerdictResult) -> str:
    """
    Builds the prompt for the shareable awareness graphic. Generated for every
    verdict, not just scams: the headline, colours and wording follow the
    verdict, and the bullet points come from what the fact-check actually found
    about *this* content (red flags first, then the awareness tips).
    """
    label = verdict.label.value
    headline, look, list_title = _LABEL_STYLE.get(label, _LABEL_STYLE["uncertain"])

    points = (list(verdict.red_flags[:2]) + list(verdict.awareness_tips[:3]))[:4]
    if not points:
        points = [_DEFAULT_POINT.get(label, _DEFAULT_POINT["uncertain"])]
    points_text = "; ".join(points)

    # Keep the subheading short: long strings hurt legibility at small
    # WhatsApp thumbnail sizes even on a 4K canvas.
    subheading = verdict.summary[:140].strip()

    return (
        "Design a clean, shareable public-awareness graphic meant to be forwarded on "
        "WhatsApp so family and friends learn something useful about a message, image, "
        "video or link that was just fact-checked. Portrait layout, "
        f"{look} near the top, simple modern public-safety-poster style, "
        "high contrast, not cluttered. Render the following text accurately, legibly, "
        "and exactly as written, with correct spelling:\n"
        f'- Large bold headline at the top: "{headline}"\n'
        f'- Medium-size subheading below it: "{subheading}"\n'
        f'- A short bullet list titled "{list_title}" listing: {points_text}\n'
        '- Small footer text at the bottom: "Verify before you forward. '
        'AI-generated fact-check, not a substitute for official confirmation."\n'
        "The design must stay legible even when viewed as a small chat thumbnail."
    )