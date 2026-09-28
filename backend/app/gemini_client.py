import asyncio
import io
import os
import pathlib
import uuid
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

from . import config as c, pricing
from .scam_prompts import ANALYZE_SYSTEM, image_prompt
from .schemas import Source, VerdictResult

OUT = pathlib.Path("generated"); OUT.mkdir(exist_ok=True)
_client = None
UA = {"User-Agent": "Mozilla/5.0 (compatible; ScamCheckerLinkCheck/1.0)"}
MAX_SOURCES = 4


def client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


# ---------- source verification ----------

def _domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _grounded(resp) -> list[tuple[str, str]]:
    """Pages Gemini's search actually retrieved: (uri, title)."""
    out = []
    try:
        gm = resp.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or []):
            if ch.web and ch.web.uri:
                out.append((ch.web.uri, ch.web.title or ""))
    except (AttributeError, IndexError, TypeError):
        pass
    return out


async def _reachable(http: httpx.AsyncClient, url: str) -> str | None:
    """Return the final URL if the page exists, else None.
    404/410 and connection errors are dead. 401/403/429 mean the site blocks bots
    but the page is real, so those are kept."""
    if not url.startswith(("http://", "https://")):
        return None
    try:
        r = await http.get(url)
    except Exception:
        return None
    if r.status_code < 400 or r.status_code in (401, 403, 429):
        return str(r.url)
    return None


async def _verified_sources(v: VerdictResult, grounded: list[tuple[str, str]]) -> list[Source]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=6, headers=UA) as http:
        model_final, grounded_final = await asyncio.gather(
            asyncio.gather(*[_reachable(http, s.url) for s in v.sources]),
            asyncio.gather(*[_reachable(http, u) for u, _ in grounded[:8]]),
        )
    result: list[Source] = []
    seen: set[str] = set()

    def add(title: str, url: str, note: str):
        d = _domain(url)
        if d and d not in seen and len(result) < MAX_SOURCES:
            seen.add(d)
            result.append(Source(title=title or d, url=url, note=note))

    # 1. model-written sources, only if the page really exists
    for s, final in zip(v.sources, model_final):
        if final:
            add(s.title, final, s.note)
    # 2. pages the search actually retrieved
    for (_, title), final in zip(grounded[:8], grounded_final):
        if final:
            add(title, final, "Found while checking this content.")
    return result


# ---------- analysis ----------

async def analyze(text: str, file: tuple[bytes, str] | None) -> tuple[VerdictResult, float]:
    parts, uploaded = [], None
    if file:
        data, mime = file
        if mime.startswith("video/"):
            uploaded = await client().aio.files.upload(
                file=io.BytesIO(data), config=types.UploadFileConfig(mime_type=mime))
            for _ in range(60):  # wait up to ~2 min for processing
                uploaded = await client().aio.files.get(name=uploaded.name)
                state = getattr(uploaded.state, "name", str(uploaded.state))
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError("Video processing failed")
                await asyncio.sleep(2)
            else:
                raise RuntimeError("Video processing timed out")
            parts.append(types.Part.from_uri(file_uri=uploaded.uri, mime_type=mime))
        else:
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    parts.append(types.Part.from_text(text=text or "Check the attached content."))
    try:
        resp = await client().aio.models.generate_content(
            model=c.TEXT_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=ANALYZE_SYSTEM,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=VerdictResult,
            ),
        )
    finally:
        if uploaded:
            try:
                await client().aio.files.delete(name=uploaded.name)
            except Exception:
                pass
    verdict = VerdictResult.model_validate_json(resp.text)
    verdict.sources = await _verified_sources(verdict, _grounded(resp))
    u = resp.usage_metadata
    cost = pricing.text_cost(u.prompt_token_count or 0, u.candidates_token_count or 0)
    return verdict, cost


# ---------- poster ----------

async def make_poster(v: VerdictResult) -> str | None:
    resp = await client().aio.models.generate_content(
        model=c.IMAGE_MODEL,
        contents=image_prompt(v),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="3:4", image_size=c.IMAGE_SIZE),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            name = f"{uuid.uuid4().hex}.png"
            (OUT / name).write_bytes(part.inline_data.data)
            return f"/generated/{name}"
    return None