# AI Media Legitimacy Checker

A small, self-contained web app: paste a suspicious message/link, or upload
an image or video circulating on WhatsApp/social media, and get back a
plain-language AI verdict — **legitimate**, **likely fake**, **scam**, or
**uncertain** — backed by the actual web sources the AI checked. If the
verdict is fake or a scam, the app also generates a downloadable,
shareable 4K warning graphic you can forward to warn others.

This is a test build for evaluating an agentic-AI pipeline (multimodal
reasoning + live web grounding + image generation) end to end, built against
a fixed Rs 2,500/month Gemini API budget.

## How it works

1. **Analysis** — [`gemini-3.5-flash-lite`](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
   reads the submitted text/image/video, uses the **Google Search** and
   **URL Context** tools to check the claim against real sources, and
   returns a structured, schema-validated verdict (no fragile text parsing).
2. **Warning image** — if the verdict is fake/scam,
   [`gemini-3-pro-image`](https://ai.google.dev/gemini-api/docs/models/gemini-3-pro-image)
   ("Nano Banana Pro", chosen for its accurate text rendering) generates a
   4K, WhatsApp-shareable warning graphic with the verdict baked in as
   legible text.
3. A local budget guard tracks estimated spend for both calls and stops
   before the configured monthly cap is exceeded.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full pipeline
diagram, why these specific models were chosen, and the assumptions made
while building this.

## Project structure

```
ai-media-legitimacy-checker/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   └── ARCHITECTURE.md        # pipeline, model choice, assumptions
├── backend/
│   ├── requirements.txt       # runtime dependencies
│   ├── requirements-dev.txt   # + pytest, httpx
│   ├── .env.example           # copy to .env and fill in your API key
│   ├── pytest.ini
│   ├── run.py                 # `python run.py` to start the dev server
│   ├── app/
│   │   ├── main.py            # FastAPI routes
│   │   ├── config.py          # settings, loaded from environment variables
│   │   ├── schemas.py         # Pydantic models (also used as the Gemini
│   │   │                      #   Structured Output schema)
│   │   ├── prompts.py         # prompt templates for both Gemini calls
│   │   ├── gemini_client.py   # all Gemini API calls live here
│   │   ├── pricing.py         # Gemini pricing constants + cost estimation
│   │   ├── budget_guard.py    # local monthly spend tracking/cap
│   │   └── static/verdicts/   # generated warning images are saved here
│   └── tests/                 # pytest unit tests (see Testing, below)
└── frontend/
    ├── index.html             # single-page upload UI, no build step
    ├── styles.css
    └── app.js
```

## Prerequisites

- Python 3.11+
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Setup

```bash
# 1. Clone and enter the project
git clone <this-repo-url>
cd ai-media-legitimacy-checker/backend

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=<your key>

# 5. Run the server
python run.py
```

Open **http://127.0.0.1:8000** in your browser — the FastAPI backend also
serves the frontend, so there's nothing else to start.

## Usage examples

**Via the web UI:** paste a message/link or upload an image/video, add
optional context, and click "Check this."

**Via curl** (checking a pasted message):

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "text=Congratulations! You've won a lottery. Pay Rs 500 to claim: bit.ly/xyz" \
  -F "note=Received this on WhatsApp from an unknown number"
```

**Via curl** (checking an uploaded screenshot):

```bash
curl -X POST http://127.0.0.1:8000/api/analyze \
  -F "file=@/path/to/screenshot.png"
```

Example response shape:

```json
{
  "verdict": {
    "label": "scam",
    "confidence": 0.93,
    "summary": "This message asks for an upfront payment to release a lottery prize, a classic advance-fee scam pattern with no legitimate lottery involved.",
    "red_flags": ["Requests an upfront payment", "Creates false urgency", "Uses a shortened, unverifiable link"],
    "sources": [
      {"title": "Consumer protection advisory", "url": "https://example.gov/advisory", "note": "Confirms this exact scam pattern is currently circulating."}
    ]
  },
  "warning_image_url": "/static/verdicts/3f9a1c2b.png"
}
```

**Checking remaining budget for the month:**

```bash
curl http://127.0.0.1:8000/api/usage
```

## Testing

Unit tests cover the schema validation, prompt building, cost-estimation
math, and the Gemini client's request/response handling (via a mocked
client, so tests never make real network calls or spend budget):

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Budget

Fixed at **Rs 2,500/month** (see [`.env.example`](backend/.env.example) →
`MONTHLY_BUDGET_INR`), enforced by the local guard in
[`backend/app/budget_guard.py`](backend/app/budget_guard.py) — see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#budget-guard-what-it-is-and-isnt)
for exactly what that guard does and doesn't cover.

Rough estimate at moderate usage (based on Gemini's published per-token and
per-image pricing as of September 2026): ~300 checks/month, ~30% flagged as
fake/scam and triggering a 4K warning image, comes to roughly **Rs 2,000–2,200**
— leaving headroom under the cap, but the guard exists precisely so you don't
have to trust that estimate.

If the project genuinely needs more than Rs 2,500/month, raise a request
with the team explaining why *before* increasing `MONTHLY_BUDGET_INR` or
usage — per the brief, this can go up to Rs 20,000 with approval.

## Known limitations & assumptions

- This checks a *pasted* message/link or an uploaded file — there's no live
  WhatsApp/social-media integration.
- The budget guard is a soft, in-app estimate, not a hard Google Cloud
  billing cap (pair it with a real billing alert for production use).
- No per-user authentication or rate limiting — this is a pipeline
  evaluation build, not a hardened public service.
- Structured Outputs combined with Google Search + URL Context tools was, at
  the time of writing, documented as a preview capability for Gemini 3
  models; if your account/model combination rejects it, switch
  `ANALYSIS_MODEL` in `.env`.

Full details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## License

[MIT](LICENSE)
