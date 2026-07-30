# a_Quant

A composite stock signal analyzer — trend, risk, volume, institutional & insider
activity, and free cash flow, all pulled from Yahoo Finance (via `yfinance`) into
one plain-English report.

## Architecture

- **Backend**: FastAPI (`api.py` + `stock_tool.py`), deployed on Render at
  `https://a-quant.onrender.com`.
- **Frontend**: static HTML/CSS/JS (`index.html`, `static/`), deployed on GitHub
  Pages at `https://johnhazukajr.github.io/a_Quant/`.
- **Endpoints**: `GET /report/{ticker}` returns the full signal report as JSON;
  `GET /health` is a dependency-free liveness check.

The two deployments are wired together by two places that must stay in sync if
either domain ever changes:
- `api.py`'s `allow_origins` (CORS) must include the GitHub Pages origin.
- `static/app.js`'s `API_BASE` must point at the Render URL when running on
  GitHub Pages (it uses a relative path everywhere else, including local dev).

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn api:app --reload
```

Then open `http://127.0.0.1:8000`. Locally, `app.js`'s `API_BASE` resolves to an
empty string, so the frontend calls the backend on the same origin — no CORS or
separate hosting needed for local dev.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests run entirely against mocked yfinance calls — no real network access or API
quota is used.

## Deployment

- **Render (backend)**: redeploys automatically on push to `main` (or manually via
  the Render dashboard). Build command: `pip install -r requirements.txt`. Start
  command: `uvicorn api:app --host 0.0.0.0 --port $PORT`. `render.yaml` documents
  this configuration, but Render only treats it as the live source of truth if
  Blueprint/Infrastructure-as-Code sync is explicitly enabled for the service in
  the dashboard — check that setting if you want the file to be authoritative.
- **GitHub Pages (frontend)**: redeploys automatically on push to whichever
  branch/folder Pages is configured to serve from repo settings.

## Notes

This is an educational analysis tool, not financial advice. No combination of
these signals reliably predicts future price movement.
