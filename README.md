---
title: Mewar Erp Bot
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Mewar ERP AI Chatbot 🚀

An AI layer on top of an existing **MySQL 5.7 ERP database**, built for factory and shop-floor staff who
need answers without navigating ERP menus. Users ask questions in natural language — mostly **Hinglish**
("bearing ka stock kitna hai?", "Arawali ke pichle 5 orders dikhao") — and the backend classifies the
intent, runs parameterised SQL against the live ERP, and answers conversationally with typed UI cards.

Alongside the chatbot it ships:

- a **proactive inventory-shortage agent** that scans for material shortages every hour and streams its
  reasoning to a live 3D dashboard over WebSocket,
- a **WhatsApp bot** (Meta Cloud API webhook),
- a **Generative UI "Command Center"** that builds a one-off dashboard from a spoken/typed intent,
- a set of **CrewAI agents** and **Streamlit** dashboards for store-admin workflows.

> Backend deployed on Hugging Face Spaces using Docker. Also deployable to Modal and Vercel.

---

## Table of contents

- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Setup](#setup)
- [Running the services](#running-the-services)
- [Architecture](#architecture)
  - [Request pipeline](#request-pipeline)
  - [Database access](#database-access)
  - [Proactive agent](#proactive-agent)
  - [Generative UI](#generative-ui--command-center)
  - [CrewAI agents](#crewai-agents)
  - [Frontend](#frontend)
- [API reference](#api-reference)
- [Role-based permissions](#role-based-permissions)
- [Deployment](#deployment)
- [Gotchas for contributors](#gotchas-for-contributors)

---

## Tech stack

| Concern | Choice |
| --- | --- |
| API framework | FastAPI + Uvicorn |
| Database | MySQL 5.7 (existing ERP), accessed via SQLAlchemy Core + PyMySQL |
| ORM | **None** — every query is raw `sqlalchemy.text()` SQL |
| LLM | Groq / OpenAI-compatible chat APIs via the `openai` SDK |
| Semantic search | `fastembed` embeddings + `faiss-cpu` index, `difflib`/`rapidfuzz` fallback |
| Scheduling | APScheduler (`BackgroundScheduler`) inside the FastAPI lifespan |
| Realtime | Native FastAPI WebSockets (`/ws/agent-logs`) |
| Auth | JWT via `python-jose`, OAuth2 password form |
| Agents | CrewAI (standalone experiment under `app/ai_agents/`) |
| Dashboards | Streamlit + static HTML/Three.js (no JS build pipeline) |
| Deploy targets | Docker / Hugging Face Spaces, Modal, Vercel |

---

## Repository layout

```
chatbotai/
├── app/
│   ├── main.py                  # FastAPI app: routers, lifespan/scheduler, WebSocket, static pages
│   ├── dependencies.py
│   ├── auth/jwt.py              # JWT create/verify helpers
│   ├── db/database.py           # SQLAlchemy engine + SessionLocal + get_db()
│   ├── models/schema.py         # (empty — no ORM models by design)
│   ├── schemas/chat.py          # ChatRequest pydantic model
│   ├── routers/
│   │   ├── chatbot.py           # ~2.9k lines. Main NL pipeline, mounted at /chatbot
│   │   ├── auth.py              # /auth/login (demo credentials)
│   │   ├── inventory_dropdown.py
│   │   ├── inventory_smart.py
│   │   ├── supplier.py, supplier_search.py
│   │   ├── proactive_agent.py   # write-side agent actions (confirm PO, cleanup)
│   │   ├── gen_ui.py            # POST /api/generate-ui
│   │   ├── whatsapp.py          # Meta Cloud API webhook (GET verify + POST receive)
│   │   └── api.py
│   ├── services/
│   │   ├── ollama_engine.py     # (misnamed) intent classification via Groq/OpenAI
│   │   ├── nl2sql_engine.py     # schema-aware SQL generation + read-only validation
│   │   ├── proactive_agent.py   # Observer → Cognitive → Approver shortage workflow
│   │   ├── nlp_engine.py
│   │   └── love_brain.py        # remote maintenance-flag check (can sys.exit)
│   ├── ai_agents/               # CrewAI experiment: team.py, tools.py, po_creator_agent.py
│   │   └── ai_dashboard.py      # Streamlit UI for the CrewAI agent
│   ├── streamlit_app.py         # Streamlit chat client
│   └── view_inventories.py
├── agent_ui/                    # 3D agent dashboard (HTML + .glb assets)
├── command_center/              # Generative UI renderer
├── frontend/, chat.html, ...    # static clients & older prototypes
├── docs/archicture.md           # scratch command notes
├── table_structures (mewar_erp).txt  # 46 CREATE TABLE statements for the ERP schema
├── requirements.txt
├── Dockerfile                   # Hugging Face Spaces build (port 7860)
├── modal_deploy.py              # Modal ASGI deployment
├── vercel.json                  # Alternate Vercel deployment
└── analytics_dashboard.py       # Standalone Streamlit analytics
```

---

## Setup

### 1. Prerequisites

- **Python 3.10+** (the Docker image pins 3.10, Modal pins 3.11)
- Network access to the **MySQL 5.7 ERP database**
- A **Groq** and/or **OpenAI** API key
- Optional: Docker (for n8n / container builds), a Modal account, WhatsApp Cloud API credentials

### 2. Clone and create a virtual environment

```powershell
git clone https://github.com/love995077/mewar_erp.git
cd mewar_erp

python -m venv env
.\env\Scripts\activate          # Windows (PowerShell)
# source env/bin/activate       # macOS / Linux
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

`requirements.txt` deliberately omits `crewai` — the CrewAI agents under `app/ai_agents/` are a
standalone experiment. Install it separately only if you need them:

```powershell
pip install crewai crewai-tools
```

### 4. Configure environment variables

Create a `.env` file in the repository root. It is **gitignored** and must never be committed.

```dotenv
# ── Database (MySQL 5.7 ERP) ──────────────────────────────
DB_USER=your_db_user
DB_PASSWORD=your_db_password      # special characters are URL-encoded automatically
DB_HOST=your_db_host
DB_NAME=mewar_erp

# ── LLM providers ─────────────────────────────────────────
OPENAI_API_KEY=sk-...
GROQ_API_KEY_1=gsk_...            # primary key
GROQ_API_KEY_2=gsk_...            # fallback key used on rate limit
SAMBANOVA_API_KEY=                # optional, used by an alternate engine variant

# ── WhatsApp Cloud API (optional) ─────────────────────────
WHATSAPP_TOKEN=
PHONE_NUMBER_ID=
VERIFY_TOKEN=                     # must match the token set in the Meta webhook console

# ── Hugging Face (optional) ───────────────────────────────
HF_TOKEN=                         # used by love_brain.py maintenance check
```

Notes:

- `app/db/database.py` builds `mysql+pymysql://{DB_USER}:{quoted(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}`
  with `pool_pre_ping=True` and `pool_recycle=1800`. Missing values fall back to
  `default_user@localhost/default_db`, which will fail at query time rather than at import.
- Different files read different LLM keys depending on which engine variant is active — set both
  `OPENAI_API_KEY` and `GROQ_API_KEY_1` if you are unsure.
- `app/services/love_brain.py` fetches a remote Hugging Face dataset config at startup; if that config
  reports a non-`ACTIVE` status, `load_core_services()` calls `sys.exit(1)` and the process dies. Set
  `HF_TOKEN` (or avoid calling `load_core_services`) when running locally.

### 5. Verify the database connection

```powershell
python test_connection.py
```

---

## Running the services

Activate the venv first (`.\env\Scripts\activate`), then:

### FastAPI backend

```powershell
uvicorn app.main:app --reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:

| URL | What it serves |
| --- | --- |
| `http://127.0.0.1:8000/` | health/root JSON |
| `http://127.0.0.1:8000/docs` | interactive OpenAPI docs |
| `http://127.0.0.1:8000/chat` | static chatbot UI |
| `http://127.0.0.1:8000/agent` | 3D proactive-agent dashboard (`agent_ui/agent_dashboard.html`) |
| `http://127.0.0.1:8000/command_center/command_center.html` | Generative UI Command Center |
| `ws://127.0.0.1:8000/ws/agent-logs` | live agent status stream |

Starting the server also starts the APScheduler background jobs: a **9:00 AM morning briefing** cron
job and an **hourly proactive inventory scan**.

CORS is allow-listed in `app/main.py` for `localhost:3000/5173/5500`, `127.0.0.1:5173/5500`, the live
Hugging Face Space, and `null` (file:// pages). Add your origin there if you serve the frontend
elsewhere.

### Streamlit dashboards

```powershell
streamlit run app/streamlit_app.py                     # chat client
streamlit run analytics_dashboard.py                   # analytics
python -m streamlit run app/ai_agents/ai_dashboard.py  # CrewAI store-admin agent
```

### Trigger the proactive agent on demand

```powershell
curl http://127.0.0.1:8000/trigger-agent
```

Open `/agent` in a browser first so the WebSocket dashboard animates the run live.

### Tests

```powershell
pytest test_bot.py -v
```

`test_bot.py` and `test_connection.py` are ad-hoc scripts that spin up a `TestClient` / live connection
and fire sample Hinglish queries at the chatbot endpoint. They are **not** an assertion-based pytest
suite — read the printed output to judge results. (`test_bot.py` is gitignored.)

### n8n (workflow automation, used alongside the bot)

```powershell
docker run -d --name my-n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
npx n8n     # without Docker
```

---

## Architecture

### Request pipeline

`app/routers/chatbot.py` (mounted at `/chatbot`) handles a query in five stages:

1. **Intent classification** — `app/services/ollama_engine.py` (despite the name it calls
   Groq/OpenAI-compatible chat APIs) classifies the query into one or more intents and extracts a clean
   `search_target` plus `filters`, returning a human-toned Hinglish `reasoning` string that is shown to
   the user while the query runs. Intents include `search` (inventory), `supplier_search`,
   `project_search`, `po_search`, `shortage_search`, `financial_search`, `rs_search`, `sql_analysis`.
2. **Permission check** — `ROLE_PERMISSIONS` gates which intents a role may use (see below).
3. **Fuzzy name matching** — FAISS semantic indexes over inventory / supplier / project names
   (`load_faiss_once`, `smart_match`) resolve typos and partial names before falling back to `difflib`.
   Indexes are built once and cached in memory.
4. **Intent branches** — each intent has a hand-written branch that builds **parameterised** SQL and
   formats results as chat text plus typed UI cards (`type: result | po | project | dropdown | chat |
   nl2sql_table`) for the frontend to render.
5. **NL2SQL fallback** — if intent detection fails or the query maps to no known branch,
   `app/services/nl2sql_engine.py` asks an LLM to generate a full `SELECT` from the schema, validates
   it is read-only (`is_safe_sql`), executes it, and summarises the rows in natural Hinglish.

`generate_morning_briefing()` (also in `chatbot.py`) is the scheduled 9 AM job.

```
user query
    │
    ▼
┌───────────────────┐   role denied
│ intent classifier │──────────────► polite refusal card
└─────────┬─────────┘
          │ intents + search_target + filters
          ▼
┌───────────────────┐
│ FAISS smart_match │  fuzzy name → canonical ERP name
└─────────┬─────────┘
          ▼
┌───────────────────┐   no branch matched   ┌──────────────────┐
│  intent branches  │──────────────────────►│  NL2SQL fallback │
│ (parameterised SQL)│                      │ (LLM SELECT gen) │
└─────────┬─────────┘                       └────────┬─────────┘
          │                                          │
          ▼                                          ▼
     typed UI cards  ◄────────────────────────  chat + table
```

### Database access

There is **no ORM**. `app/models/schema.py` is intentionally empty. `app/db/database.py` exposes an
engine, `SessionLocal`, and a `get_db()` FastAPI dependency; every query in the codebase is a raw
`sqlalchemy.text()` string.

The production database is **MySQL 5.7**, so hand-written SQL **must avoid `WITH` / CTEs** — use nested
derived-table subqueries instead. This constraint is repeated in the live LLM prompts so generated SQL
obeys it too.

The full ERP schema (46 tables) lives in `table_structures (mewar_erp).txt`. The tables the bot actually
reads and writes are: `projects`, `purchase_orders`, `purchase_order_items`, `suppliers`, `inventories`,
`stock_transactions`, `requisition_slips`, `consumptions`, `categories`, and related lookup tables.

### Proactive agent

`app/services/proactive_agent.py::run_proactive_workflow` implements an
**Observer → Cognitive → Approver** loop:

- **Observer** — one large SQL query computes real shortage: required quantity from active projects' BOM
  vs. available stock vs. quantity already incoming on open POs.
- **Cognitive** — an LLM reasons over the shortage rows and drafts a recommendation.
- **Approver** — the recommendation is surfaced for human approval rather than executed.

Every step pushes status over the broadcast callback so the 3D dashboard animates live. It runs hourly
via the scheduler and on demand via `GET /trigger-agent`.

The write side lives in `app/routers/proactive_agent.py`: `POST /api/confirm-po` inserts an approved PO
into the live ERP tables, and `GET /api/delete-test-po` is a manual cleanup endpoint for a hardcoded
test PO number.

### Generative UI / Command Center

The premise (see `GENUI.md`): ERPs become "data graveyards" of menus and static reports. Instead, the
user states an intent — *"show me a visualization of production line 4 performance vs. energy
consumption during the night shift"* — and the system builds a **one-off dashboard** for exactly that
question.

`POST /api/generate-ui` (`app/routers/gen_ui.py`) either routes the command to a hand-verified SQL
template (e.g. the shortage query) or has an LLM synthesise one via the NL2SQL engine, then returns a UI
spec that `command_center/command_center.html` renders.

### CrewAI agents

`app/ai_agents/` is a separate, mostly standalone experiment:

- `team.py` — a "Store Admin" `Agent`/`Crew` backed by Groq
- `tools.py` — `@tool`-decorated functions (`check_inventory_shortage`, `get_item_purchase_history`)
  that run their own raw SQL against `SessionLocal`
- `po_creator_agent.py` — drafts purchase orders (`check_low_stock`, `get_best_supplier`,
  `draft_purchase_order`, `run_proactive_po_workflow`)
- `ai_dashboard.py` — a Streamlit UI for the crew

### Frontend

There is **no JS build pipeline**. `agent_ui/` and `command_center/` contain static HTML dashboards
served directly via `FileResponse` routes in `app/main.py`, plus `.glb` 3D model assets served from
`GET /object_0.glb`.

Several loose `*.html` / `*.md` files at the repo root (`chat.html`, `claude.html`,
`mewar_chatbot.html`, `test_chat.html`, `backup*.md`, `main_backup.md`) are older prototypes and scratch
files, **not** part of the served app.

---

## API reference

### Chatbot

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/chatbot/` | Main NL query endpoint |

Request body (`app/schemas/chat.py`):

```json
{
  "query": "bearing ka stock kitna hai",
  "history": [{ "role": "user", "content": "previous message" }],
  "ui_filters": {},
  "role": "store admin"
}
```

The response is `{"results": [...]}`, an ordered list of typed cards the frontend renders in sequence
(`chat`, `result`, `po`, `project`, `dropdown`, `nl2sql_table`, `pr_draft_action`).

### Agent, KPI and purchase requests (`app/main.py`)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Root/health |
| `WS` | `/ws/agent-logs` | Live agent status stream for the 3D dashboard |
| `GET` | `/trigger-agent` | Run the proactive shortage workflow on demand |
| `GET` | `/api/kpi-stats` | Aggregate KPI numbers for dashboards |
| `POST` | `/api/purchase_request/store` | Create a purchase request |
| `DELETE` | `/api/purchase_request/delete/{pr_no}` | Delete a test purchase request |
| `GET` | `/agent` | Serve the 3D agent dashboard |
| `GET` | `/chat` | Serve the chatbot UI |
| `GET` | `/command_center/command_center.html` | Serve the Command Center |
| `GET` | `/object_0.glb` | Serve the 3D model asset |

### Proactive agent actions

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/confirm-po` | Insert an approved PO into the live ERP tables |
| `GET` | `/api/delete-test-po` | Manual cleanup for a hardcoded test PO |

### Generative UI

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/generate-ui` | `{"command": "..."}` → UI spec for a one-off dashboard |

### Inventory & suppliers

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/inventory/search` | Smart inventory search |
| `POST` | `/inventory/supplier-search` | Supplier dropdown search |
| `POST` | `/supplier/suggest` | Supplier suggestions |
| `GET` | `/supplier/search` | Supplier search |
| `GET` | `/supplier/details/{supplier_id}` | Supplier detail card |
| `GET` | `/supplier/by-code` | Look up supplier by code |

> `app/routers/supplier.py` and `app/routers/supplier_search.py` both declare
> `APIRouter(prefix="/supplier")` but are **not** currently included in `app/main.py` — wire them in if
> you need those endpoints.

### Auth

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/login` | OAuth2 password form → JWT bearer token |

⚠️ Auth is currently a **demo stub**: `app/routers/auth.py` hardcodes `admin` / `12345`, and
`app/auth/jwt.py` hardcodes `SECRET_KEY = "MEWAR_ERP_SECRET_KEY_CHANGE_THIS"` with a 60-minute HS256
token. Replace both with real credential storage and an env-sourced secret before any production use.
Note also that the chatbot takes `role` from the **request body**, not from a verified token.

### WhatsApp

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/whatsapp/webhook` | Meta webhook verification (echoes `hub.challenge` if `VERIFY_TOKEN` matches) |
| `POST` | `/whatsapp/webhook` | Receive inbound messages and reply via the Cloud API |

---

## Role-based permissions

`ROLE_PERMISSIONS` in `app/routers/chatbot.py` gates intents per role:

| Role | inventory | supplier | po | project | financials | general_chat |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| `supervisor` | ✅ | | | ✅ | | ✅ |
| `sales` | ✅ | | | | | ✅ |
| `purchase` | ✅ | ✅ | ✅ | | | ✅ |
| `purchase admin` | ✅ | ✅ | ✅ | | ✅ | ✅ |
| `store admin` | ✅ | | ✅ | ✅ | | ✅ |
| `store department` | ✅ | | | | | ✅ |
| `hod` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `hr` | | | | | | ✅ |

Roles are matched lowercase and trimmed; an unknown role gets no permissions.

---

## Deployment

### Docker / Hugging Face Spaces

The root `Dockerfile` builds from `python:3.10`, installs `requirements.txt`, and listens on **port
7860** (the port Hugging Face Spaces expects). The YAML front matter at the top of this README is the
Space configuration — **do not remove it**.

```powershell
docker build -t mewar-erp-bot .
docker run -p 7860:7860 --env-file .env mewar-erp-bot
```

On Spaces, set every variable from the `.env` block above as a **Space secret**.

### Modal

`modal_deploy.py` defines a `mewar-erp-backend` app that installs the dependency list into a
`debian_slim` Python 3.11 image, mounts the local `app` package, and serves `app.main:app` as an ASGI
app with `min_containers=1`. Secrets come from the Modal secret named `mewar-erp-backend`.

```powershell
modal deploy modal_deploy.py
```

### Vercel

`vercel.json` routes all traffic to `app/main.py` via `@vercel/python`. Note that the APScheduler
background jobs and the WebSocket endpoint do **not** work on Vercel's serverless runtime — use Docker
or Modal if you need the proactive agent.

---

## Gotchas for contributors

- **Files contain multiple stacked, fully commented-out historical implementations.** `app/main.py`,
  `app/routers/chatbot.py` (~2,900 lines, four full prior versions), `app/services/nl2sql_engine.py`,
  `app/services/ollama_engine.py`, `app/routers/gen_ui.py`, and `app/db/database.py` all follow the same
  pattern: earlier attempts are left in as large `#`-commented blocks above the real code.
  **The active code is always the last, non-commented block at the bottom of the file.** When editing
  behaviour, find the *last* `router = APIRouter(...)` / `def` / class definition — not the first search
  hit.
- **No CTEs.** MySQL 5.7 does not support `WITH`. Use nested derived-table subqueries.
- **Never commit secrets or conversation data.** `.env`, `chat_history.json`, and the virtual
  environment (`env/`, `venv/`, `.venv/`) are gitignored. If any of them was ever committed, untrack it
  with `git rm --cached <file>` and rotate the exposed credentials.
- **LLM prompts are Hinglish-tuned.** The `reasoning` strings are deliberately colloquial and part of
  the product feel — keep the tone when editing prompts.
- **`app/services/love_brain.py` can kill the process.** `load_core_services()` calls `sys.exit(1)` if
  the remote maintenance flag is not `ACTIVE`.
- **All new SQL must be parameterised.** The NL2SQL path is guarded by a read-only validator; the
  hand-written branches rely on bound parameters. Do not string-interpolate user input into SQL.
