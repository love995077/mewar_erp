import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from sqlalchemy import text  # <-- NAYA IMPORT: Custom SQL queries chalane ke liye zaroori hai


# Database
from app.db.database import get_db, SessionLocal

# Routers & Background Tasks
from app.routers.chatbot import router as chatbot_router, generate_morning_briefing
from app.routers.auth import router as auth_router
from app.routers.inventory_dropdown import router as inventory_router
from app.routers.inventory_smart import router as inventory_smart_router
from app.routers.whatsapp import router as whatsapp_router
from app.services.proactive_agent import run_proactive_workflow
from app.routers.proactive_agent import router as agent_action_router
from app.routers import gen_ui



# ==========================================
# 🔌 WEBSOCKET MANAGER (For 3D Dashboard)
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

# ==========================================
# 🤖 SCHEDULER WRAPPER FUNCTION (Agent Auto-Pilot)
# ==========================================
def scheduled_agent_task():
    """
    Ye function har 1 ghante mein background mein chalega.
    Isse FastAPI ki normal API request ki zaroorat nahi hai.
    """
    print("⏰ [Auto-Scheduler] Waking up AI Agent to scan inventory...")
    db = SessionLocal()  # Naya temporary DB connection open kiya
    try:
        # Background thread mein async function ko chalane ke liye asyncio.run()
        asyncio.run(run_proactive_workflow(manager.broadcast, db))
    except Exception as e:
        print(f"❌ Auto-Scheduler Error: {e}")
    finally:
        db.close()  # Kaam hone ke baad connection safely close kar diya


# ==========================================
# 🚀 LIFESPAN (Server start aur stop hone ka logic)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 App starting up... AI Engine is ready!")
    
    # 1. ⏰ Scheduler (Automation) Start Karna
    scheduler = BackgroundScheduler()
    
    # Morning Briefing Job
    scheduler.add_job(generate_morning_briefing, 'cron', hour=9, minute=0)
    
    # 🌟 NAYA: 1-HOUR PROACTIVE AGENT JOB
    scheduler.add_job(scheduled_agent_task, 'interval', hours=1)
    
    scheduler.start()
    print("⏰ Background Automation Scheduler Started (Scanning every 1 hour)!")
    
    yield  # <-- Yahan aapka main server mast chalta rahega
    
    # 2. 🛑 Server Band hone par sab safe close karna
    scheduler.shutdown()
    print("🛑 Server and Scheduler Stopped Safely!")


# Initialize FastAPI
app = FastAPI(title="Mewar ERP API", redirect_slashes=True, lifespan=lifespan)

# ==========================================
# 🛡️ CORS SETTINGS
# ==========================================
_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,null,*"
).strip()

if _cors_raw == "*":
    allowed_origins = ["*"]
    _allow_credentials = False
else:
    allowed_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 🔗 INCLUDE ROUTERS
# ==========================================
app.include_router(chatbot_router)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(inventory_smart_router)
app.include_router(whatsapp_router, prefix="/whatsapp")
app.include_router(agent_action_router)
app.include_router(gen_ui.router) 

# ==========================================
# 🟢 ROOT & WEBSOCKET ENDPOINTS
# ==========================================
@app.get("/")
def root():
    return {"message": "Mewar ERP API is running perfectly! 🚀"}

@app.websocket("/ws/agent-logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/trigger-agent")
async def trigger_proactive_agent(db: Session = Depends(get_db)):
    try:
        await run_proactive_workflow(manager.broadcast, db)
        return {"status": "success", "message": "Agent workflow triggered! Look at your 3D Dashboard."}
    except Exception as e:
        print("Agent Trigger Error:", str(e))
        return {"status": "error", "message": str(e)}

# ==========================================
# 📊 NEW: REAL-TIME KPI API FOR DASHBOARD
# ==========================================
@app.get("/api/kpi-stats")
def get_kpi_stats(db: Session = Depends(get_db)):
    """
    Dashboard ke upar jo 3 banners hain (Active Demands, Low Stock, POs Today),
    unke liye ye real-time numbers database se nikal kar dega.
    """
    try:
        # 1. Active Demands (Total In-Progress Projects)
        active_projects = db.execute(
            text("SELECT COUNT(id) FROM projects WHERE status = 'in_progress'")
        ).scalar() or 0

        # 2. POs Generated Today
        pos_today = db.execute(
            text("SELECT COUNT(id) FROM purchase_orders WHERE DATE(created_at) = CURDATE()")
        ).scalar() or 0

        # 3. Low Stock Items (Same advanced query used by Scanner Agent, but just counting rows)
        low_stock_query = text("""
            WITH RunningProjects AS (
                SELECT id FROM projects WHERE status = 'in_progress'
            ),
            ReqUnion AS (
                SELECT pi.inventory_id, SUM(CAST(pp.quantity AS SIGNED) * CAST(pi.quantity AS SIGNED)) as req
                FROM RunningProjects p
                JOIN project_products pp ON p.id = pp.project_id
                JOIN product_items pi ON pp.product_id = pi.product_id
                GROUP BY pi.inventory_id
                UNION ALL
                SELECT p_item.inventory_id, SUM(CAST(p_item.quantity AS SIGNED)) as req
                FROM RunningProjects p
                JOIN project_item p_item ON p.id = p_item.project_id
                GROUP BY p_item.inventory_id
            ),
            TotalReq AS (
                SELECT inventory_id, SUM(req) as total_req FROM ReqUnion GROUP BY inventory_id
            ),
            AllowedMachines AS (
                SELECT DISTINCT machine_id FROM stock_transactions 
                WHERE project_id IN (SELECT id FROM RunningProjects) AND machine_id IS NOT NULL
            ),
            Consumption AS (
                SELECT inventory_id, SUM(quantity) as cons_qty
                FROM stock_transactions
                WHERE LOWER(txn_type) = 'out'
                  AND (project_id IN (SELECT id FROM RunningProjects) OR machine_id IN (SELECT machine_id FROM AllowedMachines))
                GROUP BY inventory_id
            ),
            AvailableStock AS (
                SELECT inventory_id,
                    (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)
                    -
                    SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail
                FROM stock_transactions GROUP BY inventory_id
            ),
            PendingPOs AS (
                SELECT poi.inventory_id, SUM(poi.ordered_qty) as incoming_qty
                FROM purchase_order_items poi
                JOIN purchase_orders po ON poi.purchase_order_id = po.id
                WHERE po.status IN ('Draft', 'Submitted', 'Approved', 'Pending') 
                GROUP BY poi.inventory_id
            )
            SELECT COUNT(*) FROM (
                SELECT tr.inventory_id, 
                ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0) - COALESCE(p_po.incoming_qty, 0)) as shortage 
                FROM TotalReq tr 
                LEFT JOIN Consumption c ON tr.inventory_id = c.inventory_id
                LEFT JOIN AvailableStock a ON tr.inventory_id = a.inventory_id 
                LEFT JOIN PendingPOs p_po ON tr.inventory_id = p_po.inventory_id
                HAVING shortage > 0
            ) as shortage_table
        """)
        low_stock_count = db.execute(low_stock_query).scalar() or 0

        return {
            "status": "success",
            "active_demands": active_projects,
            "low_stock_items": low_stock_count,
            "pos_today": pos_today
        }
    except Exception as e:
        print("KPI Fetch Error:", e)
        return {"status": "error", "active_demands": 0, "low_stock_items": 0, "pos_today": 0}
    

# ---------------------------------------------------------
# 🚀 NEW ROUTE: FOR AGENT 3D DASHBOARD
# ---------------------------------------------------------
@app.get("/agent")
def serve_agent_dashboard():
    # Ye route hit hote hi aapki nayi HTML file serve ho jayegi
    return FileResponse("agent_ui/agent_dashboard.html")

@app.get("/object_0.glb")
def serve_3d_model():
    # Ye route browser ko 3D file dega
    return FileResponse("agent_ui/object_0.glb")


##----------------------------------------------NL2SQL------------------------------------------------------------------------------


import os
import re
from openai import OpenAI
import time
import datetime
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Keys ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = OpenAI(api_key=OPENAI_API_KEY)
MODEL_NAME = "gpt-4o-mini"

# ── Schema cache (used by get_db_schema / invalidate_schema_cache) ───────────
_schema_full    : str = ""
_schema_compact : str = ""

SAMPLE_ROWS  = 3
MAX_CELL_LEN = 50


def _cell(v) -> str:
    if v is None:
        return "NULL"
    s = str(v)
    return s[:MAX_CELL_LEN] + "…" if len(s) > MAX_CELL_LEN else s


def _build_schemas(db):
    global _schema_full, _schema_compact
    from sqlalchemy import text
    tables = db.execute(text("SHOW TABLES")).fetchall()
    full_parts    = []
    compact_parts = []

    for (table,) in tables:
        cols      = db.execute(text(f"DESCRIBE `{table}`")).fetchall()
        col_names = [c[0] for c in cols]
        col_defs  = ", ".join(f"{c[0]} ({c[1]})" for c in cols)

        compact_parts.append(f"Table `{table}`: {col_defs}")

        try:
            sample = db.execute(text(f"SELECT * FROM `{table}` LIMIT {SAMPLE_ROWS}")).fetchall()
        except Exception:
            sample = []

        block = [f"Table `{table}`:"]
        block.append(f"  Columns: {col_defs}")
        if sample:
            block.append("  Sample rows:")
            block.append("    " + " | ".join(col_names))
            for row in sample:
                block.append("    " + " | ".join(_cell(v) for v in row))
        full_parts.append("\n".join(block))

    _schema_full    = "\n\n".join(full_parts)
    _schema_compact = "\n".join(compact_parts)


def get_db_schema(db, compact: bool = False) -> str:
    if not _schema_full:
        _build_schemas(db)
    return _schema_compact if compact else _schema_full


def invalidate_schema_cache():
    global _schema_full, _schema_compact
    _schema_full = _schema_compact = ""


# ── Prompts ───────────────────────────────────────────────────────────────────

_SQL_SYSTEM = """\
You are an expert MySQL query writer for Mewar ERP — a business management system.

DATABASE SCHEMA (exact column names — do NOT guess):

categories: id, name, is_delete, deleted_at, created_at, updated_at
consumptions: id, request_slips_id, transaction_date, created_by(->users), rs_row_id, inventory_id(->inventories), machine_id, unit, quantity, height, width, project_id(->projects), remark
departments: id, department_name, status, created_at, updated_at
firms: id, name, phone, address, email, website, gst_no, pan, logo, created_at, updated_at
grns: id, grn_number, purchase_order_id(->purchase_orders), grn_date, invoice_no, remarks, created_at, updated_at
grn_items: id, grn_id(->grns), inventory_id(->inventories), received_qty, accepted_qty, rejected_qty, placement, created_at, updated_at
inventories: id, name, opening_quantity, min_quantity, unit_id(->units), unit, model, category_id(->categories), grade, height, width, length, thikness, is_deleted, opening_stock, type, classification, placement, composition, outer_diameter, inner_diameter, no_of_coil, created_at, updated_at
issue_slips: id, issue_slip_no, project_id(->projects), requisition_slip_id(->requisition_slips), transaction_date, department_id(->departments), employee_id(->users), total_req_qty, total_issue_qty, total_pending_qty, comment, status, flag, created_by, edited_by, created_on, edited_on
issue_slip_rows: id, issue_slip_id(->issue_slips), requisition_slip_row_id, item_id(->inventories), quantity, description, status, pr_status, machine_id, order_qty, issue_qty, pending_qty, pr_machining_status, supplier_id(->suppliers)
job_cards: id, transaction_date, job_card_no, priority, status, vendor_id(->vendors), employee_id(->users), created_by, total_qty, pending_qty, total_received_qty, completion_date, created_at, completed_at
job_card_rows: id, job_card_id(->job_cards), issue_slip_row_id, item_id(->inventories), qty, item_pending_qty, received_qty, completion_date, status, description, supplier_id(->suppliers)
placements: id, name, created_at, updated_at
po_status_logs: id, purchase_order_id(->purchase_orders), status, changed_by(->users), changed_at, remarks
po_transactions: id, po_id(->purchase_orders), pay_amount, transaction_date
products: id, name, is_deleted, estimation_budget, estimation_duration, start_date, created_at, updated_at
product_items: id, product_id(->products), inventory_id(->inventories), quantity, is_deleted, created_at, updated_at
projects: id, name, status, priority, deadline, start_date, end_date, created_by(->users), is_deleted, completion_date, budget, comment, refurbish, created_at, updated_at
project_item: id, project_id(->projects), inventory_id(->inventories), quantity, length, created_at, updated_at
project_products: id, project_id(->projects), product_id(->products), quantity, status, is_deleted, created_at, updated_at
purchase_orders: id, po_number, supplier_id(->suppliers), po_date, expected_delivery, total_qty, subtotal, tax_amount, total_amount, subtotal_discount_amount, final_discount, loading_cutting_charges, freight_charges, advance_amount, balance_amount, remaining_amount, status, delivery_status, firm(->firms), remarks, terms_and_conditions, created_by(->users), approved_by(->users), created_at, completed_at
purchase_order_items: id, purchase_order_id(->purchase_orders), pr_item_id(->purchase_request_items), inventory_id(->inventories), hsn, ordered_qty, received_qty, unit_price, discount, discount_amount, tax_type, tax_percent, tax_amount, taxable_total, line_total, item_not, created_at
purchase_requests: id, pr_no, request_date, requested_by(->users), department_id(->departments), priority, status, remarks, total_qty, approved_by(->users), approved_at, created_at, updated_at
purchase_request_approvals: id, purchase_request_id(->purchase_requests), approver_id(->users), approval_level, status, remarks, action_date
purchase_request_items: id, purchase_request_id(->purchase_requests), issue_slip_row_id, item_id(->inventories), description, requested_qty, approved_qty, ordered_qty, uom, required_date, status, exited_qty, created_at
purchase_request_po_map: id, purchase_request_item_id(->purchase_request_items), purchase_order_item_id(->purchase_order_items), created_at
request_slip_histories: id, request_slip_id, action_by(->users), action, status, remarks, hold_by, created_at, updated_at
requisition_slips: id, rs_id, requisition_slip_no, store_rs, transaction_date, employee_id(->users), project_id(->projects), machine_id, lot_no, batch_no, department_id(->departments), purpose, total_qty, comment, status, approved_by(->users), rejected_by(->users), admin_id(->users), approved_date, rejected_date, admin_action_date, approve_comment, rejected_reason, admin_action_remark, admin_approve_status, po_flag, issue_completed, flag, is_exited, hold_by, created_by, edited_by, created_on, edited_on
requisition_slip_rows: id, requisition_slip_id(->requisition_slips), machine_id, item_id(->inventories), unit_id(->units), quantity, order_qty, issue_qty, pending_qty, order_pending_qty, issued_qty, consumed_qty, issued_height, issued_width, consumed_height, consumed_width, description, status, exited_qty, is_completed, unit
requisition_slip_row_pieces: id, item_id(->inventories), requisition_slip_row_id(->requisition_slip_rows), issued_height, issued_width, issued_qty, consumed_height, consumed_width, consumed_qty, shape, is_completed, send_hod
roles: id, name, deleted_at, created_at, updated_at
stock_transactions: id, project_id(->projects), machine_id, inventory_id(->inventories), txn_date, txn_type(enum: In/Out), quantity, ref_type, ref_no, issued_to(->users), issue_by(->users), requision_id(->requisition_slips), issue_slip_id(->issue_slips), supplier_id(->suppliers), vendor_id(->vendors), remarks
suppliers: id, category, registration_date, supplier_name, supplier_code, contact_person, email, state, city, mobile, gst_registered, gstin, pan, supplier_address, bank_name, branch_address, ifsc, account_number, created_at, updated_at
supplier_inventories: id, supplier_id(->suppliers), inventory_id(->inventories), quantity, created_at, updated_at
units: id, name, is_deleted, created_at, updated_at
users: id, name, email, status, date, is_delete, password, address, role_id(->roles), country_code, mobile, department_id(->departments), authority_id, image, created_at, updated_at
vendors: id, name, mobile_no, email, address, city, created_at, updated_at
vendor_payments: id, vendor_id(->vendors), purchase_order_id(->purchase_orders), amount, payment_date, payment_mode, reference_no, created_at

OUTPUT RULES — MUST FOLLOW:
1. Output ONLY a raw MySQL SELECT query. No explanation. No markdown. No code fences.
2. Never write INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, or any write operation.
3. Do NOT add any LIMIT clause. Return all rows unless the user explicitly asks for a top-N.
4. For ANY name or text search, ALWAYS use fuzzy matching:
   WHERE (col LIKE '%term%' OR col SOUNDS LIKE 'term' OR col LIKE '%word1%' OR col LIKE '%word2%')
5. If the question truly cannot be answered from this schema, output exactly: CANNOT_ANSWER
6. For vague/analytical questions ("best", "worst", "recommend"), fetch relevant metrics so the answer step can give a real recommendation.

CRITICAL RULES (never violate):
- NEVER use `pp.inventory_id` or `project_products.inventory_id`. This column DOES NOT EXIST and will crash the database. ALWAYS use `pit.inventory_id` (from the `product_items` table) for grouping and selecting inventory.
- RESPONSE TEXT RULE: NEVER guess or mention calculated numbers (like sums, counts, or totals) in your introductory text before the table. Let the SQL table display the final number. Use a simple intro like: "Here is the total sum based on your request:"
- UNIVERSAL COMBO RULE (List + Total/Sum in ONE question): If the user asks for a list AND its total sum or count in the SAME message (e.g., "show pending POs and their total amount", "kon konse items ki shortage hai or unka sum kitna hai"), ALWAYS wrap your base query in a CTE (WITH clause).
Use this exact format:

WITH base_data AS (
    -- Write your complete base query here for the list (without ORDER BY or LIMIT) --
)
SELECT bd.*, 
       (SELECT COUNT(*) FROM base_data) AS combo_total_count,
       (SELECT SUM(column_name_to_sum) FROM base_data) AS combo_total_sum 
FROM base_data bd
ORDER BY 1 ASC;
- COMBO TEXT RESPONSE: When you execute a combo query, use the `combo_total_sum` or `combo_total_count` values to announce the total in your introductory sentence (e.g., "Total sum is X. Here is the list:"). Do not try to manually calculate it in text, trust the SQL output.
- suppliers name column: `supplier_name` — NEVER write s.name or suppliers.name
- suppliers name column: `supplier_name` — NEVER write s.name or suppliers.name
- purchase_order_items FK to purchase_orders: column is `purchase_order_id` — NEVER write `po_id`
- purchase_order_items has NO supplier_id — FK is on purchase_orders.supplier_id
- purchase_order_items amount columns: `line_total`, `taxable_total` only — NO total_amount/balance_amount
- purchase_order_items has NO name/description/item_name — item name is in inventories.name via inventory_id
- When aggregating per supplier: GROUP BY s.id, s.supplier_name ONLY — never include purchase_orders columns in GROUP BY
- purchase_orders has NO project_id — no direct join between purchase_orders and projects
- requisition_slips = request slips (rs) — same table; alias it `rs` NOT `is` (that's reserved for issue_slips)
- issue_slips alias must be `isl` or `islip` — NEVER use alias `is` (reserved SQL keyword)
- issue_slip_rows FK to issue_slips: column is `issue_slip_id` — join: isl.id = isr.issue_slip_id
- issue_slip_rows item column: `item_id` (-> inventories) — NEVER write `inventory_id` on this table
- requisition_slips has NO total_issue_qty / total_pending_qty columns — those are on issue_slips (total_issue_qty, total_pending_qty). To get issued/pending per RS, join: requisition_slips -> issue_slips via issue_slips.requisition_slip_id
- When the question asks for "issued qty" or "pending qty" per RS, use issue_slips.total_issue_qty and issue_slips.total_pending_qty
- COLUMN NAMING: always SELECT and GROUP BY the raw FK id column alongside the name — e.g. SELECT st.inventory_id, i.name, SUM(...) ... GROUP BY st.inventory_id, i.name. Never drop inventory_id from the SELECT.
- inventories has NO columns named `current_stock` or `shortage` — never reference them directly; always compute inline with COALESCE/SUM subquery
- stock_transactions join to inventories: st.inventory_id = i.id (NOT i.inventory_id)
- project_item table alias: use `pi` — but NEVER use `pi.name`; project name comes from projects.name via pi.project_id = p.id
- grn_items FK to grns: column is `grn_id` — join: g.id = gi.grn_id
- grn_items has NO `po_id` — to link GRN to PO: grn_items -> grns.purchase_order_id -> purchase_orders
- requisition_slip_rows has NO `project_id` — get project via: rsr -> requisition_slips.project_id -> projects
- stock_transactions `txn_type` values are exactly: 'In' and 'Out' (capital first letter)
- inventories has NO `current_stock` column — compute it: COALESCE(opening_quantity,0) + COALESCE(net_txn,0)
- inventories has NO `quantity` column — use `opening_quantity` or compute from stock_transactions
- DUAL EXTREMES (MAX & MIN): If the user asks for BOTH highest/biggest AND lowest/smallest metrics, you MUST use UNION ALL. CRITICAL SQL SYNTAX: In MariaDB/MySQL, when using ORDER BY and LIMIT inside a UNION ALL, you MUST wrap each SELECT statement in parentheses. Example: (SELECT id, po_number, total_amount FROM purchase_orders ORDER BY total_amount DESC LIMIT 1) UNION ALL (SELECT id, po_number, total_amount FROM purchase_orders ORDER BY total_amount ASC LIMIT 1).
- SPELLING OVERRIDES: For item thickness, ALWAYS use the exact column name 'thikness' (without 'c'). Never autocorrect it to 'thickness' in the query, otherwise it will crash. Other dimensions are 'height', 'width', 'length', 'outer_diameter', 'composition', 'grade'.
- purchase_orders `status` values: 'Draft', 'Approved', 'Completed' (capital first letter)
- When joining purchase_orders with grns: purchase_orders.id = grns.purchase_order_id
- projects `status` values are exactly: 'new' and 'in_progress' (lowercase with underscore) — NEVER use 'In Progress', 'inprogress', 'active', or any other variant
- "in progress projects", "jo projects chal rahe hain", "current projects" means WHERE status='in_progress' — apply this filter strictly, do NOT return all projects
- projects table date columns: `start_date` = project start, `end_date` = project end/deadline, `deadline` column is usually NULL — ALWAYS use `end_date` when asked for deadline, due date, end date, or "kab tak chalega"
- ENTITY RESOLUTION (PROJECTS vs SUPPLIERS): They are completely separate. 
  1. If the user asks about timelines, deadlines, budgets, or inventory required/consumed at a site -> SEARCH IN `projects` table (projects.name LIKE '%term%'). 
  2. If the user asks about POs, orders, pending balance, payments, or contact details (mobile/email) -> SEARCH IN `suppliers` table (supplier_name LIKE '%term%').
  Do NOT mix them. Use the context of the question (e.g., 'balance' means supplier, 'deadline/site' means project) to decide which table to search if the user just provides a name.
- PROJECT INVENTORY ITEMS: When asked for a project's inventory (e.g., "X project ki inventory batao"), you MUST NEVER output CANNOT_ANSWER. Always use this EXACT template. For the LIKE clause, extract the core parts of the user's word to bypass typos (e.g., for "mahipal singh", use `p.name LIKE '%mahip%' AND p.name LIKE '%sing%'`):
  SELECT i.id, i.name, i.model, SUM(pp.quantity * pit.quantity) AS required_qty, 'BOM' AS source
  FROM projects p JOIN project_products pp ON pp.project_id=p.id AND pp.is_deleted=0
  JOIN product_items pit ON pit.product_id=pp.product_id AND pit.is_deleted=0
  JOIN inventories i ON i.id=pit.inventory_id
  WHERE (p.name LIKE '%term1%' AND p.name LIKE '%term2%')
  GROUP BY i.id, i.name, i.model, source
  UNION ALL
  SELECT i.id, i.name, i.model, SUM(pi.quantity) AS required_qty, 'Direct' AS source
  FROM projects p JOIN project_item pi ON pi.project_id=p.id
  JOIN inventories i ON i.id=pi.inventory_id
  WHERE (p.name LIKE '%term1%' AND p.name LIKE '%term2%')
  GROUP BY i.id, i.name, i.model, source
- Hindi/Hinglish list words: "sarii", "saari", "saare", "sari", "sabhi", "sab", "sare" all mean "all" — fetch ALL rows with NO date or status filter unless the user also specifies one
- Date day filter: "13 date wali", "13 tarikh wali", "only 13 date" means DAY(transaction_date) = 13 — use DAY() function
- "X month wali" or "X mahine wali" means MONTH(transaction_date) = X
- GLOBAL INVENTORY SHORTAGE: "inventory items ki shortage" (without project context) means items where
  current_stock < inventories.min_quantity. shortage = min_quantity - current_stock.
  current_stock for global shortage = COALESCE(opening_quantity, 0) + net stock_transactions (In minus Out).
  Simpler formula used in practice: shortage = min_quantity - opening_quantity when opening_quantity < min_quantity.
- "paisa baaki" or "rokra" for suppliers means purchase_orders.balance_amount — SUM(balance_amount) per supplier
- ITEM TYPE STOCK QUERY ("bearing ka stock", "bolt ka stock", "how much bearings do we have"):
  These ask for the TOTAL combined stock of ALL items whose name contains that word.
  ALWAYS use this structure:
  SELECT SUM(COALESCE(i.opening_quantity, 0) + COALESCE(st.net_qty, 0)) AS total_stock
  FROM inventories i
  LEFT JOIN (
      SELECT inventory_id, SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) AS net_qty
      FROM stock_transactions GROUP BY inventory_id
  ) st ON i.id = st.inventory_id
  WHERE i.name LIKE '%...%' AND i.is_deleted = 0;
  Return a SINGLE row with total_stock. Do NOT list individual items — aggregate them.
- MULTI-TYPE STOCK ("bolts and bearings ka stock", "how much X and Y do we have"):
  Search by item name, NOT by categories table — categories has generic names like 'Raw Material', not 'Bearings'/'Bolts'.
  Use UNION ALL to show each type as a labeled group. Example for bolt+bearing:
  SELECT 'Bolt' AS item_type, SUM(COALESCE(i.opening_quantity,0)+COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id=i.id),0)) AS total_stock FROM inventories i WHERE i.name LIKE '%bolt%'
  UNION ALL
  SELECT 'Bearing' AS item_type, SUM(...) FROM inventories i WHERE i.name LIKE '%bearing%'
  Always label each row with a human-readable item_type, not a model number or id.
- MODEL-WISE STOCK BREAKDOWN ("model wise stock", "X ke saare models dikhao", "model wise breakdown"):
  Show each individual item row (not aggregated). Use this exact pattern:
  SELECT i.name, i.model,
    COALESCE(i.opening_quantity,0) + COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions st WHERE st.inventory_id=i.id),0) AS current_stock
  FROM inventories i
  WHERE (i.name LIKE '%bolt%' OR i.name LIKE '%bearing%' OR i.name LIKE '%spring%' OR i.name LIKE '%cutting rod%')
  ORDER BY i.name, i.model
  NEVER select `model` as a stock value. `model` is a text descriptor column on inventories. `current_stock` must always be computed from opening_quantity + stock_transactions SUM.
- Pronouns "iski", "iska", "is item ki", "is cheez ki" in a follow-up refer to the item mentioned in the previous turn — resolve them from conversation context.
- CONTEXTUAL AGGREGATION (COUNT/SUM): If the user asks for a "total count", "kitne items hain", or "sum" (e.g., "unki total required quantity ka sum") based on the previous list, DO NOT write a new query. DO NOT try to filter by item names (No WHERE i.name LIKE). You MUST wrap the EXACT, UNMODIFIED previous query inside a SUM() or COUNT() block.
  If they ask for SUM, use this exact format:
  SELECT SUM(required_qty) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
  If they ask for COUNT, use this exact format:
  SELECT COUNT(*) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
- REQUIRED VS AVAILABLE STOCK ("required vs available", "shortage", "sabse badi shortage", "project ke liye kitna chahiye vs kitna hai"):
  CRITICAL: You MUST COPY AND PASTE this exact SQL template. Do NOT modify the JOINs. Ensure `product_items pit` is properly JOINED. Do NOT try to filter by item name.
  
  SELECT i.id, i.name, i.model, i.classification,
    GREATEST((COALESCE(bom.req, 0) + COALESCE(direct.req, 0)) - COALESCE(cons.consumed, 0), 0) AS required_qty,
    COALESCE(st.t_in, 0) - COALESCE(st.t_out, 0) AS available_qty,
    CASE 
      WHEN i.classification = 'FINISH' OR i.classification IS NULL OR i.classification = '' THEN 0 
      ELSE COALESCE(st.t_mc, 0) - COALESCE(st.t_finish, 0) 
    END AS machining,
    CASE 
      WHEN i.classification = 'FINISH' OR i.classification IS NULL OR i.classification = '' THEN COALESCE(st.t_in, 0) - COALESCE(st.t_out, 0) 
      ELSE COALESCE(st.t_finish, 0) - COALESCE(st.t_out, 0) 
    END AS finish,
    CASE 
      WHEN i.classification = 'FINISH' OR i.classification IS NULL OR i.classification = '' THEN 0 
      ELSE COALESCE(st.t_in, 0) - COALESCE(st.t_mc, 0) 
    END AS semi_finish,
    (COALESCE(st.t_in, 0) - COALESCE(st.t_out, 0)) - GREATEST((COALESCE(bom.req, 0) + COALESCE(direct.req, 0)) - COALESCE(cons.consumed, 0), 0) AS short_extra
  FROM inventories i
  LEFT JOIN (
      SELECT pit.inventory_id, SUM(pp.quantity * pit.quantity) AS req 
      FROM projects p 
      JOIN project_products pp ON pp.project_id = p.id AND pp.is_deleted = 0 
      JOIN product_items pit ON pit.product_id = pp.product_id AND pit.is_deleted = 0 
      WHERE p.status NOT IN ('completed','hold') AND p.is_deleted = 0 
      GROUP BY pit.inventory_id
  ) bom ON bom.inventory_id = i.id
  LEFT JOIN (
      SELECT pi.inventory_id, SUM(pi.quantity) AS req 
      FROM projects p 
      JOIN project_item pi ON pi.project_id = p.id 
      WHERE p.status NOT IN ('completed','hold') AND p.is_deleted = 0 
      GROUP BY pi.inventory_id
  ) direct ON direct.inventory_id = i.id
  LEFT JOIN (
      SELECT inventory_id, SUM(quantity) AS consumed
      FROM stock_transactions
      WHERE LOWER(txn_type) = 'out'
      AND (
          project_id IN (SELECT id FROM projects WHERE status NOT IN ('completed','hold') AND is_deleted = 0)
          OR machine_id IN (
              SELECT DISTINCT machine_id FROM stock_transactions 
              WHERE project_id IN (SELECT id FROM projects WHERE status NOT IN ('completed','hold') AND is_deleted = 0) 
              AND machine_id IS NOT NULL
          )
      )
      GROUP BY inventory_id
  ) cons ON cons.inventory_id = i.id
  LEFT JOIN (
      SELECT inventory_id, 
             SUM(CASE WHEN LOWER(txn_type) = 'in' AND LOWER(COALESCE(ref_type,'')) != 'finish' THEN quantity ELSE 0 END) AS t_in, 
             SUM(CASE WHEN LOWER(txn_type) = 'out' AND LOWER(COALESCE(ref_type,'')) != 'machining' THEN quantity ELSE 0 END) AS t_out, 
             SUM(CASE WHEN LOWER(txn_type) = 'in' AND LOWER(ref_type) = 'finish' THEN quantity ELSE 0 END) AS t_finish, 
             SUM(CASE WHEN LOWER(txn_type) = 'out' AND LOWER(ref_type) = 'machining' THEN quantity ELSE 0 END) AS t_mc 
      FROM stock_transactions 
      GROUP BY inventory_id
  ) st ON st.inventory_id = i.id
  WHERE GREATEST((COALESCE(bom.req, 0) + COALESCE(direct.req, 0)) - COALESCE(cons.consumed, 0), 0) > 0
  ORDER BY short_extra ASC
- GROUP BY STRICT MODE: If you use a GROUP BY clause, EVERY column in the SELECT list that is not inside an aggregate function (like SUM, COUNT, MAX) MUST be included in the GROUP BY clause. Do not leave trailing non-aggregated columns.
- SOUNDS LIKE SYNTAX: NEVER use wildcard characters ('%') with SOUNDS LIKE. Correct: `col SOUNDS LIKE 'term'`. Wrong: `col SOUNDS LIKE '%term%'`.
- DATE COMPARISONS: For queries asking about "today", "aaj", or "current", ALWAYS use the MySQL CURDATE() or NOW() functions instead of hardcoding dates.
- NO DATA CREATION/FORMS: You are a READ-ONLY data retrieval assistant. NEVER say you are "creating", "drafting", or "preparing a form" for a request slip or PO. Always fetch EXISTING records using SELECT queries.
- REQUEST SLIPS (RS) BY PROJECT: If the user asks for "request slips", "RS", or "slips" for a specific project (e.g., "sonampur cement ki request slip"), you MUST join with the projects table.
  Pattern: SELECT rs.requisition_slip_no, p.name AS project, rs.transaction_date, rs.status 
  FROM requisition_slips rs JOIN projects p ON rs.project_id = p.id 
  WHERE p.name LIKE '%term%'.
  (CRITICAL: Intelligently fix minor typos in the LIKE clause. e.g., if user writes 'sonampur', search for '%sonapur%').
  - REQUEST SLIPS (RS) BY PROJECT: If the user asks for "request slips", "RS", or "slips" for a specific project (e.g., "sonampur cement ki request slip"), you MUST join with the projects table.
  Pattern: SELECT rs.requisition_slip_no, p.name AS project, rs.transaction_date, rs.status 
  FROM requisition_slips rs JOIN projects p ON rs.project_id = p.id 
  WHERE p.name LIKE '%term%'.
  (CRITICAL: Intelligently fix minor typos in the LIKE clause. e.g., if user writes 'sonampur', search for '%sonapur%').

- GRN LIST DASHBOARD: If the user asks for "grn list", "saare grn", or "grn dikhao", fetch the exact dashboard view using this SQL structure:
  SELECT g.id, g.grn_number, po.po_number, s.supplier_name, g.grn_date, g.invoice_no, COALESCE(SUM(gi.accepted_qty), 0) AS total_accepted
  FROM grns g
  LEFT JOIN purchase_orders po ON g.purchase_order_id = po.id
  LEFT JOIN suppliers s ON po.supplier_id = s.id
  LEFT JOIN grn_items gi ON gi.grn_id = g.id
  GROUP BY g.id, g.grn_number, po.po_number, s.supplier_name, g.grn_date, g.invoice_no
  ORDER BY g.grn_date DESC
  - REQUEST SLIP (RS) DASHBOARD: If the user asks for "saari request slips", "pending RS", or filters by date/project/status/code, ALWAYS use this dashboard structure:
  SELECT rs.requisition_slip_no AS rs_code, p.name AS project_name, rs.transaction_date AS created_date, rs.status
  FROM requisition_slips rs
  LEFT JOIN projects p ON rs.project_id = p.id
  WHERE 1=1
  -- (CRITICAL AI FILTERING RULES: Apply these dynamically based on user query)
  -- 1. Date Filters ("14 March ki RS", "April ki slips"): AND rs.transaction_date >= '...' AND rs.transaction_date <= '...'
  -- 2. Status ("pending", "approved", "rejected"): AND LOWER(rs.status) = 'pending'
  -- 3. RS Code ("RS 00012", "slip number 10"): AND rs.requisition_slip_no LIKE '%00012%'
  -- 4. Project ("Sonapur cement ki RS"): AND p.name LIKE '%sonapur%'
  ORDER BY rs.transaction_date DESC
  - PURCHASE REQUEST (PR) DASHBOARD: If the user asks for "saari purchase requests", "PR list", "pending PR", or filters by priority/status/date, ALWAYS use this dashboard structure:
  SELECT pr.pr_number, pr.request_date, pr.requested_by, pr.total_qty, pr.priority, pr.status
  FROM purchase_requests pr
  WHERE 1=1
  -- (CRITICAL AI FILTERING RULES for PRs: Apply dynamically based on user query)
  -- 1. Date Filters ("16 April ki PR", "March ki requests"): AND pr.request_date >= '...' AND pr.request_date <= '...'
  -- 2. Status ("ordered", "submitted", "approved"): AND LOWER(pr.status) = 'ordered'
  -- 3. Priority ("High priority wali PR dikhao"): AND LOWER(pr.priority) = 'high'
  -- 4. PR Number ("PR-104 ki details"): AND pr.pr_number LIKE '%104%'
  ORDER BY pr.request_date DESC
  - TOP N QUERIES (Ranking): If the user asks for "top 5", "highest", "biggest", or "sabse bade" (e.g., "top 5 po dikhao"), NEVER use LIKE '%top%'. You MUST use `ORDER BY` and `LIMIT`.
  Pattern for POs: SELECT po.po_number, s.supplier_name, po.po_date, po.total_amount, po.status FROM purchase_orders po LEFT JOIN suppliers s ON po.supplier_id = s.id ORDER BY po.total_amount DESC LIMIT 5
  - CRITICAL RULE FOR CHATBOT RESPONSE TONE & LOGIC:
  1. If the SQL query returns an empty table or states required_qty is 0 for an item, DO NOT say "Stock is insufficient". Instead, professionally state: "Currently, this item is not required for any active projects."
  2. Maintain a strict, professional corporate tone. NEVER use casual filler words like "hmm", "ek sec", or emojis like 🧐. Use phrases like "Scanning inventory and project requirements..."
  3. Only state there is a shortage if the data explicitly shows required_qty > available_qty.
"""

_FIX_PROMPT = """\
Original question: {question}

Your previous SQL failed:
SQL: {sql}
Error: {error}

Fix it and return ONLY the corrected SQL. No explanation.
"""

_ANSWER_SYSTEM = """\
You are a smart business assistant for Mewar ERP. Keep replies SHORT — 1 to 3 sentences max.

LANGUAGE: Always reply in Hinglish (Hindi + English mix). Use English for numbers, names, dates.
Examples: "Total 6 suppliers hain.", "Arawali Minerals ne sabse zyada orders diye — 18 POs."

- Factual queries: give the key number/name directly, skip preamble.
- Analytical queries ("best", "recommend"): 1 sentence insight + 1 sentence reason.
- If no data: say so in 1 line.
- NEVER mention SQL, database, tables, or technical terms.
- Today is {today}.
"""


# ── Provider calls ────────────────────────────────────────────────────────────

def _call_ai(system_full: str, system_compact: str, user: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_full},
                {"role": "user",   "content": user},
            ],
            temperature=0.0,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[NL2SQL] OpenAI failed: {e}")
        raise RuntimeError(f"OpenAI failed: {e}")


# ── SQL generation ────────────────────────────────────────────────────────────

def _clean_sql(raw: str) -> str:
    raw = re.sub(r"^```(?:sql)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()
    return raw


def _validate(raw: str) -> str:
    if raw.upper().startswith("CANNOT_ANSWER"):
        raise ValueError("Cannot be answered from the schema")
    
    # 🟢 UPDATE: Bracket '(' se shuru hone wali queries ko bhi allow karo
    if not re.match(r"^\s*(?:SELECT|WITH|\()", raw, re.IGNORECASE):
        raise ValueError(f"Non-SELECT output: {raw[:80]}")
        
    if raw.count("(") != raw.count(")"):
        raise ValueError(f"Truncated SQL (unbalanced parentheses): {raw[-60:]}")
    return raw


def _history_context(history: list) -> str:
    """Build a compact conversation context string from the last 4 turns."""
    if not history:
        return ""
    turns = history[-4:]
    lines = []
    for h in turns:
        role    = str(h.get("role", "")).lower()
        content = str(h.get("content", "")).strip()[:300]
        if role == "user":
            lines.append(f"User previously asked: {content}")
        elif role in ("assistant", "bot"):
            lines.append(f"Assistant previously answered: {content}")
    if not lines:
        return ""
    return (
        "CONVERSATION CONTEXT:\n"
        + "\n".join(lines)
        + "\n"
        "FOLLOW-UP RULES: If the new query is a filter/refinement on the previous one (e.g. 'only 13 date wali', 'sirf approved wali', 'project 5 wali'), "
        "apply that filter to the SAME table from the previous query. "
        "A bare number + 'date'/'tarikh' means DAY(date_column) = that number. "
        "Resolve 'unhe', 'unka', 'woh', 'those', 'them', 'iski', 'iska', 'is item ki' to refer to the specific item/entity mentioned in the previous turn. "
        "If the previous answer mentioned a specific inventory item name (e.g. 'Hard Facing Mig Roll'), "
        "use that exact item name in a LIKE '%name%' filter on inventories.name in the new query.\n\n"
    )


def generate_sql(user_query: str, schema_full: str = "", schema_compact: str = "",
                 previous_sql: str = None, sql_error: str = None,
                 history: list = None) -> str:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    system = _SQL_SYSTEM + f"\nToday's date: {today}. Use this to resolve partial dates (e.g. '23 feb' = '2026-02-23', 'April' = month 4).\n"
    ctx = _history_context(history or [])
    if previous_sql and sql_error:
        user = ctx + _FIX_PROMPT.format(question=user_query, sql=previous_sql, error=sql_error)
    else:
        user = ctx + user_query
    raw = _call_ai(
        system_full=system,
        system_compact=system,
        user=user,
    )
    sql = _validate(_clean_sql(raw))
    print(f"[NL2SQL] SQL: {sql[:200]}")
    return sql


# ── Answer formatting ─────────────────────────────────────────────────────────

def format_answer(user_query: str, rows: list, columns: list,
                  history: list = None) -> str:
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    if not rows:
        data_text = "No data found."
        null_warning = ""
    else:
        header = " | ".join(columns)
        body   = "\n".join(" | ".join(str(v) for v in row) for row in rows[:50])
        data_text = f"{header}\n{body}"

        null_cols = [
            col for col, val in zip(columns, rows[0])
            if val is None or str(val).strip() in ("", "None", "NULL", "N/A")
        ]
        null_warning = (
            f"\nWARNING: The following columns have NULL/empty values in the data: {', '.join(null_cols)}. "
            "Do NOT invent or guess values for these fields. Say the info is not available.\n"
        ) if null_cols else ""

    ctx  = _history_context(history or [])
    user = f"{ctx}User asked: {user_query}\n\nData returned:\n{data_text}\n{null_warning}\nGive a clear friendly answer."
    system = _ANSWER_SYSTEM.format(today=today)

    try:
        return _call_ai(system_full=system, system_compact=system, user=user)
    except Exception:
        return data_text if rows else "Koi data nahi mila."


#fgddxf


#--------------------------------------------------------new fully ai code ----------------------------------------------------------------------------------
import time
import datetime
from fastapi import APIRouter, Depends, Query as _Query
from sqlalchemy.orm import Session
from sqlalchemy import text
import re
import json
import os

from app.db.database import get_db, SessionLocal
from app.schemas.chat import ChatRequest
# 🚀 NAYA: Ab 'ollama_engine.py' se import karenge
from app.services.ollama_engine import ask_ollama
from app.services.nl2sql_engine import get_db_schema, generate_sql, format_answer

router = APIRouter(prefix="/chatbot", tags=["Chatbot Final"])

# ── 1. SECURITY FIREWALL FUNCTION ──────────────────────────────────────────
def is_safe_sql(sql_query: str) -> bool:
    if not sql_query: return False
    q = sql_query.upper().strip()
    
    # 🟢 UPDATE: yahan q.startswith("(") add kar diya hai
    if not (q.startswith("SELECT") or q.startswith("WITH") or q.startswith("(")): 
        return False
        
    dangerous_words = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
    for word in dangerous_words:
        if re.search(rf'\b{word}\b', q): return False 
    return True

# ── 2. ROLE PERMISSIONS MATRIX ──────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "supervisor":      ["inventory", "project", "general_chat"],
    "sales":           ["inventory", "general_chat"],
    "purchase":        ["inventory", "supplier", "po", "general_chat"],
    "purchase admin":  ["inventory", "supplier", "po", "financials", "general_chat"],
    "store admin":     ["inventory", "po", "project", "general_chat"],
    "store department":["inventory", "general_chat"],
    "hod":             ["inventory", "project", "supplier", "po", "financials", "general_chat"],
    "hr":              ["general_chat"],
}

# ── 3. OFF-TOPIC CONSTANTS ─────────────────────────────────────
_ERP_KEYWORDS = {
    "supplier", "vendor", "party", "sup",
    "po", "order", "orders", "purchase", "transit", "delivery", "grn", "dispatch",
    "stock", "maal", "item", "inventory", "qty", "quantity",
    "project", "site", "crusher",
    "balance", "payment", "invoice", "gst", "tax", "cgst", "sgst",
    "rokra", "paisa", "kharcha", "hisab",
    "mewar", "erp", "sale", "sales", "report", "employee", "account",
    "slip", "request", "banao", "batao", "dikhao", "milao", "details",
    "kitna", "kitne", "kahan", "kaisa", "kab", "lagao", "nikalo",
    "total", "list", "count", "kitni", "sabhi", "saare",
    "show", "find", "get", "check", "all", "mere", "mera",
}

_CLEANLY_OFFTOPIC = {
    "poem", "poetry", "joke", "weather", "recipe", "cook", "song", "lyrics",
    "translate", "movie", "cricket", "football", "game", "news", "capital of",
    "who is the president", "write a story", "tell me a story",
}

def _is_off_topic(query: str) -> bool:
    q = query.lower()
    if len(q.split()) <= 3: return False
    if any(kw in q for kw in _CLEANLY_OFFTOPIC): return True
    return not any(kw in q for kw in _ERP_KEYWORDS)

def log_query_pro(user_role, query, intents, final_results, process_time):
    bot_reply = "No Response"
    if isinstance(final_results, dict) and "results" in final_results:
        for res in final_results["results"]:
            if res.get("type") == "chat":
                bot_reply = res.get("message", "")
                break 
    is_fail = any(w in str(bot_reply).lower() for w in ["nahi mila", "error", "samajh nahi", "maaf kijiye", "kripya", "permission nahi"])
    log_entry = {
        "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "role": user_role, "user_query": query, "intent": str(intents),
        "bot_response": final_results["results"] if "results" in final_results else final_results, 
        "time_taken_sec": round(process_time, 2), "status": "Fail ❌" if is_fail else "Success ✅"
    }
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e: print(f"❌ Logger File Exception: {e}")


# ── 4. THE 100% AI-DRIVEN ENGINE ────────────────────────────────────────
def _nl2sql_response(raw_q: str, db, history: list = None) -> dict | None:
    history = history or []
    try:
        # 🧠 OpenAI will handle typos natively, we just need the schema
        schema_full = get_db_schema(db, compact=False)
        schema_compact = get_db_schema(db, compact=True)
        
        # Generates SQL query using the new OpenAI powered nl2sql_engine
        sql = generate_sql(raw_q, schema_full, schema_compact, history=history)
        
        if not sql or not is_safe_sql(sql):
            return None
            
        try: 
            result = db.execute(text(sql))
        except Exception as exec_err:
            # Self-healing loop: if SQL fails, ask OpenAI to fix it
            sql = generate_sql(raw_q, schema_full, schema_compact, previous_sql=sql, sql_error=str(exec_err), history=history)
            if not sql or not is_safe_sql(sql): return None
            result = db.execute(text(sql))
            
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
        
        # Let OpenAI format the final conversational response
        answer = format_answer(raw_q, rows, columns, history=history)
        
        parts = [{"type": "chat", "message": answer}]
        if rows:
            rows_as_dicts = [dict(zip(columns, row)) for row in rows[:50]]
            parts.append({"type": "nl2sql_table", "rows": rows_as_dicts, "columns": columns})
        return {"results": parts}
        
    except Exception as e:
        print(f"[NL2SQL Final Execution Alert] Failed: {e}")
        return None

# ══════════════════════════════════════════════════════════════════════════════
# 🧠 MAIN UNIFIED ROUTER FUNCTION (CLEANED)
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/")
def chatbot(request: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    raw_q = request.query.strip()
    low_q = raw_q.lower()
    chat_history = getattr(request, "history", []) 
    user_role = getattr(request, "role", "guest").lower().strip()

    # 🛑 GUARD 1: Off-Topic Security Firewall
    if _is_off_topic(raw_q) and not bool(chat_history):
        return {"results": [{"type": "chat", "message": "Bhai, main sirf Mewar ERP ke bartaav par bachaav kar sakta hoon — Suppliers, Purchase Orders, Inventory, aur Projects. In topics par koi jaankari chahiye toh batao! 😊"}]}

    # 🛑 GUARD 2: Fast-Track Direct ID Pipeline
    if low_q.isdigit() and len(low_q) < 8:
        allowed_perms = ROLE_PERMISSIONS.get(user_role, [])
        if user_role in ["superadmin", "super admin"] or "inventory" in allowed_perms:
            try:
                inv = db.execute(text("SELECT id, name, classification, placement FROM inventories WHERE id = :id AND is_deleted=0"), {"id": int(low_q)}).fetchone()
                if inv:
                    stock_res = db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id = :id"), {"id": inv.id}).scalar()
                    total_qty = float(stock_res or 0)
                    cls = str(inv.classification).lower() if inv.classification else ""
                    m, f, sf = (total_qty, 0, 0) if "machining" in cls else (0, 0, total_qty) if "semi" in cls else (0, total_qty, 0)
                    return {"results": [{"type": "result", "inventory": {"id": inv.id, "name": inv.name, "category": cls.upper(), "placement": inv.placement or "N/A"}, "total_stock": total_qty, "finish_stock": f, "semi_finish_stock": sf, "machining_stock": m}]}
            except: pass
        else:
            return {"results": [{"type": "chat", "message": f"Aapka current active status '{user_role.title()}' hai. Aapko Item Codes / Barcode ID se directly view karne ki permissions restricted hain. 🛑"}]}

    # 🔒 GUARD 3: Role Security Firewall Checks (Early Check)
    if user_role not in ["superadmin", "super admin"]:
        allowed_perms = ROLE_PERMISSIONS.get(user_role, [])
        if any(w in low_q for w in ["po", "order"]) and "po" not in allowed_perms: 
            return {"results": [{"type": "chat", "message": "Aapke user profile ko Purchase Orders access karne ki authorization nahi hai. 🛑"}]}
        if any(w in low_q for w in ["supplier", "vendor", "party"]) and "supplier" not in allowed_perms: 
            return {"results": [{"type": "chat", "message": "Aapke user profile ko Supplier records view karne ki authorization nahi hai. 🛑"}]}
        if any(w in low_q for w in ["project", "site"]) and "project" not in allowed_perms: 
            return {"results": [{"type": "chat", "message": "Aapke user profile ko Projects management systems open karne ki permission nahi hai. 🛑"}]}

    # 🧠 EXECUTE STEP 1: Process Query through Ollama Engine (Replaces FAISS/Manual Logic)
    try:
        # Ollama gets the intent and conversational reasoning directly
        ai_data = ask_ollama(raw_q, chat_history)
    except Exception as e:
        print(f"❌ AI Core Exception: {str(e)}")
        # If Intent engine fails, jump directly to NL2SQL
        nl2_r = _nl2sql_response(raw_q, db, history=chat_history)
        return nl2_r if nl2_r else {"results": [{"type": "chat", "message": "Bhai, mera AI brain abhi connect nahi ho pa raha. 🙏"}]}

    intents = ai_data.get("intents", [])
    reasoning = ai_data.get("reasoning", "hmm ek sec... main check karta hoon 👍")
    target = ai_data.get("search_target", raw_q)
    if not target: 
        target = raw_q

    # =========================================================================
    # 🧠 NAYA AMBIGUITY & BRIDGE LOGIC
    # =========================================================================
    words = low_q.split()
    # Check karo ki user ne koi specific action manga hai kya?
    has_action = any(w in low_q for w in ["order", "po", "bill", "profile", "detail", "stock", "qty", "kitna"])

    # =========================================================================
    # 🧠 SMART AUTO-DETECT (PROJECT VS SUPPLIER) & AMBIGUITY GATE
    # =========================================================================
    words = low_q.split()
    action_words = ["order", "po", "bill", "profile", "detail", "stock", "qty", "kitna", "batao", "dikhao", "balance", "ledger", "paisa", "inventory"]
    has_action = any(w in low_q for w in action_words)

    # 🛑 1. DIRECT DATABASE PRE-CHECK (Entity Resolution)
    # Agar user ne sirf 1-3 words ka naam likha hai aur koi action word nahi hai
    if len(words) <= 3 and not has_action:
        
        # Check 1: Kya ye naam Project list mein hai?
        proj_check = db.execute(text(f"SELECT name FROM projects WHERE name LIKE '%{raw_q}%' AND is_deleted=0 LIMIT 1")).fetchone()
        if proj_check:
            target = proj_check[0]
            return {
                "results": [{
                    "type": "chat", 
                    "message": f"hmm.. **{target}** ek **Project** ke roop mein mil gaya hai. 🏗️ Bhai, aapko is Project ki Details dekhni hai ya Inventory? 🤔"
                }]
            }

        # Check 2: Kya ye naam Supplier list mein hai?
        sup_check = db.execute(text(f"SELECT supplier_name FROM suppliers WHERE supplier_name LIKE '%{raw_q}%' LIMIT 1")).fetchone()
        if sup_check:
            target = sup_check[0]
            return {
                "results": [{
                    "type": "chat", 
                    "message": f"hmm.. **{target}** ek **Supplier** ke roop mein mil gaye hain. 🤝 Bhai, aapko inki Profile dekhni hai ya Purchase Orders? 🤔"
                }]
            }
    # 🌉 2. BRIDGE LOGIC: Agar action hai (ya button click hua hai), toh clear instruction banao
    sql_query = raw_q
    
    # 🧠 CONTEXT MEMORY (Short-Term Memory Fix)
    if len(words) <= 3 and chat_history:
        try:
            # Pichli chat ka aakhri message uthao
            last_msg = chat_history[-1].get("content", "") if isinstance(chat_history[-1], dict) else getattr(chat_history[-1], "content", "")
            # Usme se bold kiya hua naam (target) nikaalo, jaise **Mahipal Singh**
            import re
            match = re.search(r'\*\*(.*?)\*\*', last_msg)
            if match:
                past_target = match.group(1)
                # Nayi query banao pichle context ke sath
                if "inventory" in low_q:
                    sql_query = f"{past_target} project ki inventory batao"
                elif "detail" in low_q or "profile" in low_q:
                    sql_query = f"{past_target} ki profile details batao"
                elif "po" in low_q or "order" in low_q:
                    sql_query = f"{past_target} ke purchase orders dikhao"
        except Exception as e:
            pass

    # Agar memory use nahi hui, toh normal chalao
    elif len(words) <= 5: 
        # 🟢 NAYA ANALYTICS BYPASS: In words ko normal search mat samjho
        if any(word in low_q for word in ["grn", "top", "highest", "sabse", "latest", "recent"]): 
            sql_query = raw_q
        elif "supplier_search" in intents:
            sql_query = f"Show all profile details for supplier: '{target}'"
        elif "po_search" in intents:
            sql_query = f"Show purchase orders where PO number OR supplier name matches '{target}'"
        elif "project_search" in intents:
            sql_query = f"Show project details and budget for: '{target}'"
        elif "search" in intents:
            sql_query = f"Show total stock and placement for inventory item: '{target}'"

    # 🧠 EXECUTE STEP 2: Process NL2SQL
    final_response = _nl2sql_response(sql_query, db, history=chat_history)

    # If SQL Engine fails to generate a response, return a graceful fallback
    if not final_response:
        is_english = any(w in low_q for w in ["what", "how", "show", "list", "get", "who"])
        suggestion = "I couldn't quite resolve that query.\nTry asking about:\n1. **Purchase Orders**\n2. **Inventory Stock**\n3. **Suppliers Profile**" if is_english else "Maaf kijiye, main is query ko process nahi kar paaya.\nAap poochh sakte hain:\n1. **Purchase Orders Details**\n2. **Inventory Available Stock**\n3. **Suppliers Account Statements**"
        final_response = {"results": [{"type": "chat", "message": suggestion}]}

    # Append reasoning at the top of the chat (The natural human-like filler)
    if final_response and "results" in final_response:
        final_response["results"].insert(0, {"type": "chat", "message": reasoning})

    process_time = time.time() - start_time
    try: log_query_pro(user_role, raw_q, intents, final_response, process_time)
    except Exception as e: print(f"Logging Worker Block Exception: {e}")
    
    return final_response

# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND DAEMON CHANNELS (WHATSAPP PARSING WORKERS)
# ══════════════════════════════════════════════════════════════════════════════
async def process_chat_message(user_text: str) -> str:
    db = SessionLocal()
    try:
        request_data = ChatRequest(query=user_text, role="superadmin")
        response_dict = chatbot(request_data, db)
        final_whatsapp_text = ""
        if "results" in response_dict:
            for res in response_dict["results"]:
                res_type = res.get("type")
                if res_type == "chat": final_whatsapp_text += res.get("message", "") + "\n\n"
                elif res_type == "nl2sql_table":
                    # Simple text formatting for tables
                    for row in res.get("rows", []):
                        final_whatsapp_text += " | ".join(str(v) for v in row.values()) + "\n"
                    final_whatsapp_text += "\n"
        
        if not final_whatsapp_text.strip(): final_whatsapp_text = "Maaf karna bhai, mujhe iska valid response nahi mil paya database records mein. 😅"
        return final_whatsapp_text.strip()
    except Exception as e: 
        print(f"❌ WhatsApp Parsing Error: {e}")
        return "Bhai, backend pipeline process karne mein technical error hai. Try again later! 🙏"
    finally: db.close()

def generate_morning_briefing():
    db = SessionLocal()
    try:
        po_res = db.execute(text("SELECT COUNT(id), SUM(balance_amount) FROM purchase_orders WHERE balance_amount>0 AND LOWER(status)!='completed'")).fetchone()
        proj_res = db.execute(text("SELECT COUNT(id) FROM projects WHERE is_deleted=0 AND (end_date < CURRENT_DATE OR deadline < CURRENT_DATE) AND LOWER(status)!='completed'")).fetchone()
        pending_pos = po_res[0] or 0; pending_amt = po_res[1] or 0.0; overdue = proj_res[0] or 0
        msg = f"🌅 *Good Morning! Here is your Mewar ERP Daily Briefing:* 🌅\n\n📦 *Pending Purchase Orders:* {pending_pos} Orders (Total Due: ₹{float(pending_amt):,.2f})\n"
        if overdue > 0: msg += f"🚨 *Alert:* {overdue} Projects apne deadline se late chal rahe hain!\n"
        else: msg += f"✅ *Projects:* Sabhi active projects proper timeline standard par chal rahe hain.\n"
        print("\n" + "⭐"*30 + "\n🤖 AUTO-TRIGGERED DAILY AUTOMATION DAEMON:\n" + msg + "⭐"*30 + "\n")
    except Exception as e: print(f"❌ Automated Cron Worker Briefing Fault: {e}")
    finally: db.close()

##---------------------------------------------------------------------------------------------------

import os
import re
from openai import OpenAI
import time
import datetime
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Keys ─────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
client = OpenAI(api_key=OPENAI_API_KEY)
MODEL_NAME = "gpt-4o-mini"

# ── Schema cache (used by get_db_schema / invalidate_schema_cache) ───────────
_schema_full    : str = ""
_schema_compact : str = ""

SAMPLE_ROWS  = 3
MAX_CELL_LEN = 50


def _cell(v) -> str:
    if v is None:
        return "NULL"
    s = str(v)
    return s[:MAX_CELL_LEN] + "…" if len(s) > MAX_CELL_LEN else s


def _build_schemas(db):
    global _schema_full, _schema_compact
    from sqlalchemy import text
    tables = db.execute(text("SHOW TABLES")).fetchall()
    full_parts    = []
    compact_parts = []

    for (table,) in tables:
        cols      = db.execute(text(f"DESCRIBE `{table}`")).fetchall()
        col_names = [c[0] for c in cols]
        col_defs  = ", ".join(f"{c[0]} ({c[1]})" for c in cols)

        compact_parts.append(f"Table `{table}`: {col_defs}")

        try:
            sample = db.execute(text(f"SELECT * FROM `{table}` LIMIT {SAMPLE_ROWS}")).fetchall()
        except Exception:
            sample = []

        block = [f"Table `{table}`:"]
        block.append(f"  Columns: {col_defs}")
        if sample:
            block.append("  Sample rows:")
            block.append("    " + " | ".join(col_names))
            for row in sample:
                block.append("    " + " | ".join(_cell(v) for v in row))
        full_parts.append("\n".join(block))

    _schema_full    = "\n\n".join(full_parts)
    _schema_compact = "\n".join(compact_parts)


def get_db_schema(db, compact: bool = False) -> str:
    if not _schema_full:
        _build_schemas(db)
    return _schema_compact if compact else _schema_full


def invalidate_schema_cache():
    global _schema_full, _schema_compact
    _schema_full = _schema_compact = ""


# ── Prompts ───────────────────────────────────────────────────────────────────

_SQL_SYSTEM = """\
You are an expert MySQL query writer for Mewar ERP — a business management system.

DATABASE SCHEMA (exact column names — do NOT guess):

categories: id, name, is_delete, deleted_at, created_at, updated_at
consumptions: id, request_slips_id, transaction_date, created_by(->users), rs_row_id, inventory_id(->inventories), machine_id, unit, quantity, height, width, project_id(->projects), remark
departments: id, department_name, status, created_at, updated_at
firms: id, name, phone, address, email, website, gst_no, pan, logo, created_at, updated_at
grns: id, grn_number, purchase_order_id(->purchase_orders), grn_date, invoice_no, remarks, created_at, updated_at
grn_items: id, grn_id(->grns), inventory_id(->inventories), received_qty, accepted_qty, rejected_qty, placement, created_at, updated_at
inventories: id, name, opening_quantity, min_quantity, unit_id(->units), unit, model, category_id(->categories), grade, height, width, length, thikness, is_deleted, opening_stock, type, classification, placement, composition, outer_diameter, inner_diameter, no_of_coil, created_at, updated_at
issue_slips: id, issue_slip_no, project_id(->projects), requisition_slip_id(->requisition_slips), transaction_date, department_id(->departments), employee_id(->users), total_req_qty, total_issue_qty, total_pending_qty, comment, status, flag, created_by, edited_by, created_on, edited_on
issue_slip_rows: id, issue_slip_id(->issue_slips), requisition_slip_row_id, item_id(->inventories), quantity, description, status, pr_status, machine_id, order_qty, issue_qty, pending_qty, pr_machining_status, supplier_id(->suppliers)
job_cards: id, transaction_date, job_card_no, priority, status, vendor_id(->vendors), employee_id(->users), created_by, total_qty, pending_qty, total_received_qty, completion_date, created_at, completed_at
job_card_rows: id, job_card_id(->job_cards), issue_slip_row_id, item_id(->inventories), qty, item_pending_qty, received_qty, completion_date, status, description, supplier_id(->suppliers)
placements: id, name, created_at, updated_at
po_status_logs: id, purchase_order_id(->purchase_orders), status, changed_by(->users), changed_at, remarks
po_transactions: id, po_id(->purchase_orders), pay_amount, transaction_date
products: id, name, is_deleted, estimation_budget, estimation_duration, start_date, created_at, updated_at
product_items: id, product_id(->products), inventory_id(->inventories), quantity, is_deleted, created_at, updated_at
projects: id, name, status, priority, deadline, start_date, end_date, created_by(->users), is_deleted, completion_date, budget, comment, refurbish, created_at, updated_at
project_item: id, project_id(->projects), inventory_id(->inventories), quantity, length, created_at, updated_at
project_products: id, project_id(->projects), product_id(->products), quantity, status, is_deleted, created_at, updated_at
purchase_orders: id, po_number, supplier_id(->suppliers), po_date, expected_delivery, total_qty, subtotal, tax_amount, total_amount, subtotal_discount_amount, final_discount, loading_cutting_charges, freight_charges, advance_amount, balance_amount, remaining_amount, status, delivery_status, firm(->firms), remarks, terms_and_conditions, created_by(->users), approved_by(->users), created_at, completed_at
purchase_order_items: id, purchase_order_id(->purchase_orders), pr_item_id(->purchase_request_items), inventory_id(->inventories), hsn, ordered_qty, received_qty, unit_price, discount, discount_amount, tax_type, tax_percent, tax_amount, taxable_total, line_total, item_not, created_at
purchase_requests: id, pr_no, request_date, requested_by(->users), department_id(->departments), priority, status, remarks, total_qty, approved_by(->users), approved_at, created_at, updated_at
purchase_request_approvals: id, purchase_request_id(->purchase_requests), approver_id(->users), approval_level, status, remarks, action_date
purchase_request_items: id, purchase_request_id(->purchase_requests), issue_slip_row_id, item_id(->inventories), description, requested_qty, approved_qty, ordered_qty, uom, required_date, status, exited_qty, created_at
purchase_request_po_map: id, purchase_request_item_id(->purchase_request_items), purchase_order_item_id(->purchase_order_items), created_at
request_slip_histories: id, request_slip_id, action_by(->users), action, status, remarks, hold_by, created_at, updated_at
requisition_slips: id, rs_id, requisition_slip_no, store_rs, transaction_date, employee_id(->users), project_id(->projects), machine_id, lot_no, batch_no, department_id(->departments), purpose, total_qty, comment, status, approved_by(->users), rejected_by(->users), admin_id(->users), approved_date, rejected_date, admin_action_date, approve_comment, rejected_reason, admin_action_remark, admin_approve_status, po_flag, issue_completed, flag, is_exited, hold_by, created_by, edited_by, created_on, edited_on
requisition_slip_rows: id, requisition_slip_id(->requisition_slips), machine_id, item_id(->inventories), unit_id(->units), quantity, order_qty, issue_qty, pending_qty, order_pending_qty, issued_qty, consumed_qty, issued_height, issued_width, consumed_height, consumed_width, description, status, exited_qty, is_completed, unit
requisition_slip_row_pieces: id, item_id(->inventories), requisition_slip_row_id(->requisition_slip_rows), issued_height, issued_width, issued_qty, consumed_height, consumed_width, consumed_qty, shape, is_completed, send_hod
roles: id, name, deleted_at, created_at, updated_at
stock_transactions: id, project_id(->projects), machine_id, inventory_id(->inventories), txn_date, txn_type(enum: In/Out), quantity, ref_type, ref_no, issued_to(->users), issue_by(->users), requision_id(->requisition_slips), issue_slip_id(->issue_slips), supplier_id(->suppliers), vendor_id(->vendors), remarks
suppliers: id, category, registration_date, supplier_name, supplier_code, contact_person, email, state, city, mobile, gst_registered, gstin, pan, supplier_address, bank_name, branch_address, ifsc, account_number, created_at, updated_at
supplier_inventories: id, supplier_id(->suppliers), inventory_id(->inventories), quantity, created_at, updated_at
units: id, name, is_deleted, created_at, updated_at
users: id, name, email, status, date, is_delete, password, address, role_id(->roles), country_code, mobile, department_id(->departments), authority_id, image, created_at, updated_at
vendors: id, name, mobile_no, email, address, city, created_at, updated_at
vendor_payments: id, vendor_id(->vendors), purchase_order_id(->purchase_orders), amount, payment_date, payment_mode, reference_no, created_at

OUTPUT RULES — MUST FOLLOW:
1. Output ONLY a raw MySQL SELECT query. No explanation. No markdown. No code fences.
2. Never write INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, or any write operation.
3. Do NOT add any LIMIT clause. Return all rows unless the user explicitly asks for a top-N.
4. For ANY name or text search, ALWAYS use fuzzy matching:
   WHERE (col LIKE '%term%' OR col SOUNDS LIKE 'term' OR col LIKE '%word1%' OR col LIKE '%word2%')
5. If the question truly cannot be answered from this schema, output exactly: CANNOT_ANSWER
6. For vague/analytical questions ("best", "worst", "recommend"), fetch relevant metrics so the answer step can give a real recommendation.

CRITICAL RULES (never violate):
- NEVER use `pp.inventory_id` or `project_products.inventory_id`. This column DOES NOT EXIST and will crash the database. ALWAYS use `pit.inventory_id` (from the `product_items` table) for grouping and selecting inventory.
- RESPONSE TEXT RULE: NEVER guess or mention calculated numbers (like sums, counts, or totals) in your introductory text before the table. Let the SQL table display the final number. Use a simple intro like: "Here is the total sum based on your request:"
- UNIVERSAL COMBO RULE (List + Total/Sum in ONE question): If the user asks for a list AND its total sum or count in the SAME message (e.g., "show pending POs and their total amount", "kon konse items ki shortage hai or unka sum kitna hai"), ALWAYS wrap your base query in a CTE (WITH clause).
Use this exact format:

WITH base_data AS (
    -- Write your complete base query here for the list (without ORDER BY or LIMIT) --
)
SELECT bd.*, 
       (SELECT COUNT(*) FROM base_data) AS combo_total_count,
       (SELECT SUM(column_name_to_sum) FROM base_data) AS combo_total_sum 
FROM base_data bd
ORDER BY 1 ASC;
- COMBO TEXT RESPONSE: When you execute a combo query, use the `combo_total_sum` or `combo_total_count` values to announce the total in your introductory sentence (e.g., "Total sum is X. Here is the list:"). Do not try to manually calculate it in text, trust the SQL output.
- suppliers name column: `supplier_name` — NEVER write s.name or suppliers.name
- suppliers name column: `supplier_name` — NEVER write s.name or suppliers.name
- purchase_order_items FK to purchase_orders: column is `purchase_order_id` — NEVER write `po_id`
- purchase_order_items has NO supplier_id — FK is on purchase_orders.supplier_id
- purchase_order_items amount columns: `line_total`, `taxable_total` only — NO total_amount/balance_amount
- purchase_order_items has NO name/description/item_name — item name is in inventories.name via inventory_id
- When aggregating per supplier: GROUP BY s.id, s.supplier_name ONLY — never include purchase_orders columns in GROUP BY
- purchase_orders has NO project_id — no direct join between purchase_orders and projects
- requisition_slips = request slips (rs) — same table; alias it `rs` NOT `is` (that's reserved for issue_slips)
- issue_slips alias must be `isl` or `islip` — NEVER use alias `is` (reserved SQL keyword)
- issue_slip_rows FK to issue_slips: column is `issue_slip_id` — join: isl.id = isr.issue_slip_id
- issue_slip_rows item column: `item_id` (-> inventories) — NEVER write `inventory_id` on this table
- requisition_slips has NO total_issue_qty / total_pending_qty columns — those are on issue_slips (total_issue_qty, total_pending_qty). To get issued/pending per RS, join: requisition_slips -> issue_slips via issue_slips.requisition_slip_id
- When the question asks for "issued qty" or "pending qty" per RS, use issue_slips.total_issue_qty and issue_slips.total_pending_qty
- COLUMN NAMING: always SELECT and GROUP BY the raw FK id column alongside the name — e.g. SELECT st.inventory_id, i.name, SUM(...) ... GROUP BY st.inventory_id, i.name. Never drop inventory_id from the SELECT.
- inventories has NO columns named `current_stock` or `shortage` — never reference them directly; always compute inline with COALESCE/SUM subquery
- stock_transactions join to inventories: st.inventory_id = i.id (NOT i.inventory_id)
- project_item table alias: use `pi` — but NEVER use `pi.name`; project name comes from projects.name via pi.project_id = p.id
- grn_items FK to grns: column is `grn_id` — join: g.id = gi.grn_id
- grn_items has NO `po_id` — to link GRN to PO: grn_items -> grns.purchase_order_id -> purchase_orders
- requisition_slip_rows has NO `project_id` — get project via: rsr -> requisition_slips.project_id -> projects
- stock_transactions `txn_type` values are exactly: 'In' and 'Out' (capital first letter)
- inventories has NO `current_stock` column — compute it: COALESCE(opening_quantity,0) + COALESCE(net_txn,0)
- inventories has NO `quantity` column — use `opening_quantity` or compute from stock_transactions
- DUAL EXTREMES (MAX & MIN): If the user asks for BOTH highest/biggest AND lowest/smallest metrics, you MUST use UNION ALL. CRITICAL SQL SYNTAX: In MariaDB/MySQL, when using ORDER BY and LIMIT inside a UNION ALL, you MUST wrap each SELECT statement in parentheses. Example: (SELECT id, po_number, total_amount FROM purchase_orders ORDER BY total_amount DESC LIMIT 1) UNION ALL (SELECT id, po_number, total_amount FROM purchase_orders ORDER BY total_amount ASC LIMIT 1).
- SPELLING OVERRIDES: For item thickness, ALWAYS use the exact column name 'thikness' (without 'c'). Never autocorrect it to 'thickness' in the query, otherwise it will crash. Other dimensions are 'height', 'width', 'length', 'outer_diameter', 'composition', 'grade'.
- purchase_orders `status` values: 'Draft', 'Approved', 'Completed' (capital first letter)
- When joining purchase_orders with grns: purchase_orders.id = grns.purchase_order_id
- projects `status` values are exactly: 'new' and 'in_progress' (lowercase with underscore) — NEVER use 'In Progress', 'inprogress', 'active', or any other variant
- "in progress projects", "jo projects chal rahe hain", "current projects" means WHERE status='in_progress' — apply this filter strictly, do NOT return all projects
- projects table date columns: `start_date` = project start, `end_date` = project end/deadline, `deadline` column is usually NULL — ALWAYS use `end_date` when asked for deadline, due date, end date, or "kab tak chalega"
- ENTITY RESOLUTION (PROJECTS vs SUPPLIERS): They are completely separate. 
  1. If the user asks about timelines, deadlines, budgets, or inventory required/consumed at a site -> SEARCH IN `projects` table (projects.name LIKE '%term%'). 
  2. If the user asks about POs, orders, pending balance, payments, or contact details (mobile/email) -> SEARCH IN `suppliers` table (supplier_name LIKE '%term%').
  Do NOT mix them. Use the context of the question (e.g., 'balance' means supplier, 'deadline/site' means project) to decide which table to search if the user just provides a name.
- PROJECT INVENTORY ITEMS: When asked for a project's inventory (e.g., "X project ki inventory batao"), you MUST NEVER output CANNOT_ANSWER. Always use this EXACT template. For the LIKE clause, extract the core parts of the user's word to bypass typos (e.g., for "mahipal singh", use `p.name LIKE '%mahip%' AND p.name LIKE '%sing%'`):
  SELECT i.id, i.name, i.model, SUM(pp.quantity * pit.quantity) AS required_qty, 'BOM' AS source
  FROM projects p JOIN project_products pp ON pp.project_id=p.id AND pp.is_deleted=0
  JOIN product_items pit ON pit.product_id=pp.product_id AND pit.is_deleted=0
  JOIN inventories i ON i.id=pit.inventory_id
  WHERE (p.name LIKE '%term1%' AND p.name LIKE '%term2%')
  GROUP BY i.id, i.name, i.model, source
  UNION ALL
  SELECT i.id, i.name, i.model, SUM(pi.quantity) AS required_qty, 'Direct' AS source
  FROM projects p JOIN project_item pi ON pi.project_id=p.id
  JOIN inventories i ON i.id=pi.inventory_id
  WHERE (p.name LIKE '%term1%' AND p.name LIKE '%term2%')
  GROUP BY i.id, i.name, i.model, source
- Hindi/Hinglish list words: "sarii", "saari", "saare", "sari", "sabhi", "sab", "sare" all mean "all" — fetch ALL rows with NO date or status filter unless the user also specifies one
- Date day filter: "13 date wali", "13 tarikh wali", "only 13 date" means DAY(transaction_date) = 13 — use DAY() function
- "X month wali" or "X mahine wali" means MONTH(transaction_date) = X
- GLOBAL INVENTORY SHORTAGE: "inventory items ki shortage" (without project context) means items where
  current_stock < inventories.min_quantity. shortage = min_quantity - current_stock.
  current_stock for global shortage = COALESCE(opening_quantity, 0) + net stock_transactions (In minus Out).
  Simpler formula used in practice: shortage = min_quantity - opening_quantity when opening_quantity < min_quantity.
- "paisa baaki" or "rokra" for suppliers means purchase_orders.balance_amount — SUM(balance_amount) per supplier
- ITEM TYPE STOCK QUERY ("bearing ka stock", "bolt ka stock", "how much bearings do we have"):
  These ask for the TOTAL combined stock of ALL items whose name contains that word.
  ALWAYS use this structure:
  SELECT SUM(COALESCE(i.opening_quantity, 0) + COALESCE(st.net_qty, 0)) AS total_stock
  FROM inventories i
  LEFT JOIN (
      SELECT inventory_id, SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) AS net_qty
      FROM stock_transactions GROUP BY inventory_id
  ) st ON i.id = st.inventory_id
  WHERE i.name LIKE '%...%' AND i.is_deleted = 0;
  Return a SINGLE row with total_stock. Do NOT list individual items — aggregate them.
- MULTI-TYPE STOCK ("bolts and bearings ka stock", "how much X and Y do we have"):
  Search by item name, NOT by categories table — categories has generic names like 'Raw Material', not 'Bearings'/'Bolts'.
  Use UNION ALL to show each type as a labeled group. Example for bolt+bearing:
  SELECT 'Bolt' AS item_type, SUM(COALESCE(i.opening_quantity,0)+COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id=i.id),0)) AS total_stock FROM inventories i WHERE i.name LIKE '%bolt%'
  UNION ALL
  SELECT 'Bearing' AS item_type, SUM(...) FROM inventories i WHERE i.name LIKE '%bearing%'
  Always label each row with a human-readable item_type, not a model number or id.
- MODEL-WISE STOCK BREAKDOWN ("model wise stock", "X ke saare models dikhao", "model wise breakdown"):
  Show each individual item row (not aggregated). Use this exact pattern:
  SELECT i.name, i.model,
    COALESCE(i.opening_quantity,0) + COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions st WHERE st.inventory_id=i.id),0) AS current_stock
  FROM inventories i
  WHERE (i.name LIKE '%bolt%' OR i.name LIKE '%bearing%' OR i.name LIKE '%spring%' OR i.name LIKE '%cutting rod%')
  ORDER BY i.name, i.model
  NEVER select `model` as a stock value. `model` is a text descriptor column on inventories. `current_stock` must always be computed from opening_quantity + stock_transactions SUM.
- Pronouns "iski", "iska", "is item ki", "is cheez ki" in a follow-up refer to the item mentioned in the previous turn — resolve them from conversation context.
- CONTEXTUAL AGGREGATION (COUNT/SUM): If the user asks for a "total count", "kitne items hain", or "sum" (e.g., "unki total required quantity ka sum") based on the previous list, DO NOT write a new query. DO NOT try to filter by item names (No WHERE i.name LIKE). You MUST wrap the EXACT, UNMODIFIED previous query inside a SUM() or COUNT() block.
  If they ask for SUM, use this exact format:
  SELECT SUM(required_qty) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
  If they ask for COUNT, use this exact format:
  SELECT COUNT(*) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
- REQUIRED VS AVAILABLE STOCK ("required vs available", "shortage", "sabse badi shortage", "project ke liye kitna chahiye vs kitna hai"):
  CRITICAL: You MUST COPY AND PASTE this exact SQL template for shortage. Do NOT modify the core logic.
  WITH RunningProjects AS (
      SELECT id FROM projects WHERE status = 'in_progress'
  ),
  ReqUnion AS (
      SELECT pi.inventory_id, SUM(CAST(pp.quantity AS SIGNED) * CAST(pi.quantity AS SIGNED)) as req
      FROM RunningProjects p JOIN project_products pp ON p.id = pp.project_id JOIN product_items pi ON pp.product_id = pi.product_id GROUP BY pi.inventory_id
      UNION ALL
      SELECT p_item.inventory_id, SUM(CAST(p_item.quantity AS SIGNED)) as req
      FROM RunningProjects p JOIN project_item p_item ON p.id = p_item.project_id GROUP BY p_item.inventory_id
  ),
  TotalReq AS (
      SELECT inventory_id, SUM(req) as total_req FROM ReqUnion GROUP BY inventory_id
  ),
  AllowedMachines AS (
      SELECT DISTINCT machine_id FROM stock_transactions WHERE project_id IN (SELECT id FROM RunningProjects) AND machine_id IS NOT NULL
  ),
  Consumption AS (
      SELECT inventory_id, SUM(quantity) as cons_qty FROM stock_transactions WHERE LOWER(txn_type) = 'out' AND (project_id IN (SELECT id FROM RunningProjects) OR machine_id IN (SELECT machine_id FROM AllowedMachines)) GROUP BY inventory_id
  ),
  AvailableStock AS (
      SELECT inventory_id, (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) - SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail FROM stock_transactions GROUP BY inventory_id
  )
  SELECT i.name as item_name, (COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) AS required_qty, COALESCE(a.total_avail, 0) AS available_stock, ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0)) AS shortage_qty 
  FROM TotalReq tr JOIN inventories i ON tr.inventory_id = i.id LEFT JOIN Consumption c ON tr.inventory_id = c.inventory_id LEFT JOIN AvailableStock a ON tr.inventory_id = a.inventory_id 
  WHERE i.is_deleted = 0 HAVING shortage_qty > 0 ORDER BY shortage_qty DESC;
  - ANY STOCK, INVENTORY, OR VALUATION QUERY ("stock", "qty", "valuation", "available", "semi-finish", "finish"):
  CRITICAL & MANDATORY RULE: You MUST COPY AND PASTE this exact CTE template for calculating current stock and valuation. Do NOT modify the math.
  
  WITH TxnSummary AS (
      SELECT inventory_id,
      SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) as total_in,
      SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) as total_out,
      SUM(CASE WHEN LOWER(txn_type) = 'in' AND LOWER(ref_type) = 'finish' THEN quantity ELSE 0 END) as total_finish,
      SUM(CASE WHEN LOWER(txn_type) = 'out' AND LOWER(ref_type) = 'machining' THEN quantity ELSE 0 END) as total_mc
      FROM stock_transactions GROUP BY inventory_id
  ),
  CurrentStock AS (
      SELECT i.name as item_name, COALESCE(i.rate, 0.0) as rate, 
             (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) as total_qty, 
             ((COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) * COALESCE(i.rate, 0.0)) AS valuation,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN (COALESCE(t.total_mc, 0) - COALESCE(t.total_finish, 0)) ELSE 0 END AS machining_stock,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) IN ('FINISH', '', 'NULL') THEN (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN (COALESCE(t.total_finish, 0) - COALESCE(t.total_out, 0)) ELSE (COALESCE(t.total_in, 0) - COALESCE(t.total_finish, 0)) END AS finish_stock,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN ((COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) - (COALESCE(t.total_mc, 0) - COALESCE(t.total_finish, 0)) - (COALESCE(t.total_finish, 0) - COALESCE(t.total_out, 0))) ELSE 0 END AS semi_finish_stock
      FROM inventories i LEFT JOIN TxnSummary t ON i.id = t.inventory_id
      WHERE i.is_deleted = 0 AND (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) > 0
  )
  -- IMPORTANT: You must SELECT from the CurrentStock CTE above based on user's query:
  -- IF overall total: SELECT SUM(total_qty) AS total_items, SUM(valuation) AS total_valuation FROM CurrentStock
  -- IF specific item: SELECT item_name, total_qty, semi_finish_stock, finish_stock, valuation FROM CurrentStock WHERE item_name LIKE '%term%'
 - STOCK LEDGER ("stock ledger", "item history", "ledger of X item", "transactions of X"):
  CRITICAL: When a user asks for the ledger or transaction history of a specific item, you MUST match the ERP UI by including Party/Project details and proper chronological sorting.
  Pattern: 
  SELECT st.txn_date, st.txn_type, st.ref_type, i.name AS item_name, st.quantity, COALESCE(s.supplier_name, v.name, p.name, 'N/A') AS party_project_details, st.remarks 
  FROM stock_transactions st 
  JOIN inventories i ON st.inventory_id = i.id 
  LEFT JOIN suppliers s ON st.supplier_id = s.id 
  LEFT JOIN vendors v ON st.vendor_id = v.id 
  LEFT JOIN projects p ON st.project_id = p.id 
  WHERE (i.name LIKE '%term1%' OR i.name LIKE '%term2%') 
  ORDER BY st.txn_date DESC, st.id DESC;
  - ITEM PURCHASE HISTORY, SUPPLIER & PRICING ("item ka price", "who supplies X", "PO history of item", "kisse kharida"):
  When a user asks for the supplier, PO details, or purchase price of a specific item name, you MUST join purchase_order_items, purchase_orders, suppliers, and inventories.
  Pattern:
  SELECT i.name AS item_name, s.supplier_name, po.po_number, po.po_date AS order_date, poi.ordered_qty, poi.unit_price AS price
  FROM purchase_order_items poi
  JOIN purchase_orders po ON poi.purchase_order_id = po.id
  JOIN suppliers s ON po.supplier_id = s.id
  JOIN inventories i ON poi.inventory_id = i.id
  WHERE (i.name LIKE '%term1%' OR i.name LIKE '%term2%')
  ORDER BY po.po_date DESC;
- GROUP BY STRICT MODE: If you use a GROUP BY clause, EVERY column in the SELECT list that is not inside an aggregate function (like SUM, COUNT, MAX) MUST be included in the GROUP BY clause. Do not leave trailing non-aggregated columns.
- SOUNDS LIKE SYNTAX: NEVER use wildcard characters ('%') with SOUNDS LIKE. Correct: `col SOUNDS LIKE 'term'`. Wrong: `col SOUNDS LIKE '%term%'`.
- DATE COMPARISONS: For queries asking about "today", "aaj", or "current", ALWAYS use the MySQL CURDATE() or NOW() functions instead of hardcoding dates.
- NO DATA CREATION/FORMS: You are a READ-ONLY data retrieval assistant. NEVER say you are "creating", "drafting", or "preparing a form" for a request slip or PO. Always fetch EXISTING records using SELECT queries.
- REQUEST SLIPS (RS) BY PROJECT: If the user asks for "request slips", "RS", or "slips" for a specific project (e.g., "sonampur cement ki request slip"), you MUST join with the projects table.
  Pattern: SELECT rs.requisition_slip_no, p.name AS project, rs.transaction_date, rs.status 
  FROM requisition_slips rs JOIN projects p ON rs.project_id = p.id 
  WHERE p.name LIKE '%term%'.
  (CRITICAL: Intelligently fix minor typos in the LIKE clause. e.g., if user writes 'sonampur', search for '%sonapur%').
  - REQUEST SLIPS (RS) BY PROJECT: If the user asks for "request slips", "RS", or "slips" for a specific project (e.g., "sonampur cement ki request slip"), you MUST join with the projects table.
  Pattern: SELECT rs.requisition_slip_no, p.name AS project, rs.transaction_date, rs.status 
  FROM requisition_slips rs JOIN projects p ON rs.project_id = p.id 
  WHERE p.name LIKE '%term%'.
  (CRITICAL: Intelligently fix minor typos in the LIKE clause. e.g., if user writes 'sonampur', search for '%sonapur%').

- GRN LIST DASHBOARD: If the user asks for "grn list", "saare grn", or "grn dikhao", fetch the exact dashboard view using this SQL structure:
  SELECT g.id, g.grn_number, po.po_number, s.supplier_name, g.grn_date, g.invoice_no, COALESCE(SUM(gi.accepted_qty), 0) AS total_accepted
  FROM grns g
  LEFT JOIN purchase_orders po ON g.purchase_order_id = po.id
  LEFT JOIN suppliers s ON po.supplier_id = s.id
  LEFT JOIN grn_items gi ON gi.grn_id = g.id
  GROUP BY g.id, g.grn_number, po.po_number, s.supplier_name, g.grn_date, g.invoice_no
  ORDER BY g.grn_date DESC
  - REQUEST SLIP (RS) DASHBOARD: If the user asks for "saari request slips", "pending RS", or filters by date/project/status/code, ALWAYS use this dashboard structure:
  SELECT rs.requisition_slip_no AS rs_code, p.name AS project_name, rs.transaction_date AS created_date, rs.status
  FROM requisition_slips rs
  LEFT JOIN projects p ON rs.project_id = p.id
  WHERE 1=1
  -- (CRITICAL AI FILTERING RULES: Apply these dynamically based on user query)
  -- 1. Date Filters ("14 March ki RS", "April ki slips"): AND rs.transaction_date >= '...' AND rs.transaction_date <= '...'
  -- 2. Status ("pending", "approved", "rejected"): AND LOWER(rs.status) = 'pending'
  -- 3. RS Code ("RS 00012", "slip number 10"): AND rs.requisition_slip_no LIKE '%00012%'
  -- 4. Project ("Sonapur cement ki RS"): AND p.name LIKE '%sonapur%'
  ORDER BY rs.transaction_date DESC
  - PURCHASE REQUEST (PR) DASHBOARD: If the user asks for "saari purchase requests", "PR list", "pending PR", or filters by priority/status/date, ALWAYS use this dashboard structure:
  SELECT pr.pr_number, pr.request_date, pr.requested_by, pr.total_qty, pr.priority, pr.status
  FROM purchase_requests pr
  WHERE 1=1
  -- (CRITICAL AI FILTERING RULES for PRs: Apply dynamically based on user query)
  -- 1. Date Filters ("16 April ki PR", "March ki requests"): AND pr.request_date >= '...' AND pr.request_date <= '...'
  -- 2. Status ("ordered", "submitted", "approved"): AND LOWER(pr.status) = 'ordered'
  -- 3. Priority ("High priority wali PR dikhao"): AND LOWER(pr.priority) = 'high'
  -- 4. PR Number ("PR-104 ki details"): AND pr.pr_number LIKE '%104%'
  ORDER BY pr.request_date DESC
  - TOP N QUERIES (Ranking): If the user asks for "top 5", "highest", "biggest", or "sabse bade" (e.g., "top 5 po dikhao"), NEVER use LIKE '%top%'. You MUST use `ORDER BY` and `LIMIT`.
  Pattern for POs: SELECT po.po_number, s.supplier_name, po.po_date, po.total_amount, po.status FROM purchase_orders po LEFT JOIN suppliers s ON po.supplier_id = s.id ORDER BY po.total_amount DESC LIMIT 5
  - CRITICAL RULE FOR CHATBOT RESPONSE TONE & LOGIC:
  1. If the SQL query returns an empty table or states required_qty is 0 for an item, DO NOT say "Stock is insufficient". Instead, professionally state: "Currently, this item is not required for any active projects."
  2. Maintain a strict, professional corporate tone. NEVER use casual filler words like "hmm", "ek sec", or emojis like 🧐. Use phrases like "Scanning inventory and project requirements..."
  3. Only state there is a shortage if the data explicitly shows required_qty > available_qty.
"""

_FIX_PROMPT = """\
Original question: {question}

Your previous SQL failed:
SQL: {sql}
Error: {error}

Fix it and return ONLY the corrected SQL. No explanation.
"""

_ANSWER_SYSTEM = """\
You are a smart business assistant for Mewar ERP. Keep replies SHORT — 1 to 3 sentences max.

LANGUAGE: Always reply in Hinglish (Hindi + English mix). Use English for numbers, names, dates.
Examples: "Total 6 suppliers hain.", "Arawali Minerals ne sabse zyada orders diye — 18 POs."

- Factual queries: give the key number/name directly, skip preamble.
- Analytical queries ("best", "recommend"): 1 sentence insight + 1 sentence reason.
- If no data: say so in 1 line.
- NEVER mention SQL, database, tables, or technical terms.
- Today is {today}.
"""


# ── Provider calls ────────────────────────────────────────────────────────────

def _call_ai(system_full: str, system_compact: str, user: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_full},
                {"role": "user",   "content": user},
            ],
            temperature=0.0,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[NL2SQL] OpenAI failed: {e}")
        raise RuntimeError(f"OpenAI failed: {e}")


# ── SQL generation ────────────────────────────────────────────────────────────

def _clean_sql(raw: str) -> str:
    raw = re.sub(r"^```(?:sql)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()
    return raw


def _validate(raw: str) -> str:
    if raw.upper().startswith("CANNOT_ANSWER"):
        raise ValueError("Cannot be answered from the schema")
    
    # 🟢 UPDATE: Bracket '(' se shuru hone wali queries ko bhi allow karo
    if not re.match(r"^\s*(?:SELECT|WITH|\()", raw, re.IGNORECASE):
        raise ValueError(f"Non-SELECT output: {raw[:80]}")
        
    if raw.count("(") != raw.count(")"):
        raise ValueError(f"Truncated SQL (unbalanced parentheses): {raw[-60:]}")
    return raw


def _history_context(history: list) -> str:
    """Build a compact conversation context string from the last 4 turns."""
    if not history:
        return ""
    turns = history[-4:]
    lines = []
    for h in turns:
        role    = str(h.get("role", "")).lower()
        content = str(h.get("content", "")).strip()[:300]
        if role == "user":
            lines.append(f"User previously asked: {content}")
        elif role in ("assistant", "bot"):
            lines.append(f"Assistant previously answered: {content}")
    if not lines:
        return ""
    return (
        "CONVERSATION CONTEXT:\n"
        + "\n".join(lines)
        + "\n"
        "FOLLOW-UP RULES: If the new query is a filter/refinement on the previous one (e.g. 'only 13 date wali', 'sirf approved wali', 'project 5 wali'), "
        "apply that filter to the SAME table from the previous query. "
        "A bare number + 'date'/'tarikh' means DAY(date_column) = that number. "
        "Resolve 'unhe', 'unka', 'woh', 'those', 'them', 'iski', 'iska', 'is item ki' to refer to the specific item/entity mentioned in the previous turn. "
        "If the previous answer mentioned a specific inventory item name (e.g. 'Hard Facing Mig Roll'), "
        "use that exact item name in a LIKE '%name%' filter on inventories.name in the new query.\n\n"
    )


def generate_sql(user_query: str, schema_full: str = "", schema_compact: str = "",
                 previous_sql: str = None, sql_error: str = None,
                 history: list = None) -> str:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    system = _SQL_SYSTEM + f"\nToday's date: {today}. Use this to resolve partial dates (e.g. '23 feb' = '2026-02-23', 'April' = month 4).\n"
    ctx = _history_context(history or [])
    if previous_sql and sql_error:
        user = ctx + _FIX_PROMPT.format(question=user_query, sql=previous_sql, error=sql_error)
    else:
        user = ctx + user_query
    raw = _call_ai(
        system_full=system,
        system_compact=system,
        user=user,
    )
    sql = _validate(_clean_sql(raw))
    print(f"[NL2SQL] SQL: {sql[:200]}")
    return sql


# ── Answer formatting ─────────────────────────────────────────────────────────

def format_answer(user_query: str, rows: list, columns: list,
                  history: list = None) -> str:
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    if not rows:
        data_text = "No data found."
        null_warning = ""
    else:
        header = " | ".join(columns)
        body   = "\n".join(" | ".join(str(v) for v in row) for row in rows[:50])
        data_text = f"{header}\n{body}"

        null_cols = [
            col for col, val in zip(columns, rows[0])
            if val is None or str(val).strip() in ("", "None", "NULL", "N/A")
        ]
        null_warning = (
            f"\nWARNING: The following columns have NULL/empty values in the data: {', '.join(null_cols)}. "
            "Do NOT invent or guess values for these fields. Say the info is not available.\n"
        ) if null_cols else ""

    ctx  = _history_context(history or [])
    user = f"{ctx}User asked: {user_query}\n\nData returned:\n{data_text}\n{null_warning}\nGive a clear friendly answer."
    system = _ANSWER_SYSTEM.format(today=today)

    try:
        return _call_ai(system_full=system, system_compact=system, user=user)
    except Exception:
        return data_text if rows else "Koi data nahi mila."


#fgddxf


