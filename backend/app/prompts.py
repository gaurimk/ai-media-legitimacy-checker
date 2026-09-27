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


_LABEL_HEADLINES = {
    "scam": "SCAM ALERT",
    "likely_fake": "LIKELY FAKE",
}


def build_image_prompt(verdict: VerdictResult) -> str:
    """Builds the prompt for the 4K shareable warning graphic."""
    headline = _LABEL_HEADLINES.get(verdict.label.value, "WARNING: UNVERIFIED")
    top_flags = verdict.red_flags[:3]
    flags_text = "; ".join(top_flags) if top_flags else "Claims could not be verified against reliable sources."
    # Keep the subheading short: long strings hurt legibility at small
    # WhatsApp thumbnail sizes even on a 4K canvas.
    subheading = verdict.summary[:140].strip()

    return (
        "Design a clean, shareable warning graphic meant to be forwarded on WhatsApp "
        "to warn family and friends about a scam or fake message. Portrait layout, "
        "bold red-and-white colour scheme, a clear warning-triangle icon near the top, "
        "simple modern public-safety-poster style, high contrast, not cluttered. "
        "Render the following text accurately, legibly, and exactly as written, with "
        "correct spelling:\n"
        f'- Large bold headline at the top: "{headline}"\n'
        f'- Medium-size subheading below it: "{subheading}"\n'
        f'- A short bullet list titled "Why this looks fake" listing: {flags_text}\n'
        '- Small footer text at the bottom: "Verify before you forward. '
        'AI-generated fact-check, not a substitute for official confirmation."\n'
        "The design must stay legible even when viewed as a small chat thumbnail."
    )
