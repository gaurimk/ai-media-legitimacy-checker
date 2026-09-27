"""
Convenience entry point: `python run.py` from the backend/ directory.

Reads HOST/PORT/RELOAD from the environment so the exact same command works:
- locally            -> http://127.0.0.1:8000, auto-reload on file changes
- on Render or similar -> binds 0.0.0.0:$PORT, no reload (production mode)

Render (and most PaaS hosts) set PORT automatically; nothing extra to
configure there beyond your other env vars (GEMINI_API_KEY, etc.).
"""
import os

import uvicorn

if __name__ == "__main__":
    # If a platform supplied PORT, assume we're not on a local machine and
    # need to bind all interfaces, not just localhost.
    host = os.environ.get("HOST", "0.0.0.0" if "PORT" in os.environ else "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    # Auto-reload only makes sense for local dev; default it off whenever a
    # PORT is supplied by the platform (a reliable signal we're not local).
    reload = os.environ.get("RELOAD", "0" if "PORT" in os.environ else "1") == "1"

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
