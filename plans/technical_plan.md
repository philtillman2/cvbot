# CVbot — Technical Implementation Plan

## Problem Statement
Build a web application where a hiring manager can chat with a candidate's work experience via an LLM. The app uses FastAPI/Jinja2/Bootstrap/vanilla JS with SQLite and OpenRouter.ai for LLM integration. The UI should be modern and sleek like T3 Chat with streaming responses, light/dark mode, and a cost tracking dashboard.

## Proposed Approach
A single-server FastAPI application with:
- **Server-Sent Events (SSE)** for streaming LLM responses to the browser
- **OpenRouter.ai** (OpenAI-compatible API) for LLM chat completions
- **SQLite** via `aiosqlite` for async DB access
- **Candidate profiles** loaded from JSON files and injected into the system prompt
- **Chart.js** for cost tracking visualizations

---

## Architecture

### Directory Structure
```
cvbot/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan, mount static
│   ├── config.py               # Settings (env vars: OPENROUTER_API_KEY, DB_PATH, etc.)
│   ├── database.py             # SQLite setup, migrations, async helpers
│   ├── models.py               # Pydantic models (Candidate, Message, Conversation, LLMRequest)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py             # Chat page + SSE streaming endpoint
│   │   ├── conversations.py    # CRUD for conversations (list, create, delete)
│   │   ├── candidates.py       # List/view candidates
│   │   └── costs.py            # Cost tracking API (JSON data for charts)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py              # OpenRouter client (streaming chat completions)
│   │   ├── candidate_loader.py # Load & parse candidate JSON files
│   │   └── cost_tracker.py     # Log & query LLM request costs
│   ├── templates/
│   │   ├── base.html           # Base layout (Bootstrap 5, theme toggle, nav)
│   │   ├── chat.html           # Main chat UI (sidebar + message area)
│   │   └── costs.html          # Cost tracking dashboard
│   └── static/
│       ├── css/
│       │   └── style.css       # Custom styles (T3 Chat-inspired dark/light theme)
│       └── js/
│           ├── chat.js         # Chat logic: SSE listener, message rendering, markdown
│           ├── theme.js        # Light/dark mode toggle (system preference detection)
│           └── costs.js        # Chart.js charts for cost dashboard
├── data/
│   └── candidates/             # Candidate JSON files go here
│       └── phil_tillman.json
├── cvbot.db                    # SQLite database (created at runtime)
├── requirements.txt
├── .env.example
└── README.md
```

### Database Schema (SQLite)

```sql
-- Candidate metadata (denormalized from JSON for quick lookup)
CREATE TABLE candidates (
    id TEXT PRIMARY KEY,                    -- slug from filename, e.g. "phil_tillman"
    display_name TEXT NOT NULL,
    json_path TEXT NOT NULL,                -- path to source JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat conversations (one per candidate per session)
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    title TEXT,                             -- auto-generated or user-set
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat messages
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LLM cost tracking
CREATE TABLE llm_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER REFERENCES conversations(id),
    model_id TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL,                          -- computed from model pricing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirect to `/chat` |
| GET | `/chat` | Chat page (Jinja2 template) |
| GET | `/chat/{conversation_id}` | Chat page for specific conversation |
| POST | `/api/conversations` | Create new conversation (body: `{candidate_id}`) |
| GET | `/api/conversations` | List conversations |
| DELETE | `/api/conversations/{id}` | Delete a conversation |
| POST | `/api/chat/{conversation_id}` | Send message, returns SSE stream |
| GET | `/api/candidates` | List available candidates |
| GET | `/costs` | Cost dashboard page (Jinja2 template) |
| GET | `/api/costs/daily` | Daily cumulative cost data (JSON) |
| GET | `/api/costs/monthly` | Monthly cumulative cost data (JSON) |

### LLM Integration (OpenRouter.ai)

- **Endpoint**: `POST https://openrouter.ai/api/v1/chat/completions`
- **Auth**: `Authorization: Bearer $OPENROUTER_API_KEY`
- **Streaming**: `"stream": true` → Server-Sent Events
- **System prompt construction**:
  ```
  You are an AI assistant representing the professional experience of {candidate_name}.
  Answer questions about their work experience, skills, education, and publications
  based ONLY on the following data. If information is not in the data, say so.
  
  === CANDIDATE DATA ===
  {json.dumps(candidate_data, indent=2)}
  ```
- **Token counting**: Parse `usage` from the final SSE chunk (`usage.prompt_tokens`, `usage.completion_tokens`) or from response headers
- **Cost calculation**: Fetch model pricing from OpenRouter `/api/v1/models` endpoint (cache it), compute `cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000`

### Frontend Design (T3 Chat-inspired)

**Layout** (see t3chat.png reference):
- **Left sidebar** (collapsible on mobile):
  - "New Chat" button at top
  - Search threads input
  - List of past conversations grouped by recency
  - Candidate selector at bottom
- **Main area**:
  - Welcome screen with candidate name when no messages ("How can I help you?")
  - Scrollable message list (user bubbles right-aligned, assistant left-aligned)
  - Markdown rendering for assistant responses (use `marked.js` or similar lightweight lib)
  - Input area at bottom: textarea + send button
  - Model selector dropdown (populate from OpenRouter)

**Streaming UX**:
- On send: POST to `/api/chat/{conversation_id}` 
- Read SSE stream via `EventSource` or `fetch` + `ReadableStream`
- Append tokens to assistant message div in real-time
- After stream ends, render final markdown

**Theme**:
- CSS custom properties for all colors (background, text, accent, sidebar)
- `prefers-color-scheme` media query for auto-detection
- Manual toggle stored in `localStorage`
- Dark theme: deep purple/charcoal palette (like T3 Chat screenshot)
- Light theme: clean white/gray

### Cost Tracker Dashboard

- **Daily cumulative line chart** (Chart.js): x-axis = date, y-axis = cumulative USD
- **Monthly cumulative bar chart** (Chart.js): x-axis = month, y-axis = total USD
- Data fetched from `/api/costs/daily` and `/api/costs/monthly`
- Show breakdown by model if multiple models used

---

## Implementation Todos

1. **project-setup** — Initialize Python project: `requirements.txt`, `.env.example`, directory structure, FastAPI app skeleton with Jinja2 and static file mounting
2. **database-setup** — Implement SQLite database: schema creation, async connection helpers using `aiosqlite`, migration on startup
3. **candidate-loader** — Build candidate JSON loader service: read from `data/candidates/`, parse into Pydantic models, register in DB
4. **llm-service** — Implement OpenRouter.ai LLM client: streaming chat completions via `httpx`, SSE parsing, token usage extraction
5. **chat-api** — Build chat API routes: create/list/delete conversations, POST message with SSE streaming response, message persistence
6. **chat-frontend** — Build chat UI: T3 Chat-inspired layout with Bootstrap 5, sidebar with conversation list, message area, streaming JS with `fetch` + `ReadableStream`, markdown rendering via `marked.js`
7. **theme-system** — Implement light/dark theme: CSS custom properties, `prefers-color-scheme` detection, manual toggle with `localStorage` persistence
8. **cost-tracker** — Implement cost tracking: log each LLM request with token counts, fetch model pricing from OpenRouter, compute costs, store in `llm_requests` table
9. **cost-dashboard** — Build cost dashboard page: daily cumulative line chart and monthly bar chart using Chart.js, API endpoints for aggregated cost data
10. **system-prompt** — Design and tune the system prompt: inject full candidate JSON, instruct the LLM to answer only from provided data, handle edge cases (unknown info, comparisons)
11. **responsive-polish** — Mobile responsiveness: collapsible sidebar, touch-friendly input, viewport-appropriate sizing
12. **testing-docs** — Write README with setup instructions, add `.env.example`, basic smoke tests

## Dependencies (`requirements.txt`)
```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
jinja2>=3.1.0
aiosqlite>=0.20.0
httpx>=0.28.0
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

## Key Technical Decisions
- **`httpx` over `openai` SDK**: Lighter weight, direct control over SSE parsing, no unnecessary dependency
- **`aiosqlite`**: Non-blocking DB access in async FastAPI handlers
- **No ORM**: SQLite is simple enough for raw SQL; avoids SQLAlchemy overhead
- **`marked.js`** for client-side markdown: Small, fast, no build step needed
- **Chart.js** for cost visualizations: Well-known, no build step, CDN-loadable
- **JSON files for candidates**: Simple filesystem-based storage; no admin UI needed initially
