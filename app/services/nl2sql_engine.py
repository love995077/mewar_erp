# import os
# import re
# import datetime
# from dotenv import load_dotenv
# from openai import OpenAI

# load_dotenv(override=True)

# # ── Keys & Models ────────────────────────────────────────────────────────────
# MODEL_NAME = "llama-3.3-70b-versatile"

# GROQ_KEYS = list(filter(None, [
#     os.getenv("GROQ_API_KEY_1"),
#     os.getenv("GROQ_API_KEY_2"),
# ]))

# current_key_index = 0

# # ── DB Schema Cache ──────────────────────────────────────────────────────
# _schema_compact : str = ""   

# def get_db_schema(db, compact: bool = True) -> str:
#     """Database ka naksha (tables/columns) nikalne ke liye."""
#     global _schema_compact
#     if _schema_compact:
#         return _schema_compact
        
#     from sqlalchemy import text
#     tables = db.execute(text("SHOW TABLES")).fetchall()
#     compact_parts = []

#     for (table,) in tables:
#         cols = db.execute(text(f"DESCRIBE `{table}`")).fetchall()
#         col_defs = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
#         compact_parts.append(f"Table `{table}`: {col_defs}")

#     _schema_compact = "\n".join(compact_parts)
#     return _schema_compact

# # ── Prompts (Memory + Business Rules) ────────────────────────────────────
# _SQL_SYSTEM = """\
# You are a highly intelligent MySQL query generator for Mewar ERP.

# DATABASE SCHEMA:
# {schema}

# RULES (STRICT):
# 1. Write ONLY a MySQL SELECT — never INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/EXEC.
# 2. Return ONLY the SQL query — no markdown, no explanation, no code fences.
# 3. Always add LIMIT 50 unless it is a COUNT/SUM/AVG aggregation.
# 4. For text searches, ALWAYS use 'LIKE %...%' and LOWER() instead of '='.
# 5. If you can't answer from schema, reply with: CANNOT_ANSWER

# BUSINESS RULES FOR MEWAR ERP (CRITICAL):
# - 'Total Kharcha' or 'Spend' = SUM of `total_amount` in `purchase_orders` table.
# - 'Rokda' or 'Pending Payment' or 'Balance' = SUM of `balance_amount` in `purchase_orders`.
# - 'Maal' or 'Stock' = Quantity from `inventories` and `stock_transactions`.
# - 'Party' or 'Vendor' = `suppliers` table.

# CONTEXT AWARENESS (LEVEL 3):
# - Always refer to the CONVERSATION HISTORY below. If user says "Inka", "Unka", or "Uska", understand they are referring to the entities mentioned in previous messages.
# """

# _FIX_PROMPT = """\
# Original question: {question}
# Your previous SQL failed with error: {error}
# SQL was: {sql}
# Fix it and return ONLY the corrected SQL.
# """

# _ANSWER_SYSTEM = """\
# You are a smart business data analyst for Mewar ERP.
# Reply in natural Hinglish (Hindi + English) as a helpful shop manager.

# RULES:
# 1. Highlight numbers, names, and total amounts in **bold**.
# 2. Give a conversational summary of the data, don't just dump it.
# 3. NEVER mention SQL, database, or technical terms.
# 4. If no data is found, politely say "Bhai, iska koi record nahi mila."
# 5. Today's date: {today}.
# """

# # ── Groq API Caller ──────────────────────────────────────────────────────────
# def _call_ai(system_prompt: str, user_prompt: str) -> str:
#     global current_key_index
#     if not GROQ_KEYS:
#         raise RuntimeError("GROQ API keys missing in .env")

#     for attempt in range(len(GROQ_KEYS) * 2): 
#         try:
#             active_key = GROQ_KEYS[current_key_index].strip()
#             client = OpenAI(
#                 base_url="https://api.groq.com/openai/v1",
#                 api_key=active_key,
#                 timeout=20.0
#             )

#             resp = client.chat.completions.create(
#                 model=MODEL_NAME,
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {"role": "user",   "content": user_prompt}
#                 ],
#                 temperature=0.0
#             )
#             return resp.choices[0].message.content.strip()

#         except Exception as e:
#             err_str = str(e).lower()
#             if "429" in err_str or "rate_limit" in err_str:
#                 current_key_index = (current_key_index + 1) % len(GROQ_KEYS)
#                 continue
#             else:
#                 current_key_index = (current_key_index + 1) % len(GROQ_KEYS)

#     raise RuntimeError("All Groq keys failed.")

# # ── Utilities & Level 3 Memory Context ───────────────────────────────────────
# def _clean_sql(raw: str) -> str:
#     """Cleaning AI output using a hack to avoid UI glitches."""
#     ticks = chr(96) * 3
#     raw = re.sub(r"^" + ticks + r"(?:sql)?\s*", "", raw.strip(), flags=re.IGNORECASE)
#     raw = re.sub(r"\s*" + ticks + r"$", "", raw).strip()
#     return raw

# def _validate(raw: str) -> str:
#     if raw.upper().startswith("CANNOT_ANSWER"):
#         raise ValueError("AI cannot answer from schema")
#     if not re.match(r"^\s*SELECT\b", raw, re.IGNORECASE):
#         raise ValueError("Invalid SQL generated")
#     return raw

# def _history_context(history: list) -> str:
#     """LEVEL 3: Building the memory block."""
#     if not history: return ""
#     lines = []
#     for h in history[-4:]: # Pichli 4 baatein
#         role = "System" if h.get("role") in ["assistant", "bot"] else "User"
#         lines.append(f"{role}: {h.get('content', '')[:200]}")
#     return "--- CONVERSATION HISTORY (MEMORY) ---\n" + "\n".join(lines) + "\n\n"

# # ── Core Functions (Exported to chatbot.py) ──────────────────────────────────
# def generate_sql(user_query: str, schema_full: str, schema_compact: str,
#                  previous_sql: str = None, sql_error: str = None, history: list = None) -> str:
#     mem_ctx = _history_context(history or [])
    
#     if previous_sql and sql_error:
#         user = mem_ctx + _FIX_PROMPT.format(question=user_query, sql=previous_sql, error=sql_error)
#     else:
#         user = f"{mem_ctx}Question: {user_query}"
        
#     system_prompt = _SQL_SYSTEM.format(schema=schema_compact)
#     raw = _call_ai(system_prompt, user)
#     return _validate(_clean_sql(raw))

# def format_answer(user_query: str, rows: list, columns: list, history: list = None) -> str:
#     today = datetime.datetime.now().strftime("%Y-%m-%d")
#     mem_ctx = _history_context(history or [])

#     if not rows:
#         data_text = "No records found."
#     else:
#         header = " | ".join(columns)
#         body   = "\n".join(" | ".join(str(v) for v in row) for row in rows[:20])
#         data_text = f"{header}\n{body}"

#     user = f"{mem_ctx}Question: {user_query}\n\nDB Data:\n{data_text}"
#     system_prompt = _ANSWER_SYSTEM.format(today=today)

#     try:
#         return _call_ai(system_prompt, user)
#     except:
#         return data_text if rows else "Data nahi mila bhai."
    

##--------------------------------------------------------------------------------------------------------------------------------
                                                  #MULTI ENGINE  (LOVE)
##--------------------------------------------------------------------------------------------------------------------------------
# import os
# import re
# import time
# import datetime
# from dotenv import load_dotenv
# from openai import OpenAI

# load_dotenv(override=True)

# # ── Keys & Models ────────────────────────────────────────────────────────────
# SAMBANOVA_KEY = os.getenv("SAMBANOVA_API_KEY", "").strip()

# GROQ_KEYS = list(filter(None, [
#     os.getenv("GROQ_API_KEY_1"),
#     os.getenv("GROQ_API_KEY_2"),
# ]))

# current_key_index = 0

# SAMBANOVA_MODELS = [
#     "DeepSeek-V3.1",                 # strongest coding/SQL model on SambaNova
#     "Meta-Llama-3.3-70B-Instruct",   # fallback
# ]
# GROQ_MODEL = "llama-3.3-70b-versatile"

# # ── Schema cache (used by get_db_schema / invalidate_schema_cache) ───────────
# _schema_full    : str = ""
# _schema_compact : str = ""

# SAMPLE_ROWS  = 3
# MAX_CELL_LEN = 50


# def _cell(v) -> str:
#     if v is None:
#         return "NULL"
#     s = str(v)
#     return s[:MAX_CELL_LEN] + "…" if len(s) > MAX_CELL_LEN else s


# def _build_schemas(db):
#     global _schema_full, _schema_compact
#     from sqlalchemy import text
#     tables = db.execute(text("SHOW TABLES")).fetchall()
#     full_parts    = []
#     compact_parts = []

#     for (table,) in tables:
#         cols      = db.execute(text(f"DESCRIBE `{table}`")).fetchall()
#         col_names = [c[0] for c in cols]
#         col_defs  = ", ".join(f"{c[0]} ({c[1]})" for c in cols)

#         compact_parts.append(f"Table `{table}`: {col_defs}")

#         try:
#             sample = db.execute(text(f"SELECT * FROM `{table}` LIMIT {SAMPLE_ROWS}")).fetchall()
#         except Exception:
#             sample = []

#         block = [f"Table `{table}`:"]
#         block.append(f"  Columns: {col_defs}")
#         if sample:
#             block.append("  Sample rows:")
#             block.append("    " + " | ".join(col_names))
#             for row in sample:
#                 block.append("    " + " | ".join(_cell(v) for v in row))
#         full_parts.append("\n".join(block))

#     _schema_full    = "\n\n".join(full_parts)
#     _schema_compact = "\n".join(compact_parts)


# def get_db_schema(db, compact: bool = False) -> str:
#     if not _schema_full:
#         _build_schemas(db)
#     return _schema_compact if compact else _schema_full


# def invalidate_schema_cache():
#     global _schema_full, _schema_compact
#     _schema_full = _schema_compact = ""


# # ── Prompts ───────────────────────────────────────────────────────────────────

# _SQL_SYSTEM = """\
# You are an expert MySQL query writer for Mewar ERP — a business management system.

# DATABASE SCHEMA (exact column names — do NOT guess):

# categories: id, name, is_delete, deleted_at, created_at, updated_at
# consumptions: id, request_slips_id, transaction_date, created_by(->users), rs_row_id, inventory_id(->inventories), machine_id, unit, quantity, height, width, project_id(->projects), remark
# departments: id, department_name, status, created_at, updated_at
# firms: id, name, phone, address, email, website, gst_no, pan, logo, created_at, updated_at
# grns: id, grn_number, purchase_order_id(->purchase_orders), grn_date, invoice_no, remarks, created_at, updated_at
# grn_items: id, grn_id(->grns), inventory_id(->inventories), received_qty, accepted_qty, rejected_qty, placement, created_at, updated_at
# inventories: id, name, opening_quantity, min_quantity, unit_id(->units), unit, model, category_id(->categories), grade, height, width, length, is_deleted, opening_stock, type, classification, placement, created_at, updated_at
# issue_slips: id, issue_slip_no, project_id(->projects), requisition_slip_id(->requisition_slips), transaction_date, department_id(->departments), employee_id(->users), total_req_qty, total_issue_qty, total_pending_qty, comment, status, flag, created_by, edited_by, created_on, edited_on
# issue_slip_rows: id, issue_slip_id(->issue_slips), requisition_slip_row_id, item_id(->inventories), quantity, description, status, pr_status, machine_id, order_qty, issue_qty, pending_qty, pr_machining_status, supplier_id(->suppliers)
# job_cards: id, transaction_date, job_card_no, priority, status, vendor_id(->vendors), employee_id(->users), created_by, total_qty, pending_qty, total_received_qty, completion_date, created_at, completed_at
# job_card_rows: id, job_card_id(->job_cards), issue_slip_row_id, item_id(->inventories), qty, item_pending_qty, received_qty, completion_date, status, description, supplier_id(->suppliers)
# placements: id, name, created_at, updated_at
# po_status_logs: id, purchase_order_id(->purchase_orders), status, changed_by(->users), changed_at, remarks
# po_transactions: id, po_id(->purchase_orders), pay_amount, transaction_date
# products: id, name, is_deleted, estimation_budget, estimation_duration, start_date, created_at, updated_at
# product_items: id, product_id(->products), inventory_id(->inventories), quantity, is_deleted, created_at, updated_at
# projects: id, name, status, priority, deadline, start_date, end_date, created_by(->users), is_deleted, completion_date, budget, comment, refurbish, created_at, updated_at
# project_item: id, project_id(->projects), inventory_id(->inventories), quantity, length, created_at, updated_at
# project_products: id, project_id(->projects), product_id(->products), quantity, status, is_deleted, created_at, updated_at
# purchase_orders: id, po_number, supplier_id(->suppliers), po_date, expected_delivery, total_qty, subtotal, tax_amount, total_amount, subtotal_discount_amount, final_discount, loading_cutting_charges, freight_charges, advance_amount, balance_amount, remaining_amount, status, delivery_status, firm(->firms), remarks, terms_and_conditions, created_by(->users), approved_by(->users), created_at, completed_at
# purchase_order_items: id, purchase_order_id(->purchase_orders), pr_item_id(->purchase_request_items), inventory_id(->inventories), hsn, ordered_qty, received_qty, unit_price, discount, discount_amount, tax_type, tax_percent, tax_amount, taxable_total, line_total, item_not, created_at
# purchase_requests: id, pr_no, request_date, requested_by(->users), department_id(->departments), priority, status, remarks, total_qty, approved_by(->users), approved_at, created_at, updated_at
# purchase_request_approvals: id, purchase_request_id(->purchase_requests), approver_id(->users), approval_level, status, remarks, action_date
# purchase_request_items: id, purchase_request_id(->purchase_requests), issue_slip_row_id, item_id(->inventories), description, requested_qty, approved_qty, ordered_qty, uom, required_date, status, exited_qty, created_at
# purchase_request_po_map: id, purchase_request_item_id(->purchase_request_items), purchase_order_item_id(->purchase_order_items), created_at
# request_slip_histories: id, request_slip_id, action_by(->users), action, status, remarks, hold_by, created_at, updated_at
# requisition_slips: id, rs_id, requisition_slip_no, store_rs, transaction_date, employee_id(->users), project_id(->projects), machine_id, lot_no, batch_no, department_id(->departments), purpose, total_qty, comment, status, approved_by(->users), rejected_by(->users), admin_id(->users), approved_date, rejected_date, admin_action_date, approve_comment, rejected_reason, admin_action_remark, admin_approve_status, po_flag, issue_completed, flag, is_exited, hold_by, created_by, edited_by, created_on, edited_on
# requisition_slip_rows: id, requisition_slip_id(->requisition_slips), machine_id, item_id(->inventories), unit_id(->units), quantity, order_qty, issue_qty, pending_qty, order_pending_qty, issued_qty, consumed_qty, issued_height, issued_width, consumed_height, consumed_width, description, status, exited_qty, is_completed, unit
# requisition_slip_row_pieces: id, item_id(->inventories), requisition_slip_row_id(->requisition_slip_rows), issued_height, issued_width, issued_qty, consumed_height, consumed_width, consumed_qty, shape, is_completed, send_hod
# roles: id, name, deleted_at, created_at, updated_at
# stock_transactions: id, project_id(->projects), machine_id, inventory_id(->inventories), txn_date, txn_type(enum: In/Out), quantity, ref_type, ref_no, issued_to(->users), issue_by(->users), requision_id(->requisition_slips), issue_slip_id(->issue_slips), supplier_id(->suppliers), vendor_id(->vendors), remarks
# suppliers: id, category, registration_date, supplier_name, supplier_code, contact_person, email, state, city, mobile, gst_registered, gstin, pan, supplier_address, bank_name, branch_address, ifsc, account_number, created_at, updated_at
# supplier_inventories: id, supplier_id(->suppliers), inventory_id(->inventories), quantity, created_at, updated_at
# units: id, name, is_deleted, created_at, updated_at
# users: id, name, email, status, date, is_delete, password, address, role_id(->roles), country_code, mobile, department_id(->departments), authority_id, image, created_at, updated_at
# vendors: id, name, mobile_no, email, address, city, created_at, updated_at
# vendor_payments: id, vendor_id(->vendors), purchase_order_id(->purchase_orders), amount, payment_date, payment_mode, reference_no, created_at

# OUTPUT RULES — MUST FOLLOW:
# 1. Output ONLY a raw MySQL SELECT query. No explanation. No markdown. No code fences.
# 2. Never write INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, or any write operation.
# 3. DO NOT use any LIMIT clause. Fetch all matching rows so the user can see everything, unless they specifically ask for "top 5".
# 4. For ANY name or text search, ALWAYS use fuzzy matching:
#    WHERE (col LIKE '%term%' OR col SOUNDS LIKE 'term' OR col LIKE '%word1%' OR col LIKE '%word2%')
# 5. If the question truly cannot be answered from this schema, output exactly: CANNOT_ANSWER
# 6. For vague/analytical questions ("best", "worst", "recommend"), fetch relevant metrics so the answer step can give a real recommendation.

# CRITICAL RULES (never violate):
# - suppliers name column: `supplier_name` — NEVER write s.name or suppliers.name
# - purchase_order_items has NO supplier_id — FK is on purchase_orders.supplier_id
# - purchase_order_items amount columns: `line_total`, `taxable_total` only — NO total_amount/balance_amount
# - purchase_order_items has NO name/description/item_name — item name is in inventories.name via inventory_id
# - PO UI CARDS: If aggregating data (like SUM of balance), ALWAYS alias the results EXACTLY as `SUM(total_amount) AS total_amount` and `SUM(balance_amount) AS balance_amount`.
# - MULTI-ITEM SEARCH: If searching for multiple items (e.g. 'bearing' and 'v belt'), you MUST NOT group by name. Select all relevant items and DO NOT use any LIMIT.
# - When aggregating per supplier: GROUP BY s.id, s.supplier_name ONLY — never include purchase_orders columns in GROUP BY
# - purchase_orders has NO project_id — no direct join between purchase_orders and projects
# - EXACT SUPPLIER MATCHING: If the user searches for a specific company name (even with typos like 'arawali minelarls'), try to match the full closest name. Do NOT fetch multiple different companies just because they share the first word (like 'Arawali'). Use LIMIT 1 if the intent is clearly a single specific entity.
# - requisition_slips = request slips (rs) — same table
# - Hindi/Hinglish list words: "sarii", "saari", "saare", "sari", "sabhi", "sab", "sare" all mean "all" — fetch ALL rows with NO date or status filter unless the user also specifies one
# - Date day filter: "13 date wali", "13 tarikh wali", "only 13 date" means DAY(transaction_date) = 13 — use DAY() function
# - "X month wali" or "X mahine wali" means MONTH(transaction_date) = X
# - "sabse bada supplier" / "top supplier" means the supplier with the highest total order value. ALWAYS select SUM(purchase_orders.total_amount) AS total_order_value along with COUNT(purchase_orders.id).
# - ALWAYS ORDER BY total_order_value DESC when asked for biggest/top suppliers.
# - CONTEXTUAL FOLLOW-UPS: If the user says short phrases like "details batao", "orders dikhao", or "uska batao" without mentioning the name, YOU MUST look at the CONVERSATION CONTEXT to find the exact supplier/project name previously discussed. You MUST add a strict `WHERE` clause for that specific name and use `LIMIT 1`. NEVER fetch all rows for a follow-up query.
# - If asking for "total inventory" or "kitna maal", use SUM() or COUNT() properly.
# - 👉 IMPORTANT: For 'pending orders' or 'kacha bill', use `status = 'Draft'` OR `balance_amount > 0`.
# - Stock: SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) AS total_stock.
# STRICT TARGET TABLE: Always base your main FROM clause on the 'STRICT TARGET TABLE'. EXCEPTION: If the user asks for "items", "inventory", or "maal", you MUST JOIN other tables (like project_item, product_items, inventories) to get the actual data.

# - UI CARDS: Always select 'id' and 'name' (or 'po_number', 'supplier_name') and other relevant columns so UI cards can render properly.
# - MIN/MAX COMBO: If the user asks 
# for BOTH the "biggest/highest" AND "smallest/lowest" items in the same query, you MUST return ONLY those two rows using a UNION query. Example: (SELECT * FROM table ORDER BY col DESC LIMIT 1) UNION (SELECT * FROM table ORDER BY col ASC LIMIT 1). Do NOT fetch the whole table.
# - 📦 NORMAL INVENTORY STOCK: If user simply asks "stock batao", "kitna maal hai", "availability check karo", ONLY use the standard stock calculation: SUM(CASE WHEN txn_type='In' THEN quantity ELSE -quantity END) AS total_stock.
# - 🏗️ PROJECT ITEMS JOIN RULE (CRITICAL): If user asks for "items" or "maal" of a project, DO NOT fetch only from projects table.
#   You MUST use this logic:
#   SELECT i.name as item_name, SUM(qty) as total_qty, i.unit 
#   FROM (
#     SELECT inventory_id, quantity as qty FROM project_item pji JOIN projects p ON p.id=pji.project_id WHERE (p.name LIKE '%...%')
#     UNION ALL
#     SELECT pi.inventory_id, (pp.quantity * pi.quantity) as qty FROM project_products pp JOIN projects p ON p.id=pp.project_id JOIN product_items pi ON pp.product_id=pi.product_id WHERE (p.name LIKE '%...%')
#   ) AS t 
#   JOIN inventories i ON t.inventory_id = i.id 
#   GROUP BY i.name, i.unit;
# - 🚨 SHORTAGE / REQUIRED VS AVAILABLE LOGIC (CRITICAL): 
#   If user asks about "shortage", "kam pad raha hai", or required stock for running projects (or a specific project), you MUST use this EXACT CTE structure. DO NOT rewrite it into subqueries!
  
#   WITH Req AS (
#     SELECT pi.inventory_id, SUM(pp.quantity * pi.quantity) as r_qty 
#     FROM projects p JOIN project_products pp ON p.id=pp.project_id JOIN product_items pi ON pp.product_id=pi.product_id 
#     WHERE LOWER(p.status) NOT IN ('completed','hold') GROUP BY pi.inventory_id
#     UNION ALL
#     SELECT pji.inventory_id, SUM(pji.quantity) as r_qty 
#     FROM projects p JOIN project_item pji ON p.id=pji.project_id 
#     WHERE LOWER(p.status) NOT IN ('completed','hold') GROUP BY pji.inventory_id
#   ),
#   TotalReq AS (
#     SELECT inventory_id, SUM(r_qty) as req FROM Req GROUP BY inventory_id
#   ),
#   Stock AS (
#     SELECT inventory_id, SUM(CASE WHEN LOWER(txn_type)='in' THEN quantity ELSE -quantity END) as avail 
#     FROM stock_transactions GROUP BY inventory_id
#   )
  
#   SELECT i.name as "item_name", 
#          tr.req as "required_qty", 
#          COALESCE(s.avail, 0) as "available_stock", 
#          (tr.req - COALESCE(s.avail, 0)) as "short_qty"
#   FROM TotalReq tr ...
#   JOIN inventories i ON tr.inventory_id=i.id 
#   LEFT JOIN Stock s ON tr.inventory_id=s.inventory_id
#   WHERE (tr.req - COALESCE(s.avail, 0)) > 0
#   ORDER BY (tr.req - COALESCE(s.avail, 0)) DESC;

# """

# _FIX_PROMPT = """\
# Original question: {question}

# Your previous SQL failed:
# SQL: {sql}
# Error: {error}

# Fix it and return ONLY the corrected SQL. No explanation.
# """

# _ANSWER_SYSTEM = """\
# You are a smart business assistant for Mewar ERP. Keep replies SHORT — 1 to 3 sentences max.

# LANGUAGE: Always reply in Hinglish (Hindi + English mix).

# RULES:
# 1. 🏗️ FOR PROJECTS: If the query is about a Project, talk about its status or its items/inventory list. NEVER ask about "Orders vs Details".
# 2. 🏭 FOR SUPPLIERS: ONLY if the query_type is 'supplier' and NOT about inventory, use the line: "💡 Aap inka kya dekhna chahte hain? **Orders** ya poori **Details**?"
# 3. 📦 FOR INVENTORY: Directly tell the stock or the list of items found.

# Examples:
# - Project: "Warrgyizmorsch project ke ye 5 items hain..." (Correct)
# - Supplier: "Shree Mahadev ka data mil gaya. 💡 Aap inka kya dekhna chahte hain? Orders ya poori Details?" (Correct)

# Today is {today}.
# """


# # ── Provider calls ────────────────────────────────────────────────────────────

# def _call_sambanova(system: str, user: str) -> str:
#     if not SAMBANOVA_KEY:
#         raise RuntimeError("No SAMBANOVA_API_KEY")
#     client = OpenAI(
#         base_url="https://api.sambanova.ai/v1",
#         api_key=SAMBANOVA_KEY,
#         timeout=30.0,
#     )
#     last_err = None
#     for model in SAMBANOVA_MODELS:
#         try:
#             resp = client.chat.completions.create(
#                 model=model,
#                 messages=[
#                     {"role": "system", "content": system},
#                     {"role": "user",   "content": user},
#                 ],
#                 temperature=0.0,
#                 max_tokens=1500,
#             )
#             return resp.choices[0].message.content.strip()
#         except Exception as e:
#             last_err = e
#     raise RuntimeError(f"SambaNova failed: {last_err}")


# def _call_groq(system: str, user: str) -> str:
#     global current_key_index
#     if not GROQ_KEYS:
#         raise RuntimeError("GROQ API keys missing in .env")

#     last_err = None
#     for attempt in range(len(GROQ_KEYS) * 2): 
#         try:
#             active_key = GROQ_KEYS[current_key_index].strip()
#             client = OpenAI(
#                 base_url="https://api.groq.com/openai/v1",
#                 api_key=active_key,
#                 timeout=20.0
#             )
#             resp = client.chat.completions.create(
#                 model=GROQ_MODEL,
#                 messages=[
#                     {"role": "system", "content": system},
#                     {"role": "user",   "content": user}
#                 ],
#                 temperature=0.0,
#                 max_tokens=1500,
#             )
#             return resp.choices[0].message.content.strip()

#         except Exception as e:
#             err_str = str(e).lower()
#             last_err = e
#             if "429" in err_str or "rate_limit" in err_str:
#                 current_key_index = (current_key_index + 1) % len(GROQ_KEYS)
#                 continue
#             else:
#                 current_key_index = (current_key_index + 1) % len(GROQ_KEYS)

#     raise RuntimeError(f"All Groq keys failed. Last error: {last_err}")


# def _call_ai(system_full: str, system_compact: str, user: str) -> str:
#     """
#     Provider chain — Try SambaNova first with full schema.
#     If it fails, fallback to Groq using compact schema and rotating keys.
#     """
#     # 1. SambaNova
#     try:
#         result = _call_sambanova(system_full, user)
#         print("[NL2SQL] answered by SambaNova")
#         return result
#     except Exception as e:
#         print(f"[NL2SQL] SambaNova failed: {str(e)[:120]}")

#     # 2. Groq (with your rotating key logic)
#     try:
#         result = _call_groq(system_compact, user)
#         print("[NL2SQL] answered by Groq (compact schema)")
#         return result
#     except Exception as e:
#         print(f"[NL2SQL] Groq failed: {str(e)[:120]}")

#     raise RuntimeError("All AI providers failed")


# # ── SQL generation ────────────────────────────────────────────────────────────

# def _clean_sql(raw: str) -> str:
#     raw = re.sub(r"^```(?:sql)?\s*", "", raw.strip(), flags=re.IGNORECASE)
#     raw = re.sub(r"\s*```$", "", raw).strip()
#     return raw


# def _validate(raw: str) -> str:
#     if raw.upper().startswith("CANNOT_ANSWER"):
#         raise ValueError("Cannot be answered from the schema")
        
#     # 👇 YAHAN CHANGE KIYA HAI: Ab SELECT ke sath-sath WITH ko bhi allow kar diya hai 👇
#     if not re.match(r"^\s*(SELECT|WITH)\b", raw, re.IGNORECASE):
#         raise ValueError(f"Invalid output (Must start with SELECT or WITH): {raw[:80]}")
        
#     if raw.count("(") != raw.count(")"):
#         raise ValueError(f"Truncated SQL (unbalanced parentheses): {raw[-60:]}")
#     return raw


# def _history_context(history: list) -> str:
#     """Build a compact conversation context string from the last 4 turns."""
#     if not history:
#         return ""
#     turns = history[-4:]
#     lines = []
#     for h in turns:
#         role    = str(h.get("role", "")).lower()
#         content = str(h.get("content", "")).strip()[:300]
#         if role == "user":
#             lines.append(f"User previously asked: {content}")
#         elif role in ("assistant", "bot"):
#             lines.append(f"Assistant previously answered: {content}")
#     if not lines:
#         return ""
#     return (
#         "CONVERSATION CONTEXT:\n"
#         + "\n".join(lines)
#         + "\n"
#         "FOLLOW-UP RULES: If the new query is a filter/refinement on the previous one (e.g. 'only 13 date wali', 'sirf approved wali', 'project 5 wali'), "
#         "apply that filter to the SAME table from the previous query. "
#         "A bare number + 'date'/'tarikh' means DAY(date_column) = that number. "
#         "Resolve 'unhe', 'unka', 'woh', 'those', 'them' to refer to the previous result set.\n\n"
#     )


# def generate_and_execute_sql(db, user_query: str, query_type: str, targets: list, filters: dict, history: list = None) -> dict:
#     today = datetime.datetime.now().strftime("%Y-%m-%d")
    
#     # 1. Get dynamic schemas
#     schema_full = get_db_schema(db, compact=False)
#     schema_compact = get_db_schema(db, compact=True)
    
#     # 2. Setup Prompts
#     system = _SQL_SYSTEM + f"\nToday's date: {today}. Use this to resolve partial dates (e.g. '23 feb' = '2026-02-23').\n"
#     ctx = _history_context(history or [])
        
#     user_prompt = f"{ctx}User Query: {user_query}\n👉 PRIMARY TARGET TABLE: {query_type.upper()} (Join other tables if required by the rules, especially for project items)\nTargets (use in WHERE): {targets}\nFilters: {filters}"
    
#     # 3. Call AI to generate SQL
#     raw_sql = _call_ai(system_full=system, system_compact=system, user=user_prompt)
    
#     try:
#         sql = _validate(_clean_sql(raw_sql))
#         print(f"[NL2SQL] Executing SQL: {sql[:200]}")
        
#         # 4. Execute SQL
#         from sqlalchemy import text
#         result = db.execute(text(sql)).fetchall()
        
#         # 5. Format Friendly Answer (using your old format_answer logic)
#         columns = list(result[0]._mapping.keys()) if result else []
#         rows = [list(r) for r in result]
#         friendly_msg = format_answer(user_query, rows, columns, history)
        
#         # 6. Format UI Cards (JSON)
#         ui_cards = format_sql_results(result, query_type)
        
#         # 7. Return Final Payload
#         return {"success": True, "results": [{"type": "chat", "message": friendly_msg}] + ui_cards}
        
#     except Exception as e:
#         print(f"❌ NL2SQL Error: {e}")
#         return {"success": False, "error": str(e)}


# # ── Answer formatting ─────────────────────────────────────────────────────────

# def format_answer(user_query: str, rows: list, columns: list,
#                   history: list = None) -> str:
#     today = datetime.datetime.now().strftime("%Y-%m-%d")

#     if not rows:
#         data_text = "No data found."
#     else:
#         header = " | ".join(columns)
#         body   = "\n".join(" | ".join(str(v) for v in row) for row in rows[:50])
#         data_text = f"{header}\n{body}"

#     ctx  = _history_context(history or [])
#     user = f"{ctx}User asked: {user_query}\n\nData returned:\n{data_text}\n\nGive a clear friendly answer."
#     system = _ANSWER_SYSTEM.format(today=today)

#     try:
#         return _call_ai(system_full=system, system_compact=system, user=user)
#     except Exception:
#         return data_text if rows else "Koi data nahi mila."
    
# # ── UI Card Formatting ────────────────────────────────────────────────────────

# def format_sql_results(db_results, query_type):
#     if not db_results: return []
    
#     final_output = []
#     for row in db_results:
#         r = row._mapping
        
#         # 👇 YAHAN SE APNA JADUI LOCK (FIX) LAGA DIYA 👇
#         if not r.get("id") and not r.get("name") and not r.get("supplier_name") and not r.get("po_number") and not r.get("project_name"):
#             continue
#         # 👆 ------------------------------------------ 👆
        
#         if query_type == "inventory":
#             stock = float(r.get('total_stock') or r.get('stock') or r.get('quantity') or r.get('available_qty') or 0)
            
#             # Classification ke hisaab se stock divide karna
#             cls = str(r.get('classification', '')).lower()
#             if "machining" in cls:
#                 m, f, sf = stock, 0, 0
#             elif "semi" in cls:
#                 m, f, sf = 0, 0, stock
#             else:
#                 m, f, sf = 0, stock, 0
                
#             final_output.append({
#                 "type": "result", 
#                 "inventory": {"id": r.get('id', 0), "name": r.get('name', 'N/A'), "category": r.get('type','Item'), "placement": r.get('placement','N/A')}, 
#                 "total_stock": stock, "finish_stock": f, "semi_finish_stock": sf, "machining_stock": m
#             })
#         elif query_type == "project":
#             final_output.append({
#                 "type": "project", "project_name": r.get('name', 'N/A'), "category": str(r.get('status','new')).title(), 
#                 "amount": float(r.get('budget', 0)), "start_date": str(r.get('start_date', 'N/A')), 
#                 "end_date": str(r.get('end_date', r.get('deadline', 'N/A'))), "comments": r.get('comment',''), "priority": r.get('priority','NORMAL')
#             })
#         elif query_type == "purchase_order":
#             # 🚀 SMART EXTRACTION: AI ke badle hue column names ko handle karna
#             po_no = r.get('po_number') or r.get('po_no')
#             if not po_no: 
#                 po_no = "Aggregated" if any("sum" in k.lower() or "total" in k.lower() for k in r.keys()) else r.get('id', 'N/A')
            
#             # Balance find karna (kisi bhi alias se)
#             bal = r.get('balance_amount')
#             if bal is None: 
#                 bal = next((v for k, v in r.items() if 'balance' in k.lower() and v is not None), 0)
            
#             # Total find karna
#             tot = r.get('total_amount')
#             if tot is None: 
#                 tot = next((v for k, v in r.items() if 'total' in k.lower() and v is not None), 0)
            
#             final_output.append({
#                 "type": "po", 
#                 "po_no": str(po_no), 
#                 "supplier": r.get('supplier_name', 'Unknown'), 
#                 "date": str(r.get('po_date') or r.get('date') or 'N/A'), 
#                 "total": float(tot or 0), 
#                 "balance": float(bal or 0), 
#                 "status": str(r.get('status', 'N/A')).capitalize()
#             })
#         elif query_type == "supplier":
#             final_output.append({
#                 "type": "result", "supplier": {"id": r.get('id', 0), "name": r.get('supplier_name', 'N/A'), "code": r.get('supplier_code', 'N/A'), "mobile": r.get('mobile', 'N/A'), "city": r.get('city', 'N/A'), "gstin": r.get('gstin', 'N/A')}
#             })
#     return final_output

##--------------------------------------------------------------------------------------------------------------------------------
                                                  #MULTI ENGINE  (ATHAK CODE TESTING)
##--------------------------------------------------------------------------------------------------------------------------------
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
- REQUIRED VS AVAILABLE STOCK ("required vs available", "shortage", "sabse badi shortage", "project ke liye kitna chahiye vs kitna hai"):
  Business logic (exact match with PHP requiredVsAvailable):
  - Active projects = status NOT IN ('completed','hold') AND is_deleted=0
  - Required = BOM (pp.quantity * pit.quantity) + Direct (pi.quantity) for active projects.
  - Transactions grouped by inventory:
    * t_in = In (excluding ref_type 'Finish')
    * t_out = Out (excluding ref_type 'Machining')
    * t_finish = In with ref_type 'Finish'
    * t_mc = Out with ref_type 'Machining'
  - Available (Total) = t_in - t_out
  - Difference (Short/Extra) = Available - Required
  ALWAYS use this exact SQL pattern:
  SELECT i.id, i.name, i.model, i.classification,
    COALESCE(bom.req,0)+COALESCE(direct.req,0) AS required_qty,
    COALESCE(t_in,0) - COALESCE(t_out,0) AS available_qty,
    CASE WHEN i.classification IN ('FINISH', '', 'null') OR i.classification IS NULL THEN 0 ELSE COALESCE(t_mc,0) - COALESCE(t_finish,0) END AS machining,
    CASE WHEN i.classification IN ('FINISH', '', 'null') OR i.classification IS NULL THEN COALESCE(t_in,0) - COALESCE(t_out,0) ELSE COALESCE(t_finish,0) - COALESCE(t_out,0) END AS finish,
    CASE WHEN i.classification IN ('FINISH', '', 'null') OR i.classification IS NULL THEN 0 ELSE COALESCE(t_in,0) - COALESCE(t_mc,0) END AS semi_finish,
    (COALESCE(t_in,0) - COALESCE(t_out,0)) - (COALESCE(bom.req,0)+COALESCE(direct.req,0)) AS short_extra
  FROM inventories i
  LEFT JOIN (SELECT pit.inventory_id, SUM(pp.quantity*pit.quantity) AS req FROM projects p JOIN project_products pp ON pp.project_id=p.id AND pp.is_deleted=0 JOIN product_items pit ON pit.product_id=pp.product_id AND pit.is_deleted=0 WHERE p.status NOT IN ('completed','hold') AND p.is_deleted=0 GROUP BY pit.inventory_id) bom ON bom.inventory_id=i.id
  LEFT JOIN (SELECT pi.inventory_id, SUM(pi.quantity) AS req FROM projects p JOIN project_item pi ON pi.project_id=p.id WHERE p.status NOT IN ('completed','hold') AND p.is_deleted=0 GROUP BY pi.inventory_id) direct ON direct.inventory_id=i.id
  LEFT JOIN (SELECT inventory_id, SUM(CASE WHEN txn_type='In' AND COALESCE(ref_type,'')!='Finish' THEN quantity ELSE 0 END) AS t_in, SUM(CASE WHEN txn_type='Out' AND COALESCE(ref_type,'')!='Machining' THEN quantity ELSE 0 END) AS t_out, SUM(CASE WHEN txn_type='In' AND ref_type='Finish' THEN quantity ELSE 0 END) AS t_finish, SUM(CASE WHEN txn_type='Out' AND ref_type='Machining' THEN quantity ELSE 0 END) AS t_mc FROM stock_transactions GROUP BY inventory_id) st ON st.inventory_id=i.id
  WHERE bom.req IS NOT NULL OR direct.req IS NOT NULLWHERE (COALESCE(bom.req,0)+COALESCE(direct.req,0)) > 0 OR (COALESCE(t_in,0) - COALESCE(t_out,0)) > 0  ORDER BY short_extra ASC
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


