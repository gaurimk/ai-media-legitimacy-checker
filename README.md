# AI Media Legitimacy Checker

Paste a message or link, or upload a screenshot or short video. The app checks it against the web with Gemini, says whether it looks **legitimate, likely fake, a scam, or uncertain**, explains why in plain language, and for scams and fakes generates a shareable warning poster.

- **Inputs:** text, links, images (PNG, JPG, WebP), videos (MP4, MOV, WebM, 3GP). Up to 50 MB. No PDFs.
- **Reasoning:** `gemini-3.5-flash-lite` with Google Search grounding and a structured JSON schema.
- **Poster:** `gemini-3-pro-image`, only for `scam` and `likely_fake` verdicts, created in a second request so the verdict appears first.
- **Budget guard:** monthly spend cap (default Rs 2,500), tracked from token usage and per-image cost estimates.
- **Frontend:** one HTML page, no build step.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the pipeline and design decisions.

## Project layout

```
.
├── README.md
├── render.yaml                 # Render blueprint
├── docs/ARCHITECTURE.md
└── backend/
    ├── run.py                  # local dev entry point (uvicorn, reload)
    ├── requirements.txt
    ├── app/
    │   ├── main.py             # FastAPI routes
    │   ├── gemini_client.py    # analysis + poster generation
    │   ├── scam_prompts.py     # system prompt + poster prompt
    │   ├── sanitize.py         # strips links and phone numbers before the image prompt
    │   ├── schemas.py          # Pydantic models (also the Gemini output schema)
    │   ├── budget.py           # monthly cap, usage.json
    │   ├── pricing.py          # cost estimates
    │   └── config.py           # env-driven settings
    ├── static/index.html       # the whole UI
    └── tests/test_core.py
```

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
python run.py                   # http://127.0.0.1:8000
pytest
```

## Configuration

All settings are environment variables. Only `GEMINI_API_KEY` is required.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | none | Gemini API key. Never commit it. |
| `TEXT_MODEL` | `gemini-3.5-flash-lite` | Reasoning model |
| `IMAGE_MODEL` | `gemini-3-pro-image` | Poster model |
| `IMAGE_SIZE` | `4K` | Set `2K` for faster, cheaper posters |
| `MONTHLY_CAP_INR` | `2500` | Monthly spend cap |
| `INR_PER_M_INPUT` | `10` | Estimated Rs per 1M input tokens |
| `INR_PER_M_OUTPUT` | `40` | Estimated Rs per 1M output tokens |
| `INR_PER_IMAGE_4K` | `20` | Estimated Rs per poster |
| `USAGE_FILE` | `usage.json` | Where monthly spend is stored |

The rupee rates are estimates. Compare `/api/usage` with Google's billing page and adjust them.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | multipart: `text` and/or `file`. Returns the verdict. |
| POST | `/api/poster` | JSON verdict in, `{warning_image_url}` out. Scam or fake only. |
| POST | `/api/feedback` | Thumbs up or down on a verdict |
| GET | `/api/usage` | Spend this month against the cap |

## Deploy on Render

1. Push this repo to GitHub (steps below).
2. In Render choose **New > Blueprint**, connect the repo, and pick `render.yaml`.
3. When asked, set `GEMINI_API_KEY`.
4. Deploy. Open the `onrender.com` URL. `/api/usage` is the health check.

Or create a **Web Service** by hand: root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and add the environment variables above.

### Before you make the URL public

- **Storage is temporary on Render's free plan.** `usage.json` and the `generated/` posters are wiped on every deploy and restart, so the budget cap resets and old poster links break. For a reliable cap, attach a Render persistent disk (paid), mount it at `/data`, and set `USAGE_FILE=/data/usage.json`.
- **There is no login or rate limiting yet.** Anyone with the URL can use your Gemini quota until the cap is hit. Keep the link private, or add per-IP rate limiting first.
- **Free instances sleep** after inactivity, so the first request can take a while.

## Push to GitHub

```bash
git status                      # confirm .env, .venv, usage.json, generated/ are NOT listed
git add .
git commit -m "Scam checker: video support, async poster, docs, Render config"
git push origin main
```

If a key was ever committed, revoke it in Google AI Studio and create a new one. Deleting the file is not enough, because it stays in git history.

## Known limitations

- Links are judged from their wording, domain, and web search. The app does not open the page.
- Source links come from the model and are not cross-checked against search metadata.
- Verdicts are an aid, not proof. The app returns `uncertain` when evidence is weak.
- Posters may contain small text errors. Check before sharing widely.