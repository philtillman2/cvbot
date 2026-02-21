# CVbot

CVbot is a web application where a hiring manager can chat with the work experience of a specific candidate via an LLM.

## Tech Stack

- **Backend**: FastAPI, Jinja2, SQLite (aiosqlite), httpx
- **Frontend**: Bootstrap 5, vanilla JavaScript, marked.js, Chart.js
- **LLM**: OpenRouter.ai (streaming via SSE)

## Setup

```bash
# Clone and enter the project
cd cvbot

# Install dependencies
uv sync

# Configure environment and app config
# Create/edit secrets/.env and set:
# - ENV=dev
# - OPENROUTER_API_KEY=...
# Then adjust config/config-dev.yaml if needed

# Add candidate JSON files to data/candidates/
# (see plans/CVbot prompt.md for the JSON schema)

# Run the server
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## Features

- **Chat with candidate experience**: Select a candidate and ask questions about their work history, skills, education
- **Streaming responses**: Real-time token-by-token LLM output via Server-Sent Events
- **Light/Dark theme**: Auto-detects system preference, with manual toggle
- **Job fit analysis page**: Paste a job description and get a structured fit assessment with overall verdict, plus side-by-side strengths/pros and weaknesses/cons cards
- **Cost dashboard**: Track LLM usage with daily cumulative line chart and monthly bar chart
- **Multiple models**: Choose from GPT-4o, Claude, Gemini via OpenRouter

## Project Structure

```
app/
├── main.py              # FastAPI app entry point
├── config.py            # Settings (env vars)
├── database.py          # SQLite schema & helpers
├── models.py            # Pydantic models
├── routers/             # API routes (chat, conversations, candidates, costs, job_fit)
├── services/            # Business logic (LLM client, candidate loader, cost tracker)
├── templates/           # Jinja2 HTML templates
└── static/              # CSS and JavaScript
data/candidates/         # Candidate JSON profiles
```
