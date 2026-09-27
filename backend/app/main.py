"""
FastAPI application for the AI Media Legitimacy Checker.

Run with:  uvicorn app.main:app --reload   (from the backend/ directory)
or simply: python run.py                   (from the backend/ directory)
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import budget_guard, gemini_client
from .config import FRONTEND_DIR, STATIC_DIR, VERDICT_IMAGE_DIR, settings
from .schemas import AnalyzeResponse, UsageStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VERDICT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI Media Legitimacy Checker",
    description="Uploads a message, image or video and returns a sourced AI verdict on whether it's genuine.",
    version="1.0.0",
)

# Assumption: this app is deployed as a single self-contained service (API +
# static frontend on the same origin), so CORS mainly matters if you call
# the API from a different origin (e.g. testing from a separate frontend).
# Defaults to "*" for local dev; set ALLOWED_ORIGINS in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

# Flat, conservative pre-flight estimates (in INR) used only to decide
# whether there is *headroom* before spending real tokens on a call. The
# real, usage-based cost is recorded afterwards via budget_guard.record_spend_inr.
PRE_FLIGHT_TEXT_ESTIMATE_INR = 1.0
PRE_FLIGHT_IMAGE_ESTIMATE_INR = 25.0


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/usage", response_model=UsageStatus)
def usage() -> UsageStatus:
    return budget_guard.get_budget_status()


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    text: Optional[str] = Form(default=None, description="Pasted message text or a link."),
    note: Optional[str] = Form(default=None, description="Optional extra context from the user."),
    file: Optional[UploadFile] = File(default=None, description="An image or video to check."),
) -> AnalyzeResponse:
    if not text and not file:
        raise HTTPException(400, "Provide either a message/link as text, or upload a file.")

    media_bytes: Optional[bytes] = None
    media_mime_type: Optional[str] = None

    if file is not None:
        media_mime_type = file.content_type or ""
        if media_mime_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(
                415,
                f"Unsupported file type '{media_mime_type}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_MEDIA_TYPES))}.",
            )
        media_bytes = await file.read()
        size_mb = len(media_bytes) / (1024 * 1024)
        if size_mb > settings.max_upload_mb:
            raise HTTPException(
                413, f"File is {size_mb:.1f} MB; the limit is {settings.max_upload_mb:.0f} MB."
            )

    try:
        budget_guard.ensure_budget_available(PRE_FLIGHT_TEXT_ESTIMATE_INR)
    except budget_guard.BudgetExceededError as exc:
        raise HTTPException(429, str(exc)) from exc

    try:
        outcome = gemini_client.analyze_content(
            text=text, media_bytes=media_bytes, media_mime_type=media_mime_type, note=note
        )
    except gemini_client.GeminiClientError as exc:
        raise HTTPException(502, str(exc)) from exc

    budget_guard.record_spend_inr(outcome.estimated_cost_inr)

    warning_image_url = None
    if outcome.verdict.label.value in ("likely_fake", "scam"):
        warning_image_url = _try_generate_warning_image(outcome.verdict)

    return AnalyzeResponse(verdict=outcome.verdict, warning_image_url=warning_image_url)


def _try_generate_warning_image(verdict) -> Optional[str]:
    """
    Best-effort image generation: a missing image should never break the
    text verdict the user already received.
    """
    try:
        budget_guard.ensure_budget_available(PRE_FLIGHT_IMAGE_ESTIMATE_INR)
    except budget_guard.BudgetExceededError as exc:
        logger.warning("Skipping verdict image: %s", exc)
        return None

    try:
        image_outcome = gemini_client.generate_verdict_image(verdict)
    except gemini_client.GeminiClientError as exc:
        logger.warning("Verdict image generation failed: %s", exc)
        return None

    budget_guard.record_spend_inr(image_outcome.estimated_cost_inr)

    filename = f"{uuid.uuid4().hex}.png"
    (VERDICT_IMAGE_DIR / filename).write_bytes(image_outcome.png_bytes)
    return f"/static/verdicts/{filename}"


# Static mounts must come after the API routes above so /api/* is matched first.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
