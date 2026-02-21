# Copilot Instructions for CVbot

## Running the App

```bash
# Install dependencies
uv sync

# Run dev server
uv run uvicorn app.main:app --reload --port 8000
```

Environment: Python 3.12, managed with `uv`. Configuration via `.env` (see `.env.example`).

There are no tests or linters configured in this project.

## Architecture

CVbot is a FastAPI web app where hiring managers chat with candidate work experience via an LLM. The frontend is server-rendered Jinja2 + Bootstrap 5 with vanilla JS — there is no build step or JS framework.

**Request flow for chat:**
1. Browser sends user message → `POST /api/chat/{conversation_id}`
2. Router builds message history from DB, injects candidate JSON into system prompt
3. `services/llm.py` streams SSE from OpenRouter.ai (OpenAI-compatible API) via `httpx`
4. Tokens stream back to browser as SSE events, rendered in real-time with `marked.js`
5. After stream completes, full response is saved to DB and cost is logged

**Key services:**
- `services/llm.py` — OpenRouter client; streams chat completions, caches model pricing
- `services/candidate_loader.py` — Reads JSON files from `data/candidates/`, caches profiles in memory, registers them in SQLite on startup
- `services/cost_tracker.py` — Logs token usage per request, computes cost from cached pricing

**Database:** SQLite via `aiosqlite` (async). Single global connection in `database.py`. Schema auto-created on startup via `init_db()`. Raw SQL throughout — no ORM.

**Candidate data:** JSON files in `data/candidates/` named as `{slug}.json`. The slug becomes the candidate ID. The entire JSON is injected verbatim into the LLM system prompt.

## Conventions

- **No ORM** — all database access is raw SQL via `aiosqlite` with `Row` factory for dict-like access
- **Routers** go in `app/routers/`, **services** (business logic) go in `app/services/`
- **Templates** use Jinja2 in `app/templates/`, static assets in `app/static/`
- **Pydantic models** for both API request/response bodies and candidate JSON schema validation live in `app/models.py`
- **SSE streaming pattern**: routers return `StreamingResponse` with an `async def event_generator()` inner function that yields `data: {json}\n\n` lines
- **Config** via `pydantic-settings` in `app/config.py`, reads from `.env`
- Default LLM model is `openai/gpt-4o-mini` (set in Pydantic model defaults)
