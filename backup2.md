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
project_main_stage: id, project_id(->projects), main_stage_id(->stages), status_id(->stage_status), created_by, created_at, updated_at
project_products: id, project_id(->projects), product_id(->products), quantity, status, is_deleted, created_at, updated_at
project_stage_timelines: id, project_id(->projects), stage_id(->stages), start_date, end_date, created_at, updated_at
project_sub_stages: id, project_id(->projects), project_main_stage_id(->project_main_stage), sub_stage_id(->stages), status_id(->stage_status), created_by, created_at, updated_at
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
stages: id, name, present, order_no, section, parent_id, created_at, updated_at
stage_status: id, name, type, order_no, created_at, updated_at
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
- CRITICAL MYSQL 5.7 RULE: The database is MySQL 5.7. You STRICTLY MUST NOT use 'WITH' clauses or Common Table Expressions (CTEs). You MUST use nested subqueries or derived tables instead. NEVER start a query with 'WITH'.
- NEVER use `pp.inventory_id` or `project_products.inventory_id`. This column DOES NOT EXIST and will crash the database. ALWAYS use `pit.inventory_id` (from the `product_items` table) for grouping and selecting inventory.
- RESPONSE TEXT RULE: NEVER guess or mention calculated numbers (like sums, counts, or totals) in your introductory text before the table. Let the SQL table display the final number. Use a simple intro like: "Here is the total sum based on your request:"
- UNIVERSAL COMBO RULE (List + Total/Sum in ONE question): If the user asks for a list AND its total sum or count in the SAME message, ALWAYS use a derived table (nested subquery) instead of a CTE.
Use this exact format:

SELECT bd.*, 
       (SELECT COUNT(*) FROM (/* PASTE BASE QUERY HERE */) AS temp_count) AS combo_total_count,
       (SELECT SUM(column_name_to_sum) FROM (/* PASTE BASE QUERY HERE */) AS temp_sum) AS combo_total_sum 
FROM (
    -- Write your complete base query here for the list (without ORDER BY or LIMIT) --
) AS bd
ORDER BY 1 ASC;

- COMBO TEXT RESPONSE: When you execute a combo query, use the `combo_total_sum` or `combo_total_count` values to announce the total in your introductory sentence. Do not try to manually calculate it in text, trust the SQL output.
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
- DUAL EXTREMES (MAX & MIN): If the user asks for BOTH highest/biggest AND lowest/smallest metrics, you MUST use UNION ALL. CRITICAL SQL SYNTAX: In MariaDB/MySQL, when using ORDER BY and LIMIT inside a UNION ALL, you MUST wrap each SELECT statement in parentheses.
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
  Search by item name, NOT by categories table.
  Use UNION ALL to show each type as a labeled group. Example for bolt+bearing:
  SELECT 'Bolt' AS item_type, SUM(COALESCE(i.opening_quantity,0)+COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id=i.id),0)) AS total_stock FROM inventories i WHERE i.name LIKE '%bolt%'
  UNION ALL
  SELECT 'Bearing' AS item_type, SUM(...) FROM inventories i WHERE i.name LIKE '%bearing%'
- MODEL-WISE STOCK BREAKDOWN ("model wise stock", "X ke saare models dikhao", "model wise breakdown"):
  Show each individual item row (not aggregated). Use this exact pattern:
  SELECT i.name, i.model,
    COALESCE(i.opening_quantity,0) + COALESCE((SELECT SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) FROM stock_transactions st WHERE st.inventory_id=i.id),0) AS current_stock
  FROM inventories i
  WHERE (i.name LIKE '%bolt%' OR i.name LIKE '%bearing%' OR i.name LIKE '%spring%' OR i.name LIKE '%cutting rod%')
  ORDER BY i.name, i.model
  NEVER select `model` as a stock value. `model` is a text descriptor column on inventories. `current_stock` must always be computed from opening_quantity + stock_transactions SUM.
- Pronouns "iski", "iska", "is item ki", "is cheez ki" in a follow-up refer to the item mentioned in the previous turn — resolve them from conversation context.
- CONTEXTUAL AGGREGATION (COUNT/SUM): If the user asks for a "total count", "kitne items hain", or "sum" based on the previous list, DO NOT write a new query. You MUST wrap the EXACT, UNMODIFIED previous query inside a SUM() or COUNT() block.
  If they ask for SUM, use this exact format:
  SELECT SUM(required_qty) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
  If they ask for COUNT, use this exact format:
  SELECT COUNT(*) FROM (
      -- PASTE THE EXACT RAW SQL QUERY FROM YOUR PREVIOUS RESPONSE HERE WITHOUT CHANGING A SINGLE WORD --
  ) AS subq
- REQUIRED VS AVAILABLE STOCK ("required vs available", "shortage", "sabse badi shortage", "project ke liye kitna chahiye vs kitna hai"):
  CRITICAL: You MUST COPY AND PASTE this exact MySQL 5.7 compatible SQL template for shortage. DO NOT use CTEs (`WITH`):

  SELECT i.name as item_name,
         (COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) AS required_qty,
         COALESCE(a.total_avail, 0) AS available_stock,
         ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0)) AS shortage_qty
  FROM (
      SELECT inventory_id, SUM(req) as total_req FROM (
          SELECT pi.inventory_id, SUM(CAST(pp.quantity AS SIGNED) * CAST(pi.quantity AS SIGNED)) as req
          FROM projects p
          JOIN project_products pp ON p.id = pp.project_id
          JOIN product_items pi ON pp.product_id = pi.product_id
          WHERE p.status = 'in_progress'
          GROUP BY pi.inventory_id
          UNION ALL
          SELECT p_item.inventory_id, SUM(CAST(p_item.quantity AS SIGNED)) as req
          FROM projects p
          JOIN project_item p_item ON p.id = p_item.project_id
          WHERE p.status = 'in_progress'
          GROUP BY p_item.inventory_id
      ) ReqUnion GROUP BY inventory_id
  ) tr
  JOIN inventories i ON tr.inventory_id = i.id
  LEFT JOIN (
      SELECT inventory_id, SUM(quantity) as cons_qty
      FROM stock_transactions
      WHERE LOWER(txn_type) = 'out'
        AND (project_id IN (SELECT id FROM projects WHERE status = 'in_progress')
             OR machine_id IN (SELECT DISTINCT machine_id FROM stock_transactions WHERE project_id IN (SELECT id FROM projects WHERE status = 'in_progress') AND machine_id IS NOT NULL))
      GROUP BY inventory_id
  ) c ON tr.inventory_id = c.inventory_id
  LEFT JOIN (
      SELECT inventory_id,
      (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) -
       SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail
      FROM stock_transactions GROUP BY inventory_id
  ) a ON tr.inventory_id = a.inventory_id
  WHERE i.is_deleted = 0
  HAVING shortage_qty > 0
  ORDER BY shortage_qty DESC;

- ANY STOCK, INVENTORY, OR VALUATION QUERY ("stock", "qty", "valuation", "available", "semi-finish", "finish"):
  CRITICAL & MANDATORY RULE: You MUST COPY AND PASTE this exact MySQL 5.7 compatible template (no CTEs). DO NOT use `WITH`.

  SELECT item_name, rate, total_qty, valuation, machining_stock, finish_stock, semi_finish_stock FROM (
      SELECT i.name as item_name, COALESCE(i.rate, 0.0) as rate,
             (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) as total_qty,
             ((COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) * COALESCE(i.rate, 0.0)) AS valuation,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN (COALESCE(t.total_mc, 0) - COALESCE(t.total_finish, 0)) ELSE 0 END AS machining_stock,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) IN ('FINISH', '', 'NULL') THEN (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN (COALESCE(t.total_finish, 0) - COALESCE(t.total_out, 0)) ELSE (COALESCE(t.total_in, 0) - COALESCE(t.total_finish, 0)) END AS finish_stock,
             CASE WHEN UPPER(TRIM(COALESCE(i.classification, ''))) = 'SEMI_FINISH' THEN ((COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) - (COALESCE(t.total_mc, 0) - COALESCE(t.total_finish, 0)) - (COALESCE(t.total_finish, 0) - COALESCE(t.total_out, 0))) ELSE 0 END AS semi_finish_stock
      FROM inventories i LEFT JOIN (
          SELECT inventory_id,
          SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) as total_in,
          SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END) as total_out,
          SUM(CASE WHEN LOWER(txn_type) = 'in' AND LOWER(ref_type) = 'finish' THEN quantity ELSE 0 END) as total_finish,
          SUM(CASE WHEN LOWER(txn_type) = 'out' AND LOWER(ref_type) = 'machining' THEN quantity ELSE 0 END) as total_mc
          FROM stock_transactions GROUP BY inventory_id
      ) t ON i.id = t.inventory_id
      WHERE i.is_deleted = 0 AND (COALESCE(t.total_in, 0) - COALESCE(t.total_out, 0)) > 0
  ) AS CurrentStock
  -- IMPORTANT: Modify the SELECT clause above based on user's query:
  -- IF overall total: SELECT SUM(total_qty) AS total_items, SUM(valuation) AS total_valuation FROM (...) AS CurrentStock
  -- IF specific item: Add `WHERE item_name LIKE '%term%'` at the end of the query.

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
- COMPARISON QUERIES ("compare X and Y", "X vs Y", "difference between"): 
  NEVER output CANNOT_ANSWER for comparison queries. If the category is not explicitly mentioned, ALWAYS assume they are suppliers. Fetch key aggregated metrics for BOTH entities using an OR condition. 
  Pattern for Supplier Comparison: 
  SELECT s.supplier_name, COUNT(po.id) AS total_orders, SUM(po.total_amount) AS total_order_value, SUM(po.balance_amount) AS pending_balance 
  FROM suppliers s 
  LEFT JOIN purchase_orders po ON s.id = po.supplier_id 
  WHERE (s.supplier_name LIKE '%term1%' OR s.supplier_name LIKE '%term2%') 
  GROUP BY s.id, s.supplier_name;
- PROJECT PROGRESS & STAGES ("project progress", "kitna complete hua", "stage batao", "workflow"):
  When asked about a project's completion, progress, or stages, you MUST join `projects`, `project_main_stage`, `stages`, and `stage_status`. The `present` column in `stages` represents the weightage percentage.
  ALWAYS use this pattern:
  SELECT p.name AS project_name, st.name AS stage_name, st.present AS weight_percent, ss.name AS current_status
  FROM projects p
  JOIN project_main_stage pms ON p.id = pms.project_id
  JOIN stages st ON pms.main_stage_id = st.id
  JOIN stage_status ss ON pms.status_id = ss.id
  WHERE (p.name LIKE '%term1%' OR p.name LIKE '%term2%')
  ORDER BY st.order_no ASC;
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

CRITICAL RULES:
- Factual queries: give the key number/name directly, skip preamble.
- DO NOT calculate or sum up quantities. The exact number of parts/records is {row_count}. If you mention how many items there are, YOU STRICTLY MUST USE THE NUMBER {row_count}. NEVER use the sum of quantities.
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
    
    # 🚀 Yahan hum exact row count nikal rahe hain
    row_count = len(rows) if rows else 0 

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
    
    # 🚀 sending row_count to prompt
    system = _ANSWER_SYSTEM.format(today=today, row_count=row_count) 

    try:
        return _call_ai(system_full=system, system_compact=system, user=user)
    except Exception:
        return data_text if rows else "Koi data nahi mila."