# Agentpress

Open-source AI Agent Platform (agent infrastructure) focused on a self-hostable runtime and MCP-based plugin ecosystem.

## Quickstart (local)

### Prereqs
- Docker + Docker Compose

### Run
```bash
docker compose up --build
```

Backend: http://localhost:8000

### Optional API key (recommended for self-host)

Set an API key to protect `/agents` and `/plugins` endpoints:

```powershell
$env:AGENTPRESS_API_KEY = "your-secret"
```

Then pass it as either:
- `X-API-Key: your-secret`, or
- `Authorization: Bearer your-secret`

### Security defaults

Agentpress ships with basic HTTP hardening enabled by default:
- **Rate limiting** (in-memory, per API key or client IP)
- **Max request body size** (rejects large payloads with HTTP 413)

Configure via env vars:
```powershell
$env:AGENTPRESS_RATE_LIMIT_ENABLED = "true"
$env:AGENTPRESS_RATE_LIMIT_REQUESTS_PER_MINUTE = "120"
$env:AGENTPRESS_MAX_REQUEST_BODY_BYTES = "1000000"

# Only enable if you run behind a trusted reverse proxy that sets X-Forwarded-For
$env:AGENTPRESS_TRUST_PROXY_HEADERS = "false"
```

### Smoke test (backend)

Runs a quick end-to-end check (health, agents CRUD, chat SSE via `/tool`, and the `echo` plugin):

```powershell
./scripts/smoke-backend.ps1
```

Optional (requires Ollama running): validate auto tool-calling end-to-end:

```powershell
./scripts/smoke-auto.ps1
```

## API quick test (agents + chat)

Create an agent:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/agents -ContentType 'application/json' -Body (@{
	name='Test Agent'
	model='ollama'
	system_prompt='You are helpful.'
	temperature=0.2
} | ConvertTo-Json)
```

Stream chat (SSE). If Ollama is not running, you'll get an `event: error`:

```powershell
Invoke-WebRequest -Method Post -Uri http://127.0.0.1:8000/agents/<agent_id>/chat -ContentType 'application/json' -Body (@{
	message='Hello'
} | ConvertTo-Json) | Select-Object -ExpandProperty Content
```

### Plugin quick test (echo)

List plugins:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/plugins
```

Call the `echo` tool directly:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/plugins/echo/tools/echo -ContentType 'application/json' -Headers @{ 'x-agent-id'='<agent_id>' } -Body (@{
	params=@{ text='hello from plugin' }
} | ConvertTo-Json)
```

### Tool call visibility (MVP)

Chat streaming emits tool visibility events when a tool is executed:
- `tool_call_start`
- `tool_call_end`
- `tool_call_error`

Until full LLM tool-calling is wired, you can trigger a tool call explicitly with a developer directive:

```powershell
Invoke-WebRequest -Method Post -Uri http://127.0.0.1:8000/agents/<agent_id>/chat -ContentType 'application/json' -Body (@{
	message='/tool echo echo {"text":"hello"}'
} | ConvertTo-Json) | Select-Object -ExpandProperty Content
```

Tool calling mode is controlled by `AGENTPRESS_TOOL_CALLING_MODE`:
- `manual` (default): `/tool ...` works; normal chat does not auto-call tools yet
- `auto`: LLM-driven tool calling (model outputs `TOOL_CALL {...}`; Agentpress executes and feeds back `TOOL_RESULT ...`)
- `disabled`: tool execution is disabled

If auto mode is flaky with a given local model, keep `manual` and use `/tool ...` for deterministic tool execution.

## LLM cost strategy (OSS)

Agentpress is designed to be free to run: by default it assumes a **local LLM**.

- Default provider: Ollama (local)
- Optional providers: OpenAI / Anthropic (user supplies keys)

### Default local model

By default, Agentpress assumes `llama3` for best first-run quality. You can switch to a smaller model (e.g. `phi`, `qwen2`) by changing `AGENTPRESS_OLLAMA_MODEL`.

### Option A (easiest): Ollama in Docker

This repo includes an Ollama compose profile (also pulls the model on first run):

```bash
docker compose --profile ollama up --build
```

Set in `.env` (or env vars):
- `AGENTPRESS_LLM_PROVIDER=ollama`
- `AGENTPRESS_OLLAMA_BASE_URL=http://ollama:11434`

### Option B (best performance/GPU): native Ollama install

1) Install Ollama (Windows/Mac/Linux): https://ollama.com

2) Pull a model:
```bash
ollama pull llama3
```

3) Point Agentpress at your local Ollama:
- Backend running on host: `AGENTPRESS_OLLAMA_BASE_URL=http://localhost:11434`
- Backend running in Docker on Windows/Mac: `AGENTPRESS_OLLAMA_BASE_URL=http://host.docker.internal:11434`

See .env.example for all settings.

## Run backend without Docker (SQLite fallback)

If Docker Desktop isn't available, you can run the backend locally using SQLite.

Fastest path (PowerShell):
```powershell
./scripts/dev.ps1
```

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install fastapi "uvicorn[standard]" pydantic pydantic-settings "sqlalchemy[asyncio]" aiosqlite
$env:AGENTPRESS_DATABASE_URL = "sqlite+aiosqlite:///./.data/agentpress.db"
uvicorn app.main:app --reload --port 8000
```

## Plugin development (MCP over stdio)

See `plugins/templates/python-stdio` for a minimal stdio-first plugin template and `plugins/examples/echo` for a working example.
