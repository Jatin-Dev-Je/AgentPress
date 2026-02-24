# PRODUCT REQUIREMENTS DOCUMENT

# Agentpress

Self-Hosted Agent Runtime + MCP Plugin Ecosystem

Version 0.1 MVP  ·  February 2026  ·  Status: Draft

| Field | Value |
| --- | --- |
| Document Owner | TBD |
| Target Release | v0.1 (MVP) |
| Status | Draft |
| Date | February 21, 2026 |
| Audience | Engineering, Design, Stakeholders |

## 1. The Real Problem

Teams and individual developers want AI agents that do real work — call tools, automate tasks, integrate with internal systems. The existing landscape fails them in three specific ways:

- Most agent platforms are cloud-hosted, meaning sensitive data leaves the building on every request.
- Building a reliable agent runtime from scratch is non-trivial: streaming UX, tool execution, plugin isolation, auth, auditability, and safe defaults all need solving.
- Plugin and tool ecosystems are fragmented. There is no simple, stable interface that tool authors can target and runtime authors can rely on.

What no one has built well yet is a small, inspectable, self-hostable runtime where local LLMs are the default, tools are installed as plugins through a single standard interface, and every tool execution is visible and auditable. That is the gap Agentpress fills.

## 2. Strategic Position

The runtime is table stakes. The plugin ecosystem is the product. Ship five genuinely useful plugins on day one and the runtime gets adopted as a side effect.

Competitors (Dify, Open WebUI, LangChain) are all racing toward the same runtime capabilities. Agentpress wins by being the most auditable and the most plugin-friendly — not by out-featuring incumbents.

Primary differentiators

- Full tool-call visibility: every invocation streamed and logged — something users will screenshot and share.
- Local-first by default: Ollama out of the box, no required external accounts.
- Smallest inspectable surface: simple API, simple UI, easy for anyone to audit.
- Plugin contract stability: a clear, versioned MCP-over-stdio spec tool authors can build against confidently.

What makes this outstanding in the product queue

Lead every demo with a workflow people already feel pain around — not "an agent platform" but "the fastest way to run an AI agent against your internal APIs without sending data to OpenAI." The audit log should be beautiful. The getting-started time should be under 10 minutes. Three working, real-world plugins ship with v0.1.

## 3. Target Users

| Persona A — Self-Hosting Developer | Persona B — Small Team Automation |
| --- | --- |
| Runs tools on a workstation or home server. Wants local LLMs and complete data control. Needs a clear plugin API and a working example to copy. | Runs on a single VPS or office server. Wants to expose an internal agent UI to a few teammates. Cares about auth, rate limiting, and basic auditing. |
| Success metric: Ships their first custom plugin in under 30 minutes. | Success metric: Confident showing the audit log to their team. |

## 4. MVP Goals (v0.1)

1. Self-hostable runtime with one-command Docker Compose quickstart.
2. Agent workspace: create agents with model/provider selection and system prompts.
3. Streaming chat: reliable token streaming via SSE with persisted conversations.
4. Tool execution with full visibility — manual and optional auto modes.
5. Plugin ecosystem foundation: MCP-over-stdio contract, three real-world example plugins, and a developer template.
6. Secure defaults: API key protection, rate limiting, body size limits, security headers, tool allowlists.
7. Audit log UI that is genuinely beautiful — this is a differentiator, treat it as one.

## 5. Non-Goals (MVP)

These are explicitly out of scope for v0.1. Naming them reduces scope creep and keeps shipping velocity high.

- OAuth / JWT browser login — API key is sufficient for v0.1. Ship it later.
- Multi-tenant orgs, RBAC, or per-user permissions beyond API key auth.
- Hosted SaaS offering.
- Complex memory systems (vector search UX, long-term planning UI).
- Plugin marketplace, signing, or remote plugin installation.
- Container or VM-level isolation for plugins — subprocess stdio is acceptable for trusted environments.
- Non-Ollama LLMs in the primary streaming chat path.

## 6. Key User Journeys

Journey 1: Run Locally (< 10 min)

8. Clone repo. Run docker compose up.
9. Visit UI. Confirm /health returns ok.
10. No accounts. No API keys needed for local Ollama path.

Journey 2: Create an Agent

11. Set name, provider (ollama | openai | anthropic), model, system prompt, temperature.
12. Set allowed_plugins and allowed_tools allowlists (can be done via API for MVP).
13. Save. Agent appears in the workspace list.

Journey 3: Stream a Chat Response

14. Select agent, type a message, hit send.
15. Tokens appear progressively. Conversation ID is created and reused.
16. Errors surface as structured events, not silent failures.

Journey 4: Execute a Tool

17. Manual mode: type /tool <tool_name> {args} — deterministic, always works.
18. Auto mode: model emits TOOL_CALL {json}, runtime executes, feeds TOOL_RESULT back.
19. Tool call start, end, and error events are visible in the chat stream in real time.

Journey 5: Operate Plugins

20. List installed plugins and their available tools from the UI.
21. Restart a wedged plugin without restarting the whole runtime.
22. Plugin developer copies template, implements one tool, sees it listed in under 30 minutes.

## 7. Functional Requirements

### 7.1 Health & Version

GET /health returns status: ok|degraded with dependency checks (DB, plugin processes). GET /version returns build metadata. These endpoints are public — no auth required.

Acceptance criteria: /health includes DB check. Status is degraded (not down) if a non-critical dependency fails.

### 7.2 Agents CRUD

Full create/read/update for agents. Each agent stores: name, provider, model, system prompt, temperature, allowed_plugins, allowed_tools. Updating allowlists supports explicit clearing (empty array = allow nothing).

Acceptance criteria: Works against SQLite (dev) and Postgres (Docker Compose). Allowlist enforcement is tested end-to-end.

### 7.3 Streaming Chat (SSE)

POST /agents/{agent_id}/chat streams a sequence of typed events: conversation (returns conversation_id), message_start, token, tool_call_start, tool_call_end, tool_call_error, message_end, error. All messages are persisted per conversation.

Acceptance criteria: Streaming works through the frontend. Errors are always structured events, never silent HTTP 500s.

### 7.4 Tool Calling

Manual mode (/tool directive) is the default and must always work reliably. Auto mode is opt-in: the model emits TOOL_CALL {json}, the runtime executes, feeds TOOL_RESULT back, and continues generation. The runtime enforces max tool call depth to prevent loops. Tool execution can be disabled globally. Agent allowlists are enforced before every call.

Acceptance criteria: Blocked tool calls return a clear error event. Loop detection triggers max_tool_calls limit cleanly.

### 7.5 Plugins (MCP-over-stdio)

Plugins are directories under the configured plugins folder. Each has plugin.json (manifest) and a stdio entrypoint. The protocol supports: initialize, tools/list, tools/call. Three real-world plugins ship with v0.1 (see Section 8). REST API: GET /plugins lists plugins and tools; POST /plugins/{id}/tools/{tool} executes a tool; POST /plugins/{id}/restart restarts the plugin process.

Acceptance criteria: All three launch plugins work end-to-end. docs/plugins-stdio.md fully documents the contract. A developer can build a new plugin from the template without reading source code.

### 7.6 Auth & Security

API key auth protects /agents, /plugins, and /audit endpoints. A dev escape hatch disables auth for local-only use. Security middleware enforces: rate limiting, max request body size, security headers. Optional JWT/OAuth is a post-MVP feature — document the hook but do not ship it in v0.1.

Acceptance criteria: Protected endpoints return 401 without a valid API key. Rate limit returns 429. All knobs are documented in .env.example.

### 7.7 Audit Log

Audit endpoints expose: auth failures (timestamp, endpoint, reason) and tool call log (timestamp, agent, plugin, tool, duration_ms, success, error_message). The audit log UI must be considered a differentiator — it should be well-designed and genuinely readable, not an afterthought.

Acceptance criteria: Tool call audit returns the last N events with duration and outcome. Auth failure log captures failed API key attempts.

### 7.8 Frontend

Three views required for MVP.

- Agent workspace: list agents, create new agent, select agent to open chat.
- Chat view: stream tokens, display tool visibility events inline, surface errors clearly.
- Audit view: readable, filterable log of tool calls and auth failures.

Login page is scaffolded but OAuth flow is post-MVP.

Acceptance criteria: A user can create an agent and stream a response entirely through the UI. Tool call events are visible in the chat stream.

## 8. Three Launch Plugins

These ship with v0.1. They are not demos — they are real, useful tools that justify the platform's existence on day one.

| Plugin | What it does | Why it matters |
| --- | --- | --- |
| postgres-query | Run read-only SQL against a local Postgres DB configured per agent. | Most common internal automation need. Immediately demonstrates value. |
| github-issues | List, read, and summarize GitHub issues for a repo. | Concrete, shareable demo. Teams see it and immediately think of their own use case. |
| file-summarize | Read and summarize files from a configured local directory. | Demonstrates safe local file access with path restrictions — shows the trust model. |

Echo plugin ships as a developer reference only — not listed as a feature. It is the starting point for the plugin template.

## 9. Definition of Done

v0.1 is shippable when all of the following are true:

- Docker Compose quickstart works in a clean environment (backend + optional Ollama profile).
- Frontend: create agent, stream chat, see tool visibility events — all working end-to-end.
- All three launch plugins work via direct HTTP call and /tool directive in chat.
- Smoke test scripts pass in a clean environment (scripts/smoke-backend.ps1 and equivalent).
- Security knobs are functional and documented in .env.example: API key, rate limits, body limits.
- Plugin developer template exists and is documented. A new plugin can be built in under 30 minutes.
- Audit log UI is shipped and readable — not scaffolded, not a TODO.
- docs/plugins-stdio.md describes the full contract including versioning.

## 10. Success Metrics

| Metric | Target | How measured |
| --- | --- | --- |
| Time to first streaming response (TTFS) | < 10 minutes from clone | Timed in clean environment by someone unfamiliar with the repo |
| Plugin developer time to first tool | < 30 minutes from template | Tested with one external developer before shipping |
| Streaming reliability under normal use | Zero unhandled errors | Smoke test suite passes; manual exploratory test |
| Tool call timeout behavior | Cleans up without hanging | Tested with a plugin that artificially delays response |

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Ecosystem window closes — incumbents ship comparable DX | High | Ship v0.1 in weeks, not months. Audit log and plugin contract are the differentiated bets — protect them. |
| Auto tool calling is flaky across models | Medium | Manual mode is default and fully supported. Auto mode is opt-in. Never block on model consistency. |
| Plugin safety — subprocess tools can do anything | Medium | Enforce allowlists. Document clearly that plugins are trusted code. Consider path/network restrictions in v0.2. |
| Windows/Docker networking breaks Ollama host | Low | Document host.docker.internal pattern prominently. Test Docker Compose on Windows before ship. |
| Maintenance surface too large for team size | High | Drop OAuth from v0.1. Reduce to: API key auth + 3 plugins + streaming + audit. Scope strictly. |

## 12. Open Questions

23. What is the canonical agent model field — separate provider + model name fields, or a single string like ollama/llama3?
24. Do we want per-agent tool timeouts, or global timeout only?
25. Plugin protocol versioning: how do we enforce compatibility between plugin.json version and runtime version?
26. Should v0.1 UI expose allowlist editing, or keep it API-only?
27. What is the upgrade path when a plugin protocol breaking change is needed?

## 13. Implementation Map

Current state of the codebase mapped to this PRD for engineering reference.

| Area | Location |
| --- | --- |
| FastAPI app + router | backend/app/main.py, backend/app/api/router.py |
| Agents + chat | backend/app/api/routes/agents.py, backend/app/chat/service.py |
| Plugins + MCP stdio | backend/app/api/routes/plugins.py, backend/app/plugins/*, docs/plugins-stdio.md |
| Auth | backend/app/api/deps.py, backend/app/api/routes/auth.py |
| Security middleware | backend/app/security/middleware.py |
| Audit endpoints | backend/app/api/routes/audit.py |
| Agents UI | frontend/src/app/app/AgentsClient.tsx |
| Chat UI | frontend/src/app/app/agents/[agentId]/chat/ChatClient.tsx |
| Login UI | frontend/src/app/login/LoginClient.tsx |
