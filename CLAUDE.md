# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Mewar ERP AI Chatbot — a FastAPI backend that lets factory/shop staff query an existing MySQL ERP database (projects, purchase orders, suppliers, inventory/stock) in natural language (mostly Hinglish), plus a proactive inventory-shortage agent, a WhatsApp bot, and a "Generative UI" command center that renders a one-off dashboard from a spoken/typed intent.

## Commands

Activate the venv first (Windows):
```
.\env\Scripts\activate
```

Run the API locally (auto-reload):
```
uvicorn app.main:app --reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the Streamlit apps:
```
streamlit run app/streamlit_app.py
streamlit run analytics_dashboard.py
python -m streamlit run app/ai_agents/ai_dashboard.py
```

Run tests:
```
pytest test_bot.py -v
```
(`test_bot.py` and `test_connection.py` are ad-hoc scripts that spin up a `TestClient`/live connection and fire sample Hinglish queries at the chatbot endpoint — not a real pytest suite with assertions per-case.)

Deploy:
```
modal deploy modal_deploy.py
```
Docker/Hugging Face Spaces build from the root `Dockerfile` (listens on port 7860). `vercel.json` routes all traffic to `app/main.py` for an alternate Vercel deployment.

n8n (workflow automation, used alongside the bot):
```
docker run -d --name my-n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
npx n8n
```

## Architecture

### Entry point & routing
`app/main.py` is the FastAPI app. It wires together all routers (`chatbot`, `auth`, `inventory_dropdown`, `inventory_smart`, `whatsapp`, `proactive_agent` action routes, `gen_ui`), starts an `APScheduler` background scheduler in the `lifespan` context (a 9am "morning briefing" cron job + an hourly proactive inventory scan), and exposes a `/ws/agent-logs` WebSocket that the 3D dashboard (`agent_ui/agent_dashboard.html`) listens on for live agent status pushed via `ConnectionManager.broadcast`.

### Database access — raw SQL, not ORM
`app/db/database.py` builds a SQLAlchemy engine/`SessionLocal` from `DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_NAME` env vars (MySQL via `pymysql`). `app/models/schema.py` is empty — there are no ORM models. Every query in the codebase is a raw `sqlalchemy.text()` SQL string executed against `SessionLocal`/`get_db()`. **The production database is MySQL 5.7**, so hand-written SQL must avoid `WITH`/CTEs (use nested derived-table subqueries instead) — this is called out explicitly in the live prompts and query code.

### Chatbot pipeline (`app/routers/chatbot.py`, mounted at `/chatbot`)
1. An LLM call (`app/services/ollama_engine.py`, despite the name it calls Groq/OpenAI-compatible chat APIs) classifies the query into one or more intents (`search`, `supplier_search`, `project_search`, `po_search`, `shortage_search`, `sql_analysis`, `rs_search`, ...) and extracts a clean `search_target` + `filters`, returning a human-toned `reasoning` string.
2. Role-based permission checks (`ROLE_PERMISSIONS`) gate which intents a user role can use.
3. FAISS (`fastembed` + `faiss-cpu`) semantic indexes over inventory/supplier/project names (`load_faiss_once`, `smart_match`) provide fuzzy/typo-tolerant name matching before falling back to `difflib`.
4. Each intent has a hand-written branch that builds parameterized SQL against the tables described in `app/services/nl2sql_engine.py`'s schema comment block (projects, purchase_orders, purchase_order_items, suppliers, inventories, stock_transactions, requisition_slips, etc.) and formats results as chat text plus typed UI "cards" (`type: result|po|project|dropdown|chat`) for the frontend to render.
5. If intent detection fails or the query doesn't map to a known branch, it falls back to `app/services/nl2sql_engine.py`, which asks an LLM to generate a full SELECT query directly from the schema, validates it's read-only, executes it, and summarizes the result in natural Hinglish.
6. `generate_morning_briefing()` (also in `chatbot.py`) is the scheduled 9am job.

### Proactive agent
`app/services/proactive_agent.py` (`run_proactive_workflow`) runs a "Observer → Cognitive → Approver" workflow: it computes real shortage (required qty from active projects' BOM vs. available stock vs. incoming POs) via a single large SQL query and pushes step-by-step status over the WebSocket broadcast callback so the 3D dashboard animates live. It's triggered both hourly by the scheduler and on-demand via `GET /trigger-agent`. `app/routers/proactive_agent.py` exposes the write-side actions (`POST /api/confirm-po` inserts an approved PO into the live ERP tables, `GET /api/delete-test-po` is a manual cleanup endpoint for a hardcoded test PO number).

### CrewAI agents (`app/ai_agents/`)
A separate, mostly standalone experiment using `crewai`: `team.py` defines a "Store Admin" `Agent`/`Crew` backed by Groq, `tools.py` defines `@tool`-decorated functions (`check_inventory_shortage`, `get_item_purchase_history`) that run their own raw SQL against `SessionLocal`, and `ai_dashboard.py` is a Streamlit UI for it. `po_creator_agent.py` is a related agent for drafting purchase orders.

### Generative UI / Command Center
`app/routers/gen_ui.py` (`POST /api/generate-ui`) takes a free-text command and either routes it to a hand-verified SQL template (e.g. the shortage query) or has an LLM synthesize one, then returns a UI spec that `command_center/command_center.html` renders as a one-off custom dashboard — this is the "Generative UI" concept described in `GENUI.md`.

### Frontend
There is no JS build pipeline. `agent_ui/` and `command_center/` contain static HTML dashboards (served directly via `FileResponse` routes in `main.py`) plus `.glb` 3D model assets. Several loose `*.html`/`*.md` files at the repo root (`chat.html`, `claude.html`, `mewar_chatbot.html`, `backup*.md`, `main_backup.md`) are older prototypes/scratch files, not part of the served app.

## Important gotchas

- **Files contain multiple stacked, fully-commented-out historical implementations.** `app/main.py`, `app/routers/chatbot.py` (~2900 lines, 4 full prior versions), `app/services/nl2sql_engine.py`, `app/services/ollama_engine.py`, `app/routers/gen_ui.py`, and `app/db/database.py` all follow the same pattern: earlier attempts are left in as large `#`-commented blocks above the real, currently-active code. **The active code is always the last, non-commented block at the bottom of the file** — when editing behavior, find the *last* `router = APIRouter(...)` / `def` / class definition in the file, not the first one that matches a search.
- Secrets (DB credentials, Groq/OpenAI/HF/WhatsApp tokens) live in `.env` (gitignored) and are loaded via `python-dotenv`; `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` drive `app/db/database.py`, and `OPENAI_API_KEY`/`GROQ_API_KEY_1`/`GROQ_API_KEY_2` drive whichever LLM engine variant is active in a given file.
- `app/services/love_brain.py`'s `is_maintenance_active()` checks a remote Hugging Face dataset config at startup and can `sys.exit(1)` the process if it reports non-`ACTIVE` status.
