# Architecture

## Pipeline

```
Browser (backend/static/index.html)
  |  multipart: text and/or one image/video
  v
POST /api/analyze
  |-- validate type (image/video only) and size (<= 50 MB)
  |-- budget.can_spend(reserve)  --no--> 429
  v
gemini_client.analyze
  |-- image: sent inline
  |-- video: uploaded via Gemini Files API, polled until ACTIVE, deleted after
  v
Gemini text model + Google Search grounding + JSON schema (VerdictResult)
  |-- cost recorded from token usage (pricing.text_cost)
  v
Verdict returned to the browser immediately
  |
  |  if label is scam or likely_fake, the browser then calls:
  v
POST /api/poster
  |-- budget.can_spend(image cost)  --no--> 429 (verdict already shown)
  |-- prompts.image_prompt: every text field passes through sanitize.scrub
  v
Gemini image model (3:4 poster, IMAGE_SIZE)  --> generated/<uuid>.png
  v
{warning_image_url}
```

## Decisions

**Two requests instead of one.** A 4K poster takes far longer than the verdict. Returning the verdict first means the person reads the answer straight away and the poster fills in when ready. A poster failure never hides the verdict.

**Posters only for scam and likely_fake.** A "do not trust this" poster on an uncertain result could wrongly brand real content as fake. It also saves image cost.

**Structured output.** `VerdictResult` in `schemas.py` is both the API model and the Gemini output schema, so field descriptions double as instructions to the model.

**Search grounding.** Verdicts are backed by web search, and sources are shown to the reader.

**Poster safety in code, not just in the prompt.** `sanitize.scrub` replaces links and phone numbers before the image prompt is built. The prompt also forbids real app logos. The model is not trusted to follow these alone.

**Budget guard.** Spend is estimated from token counts and a per-image rate, checked before each call, and stored per calendar month in a JSON file. Videos reserve more headroom than text because they use many more tokens.

**No build step.** The UI is a single HTML file with vanilla JS, served by FastAPI.

**One input at a time.** Choosing a file empties the text box, typing removes the file, and both clear after a successful check.

## Model choice

| Job | Model | Why |
|---|---|---|
| Verdict | `gemini-3.5-flash-lite` | Cheap and fast, supports search grounding, structured output, image and video input |
| Poster | `gemini-3-pro-image` | Needs readable text in the image (headline, numbered flags) |

Both IDs are configurable through environment variables.

## Assumptions

- Audience is everyday users in India, often on WhatsApp, so the poster is built to be shared in a group.
- Budget is an estimate from configured rates, not Google's billing data.
- One server instance. The budget file is not safe across several workers or instances.

## Limitations and next steps

- **Ephemeral storage on Render free:** budget state and posters reset on restart. Use a persistent disk or a small database.
- **No rate limiting or auth:** add per-IP limits before sharing the URL widely.
- **Sources are not verified** against grounding metadata.
- **Line and word limits** in schema descriptions (110 characters, 12 words) are not enforced in code.
- **Old posters are never deleted.** Add a cleanup job or object storage.
- **Links are not fetched.** Reading the destination page would catch scams on normal-looking domains.