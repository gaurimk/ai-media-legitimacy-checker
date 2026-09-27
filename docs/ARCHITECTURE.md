# Architecture

## Pipeline

```
Browser (frontend/)
   │  POST /api/analyze  (text or file, multipart form)
   ▼
FastAPI backend (backend/app/main.py)
   │  1. Validate input (type, size)
   │  2. Check local monthly budget guard
   ▼
Gemini analysis model  (gemini-3.5-flash-lite)
   - Reads the text/image/video
   - Uses the google_search + url_context tools to check the claim
     against real web sources
   - Returns a Structured Output matching VerdictResult's JSON schema
   ▼
FastAPI backend
   │  Record actual estimated cost against the monthly budget
   │  If verdict is "likely_fake" or "scam":
   ▼
Gemini image model  (gemini-3-pro-image / Nano Banana Pro)
   - Renders a 4K, text-heavy warning graphic based on the verdict
   ▼
FastAPI backend
   │  Save the PNG under backend/app/static/verdicts/, return its URL
   ▼
Browser renders the verdict, sources, and (if applicable) a
downloadable/shareable warning image.
```

## Why these two models

Both are chosen from the official Gemini model list
(https://ai.google.dev/gemini-api/docs/models), current as of September 2026:

- **`gemini-3.5-flash-lite`** for analysis/reasoning: it is the cheapest
  Gemini 3.x model that still supports multimodal input (text, image, video),
  Google Search grounding, URL Context, and Structured Outputs -- the
  combination this app needs on a Rs 2,500/month budget. If your account
  needs stronger reasoning (e.g. for tricky, ambiguous claims), swap in
  `gemini-3.6-flash` or `gemini-3.1-pro-preview` via the `ANALYSIS_MODEL`
  environment variable -- the code does not hardcode the model name anywhere
  else.
- **`gemini-3-pro-image`** (marketed as "Nano Banana Pro") for the verdict
  graphic: Google documents it specifically as the model tuned for "the
  highest level of world knowledge, advanced localization ... and precision
  creative control" for image generation, and its documentation calls out
  **accurate text rendering** at up to 4K resolution as a strength -- exactly
  what a warning graphic with several lines of legible text needs. The
  cheaper `gemini-3.1-flash-image` is a reasonable fallback via
  `IMAGE_MODEL` if you want to trade some quality for lower cost.

All Nano Banana-family images include an invisible SynthID watermark, which
is a nice property for a scam-warning graphic that people will forward --
it stays traceable as AI-generated.

## Why Structured Outputs + tools together

Gemini 3 models support combining **Structured Outputs** (a JSON Schema the
model's response must match) with built-in tools like Google Search and URL
Context in the same request
(https://ai.google.dev/gemini-api/docs/structured-output#structured-outputs-with-tools).
This app relies on that combination directly: `gemini_client.analyze_content()`
sends both `tools` and a Pydantic-derived `response_format` schema in one
call, so the model is required to ground its claim-checking in real search
results *and* return a response the backend can safely parse into
`VerdictResult` without brittle regex/string parsing.

**Assumption:** at the time this project was built, this combination was
documented as a preview feature for Gemini 3 series models. If a future
account/model combination doesn't support it, the error will surface as a
`GeminiClientError` from `analyze_content()` -- switch `ANALYSIS_MODEL` to
another Gemini 3.x model in `.env` if that happens.

## Budget guard: what it is and isn't

`backend/app/budget_guard.py` keeps a simple per-month running total (in
`backend/data/usage.json`) of the *estimated* INR cost of every Gemini call,
using the pricing constants in `backend/app/pricing.py`. Before every
analysis or image-generation call, the backend checks whether the call would
push the running total past `MONTHLY_BUDGET_INR` and, if so, skips the call
(returning HTTP 429 for analysis, or silently skipping just the image for a
verdict that's already been computed).

**This is a soft, best-effort safeguard, not a hard billing cap:**

- It only sees calls made through this app -- if the same API key is used
  elsewhere, those calls aren't counted here.
- Its cost estimates depend on the pricing table in `pricing.py` staying in
  sync with Google's published pricing
  (https://ai.google.dev/gemini-api/docs/pricing). Prices can change.
- It ignores Google Search grounding request costs (5,000 requests/month are
  shared free across Gemini 3.x models as of this writing; beyond that,
  Google bills per search request). At the expected usage volume for a
  Rs 2,500/month pilot this should stay within the free tier, but it is not
  metered here.

**Recommendation:** pair this in-app guard with a real budget alert
configured in Google AI Studio / Cloud Console billing for the account's API
key, so a bug in this app (or a key leak) cannot silently overspend.

If the project genuinely needs more than Rs 2,500/month, the brief says to
raise that as a request to the team, explaining why, before increasing usage
or `MONTHLY_BUDGET_INR` -- that approval step is intentionally a manual,
outside-the-code process, up to Rs 20,000.

## Assumptions made building this

- **"A message containing a link"** is handled as pasted text (the message,
  including the link), not a live WhatsApp integration -- there is no
  WhatsApp Business API wiring in this project.
- **Video support** relies on inlining the uploaded bytes as base64 in the
  request. `MAX_UPLOAD_MB` (default 20 MB) exists to keep both request size
  and per-call cost predictable; for materially larger files you would want
  to switch to the Gemini Files API (`client.files.upload`) instead of
  inlining bytes.
- **USD→INR conversion** (`USD_TO_INR_RATE`) is a static, configurable
  number because Gemini API billing is in USD. Update it to the current rate
  for an accurate budget estimate.
- **Single-process deployment**: the usage counter is a local JSON file, not
  a database -- fine for a single backend instance evaluating this pipeline,
  but not safe for multiple replicas writing concurrently.
- No authentication/rate-limiting per end user is implemented -- this is a
  test build for evaluating the AI pipeline, not a public-facing production
  service.
