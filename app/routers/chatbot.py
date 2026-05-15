# from asyncio import threads
# import time
# import datetime
# from fastapi import APIRouter, Depends, Query as _Query
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# import re
# import numpy as np
# import faiss
# from fastembed import TextEmbedding
# import difflib
# import json
# import os

# from app.db.database import get_db, SessionLocal
# from app.schemas.chat import ChatRequest
# from app.services.ollama_engine import ask_ollama
# from app.services.nl2sql_engine import get_db_schema, generate_sql, format_answer

# router = APIRouter(prefix="/chatbot", tags=["Chatbot Final"])

# # --- SECURITY FIREWALL FUNCTION ---
# def is_safe_sql(sql_query: str) -> bool:
#     if not sql_query: return False
#     q = sql_query.upper().strip()
#     if not (q.startswith("SELECT") or q.startswith("WITH")): return False
#     dangerous_words = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]
#     for word in dangerous_words:
#         if re.search(rf'\b{word}\b', q): return False 
#     return True

# # ── Role permissions ──────────────────────────────────────────────────────────
# ROLE_PERMISSIONS = {
#     "supervisor":     ["inventory", "project", "general_chat"],
#     "sales":          ["inventory", "general_chat"],
#     "purchase":       ["inventory", "supplier", "po", "general_chat"],
#     "purchase admin": ["inventory", "supplier", "po", "financials", "general_chat"],
#     "store admin":    ["inventory", "po", "project", "general_chat"],
#     "store department": ["inventory", "general_chat"],
#     "hod":            ["inventory", "project", "supplier", "po", "financials", "general_chat"],
#     "hr":             ["general_chat"],
# }

# # ── Off-topic guard (Junior's Logic) ──────────────────────────────────────────
# _ERP_KEYWORDS = {
#     "supplier", "vendor", "party", "sup",
#     "po", "order", "purchase", "transit", "delivery", "grn", "dispatch",
#     "stock", "maal", "item", "inventory", "qty", "quantity",
#     "project", "site", "crusher",
#     "balance", "payment", "invoice", "gst", "tax", "cgst", "sgst",
#     "rokra", "paisa", "kharcha", "hisab",
#     "mewar", "erp", "sale", "sales", "report", "employee", "account",
#     "slip", "request", "banao", "batao", "dikhao", "milao", "details",
#     "kitna", "kitne", "kahan", "kaisa", "kab", "lagao", "nikalo",
#     "total", "list", "count", "kitni", "sabhi", "saare",
#     "show", "find", "get", "check", "all", "mere", "mera",
# }

# _POOR_SIGNALS = [
#     "theek se samajh nahi", "maaf kijiye", "clear batao", "clearly batao",
#     "kripya", "naam batao", "couldn't understand", "i'm sorry",
#     "it seems you", "please provide", "thoda clear",
#     "nahi mila", "nahi mili", "nahi mile", "spelling check karoge",
#     "koi supplier nahi", "koi project nahi",
#     "ek sec", "check karta hoon", "dekh raha hoon", "dhundh raha hoon",
# ]

# _CLEARLY_OFFTOPIC = {
#     "poem", "poetry", "joke", "weather", "recipe", "cook", "song", "lyrics",
#     "translate", "movie", "cricket", "football", "game", "news", "capital of",
#     "who is the president", "write a story", "tell me a story",
# }

# def _is_off_topic(query: str) -> bool:
#     q = query.lower()
#     if len(q.split()) <= 3: return False
#     if any(kw in q for kw in _CLEARLY_OFFTOPIC): return True
#     return not any(kw in q for kw in _ERP_KEYWORDS)

# def _is_poor_result(response: dict) -> bool:
#     results = response.get("results", [])
#     data_types = {"result", "po", "dropdown", "project", "po_list", "po_summary", "project_list", "supplier_list", "rs_form"}
#     if any(r.get("type") in data_types for r in results): return False
#     chat_text = " ".join(r.get("message", "") for r in results if r.get("type") == "chat").lower()
#     return any(sig in chat_text for sig in _POOR_SIGNALS)


# # ==========================================
# # 🧠 FAISS SEMANTIC SEARCH ENGINE SETUP (From Your Old Code)
# # ==========================================
# semantic_model = None
# inv_names_list = []
# sup_names_list = []
# inv_faiss_index = None
# sup_faiss_index = None
# is_faiss_loaded = False
# proj_names_list = []
# proj_faiss_index = None
# is_loading_started = False  # 👈 Double-loading se bachane ke liye

# def load_faiss_once(db: Session):
#     global semantic_model, inv_names_list, sup_names_list, inv_faiss_index, sup_faiss_index, is_faiss_loaded, proj_names_list, proj_faiss_index, is_loading_started
    
#     # Agar pehle hi load ho chuka hai ya load ho raha hai, toh wapas mat chalao
#     if is_faiss_loaded or is_loading_started: 
#         return
        
#     is_loading_started = True # Flag ON
    
#     print("⏳ Loading Semantic Search Model... (10-15 seconds)")
#     semantic_model = TextEmbedding('BAAI/bge-small-en-v1.5', threads=1)
    
#     # 🔄 RETRY LOGIC: Aapka purana best logic
#     for attempt in range(3):
#         try:
#             print(f"🛠️ Building FAISS Memory (Attempt {attempt+1}/3)...")

#             # 1. Inventory Indexing (is_deleted = 0 add kiya for UI Sync)
#             inv_data = db.execute(text("SELECT name FROM inventories WHERE name IS NOT NULL AND is_deleted = 0")).fetchall()
#             inv_names_list = [row[0] for row in inv_data if row[0]]
#             if inv_names_list:
#                 inv_embeddings = np.array(list(semantic_model.embed(inv_names_list, batch_size=50))).astype('float32')
#                 inv_faiss_index = faiss.IndexFlatL2(inv_embeddings.shape[1])
#                 inv_faiss_index.add(inv_embeddings)

#             # 2. Supplier Indexing (is_deleted = 0 add kiya for UI Sync)
#             sup_data = db.execute(text("SELECT supplier_name FROM suppliers WHERE supplier_name IS NOT NULL")).fetchall()
#             sup_names_list = [row[0] for row in sup_data if row[0]]
#             if sup_names_list:
#                 sup_embeddings = np.array(list(semantic_model.embed(sup_names_list, batch_size=50))).astype('float32')
#                 sup_faiss_index = faiss.IndexFlatL2(sup_embeddings.shape[1])
#                 sup_faiss_index.add(sup_embeddings)

#             # 3. Project Indexing
#             proj_data = db.execute(text("SELECT name FROM projects WHERE name IS NOT NULL AND is_deleted = 0")).fetchall()
#             proj_names_list = [row[0] for row in proj_data if row[0]]
#             if proj_names_list:
#                 proj_embeddings = np.array(list(semantic_model.embed(proj_names_list, batch_size=50))).astype('float32')
#                 proj_faiss_index = faiss.IndexFlatL2(proj_embeddings.shape[1])
#                 proj_faiss_index.add(proj_embeddings)

#             # ✅ Agar yahan tak code pahunch gaya, toh success!
#             is_faiss_loaded = True
#             is_loading_started = False
#             print(f"✅ FAISS Ready! Indexed {len(inv_names_list)} Items, {len(sup_names_list)} Suppliers & {len(proj_names_list)} Projects.")
#             return # Loop se bahar nikal jao

#         except Exception as e:
#             print(f"⚠️ Attempt {attempt+1} failed: {e}")
#             try:
#                 db.rollback() 
#             except:
#                 pass
                
#             if attempt < 2:
#                 print("🔄 Database reset done. Retrying in 3 seconds...")
#                 time.sleep(3)
#             else:
#                 is_loading_started = False
#                 print("❌ All attempts failed. FAISS load error.")

# def smart_match(query_text, category="inventory"):
#     if not query_text or len(query_text) < 2 or not is_faiss_loaded: return query_text
#     try:
#         query_vector = np.array(list(semantic_model.embed([query_text]))).astype('float32') 
#         if category == "inventory" and inv_faiss_index:
#             distances, indices = inv_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 0.7:  
#                 return inv_names_list[indices[0][0]]
                
#         elif category == "supplier" and sup_faiss_index:
#             distances, indices = sup_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 0.7:
#                 return sup_names_list[indices[0][0]]

#         elif category == "project" and proj_faiss_index:
#             distances, indices = proj_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 1.0:
#                 return proj_names_list[indices[0][0]]
                
#     except Exception as e: 
#         pass
    
#     return query_text

# # ── Intent detection & Loggers ────────────────────────────────────────────────
# def advanced_intent_detector(query: str):
#     q = query.lower()
#     score = {"po_search": 0, "supplier_search": 0, "project_search": 0, "search": 0}
#     po_words = ["po", "order", "orders", "purchase", "transit", "raste", "pending", "dispatch", "delivery"]
#     sup_words = ["supplier", "vendor", "party", "contact", "mobile", "number", "account", "details", "profile"]
#     proj_words = ["project", "site", "crusher", "running", "urgent", "completed", "refurbish"]
#     inv_words = ["stock", "maal", "item", "inventory", "quantity", "kitna", "qty", "nag", "available"]
#     #rs_words = ["slip", "request slip", "rs", "banao", "issue", "banani"]

#     for w in po_words: score["po_search"] += 2 if w in q else 0
#     for w in sup_words: score["supplier_search"] += 2 if w in q else 0
#     for w in proj_words: score["project_search"] += 2 if w in q else 0
#     for w in inv_words: score["search"] += 2 if w in q else 0
#     #for w in rs_words: score["create_rs"] += 3 if w in q else 0
#     #if "slip" in q or "rs" in q: score["create_rs"] += 5
#     if any(w in q for w in ["stock", "maal", "kitna"]) and any(w in q for w in ["supplier", "party"]): score["search"] += 3 
#     best_intent = max(score, key=score.get)
#     return best_intent if score[best_intent] > 0 else "search"

# def log_query_pro(user_role, query, intents, final_results, process_time):
#     bot_reply = "No Response"
#     if isinstance(final_results, dict) and "results" in final_results:
#         for res in final_results["results"]:
#             if res.get("type") == "chat":
#                 bot_reply = res.get("message", "")
#                 break 
#     is_fail = any(w in str(bot_reply).lower() for w in ["nahi mila", "error", "samajh nahi", "maaf kijiye", "kripya", "permission nahi"])
#     log_entry = {
#         "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "role": user_role, "user_query": query, "intent": str(intents),
#         "bot_response": final_results["results"], "time_taken_sec": round(process_time, 2),
#         "status": "Fail ❌" if is_fail else "Success ✅"
#     }
#     try:
#         with open("chat_history.json", "a", encoding="utf-8") as f:
#             f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
#     except Exception as e: print(f"❌ File Log Error: {e}")

# # ══════════════════════════════════════════════════════════════════════════════
# # MAIN UNIFIED ENDPOINT
# # ══════════════════════════════════════════════════════════════════════════════
# @router.post("/")
# def chatbot(request: ChatRequest, db: Session = Depends(get_db)):
#     start_time = time.time()
#     load_faiss_once(db)
#     raw_q = request.query.strip()
#     low_q = raw_q.lower()
#     chat_history = getattr(request, "history", []) 
#     user_role = getattr(request, "role", "guest").lower().strip()

#     # ── Off-topic guard (Junior Logic) ──
#     _has_history = bool(chat_history)
#     if _is_off_topic(raw_q) and not _has_history:
#         return {"results": [{"type": "chat", "message": "Bhai, main sirf Mewar ERP ke sawaalon mein help kar sakta hoon — Suppliers, Purchase Orders, Inventory, aur Projects. In topics par kuch poochho! 😊"}]}

#     # ── 1. Fast-track ID ──
#     if low_q.isdigit() and len(low_q) < 8:
#         allowed_perms = ROLE_PERMISSIONS.get(user_role, [])
#         if user_role in ["superadmin", "super admin"] or "inventory" in allowed_perms:
#             try:
#                 inv = db.execute(text("SELECT id, name, classification, placement FROM inventories WHERE id = :id"), {"id": int(low_q)}).fetchone()
#                 if inv:
#                     stock_res = db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id = :id"), {"id": inv.id}).scalar()
#                     total_qty = float(stock_res or 0)
#                     cls = str(inv.classification).lower() if inv.classification else ""
#                     m, f, sf = (total_qty, 0, 0) if "machining" in cls else (0, 0, total_qty) if "semi" in cls else (0, total_qty, 0)
#                     return {"results": [{"type": "result", "inventory": {"id": inv.id, "name": inv.name, "category": cls.upper(), "placement": inv.placement or "N/A"}, "total_stock": total_qty, "finish_stock": f, "semi_finish_stock": sf, "machining_stock": m}]}
#             except: pass
#         else:
#             return {"results": [{"type": "chat", "message": f"Aapka role '{user_role.title()}' hai. Aapko Item Codes (Inventory) se search karne ki permission nahi hai. 🛑"}]}

#     # ── 2. AI Engine ──
#     try:
#         try: ai_data = ask_ollama(raw_q, chat_history)
#         except:
#             time.sleep(1)
#             ai_data = ask_ollama(raw_q, chat_history)
#     except Exception as e:
#         print(f"❌ AI CRASHED: {str(e)}")
#         # Auto-fallback to NL2SQL if intent engine completely dies
#         nl2_r = _nl2sql_response(raw_q, db, history=chat_history)
#         return nl2_r if nl2_r else {"results": [{"type": "chat", "message": "Bhai, mera AI brain abhi connect nahi ho pa raha. 🙏"}]}

#     intents = ai_data.get("intents") or []
#     if "intent" in ai_data and not intents: intents = [ai_data["intent"]]
#     if isinstance(intents, str): intents = [intents]
#     if not intents: intents = ["search"]

#     # ── Master Overrides (Shortage, RS, Tax) ──
#     shortage_words = ["short", "kam", "extra", "surplus", "required", "kami"]
#     if any(w in low_q.split() for w in shortage_words): intents = ["shortage_search"]
#     if "sql_analysis" not in intents:
#         if any(w in low_q for w in ["tax", "gst", "cgst", "sgst", "advance", "adv"]): intents = ["po_search"]

#     original_target = str(ai_data.get("search_target") or "").strip()
#     reasoning = ai_data.get("reasoning") or "hmm ek sec... main check karta hoon 👍"
#     final_results = [{"type": "chat", "message": reasoning}]

#     noise_words = ["supplier", "vendor", "party", "details", "contact", "profile", "ki", "ka", "ke", "project", "site", "machine"]
#     for word in noise_words: original_target = re.sub(rf'\b{word}\b', '', original_target, flags=re.IGNORECASE).strip()
#     ai_data["search_target"] = original_target
#     if re.match(r'^sup[-\s]?\d+$', original_target.lower()):
#         if "supplier_search" not in intents: intents = ["supplier_search"]

#     filters = ai_data.get("filters", {})
#     ui_filters = getattr(request, "ui_filters", {}) or {}
#     for key, value in ui_filters.items():
#         if value: filters[key] = value
#     limit = filters.get("limit", 5) or 5

#     # ── Smart Seatbelt ──
#     is_project_list_req = any(w in low_q for w in [
#         "all", "saare", "sabhi", "list", "latest", "naya", "new", "running", "chalu", "progress", "completed", "khatam", "done", 
#         "hold", "ruka", "pending", "refurbished", "purana", "repair", "urgent", "normal", "high", "priority", "remaining", "baki", "bache", 
#         "sabse", "bada", "highest", "lowest", "chhota", "late", "overdue", "dikhao", "batao"
#     ])
#     if filters.get("status") or filters.get("priority"): is_project_list_req = True

#     if not original_target:
#         if "supplier_search" in intents and not any(w in low_q for w in ["all", "saare", "list"]):
#             nl2_r = _nl2sql_response(raw_q, db, history=chat_history)
#             return nl2_r if nl2_r else {"results": [{"type": "chat", "message": "Bhai, kripya thoda clear batao ki aap kis company ki baat kar rahe ho? 🙂"}]}
#         elif "project_search" in intents and not is_project_list_req:
#             nl2_r = _nl2sql_response(raw_q, db, history=chat_history)
#             return nl2_r if nl2_r else {"results": [{"type": "chat", "message": "Bhai, kripya project ka naam batao, ya fir 'chalu projects' likho. 🙂"}]}

#     # ── Role Checks ──
#     if user_role not in ["superadmin", "super admin"]:
#         allowed_perms = ROLE_PERMISSIONS.get(user_role, [])
#         for intent in intents:
#             if intent == "po_search" and "po" not in allowed_perms: return {"results": [{"type": "chat", "message": f"Permission nahi hai. 🛑"}]}
#             elif intent == "supplier_search" and "supplier" not in allowed_perms: return {"results": [{"type": "chat", "message": f"Permission nahi hai. 🛑"}]}
#             elif intent == "project_search" and "project" not in allowed_perms: return {"results": [{"type": "chat", "message": f"Permission nahi hai. 🛑"}]}
#             elif intent in ["search", "inventory_search"] and "inventory" not in allowed_perms: return {"results": [{"type": "chat", "message": f"Permission nahi hai. 🛑"}]}

#     smart_keywords = ["all", "saare", "sabhi", "pure", "list", "batao", "dikhao", "kitne", "kitna", "running", "chalu", "progress", "chal", "completed", "poora", "khatam", "done", "hold", "ruka", "pending", "remaining", "baki", "bache", "new", "naya", "budget", "paisa", "rupay", "cost", "amount", "mehenga", "deadline", "target", "kab tak", "time", "din", "stage", "percent", "status", "sabse", "bada", "highest", "biggest", "lowest", "chhota", "kam", "late", "overdue", "delay"]
#     fixed_words = []
#     for word in low_q.split():
#         matches = difflib.get_close_matches(word, smart_keywords, n=1, cutoff=0.8)
#         fixed_words.append(matches[0] if matches else word)
#     low_q = " ".join(fixed_words)

#     # ══════════════════════════════════════════════════════════════════════════
#     # INTENT PROCESSING LOOP (POWERFUL LOGIC PRESERVED)
#     # ══════════════════════════════════════════════════════════════════════════
#     for intent in intents:
        
#         # 📁 BRANCH 1: PROJECT LOGIC 
#         if intent == "project_search":
#             try:
#                 target = original_target.strip()
#                 target_lower = target.lower()
#                 projs = []
                
#                 if any(w in low_q for w in ["all", "saare", "sabhi", "pure", "list", "batao", "kitne", "kitna", "dikhao"]): limit = 50
#                 if any(w in low_q for w in ["last", "latest", "naya", "new"]): limit = 1
                    
#                 if any(w in low_q for w in ["sabse bada project", "highest budget", "sabse mehenga", "biggest project", "sabse bada"]):
#                     big_proj = db.execute(text("SELECT * FROM projects WHERE is_deleted = 0 ORDER BY budget DESC LIMIT 1")).fetchone()
#                     if big_proj:
#                         final_results.append({"type": "chat", "message": f"🏆 **Highest Budget Project:** System ke hisaab se sabse bada project **{big_proj.name}** hai."})
#                         projs = [big_proj]; target = "SKIP_SEARCH" 
                
#                 if target != "SKIP_SEARCH":
#                     is_refurbished = is_time_remaining = is_overdue = False
#                     raw_status = str(filters.get("status") or "").lower().strip()
#                     active_priority = str(filters.get("priority") or "").lower().strip()

#                     status_mapping = {"in progress": "in_progress", "in_progress": "in_progress", "on_hold": "hold", "pending": "hold", "completed": "completed", "new_project": "new", "new": "new", "refurbished": "refurbished", "remaining": "remaining", "overdue": "overdue"}
#                     active_status = status_mapping.get(raw_status, raw_status)

#                     if active_status == "refurbished": is_refurbished = True; active_status = "" 
#                     elif active_status == "remaining": is_time_remaining = True; active_status = ""
#                     elif active_status == "overdue": is_overdue = True; active_status = ""

#                     if any(w in low_q for w in ["running", "chalu", "progress", "chal"]): active_status = "in_progress"
#                     elif any(w in low_q for w in ["completed", "poora", "khatam", "done"]): active_status = "completed"
#                     elif any(w in low_q for w in ["hold", "ruka", "pending"]): active_status = "hold"
#                     elif any(w in low_q for w in ["new", "naya"]): active_status = "new"
#                     if any(w in low_q for w in ["refurbished", "purana", "repair"]): is_refurbished = True

#                     if not is_time_remaining and any(w in low_q for w in ["remaining", "baki", "bache"]):
#                         is_time_remaining = True; active_status = ""; limit = 50
#                     elif not is_overdue and any(w in low_q for w in ["late", "overdue", "delay"]):
#                         is_overdue = True; active_status = ""; limit = 50

#                     ignore_words = ["all", "list", "projects", "latest", "project", "site", "refurbished", "purana", "repair", "running", "chalu", "progress", "completed", "poora", "khatam", "hold", "ruka", "new", "naya", "urgent", "emergency", "high", "normal", "priority", "batao", "dikhao", "kitne", "kitna", "remaining", "baki", "bache", "late", "overdue", "delay"]
#                     if "refurb" in target_lower or "purana" in target_lower: target = ""; limit = 50; is_refurbished = True 
#                     if target_lower in ignore_words: target = ""; limit = 50

#                     query = "SELECT * FROM projects WHERE is_deleted = 0"
#                     params = {}

#                     if active_status and active_status != "all" and active_status != "refurbished": query += " AND LOWER(status) = :st"; params["st"] = active_status
#                     if active_priority and active_priority != "all": query += " AND LOWER(priority) = :pr"; params["pr"] = active_priority
#                     if is_refurbished: query += " AND refurbish = 1"
#                     if filters.get("from_date") and filters.get("to_date"): query += " AND start_date BETWEEN :sd AND :ed"; params["sd"] = filters["from_date"]; params["ed"] = filters["to_date"]

#                     if is_time_remaining or is_overdue:
#                         today_str = datetime.date.today().strftime('%Y-%m-%d')
#                         if is_time_remaining: query += " AND (end_date >= :today OR deadline >= :today)"; params["today"] = today_str
#                         elif is_overdue: query += " AND (end_date < :today OR deadline < :today) AND LOWER(status) != 'completed'"; params["today"] = today_str

#                     base_filter_query = query
#                     if target:
#                         words = target_lower.split()
#                         target_conds = " AND ".join([f"(LOWER(name) LIKE :t{i} OR LOWER(comment) LIKE :t{i})" for i in range(len(words))])
#                         query += f" AND ({target_conds})"
#                         for i, w in enumerate(words): params[f"t{i}"] = f"%{w}%"

#                     projs = db.execute(text(query + f" ORDER BY id DESC LIMIT :limit"), {**params, "limit": limit}).fetchall()
#                     if not projs and target and len(target) > 3:
#                         corrected_name = smart_match(target, category="project")
#                         if corrected_name and corrected_name.lower() != target_lower:
#                             fallback_query = base_filter_query + " AND LOWER(name) LIKE :cn"
#                             params["cn"] = f"%{corrected_name.lower()}%"
#                             projs = db.execute(text(fallback_query + f" ORDER BY id DESC LIMIT :limit"), {**params, "limit": limit}).fetchall()

#                 if not projs:
#                     status_text = f" '{active_status}' " if active_status else " "
#                     final_results.append({"type": "chat", "message": f"Bhai, lagta hai{status_text}wala koi project abhi nahi mil raha. 🧐"})
#                 elif len(projs) == 1:
#                     p = projs[0]
#                     p_name = str(p.name)
#                     machine_type = "Refurbished (Purani/Repair) 🛠️" if getattr(p, 'refurbish', 0) == 1 else "New Machine 🆕"
#                     remaining_str = ""
#                     target_date = p.end_date or p.deadline
#                     if target_date:
#                         try:
#                             t_date = datetime.datetime.strptime(str(target_date), '%Y-%m-%d').date() if isinstance(target_date, str) else target_date
#                             days_left = (t_date - datetime.date.today()).days
#                             if days_left > 0: remaining_str = f" ⏳ (Abhi **{days_left} din** bache hain)"
#                             elif days_left == 0: remaining_str = f" 🚨 (Deadline **AAJ** hai!)"
#                             else: remaining_str = f" ⚠️ (Deadline **{abs(days_left)} din** pehle nikal chuki hai!)"
#                         except: pass
                    
#                     detail_msg = None
#                     show_full_card = False
#                     if any(w in low_q.split() for w in ["sab", "sabhi", "puri", "poori", "detail", "details", "all", "pura", "han", "haan", "yes"]): show_full_card = True
#                     elif any(w in low_q for w in ["budget", "paisa", "rupay", "cost", "amount", "mehenga"]): detail_msg = f"💰 **{p_name}** ka total budget **₹{float(p.budget or 0):,.2f}** set kiya gaya hai."
#                     elif any(w in low_q for w in ["deadline", "khatam", "date", "target", "kab tak", "time", "bache", "din"]): detail_msg = f"📅 **{p_name}** ki target deadline **{str(target_date or 'N/A')}** hai.{remaining_str}"
#                     elif any(w in low_q for w in ["stage", "progress", "kaha pahuncha", "percent", "status"]):
#                         status_now = str(p.status).lower()
#                         auto_stage = "100%" if status_now == "completed" else "50%" if status_now == "in_progress" else "0%"
#                         actual_stage = getattr(p, 'stage', auto_stage)
#                         detail_msg = f"🏗️ **{p_name}** abhi **'{str(p.status).replace('_', ' ').capitalize()}'** status par hai aur lagbhag **{actual_stage}** complete ho chuka hai."
#                     elif any(w in low_q for w in ["type", "machine", "refurbished", "purana", "naya", "new"]): detail_msg = f"⚙️ Ye ek **{machine_type}** wala project hai."

#                     if show_full_card:
#                         type_tag = "Refurbished" if getattr(p, 'refurbish', 0) == 1 else "New Machine"
#                         status_now = str(p.status).lower()
#                         auto_stage = "100%" if status_now == "completed" else "50%" if status_now == "in_progress" else "Hold" if status_now == "hold" else "0%"
#                         card_data = {
#                             "type": "project", "project_name": str(p.name),
#                             "category": f"{type_tag} | {str(p.status).replace('_', ' ').capitalize()}", "amount": float(p.budget or 0),
#                             "start_date": str(p.start_date) if p.start_date else "N/A", "end_date": str(p.end_date or p.deadline or "N/A"),
#                             "comments": str(p.comment or ""), "stage": getattr(p, 'stage', auto_stage), "priority": str(p.priority).upper()
#                         }
#                         final_results.append({"type": "chat", "message": f"Lijiye bhai, **{p_name}** ki poori details 📋:"})
#                         final_results.append(card_data)
#                     elif detail_msg:
#                         final_results.append({"type": "chat", "message": detail_msg + "\n\n💡 *Kya aap is project ki baaki details dekhna chahte hain? (Type: Sab)*"})
#                     else:
#                         msg = f"Bhai, mujhe **{p_name}** system mein mil gaya hai. Ye ek **{machine_type}** project hai.\nAap iska kya dekhna chahte hain?\n\n💰 Type **'Budget'**\n📅 Type **'Deadline'**\n🏗️ Type **'Stage'**\n📋 Type **'Sab'**"
#                         final_results.append({"type": "chat", "message": msg})
                        
#                     # 🚀 AI SUMMARY 
#                     try:
#                         cols = list(projs[0].keys()) if hasattr(projs[0], 'keys') else ["ID", "Name", "Status", "Budget"]
#                         row_data = [list(r) for r in projs]
#                         ai_sum = format_answer(raw_q, row_data, cols, history=chat_history)
#                         final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                     except: pass
#                 else:
#                     final_results.append({"type": "chat", "message": f"haan mil gaya 👍 Mujhe **{len(projs)} projects** mile hain:"})
                    
#                     # Cards generate karne ka logic
#                     proj_results = []
#                     for p in projs:
#                         type_tag = "Refurbished" if getattr(p, 'refurbish', 0) == 1 else "New Machine"
#                         status_now = str(p.status).lower()
#                         auto_stage = "100%" if status_now == "completed" else "50%" if status_now == "in_progress" else "Hold" if status_now == "hold" else "0%"
                        
#                         proj_results.append({
#                             "type": "project", "project_name": str(p.name),
#                             "category": f"{type_tag} | {str(p.status).replace('_', ' ').capitalize()}", "amount": float(p.budget or 0),
#                             "start_date": str(p.start_date) if p.start_date else "N/A", "end_date": str(p.end_date or p.deadline or "N/A"),
#                             "comments": str(p.comment or ""), "stage": getattr(p, 'stage', auto_stage), "priority": str(p.priority).upper()
#                         })
#                     final_results.extend(proj_results)

#                     # 🚀 NAYA FIX: AI INSIGHT KO "HINT" DENA
#                     try:
#                         cols = list(projs[0].keys()) if hasattr(projs[0], 'keys') else ["ID", "Name", "Status", "Budget"]
#                         row_data = [list(r) for r in projs]
                        
#                         # AI ko count aur detail dono ka instruction (Prompt) do
#                         detail_instruction = (
#                             f" [SYSTEM HINT: The database returned exactly {len(projs)} projects. "
#                             f"You MUST state this exact count. Do not just give a 1-line answer. "
#                             f"Provide a DETAILED summary: mention their names, current status, and give a brief overview. "
#                             f"Write 2-3 informative and helpful lines in casual Hinglish.]"
#                         )
#                         enhanced_q = raw_q + detail_instruction
                        
#                         ai_sum = format_answer(enhanced_q, row_data, cols, history=chat_history)
#                         final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                     except: pass
#             except Exception as e: final_results.append({"type": "chat", "message": f"Project Error: {str(e)}"})
            
#         # 🏭 BRANCH 2: SUPPLIER LOGIC 
#         elif intent == "supplier_search":
#             try:
#                 target_lower = original_target.lower()
#                 is_all_request = not original_target and any(w in low_q for w in ["all", "saare", "sabhi", "list"])
#                 sups = []

#                 if is_all_request:
#                     sups = db.execute(text("SELECT * FROM suppliers ORDER BY id DESC LIMIT :l"), {"l": limit}).fetchall()
#                 else:
#                     if re.match(r'^sup[-\s]?\d+$', target_lower):
#                         code_search = re.sub(r'^sup[-\s]?', '', target_lower)
#                         sups = db.execute(text("SELECT * FROM suppliers WHERE supplier_code = :c OR id = :c LIMIT 1"), {"c": code_search}).fetchall()
#                     if not sups and original_target:
#                         sups = db.execute(text("SELECT * FROM suppliers WHERE LOWER(supplier_name) = :q LIMIT 1"), {"q": target_lower}).fetchall()
#                     if not sups and original_target:
#                         words = target_lower.split()
#                         if words:
#                             like_conds = " AND ".join([f"(LOWER(supplier_name) LIKE :w{i} OR mobile LIKE :w{i})" for i in range(len(words))])
#                             params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
#                             params["l"] = limit
#                             sups = db.execute(text(f"SELECT * FROM suppliers WHERE {like_conds} LIMIT :l"), params).fetchall()
#                     if not sups and len(original_target) > 2: 
#                         corrected = smart_match(original_target, category="supplier")
#                         if corrected and corrected != original_target:
#                             sups = db.execute(text("SELECT * FROM suppliers WHERE LOWER(supplier_name) = :q LIMIT 1"), {"q": corrected.lower()}).fetchall()

#                 if not sups: 
#                     if original_target: final_results.append({"type": "chat", "message": f"Bhai, '{original_target}' naam ka koi Supplier nahi mila mujhe. 🧐"})
#                 elif len(sups) > 1: 
#                     final_results.append({"type": "chat", "message": f"haan mil gaya 👍 Mujhe {len(sups)} suppliers mile hain:"})
#                     final_results.append({"type": "dropdown", "message": "Select a supplier for details:", "items": [{"id": str(getattr(s, 'supplier_name', 'Unknown')), "name": str(getattr(s, 'supplier_name', 'Unknown'))} for s in sups]})
#                 else:
#                     s = sups[0]
#                     sup_name = str(getattr(s, 'supplier_name', 'Unknown'))
#                     detail_msg = None
#                     if any(w in low_q for w in ["mobile", "phone", "number", "call", "contact"]): detail_msg = f"📞 **{sup_name}** ka contact number **{str(getattr(s, 'mobile', 'N/A') or 'N/A')}** hai."
#                     elif any(w in low_q for w in ["email", "mail", "id"]): detail_msg = f"📧 **{sup_name}** ki email ID **{str(getattr(s, 'email', 'N/A') or 'N/A')}** hai."
#                     elif any(w in low_q for w in ["gst", "gstin", "tax"]): detail_msg = f"🏢 **{sup_name}** ka GST number **{str(getattr(s, 'gstin', 'N/A') or 'N/A')}** hai."
#                     elif any(w in low_q for w in ["city", "address", "kaha", "location"]): detail_msg = f"📍 **{sup_name}** **{str(getattr(s, 'city', 'N/A') or 'N/A')}** mein based hain."

#                     if detail_msg:
#                         final_results.append({"type": "chat", "message": detail_msg + "\n\n💡 *Kya main inki poori profile ya orders load karun?*"})
#                     else:
#                         is_asking_details = any(w in low_q for w in ["detail", "details", "contact", "number", "profile", "hisab", "account", "info"])
#                         if not is_asking_details and not is_all_request and "sup-" not in target_lower and not any(w in low_q for w in ["po", "order", "bill"]):
#                             msg = f"Bhai, mujhe **{sup_name}** system mein mil gaye hain. Aap inka kya dekhna chahte hain?\n\n📦 Type **'Orders'**\n👤 Type **'Details'**"
#                             final_results.append({"type": "chat", "message": msg})
#                             continue
                                        
#                         if "po_search" not in intents: final_results.append({"type": "chat", "message": f"haan ye raha 👍 **{sup_name}** ka profile mil gaya hai:"})
#                         inv_items = db.execute(text("SELECT i.name, SUM(CASE WHEN LOWER(t.txn_type) = 'in' THEN t.quantity ELSE -t.quantity END) as stock FROM inventories i JOIN stock_transactions t ON i.id = t.inventory_id WHERE t.supplier_id = :sid GROUP BY i.id, i.name HAVING stock != 0"), {"sid": s.id}).fetchall()
#                         final_results.append({
#                             "type": "result", 
#                             "supplier": {
#                                 "id": s.id, "name": sup_name, "code": str(getattr(s, 'supplier_code', 'N/A') or 'N/A'), 
#                                 "mobile": str(getattr(s, 'mobile', 'N/A') or 'N/A'), "city": str(getattr(s, 'city', 'N/A') or 'N/A'), 
#                                 "email": str(getattr(s, 'email', 'N/A') or 'N/A'), "gstin": str(getattr(s, 'gstin', 'N/A') or 'N/A')
#                             }, 
#                             "items": [{"name": str(row.name), "stock": float(row.stock)} for row in inv_items]
#                         })
#                         try:
#                             if inv_items:
#                                 cols = ["Item Name", "Stock Available"]
#                                 row_data = [[row.name, row.stock] for row in inv_items]
#                                 ai_sum = format_answer(raw_q, row_data, cols, history=chat_history)
#                                 final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                         except: pass
#             except Exception as e: final_results.append({"type": "chat", "message": f"Supplier search error: {str(e)}"})

#         # 🧾 BRANCH 3: PURCHASE ORDERS (BOSS MODES)
#         elif intent == "po_search":
#             try:
#                 if any(w in low_q for w in ["sabse jada balance", "highest balance", "paisa baaki", "sabse jyada balance", "maximum balance"]):
#                     bal_res = db.execute(text("SELECT s.supplier_name, SUM(p.balance_amount) as total_bal, COUNT(p.id) as pending_orders, s.mobile FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE p.balance_amount > 0 AND LOWER(p.status) != 'completed' GROUP BY s.id, s.supplier_name ORDER BY total_bal DESC LIMIT 1")).fetchone()
#                     if bal_res:
#                         final_results.append({"type": "chat", "message": f"💸 **Payment Alert:** Sabse zyada pending balance **{bal_res.supplier_name}** ka hai.\n\n💰 Total Pending: **₹{float(bal_res.total_bal):,.2f}**\n📄 Orders: **{bal_res.pending_orders} pending**\n📞 Contact: {bal_res.mobile}"})
#                         continue
#                 if any(w in low_q for w in ["sab se kam balance", "sabse kam balance", "lowest balance", "minimum balance"]):
#                     bal_res = db.execute(text("SELECT s.supplier_name, SUM(p.balance_amount) as total_bal, COUNT(p.id) as pending_orders, s.mobile FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE p.balance_amount > 0 AND LOWER(p.status) != 'completed' GROUP BY s.id, s.supplier_name ORDER BY total_bal ASC LIMIT 1")).fetchone()
#                     if bal_res:
#                         final_results.append({"type": "chat", "message": f"💸 **Payment Alert:** Sabse kam pending balance **{bal_res.supplier_name}** ka hai.\n\n💰 Total Pending: **₹{float(bal_res.total_bal):,.2f}**\n📄 Orders: **{bal_res.pending_orders} pending**\n📞 Contact: {bal_res.mobile}"})
#                         continue
#                 if any(w in low_q for w in ["highest po", "sabse bada po", "biggest order", "sabse bada order"]):
#                     big_po = db.execute(text("SELECT p.*, s.supplier_name FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id ORDER BY p.total_amount DESC LIMIT 1")).fetchone()
#                     if big_po:
#                         final_results.append({"type": "chat", "message": f"🏆 **Highest Order:** Poore system mein sabse bada Purchase Order **{big_po.supplier_name}** ka hai."})
#                         final_results.append({"type": "po", "po_no": str(big_po.po_number), "supplier": str(big_po.supplier_name), "date": str(big_po.po_date), "total": float(big_po.total_amount or 0), "advance": float(big_po.advance_amount or 0), "balance": float(big_po.balance_amount or 0), "status": str(big_po.status).capitalize()})
#                         continue
#                 if any(w in low_q for w in ["lowest po", "sabse chota po", "sabse kam po", "smallest order"]):
#                     small_po = db.execute(text("SELECT p.*, s.supplier_name FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id ORDER BY p.total_amount ASC LIMIT 1")).fetchone()
#                     if small_po:
#                         final_results.append({"type": "chat", "message": f"📉 **Lowest Order:** Poore system mein sabse chhota Purchase Order **{small_po.supplier_name}** ka hai."})
#                         final_results.append({"type": "po", "po_no": str(small_po.po_number), "supplier": str(small_po.supplier_name), "date": str(small_po.po_date), "total": float(small_po.total_amount or 0), "advance": float(small_po.advance_amount or 0), "balance": float(small_po.balance_amount or 0), "status": str(small_po.status).capitalize()})
#                         continue
#                 if any(w in low_q for w in ["tax", "gst", "cgst", "sgst"]):
#                     tax_query = "SELECT SUM(tax_amount) as total_tax, COUNT(id) as po_count FROM purchase_orders p WHERE 1=1"
#                     tax_params = {}
#                     if filters.get("from_date") and filters.get("to_date"):
#                         tax_query += " AND p.po_date BETWEEN :start AND :end"; tax_params["start"] = filters['from_date']; tax_params["end"] = filters['to_date']
#                     if original_target:
#                         tax_query = "SELECT SUM(p.tax_amount) as total_tax, COUNT(p.id) as po_count FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE 1=1"
#                         words = [w for w in original_target.split() if len(w) > 1]
#                         if words:
#                             search_conds = " AND ".join([f"LOWER(s.supplier_name) LIKE :s{i}" for i in range(len(words))])
#                             tax_query += f" AND ({search_conds})"
#                             for i, w in enumerate(words): tax_params[f"s{i}"] = f"%{w}%"
#                     tax_res = db.execute(text(tax_query), tax_params).fetchone()
#                     if tax_res and tax_res.total_tax:
#                         party_name = f"**{original_target.title()}** ke " if original_target else "In "
#                         final_results.append({"type": "chat", "message": f"🧾 **Tax (GST) Report:**\n\n{party_name}**{tax_res.po_count} orders** par total **₹{float(tax_res.total_tax):,.2f}** ka Tax/GST bana hai."})
#                         continue
#                     else:
#                         final_results.append({"type": "chat", "message": "Bhai, in filters par mujhe koi tax ya GST ka data nahi mila. 🧐"}); continue

#                 valid_statuses = ["draft", "completed", "pending", "in progress", "cancelled", "approved"]
#                 active_status = str(filters.get("status") or "").lower().strip()
#                 if active_status not in valid_statuses: active_status = "" 
#                 if any(w in low_q for w in ["pending", "draft", "kacha"]): active_status = "draft"
#                 if any(w in low_q for w in ["all", "saare", "sabhi", "pure", "poore", "sab", "pending", "draft", "batao"]): limit = 50
#                 if any(w in low_q for w in ["last", "latest", "nayan"]): limit = 1
                
#                 query = "SELECT p.*, s.supplier_name FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE 1=1"
#                 params = {"l": limit}
#                 if active_status: query += " AND LOWER(p.status) = :pst"; params["pst"] = active_status
#                 if original_target:
#                     words = [w for w in original_target.split() if len(w) > 1]
#                     if words:
#                         search_conds = " AND ".join([f"(LOWER(s.supplier_name) LIKE :s{i} OR LOWER(p.po_number) LIKE :s{i})" for i in range(len(words))])
#                         query += f" AND ({search_conds})"
#                         for i, w in enumerate(words): params[f"s{i}"] = f"%{w}%"
                
#                 pos = db.execute(text(query + " ORDER BY p.po_date DESC, p.id DESC LIMIT :l"), params).fetchall()
#                 if not pos: final_results.append({"type": "chat", "message": "Bhai, in filters par mujhe koi orders nahi mile. 🧐"})
#                 else:
#                     total_pend = sum(float(po.balance_amount or 0) for po in pos if str(po.status).lower() != 'completed')
#                     msg = f"📄 Mujhe कुल **{len(pos)} orders** mile hain."
#                     if total_pend > 0: msg += f" Inka total pending balance **₹{total_pend:,.2f}** hai."
#                     final_results.append({"type": "chat", "message": msg})
#                     for po in pos:
#                         final_results.append({"type": "po", "id": po.id, "po_no": str(po.po_number), "supplier": str(po.supplier_name), "date": str(po.po_date), "total": float(po.total_amount or 0), "advance": float(po.advance_amount or 0), "balance": float(po.balance_amount or 0), "status": str(po.status).capitalize(), "view_link": f"/purchase-order/{po.id}/show"})
#                     try:
#                         if pos:
#                             cols = list(pos[0].keys()) if hasattr(pos[0], 'keys') else ["ID", "PO Number", "Total", "Balance", "Status"]
#                             row_data = [list(r) for r in pos]
#                             ai_sum = format_answer(raw_q, row_data, cols, history=chat_history)
#                             final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                     except: pass
#             except Exception as e: final_results.append({"type": "chat", "message": f"PO Error: {str(e)}"})

#         # 📦 BRANCH 4: INVENTORY SEARCH
#         elif intent == "search":
#             try:
#                 raw_target = str(ai_data.get("search_target") or "").lower().strip()
#                 if not raw_target: raw_target = low_q
#                 clean_target = re.sub(r'[?\'"!.,]', '', raw_target).strip()
#                 clean_targets = []
#                 if len(clean_target) > 1: clean_targets.append(smart_match(clean_target, category="inventory"))
#                 if not clean_targets and ("bearing" in low_q or "belt" in low_q): clean_targets = ["bearing" if "bearing" in low_q else "belt"]

#                 all_inv_names = [row.name.lower() for row in db.execute(text("SELECT name FROM inventories")).fetchall() if row.name]
#                 found_any = False

#                 for t in clean_targets:
#                     query_str = "SELECT id, name, model, type, classification, placement FROM inventories WHERE (LOWER(name) LIKE :q OR LOWER(model) LIKE :q)"
#                     items = db.execute(text(query_str + " LIMIT 30"), {"q": f"%{t}%"}).fetchall()
#                     if not items:
#                         closest = difflib.get_close_matches(t, all_inv_names, n=1, cutoff=0.65)
#                         if closest: items = db.execute(text(query_str + " LIMIT 30"), {"q": f"%{closest[0]}%"}).fetchall(); t = closest[0]
#                     if not items: continue
#                     found_any = True

#                     ids = tuple([i.id for i in items])
#                     if len(items) > 1:
#                         total_sum = db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id IN :ids"), {"ids": ids}).scalar() or 0
#                         final_results.append({"type": "chat", "message": f"haan mil gaya 👍 **Total {t.title()} Stock:** {total_sum:.2f} units available hain."})
#                         final_results.append({"type": "dropdown", "message": f"Mujhe {len(items)} items mile hain. Kiski details dekhni hai?", "items": [{"id": i.id, "name": f"{i.name} {i.model or ''}"} for i in items]})
#                     elif len(items) == 1:
#                         i = items[0]
#                         stock = float(db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id = :id"), {"id": i.id}).scalar() or 0)
#                         disp_cat = i.type if i.type else "Raw Material"
#                         disp_loc = i.placement if i.placement else "Main Store"
#                         disp_class = str(i.classification).upper() if i.classification else "FINISH"
#                         f, sf, m = (stock, 0, 0) if disp_class == "FINISH" else (0, stock, 0) if "SEMI" in disp_class else (0, 0, stock)
#                         final_results.append({"type": "chat", "message": f"haan ye raha 👍 **{i.name}** ka data mil gaya:"})
#                         final_results.append({"type": "result", "inventory": {"id": i.id, "name": f"{i.name} {i.model or ''}", "category": disp_cat, "placement": disp_loc}, "total_stock": stock, "finish_stock": f, "semi_finish_stock": sf, "machining_stock": m})
#                         try:
#                             cols = ["Inventory Name", "Category", "Placement", "Total Stock"]
#                             row_data = [[f"{i.name} {i.model or ''}", disp_cat, disp_loc, stock]]
#                             ai_sum = format_answer(raw_q, row_data, cols, history=chat_history)
#                             final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                         except: pass
#                 if not found_any: final_results.append({"type": "chat", "message": "Bhai, ye item mere system mein nahi mila. 🧐 Thoda spelling check karoge?"})
#             except Exception as e: final_results.append({"type": "chat", "message": f"Inventory Error: {str(e)}"})

#         # 📉 BRANCH 4.5: REQUIRED VS AVAILABLE (SHORTAGE/SURPLUS) 
#         elif intent == "shortage_search":
#             try:
#                 target = original_target.strip().lower()
#                 noise_words = ["short", "kam", "zyada", "extra", "hai", "kya", "batao", "check", "available", "project", "site", "ke liye", "ki", "ka", "ke", "mein", "liye", "kon", "se", "item", "padh", "rhe"]
#                 for w in noise_words: target = re.sub(rf'\b{w}\b', '', target, flags=re.IGNORECASE).strip()

#                 is_surplus = any(w in low_q for w in ["zyada", "extra", "surplus", "bacha", "bache"])
#                 project_filter_sql = ""
#                 item_filter_sql = ""
#                 params = {}
#                 matched_project_name = None
#                 matched_supplier_name = None
                
#                 if target and target not in ["maal", "item", "stock", "inventory", "list", "sab"]:
#                     proj_check = db.execute(text("SELECT name FROM projects WHERE LOWER(name) LIKE :t AND is_deleted = 0 LIMIT 1"), {"t": f"%{target}%"}).fetchone()
#                     if proj_check:
#                         matched_project_name = proj_check.name; project_filter_sql = " AND LOWER(p.name) LIKE :t "; params["t"] = f"%{target}%"
#                     else:
#                         sup_check = db.execute(text("SELECT id, supplier_name FROM suppliers WHERE LOWER(supplier_name) LIKE :t LIMIT 1"), {"t": f"%{target}%"}).fetchone()
#                         if not sup_check and len(target) > 3:
#                             corr = smart_match(target, category="supplier")
#                             if corr and corr.lower() != target: sup_check = db.execute(text("SELECT id, supplier_name FROM suppliers WHERE LOWER(supplier_name) LIKE :t LIMIT 1"), {"t": f"%{corr.lower()}%"}).fetchone()
#                         if sup_check:
#                             matched_supplier_name = sup_check.supplier_name; item_filter_sql = " AND i.id IN (SELECT DISTINCT inventory_id FROM stock_transactions WHERE supplier_id = :sid) "; params["sid"] = sup_check.id
#                         else:
#                             item_filter_sql = " AND LOWER(i.name) LIKE :t "; params["t"] = f"%{target}%"

#                 query = f"""
#                     WITH RequiredData AS (
#                         SELECT pi.inventory_id, SUM(pp.quantity * pi.quantity) as req_qty
#                         FROM projects p JOIN project_products pp ON p.id = pp.project_id JOIN product_items pi ON pp.product_id = pi.product_id
#                         WHERE LOWER(p.status) NOT IN ('completed', 'hold') AND p.is_deleted = 0 {project_filter_sql} GROUP BY pi.inventory_id
#                         UNION ALL
#                         SELECT pji.inventory_id, SUM(pji.quantity) as req_qty
#                         FROM projects p JOIN project_item pji ON p.id = pji.project_id
#                         WHERE LOWER(p.status) NOT IN ('completed', 'hold') AND p.is_deleted = 0 {project_filter_sql} GROUP BY pji.inventory_id
#                     ),
#                     TotalRequired AS ( SELECT inventory_id, SUM(req_qty) as required_qty FROM RequiredData GROUP BY inventory_id ),
#                     StockData AS ( SELECT inventory_id, COALESCE(SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END), 0) AS available_qty FROM stock_transactions GROUP BY inventory_id )
#                     SELECT i.name, tr.required_qty, COALESCE(sd.available_qty, 0) AS available_qty FROM TotalRequired tr
#                     JOIN inventories i ON tr.inventory_id = i.id LEFT JOIN StockData sd ON tr.inventory_id = sd.inventory_id
#                     WHERE i.is_deleted = 0 {item_filter_sql}
#                 """
#                 if is_surplus:
#                     query += " AND COALESCE(sd.available_qty, 0) > tr.required_qty ORDER BY (COALESCE(sd.available_qty, 0) - tr.required_qty) DESC"
#                     alert_emoji = "✅ Extra:"; report_title = "Extra / Surplus Stock"
#                 else:
#                     query += " AND tr.required_qty > COALESCE(sd.available_qty, 0) ORDER BY (tr.required_qty - COALESCE(sd.available_qty, 0)) DESC"
#                     alert_emoji = "🚨 Short:"; report_title = "Shortage"
#                 query += " LIMIT 20"
                
#                 rows = db.execute(text(query), params).fetchall()
#                 if matched_project_name: report_title += f" for **{matched_project_name}**"
#                 elif matched_supplier_name: report_title += f" for **{matched_supplier_name}**"

#                 if not rows:
#                     if matched_project_name:
#                         if is_surplus: final_results.append({"type": "chat", "message": f"Bhai, **{matched_project_name}** project ke liye koi item extra (surplus) nahi pada hai. Jitni zaroorat hai, bas utna hi maal hai! ⚖️"})
#                         else: final_results.append({"type": "chat", "message": f"Bhai, **{matched_project_name}** project ke liye koi item short nahi hai. Is project ka saara maal available hai! 🚀"})
#                     elif matched_supplier_name:
#                         if is_surplus: final_results.append({"type": "chat", "message": f"Bhai, **{matched_supplier_name}** se supply hone wale kisi item mein zaroorat se zyada (extra) stock nahi hai."})
#                         else: final_results.append({"type": "chat", "message": f"Bhai, **{matched_supplier_name}** se linked saare items ka stock abhi ekdum set hai! Koi shortage nahi chal rahi. 👍"})
#                     elif target and not matched_project_name and not matched_supplier_name:
#                         if is_surplus: final_results.append({"type": "chat", "message": f"Bhai, **{target.title()}** abhi zaroorat se zyada (extra) nahi pada hai. Ekdum hisaab se hi available hai! ⚖️"})
#                         else: final_results.append({"type": "chat", "message": f"Bhai, **{target.title()}** ka stock ekdum set hai! Koi shortage nahi hai. 👍"})
#                     elif is_surplus: final_results.append({"type": "chat", "message": "Bhai, abhi required se zyada (extra) koi maal nahi pada hai. Sab hisaab se hi chal raha hai! ⚖️"})
#                     else: final_results.append({"type": "chat", "message": "Bhai, abhi koi shortage nahi hai. Saara maal properly available hai! ✅📦"})
#                 else:
#                     msg = f"haan mil gaya 👍 Ye rahi **{report_title}** items ki list:\n\n| Item Name | Required | Available | Difference |\n| :--- | :---: | :---: | :---: |\n"
#                     for r in rows:
#                         req = float(r.required_qty or 0); avail = float(r.available_qty or 0); diff = abs(req - avail)
#                         msg += f"| {str(r.name)} | {req} | {avail} | {alert_emoji} **{diff}** |\n"
#                     final_results.append({"type": "chat", "message": msg})
#             except Exception as e: final_results.append({"type": "chat", "message": f"Report Error: {str(e)}"})

#         # # 📝 BRANCH 5: REQUEST SLIP FORM GENERATOR
#         # elif intent == "create_rs":
#         #     try:
#         #         proj_data = db.execute(text("SELECT id, name FROM projects WHERE is_deleted = 0")).fetchall()
#         #         projects_list = [{"id": p.id, "name": p.name} for p in proj_data]
#         #         try:
#         #             mach_data = db.execute(text("SELECT pp.project_id, p.id, p.name FROM project_products pp JOIN products p ON pp.product_id = p.id WHERE pp.is_deleted = 0 AND p.is_deleted = 0")).fetchall()
#         #             machines_list = [{"id": m.id, "name": m.name, "project_id": m.project_id} for m in mach_data]
#         #         except: machines_list = [] 
#         #         try:
#         #             inv_data = db.execute(text("SELECT pi.product_id as machine_id, i.id, i.name FROM product_items pi JOIN inventories i ON pi.inventory_id = i.id")).fetchall()
#         #             inventory_list = [{"id": i.id, "name": i.name, "machine_id": i.machine_id, "project_id": None} for i in inv_data]
#         #         except:
#         #             try:
#         #                 inv_data = db.execute(text("SELECT pi.project_id, i.id, i.name FROM project_item pi JOIN inventories i ON pi.inventory_id = i.id")).fetchall()
#         #                 inventory_list = [{"id": i.id, "name": i.name, "machine_id": None, "project_id": i.project_id} for i in inv_data]
#         #             except: inventory_list = []
                
#         #         prefill_proj = None
#         #         target = original_target.replace("slip", "").replace("ki", "").replace("banao", "").strip()
#         #         if target and len(target) > 2:
#         #             matched_proj = smart_match(target, category="project")
#         #             prefill_proj = matched_proj if matched_proj else target

#         #         final_results.append({
#         #             "type": "rs_form", "message": "📝 Request Slip form taiyaar hai! Niche details confirm karke Submit karein:",
#         #             "prefill_project": prefill_proj, "projects": projects_list, "machines": machines_list, "inventory": inventory_list
#         #         })
#         #     except Exception as e: final_results.append({"type": "chat", "message": f"Form load karne mein error aayi: {str(e)}"})
        
#         # 🧠 BRANCH 6: MASTER ENGINE (NL2SQL)
#         elif intent == "sql_analysis":
#             try:
#                 system_hint = ""
#                 target = original_target.strip().lower()
#                 if target and len(target) > 2:
#                     corr_sup = smart_match(target, category="supplier")
#                     if corr_sup and corr_sup.lower() != target: system_hint += f" Correct supplier name is '{corr_sup}'."
                        
#                 enhanced_query = raw_q
#                 if system_hint: enhanced_query += f"\n[SYSTEM HINT:{system_hint} Use LOWER(col) LIKE '%name%']"

#                 schema_full = get_db_schema(db, compact=False)
#                 schema_compact = get_db_schema(db, compact=True)
#                 sql_generated = generate_sql(enhanced_query, schema_full, schema_compact, history=chat_history)
                
#                 if not is_safe_sql(sql_generated):
#                     final_results.append({"type": "chat", "message": "Bhai, ye query database ke liye safe nahi hai. Blocked! 🛑"})
#                     continue
#                 try: result = db.execute(text(sql_generated))
#                 except Exception as first_error:
#                     sql_generated = generate_sql(enhanced_query, schema_full, schema_compact, previous_sql=sql_generated, sql_error=str(first_error), history=chat_history)
#                     if not is_safe_sql(sql_generated):
#                         final_results.append({"type": "chat", "message": "Bhai, AI ne ajeeb SQL banayi hai. Blocked! 🛑"})
#                         continue
#                     result = db.execute(text(sql_generated))

#                 columns = list(result.keys())
#                 rows = [list(row) for row in result.fetchall()]

#                 if not rows: final_results.append({"type": "chat", "message": f"{reasoning}\n\nLekin yaar, database mein aisi koi entry nahi mili mujhe. 🤷‍♂️"})
#                 else:
#                     try: ai_summary = format_answer(raw_q, rows, columns, history=chat_history)
#                     except: ai_summary = f"Mujhe {len(rows)} records mile hain."
#                     final_results.append({"type": "chat", "message": f"{reasoning}\n\n{ai_summary}"})
#             except Exception as e: final_results.append({"type": "chat", "message": f"Calculation Error: {str(e)}"})

#     # ══════════════════════════════════════════════════════════════════════════
#     # FINAL RESPONSE & LAYER 2 FALLBACK 
#     # ══════════════════════════════════════════════════════════════════════════
#     if len(final_results) > 1:
#         final_response = {"results": final_results[:limit + 2]}
#     else:
#         is_english = any(word in low_q for w in ["what", "how", "show", "list", "get", "who", "where", "tell", "check"])
#         suggestion_text = (
#             "I'm sorry, I couldn't quite understand that.\n\nYou can ask about:\n1. **Purchase Orders**\n2. **Inventory**\n3. **Suppliers**"
#             if is_english else "Maaf kijiye, main theek se samajh nahi paaya.\n\nAap poochh sakte hain:\n1. **Purchase Orders**\n2. **Inventory**\n3. **Suppliers**"
#         )
#         final_response = {"results": [{"type": "chat", "message": suggestion_text}]}

#     # ── Layer 2 NL2SQL Auto-Fallback ──
#     if _is_poor_result(final_response):
#         nl2_resp = _nl2sql_response(raw_q, db, history=chat_history)
#         if nl2_resp:
#             final_response = nl2_resp
#             print(f"[NL2SQL Fallback] answered: {raw_q!r}")

#     process_time = time.time() - start_time
#     try: log_query_pro(user_role, raw_q, intents, final_response, process_time)
#     except Exception as e: print(f"Logger error: {e}")

#     return final_response

# # ── NL2SQL Helper (Layer 2 Wrapper) ───────────────────────────────────────────
# def _nl2sql_response(raw_q: str, db, history: list = None) -> dict | None:
#     """Run NL2SQL pipeline as Fallback. Returns formatted response or None."""
#     history = history or []
#     try:
#         schema_full = get_db_schema(db, compact=False)
#         schema_compact = get_db_schema(db, compact=True)
#         sql = generate_sql(raw_q, schema_full, schema_compact, history=history)
#         if not is_safe_sql(sql): return None
#         try: result = db.execute(text(sql))
#         except Exception as exec_err:
#             sql = generate_sql(raw_q, schema_full, schema_compact, previous_sql=sql, sql_error=str(exec_err), history=history)
#             if not is_safe_sql(sql): return None
#             result = db.execute(text(sql))
            
#         columns = list(result.keys())
#         rows = [list(row) for row in result.fetchall()]
#         answer = format_answer(raw_q, rows, columns, history=history)
        
#         parts = [{"type": "chat", "message": answer}]
#         if rows:
#             rows_as_dicts = [dict(zip(columns, row)) for row in rows[:50]]
#             parts.append({"type": "nl2sql_table", "rows": rows_as_dicts, "columns": columns})
#         return {"results": parts}
#     except Exception as e:
#         print(f"[NL2SQL] fallback failed: {e}")
#         return None

# # ══════════════════════════════════════════════════════════════════════════════
# # AUXILIARY ENDPOINTS (Cards, Quick Search, WhatsApp, Briefings)
# # ══════════════════════════════════════════════════════════════════════════════

# @router.get("/quick-search/supplier")
# def quick_search_supplier(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     if not q.strip(): rows = db.execute(_t("SELECT id, supplier_name, city, mobile FROM suppliers ORDER BY id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"(LOWER(supplier_name) LIKE :w{i} OR LOWER(COALESCE(city,'')) LIKE :w{i} OR COALESCE(mobile,'') LIKE :w{i})" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(f"SELECT id, supplier_name, city, mobile FROM suppliers WHERE {cond} ORDER BY supplier_name LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""), "city": str(r.city or ""), "mobile": str(r.mobile or "")} for r in rows]}

# @router.get("/quick-search/po")
# def quick_search_po(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     base = "SELECT p.id, p.po_number, p.po_date, p.total_amount, p.status, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id "
#     if not q.strip(): rows = db.execute(_t(base + "ORDER BY p.id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"(LOWER(p.po_number) LIKE :w{i} OR LOWER(COALESCE(s.supplier_name,'')) LIKE :w{i} OR LOWER(COALESCE(p.status,'')) LIKE :w{i})" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(base + f"WHERE {cond} ORDER BY p.po_date DESC LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "po_number": str(r.po_number or ""), "date": str(r.po_date or ""), "total": float(r.total_amount or 0), "status": str(r.status or ""), "supplier": str(r.supplier_name or "")} for r in rows]}

# @router.get("/quick-search/inventory")
# def quick_search_inventory(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     base = "SELECT i.id, i.name, i.unit, COALESCE(SUM(CASE WHEN LOWER(st.txn_type)='in' THEN st.quantity ELSE -st.quantity END),0) AS stock FROM inventories i LEFT JOIN stock_transactions st ON st.inventory_id=i.id WHERE i.is_deleted=0 "
#     if not q.strip(): rows = db.execute(_t(base + "GROUP BY i.id,i.name,i.unit ORDER BY i.id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"LOWER(i.name) LIKE :w{i}" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(base + f"AND {cond} GROUP BY i.id,i.name,i.unit ORDER BY i.name LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.name or ""), "unit": str(r.unit or ""), "stock": float(r.stock or 0)} for r in rows]}

# @router.get("/po/{po_id}/card")
# def po_card(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     row = db.execute(_t("SELECT p.*, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id WHERE p.id=:id LIMIT 1"), {"id": po_id}).fetchone()
#     if not row: return {"results": [{"type": "chat", "message": "PO nahi mila."}]}
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{row.po_number}** ka detail:"}, {"type": "po", "po_id": int(row.id), "po_no": str(row.po_number or ""), "supplier": str(row.supplier_name or ""), "date": str(row.po_date or ""), "total": float(row.total_amount or 0), "advance": float(row.advance_amount or 0), "balance": float(row.balance_amount or 0), "status": str(row.status or "")}]}

# @router.get("/supplier/{supplier_id}/card")
# def supplier_card(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     s = db.execute(_t("SELECT * FROM suppliers WHERE id=:id LIMIT 1"), {"id": supplier_id}).fetchone()
#     if not s: return {"results": [{"type": "chat", "message": "Supplier nahi mila."}]}
#     inv_items = db.execute(_t("SELECT i.id, i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) AS stock FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"), {"sid": supplier_id}).fetchall()
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{s.supplier_name}** ka profile:"}, {"type": "result", "supplier": {"id": int(s.id), "name": str(s.supplier_name or ""), "code": str(getattr(s, "supplier_code", "") or ""), "mobile": str(getattr(s, "mobile", "") or ""), "city": str(getattr(s, "city", "") or ""), "email": str(getattr(s, "email", "") or ""), "gstin": str(getattr(s, "gstin", "") or "")}, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]}]}

# @router.get("/inventory/{inventory_id}/card")
# def inventory_card(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     inv = db.execute(_t("SELECT * FROM inventories WHERE id=:id LIMIT 1"), {"id": inventory_id}).fetchone()
#     if not inv: return {"results": [{"type": "chat", "message": "Item nahi mila."}]}
#     stock = float(db.execute(_t("SELECT COALESCE(SUM(CASE WHEN LOWER(txn_type)='in' THEN quantity ELSE -quantity END),0) FROM stock_transactions WHERE inventory_id=:id"), {"id": inventory_id}).scalar() or 0)
#     cls = (getattr(inv, "classification", "") or "").lower()
#     finish = 0 if ("machining" in cls or "semi" in cls) else stock; semi = stock if "semi" in cls else 0; machining= stock if "machining" in cls else 0
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{inv.name}** ka stock:"}, {"type": "result", "inventory": {"id": int(inv.id), "name": str(inv.name or ""), "category": cls.upper(), "placement": str(getattr(inv, "placement", "") or ""), "unit": str(getattr(inv, "unit", "") or ""), "model": str(getattr(inv, "model", "") or ""), "grade": str(getattr(inv, "grade", "") or "")}, "total_stock": stock, "finish_stock": finish, "semi_finish_stock": semi, "machining_stock": machining}]}

# @router.post("/select")
# def handle_select(payload: dict, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     name = payload.get("selected", "")
#     s = db.execute(_t("SELECT * FROM suppliers WHERE supplier_name=:n LIMIT 1"), {"n": name}).fetchone()
#     if not s: return {"results": [{"type": "chat", "message": f"'{name}' nahi mila."}]}
#     inv_items = db.execute(_t("SELECT i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) as stock FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"), {"sid": s.id}).fetchall()
#     return {"results": [{"type": "chat", "message": f"ye raha **{s.supplier_name}** ka profile:"}, {"type": "result", "supplier": {"id": int(s.id), "name": str(s.supplier_name or ""), "code": str(getattr(s, "supplier_code", "") or ""), "mobile": str(getattr(s, "mobile", "") or ""), "city": str(getattr(s, "city", "") or ""), "email": str(getattr(s, "email", "") or ""), "gstin": str(getattr(s, "gstin", "") or "")}, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]}]}

# @router.get("/inventory/{inventory_id}/po-history")
# def inventory_po_history(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT po.id, po.po_number, po.po_date, po.status, s.supplier_name, poi.ordered_qty, poi.received_qty, poi.unit_price, poi.line_total FROM purchase_order_items poi JOIN purchase_orders po ON poi.purchase_order_id = po.id JOIN suppliers s ON po.supplier_id = s.id WHERE poi.inventory_id = :iid ORDER BY po.po_date DESC LIMIT 50"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"po_id": int(r.id), "po_number": str(r.po_number), "date": str(r.po_date or ""), "status": str(r.status  or ""), "supplier": str(r.supplier_name or ""), "ordered": float(r.ordered_qty  or 0), "received": float(r.received_qty or 0), "unit_price": float(r.unit_price   or 0), "line_total": float(r.line_total   or 0)} for r in rows]}

# @router.get("/inventory/{inventory_id}/suppliers")
# def inventory_suppliers(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT s.id, s.supplier_name, s.city, COUNT(DISTINCT po.id) AS po_count, COALESCE(SUM(poi.ordered_qty), 0) AS total_ordered, COALESCE(MIN(poi.unit_price), 0) AS min_price, COALESCE(MAX(poi.unit_price), 0) AS max_price FROM purchase_order_items poi JOIN purchase_orders po ON poi.purchase_order_id = po.id JOIN suppliers s ON po.supplier_id = s.id WHERE poi.inventory_id = :iid GROUP BY s.id, s.supplier_name, s.city ORDER BY total_ordered DESC"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""), "city": str(r.city or ""), "po_count": int(r.po_count), "total_ordered": float(r.total_ordered), "min_price": float(r.min_price), "max_price": float(r.max_price)} for r in rows]}

# @router.get("/inventory/{inventory_id}/stock-log")
# def inventory_stock_log(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT txn_date, txn_type, quantity, ref_type, ref_no, remarks FROM stock_transactions WHERE inventory_id = :iid ORDER BY txn_date DESC, id DESC LIMIT 100"), {"iid": inventory_id}).fetchall()
#     running = 0.0; result_rows = []
#     for r in reversed(rows):
#         qty = float(r.quantity or 0)
#         running += qty if str(r.txn_type).lower() == "in" else -qty
#         result_rows.append({"date": str(r.txn_date or ""), "type": str(r.txn_type or ""), "qty": qty, "balance": round(running, 2), "ref_type": str(r.ref_type or ""), "ref_no": str(r.ref_no or ""), "remarks": str(r.remarks or "")})
#     result_rows.reverse()   
#     return {"rows": result_rows, "current_stock": round(running, 2)}

# @router.get("/inventory/{inventory_id}/grns")
# def inventory_grns(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT g.grn_number, g.grn_date, g.invoice_no, g.remarks, gi.received_qty, gi.accepted_qty, gi.rejected_qty, gi.placement FROM grn_items gi JOIN grns g ON gi.grn_id = g.id WHERE gi.inventory_id = :iid ORDER BY g.grn_date DESC LIMIT 50"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"grn_number": str(r.grn_number  or ""), "date": str(r.grn_date or ""), "invoice_no": str(r.invoice_no  or ""), "received": float(r.received_qty  or 0), "accepted": float(r.accepted_qty  or 0), "rejected": float(r.rejected_qty  or 0), "placement": str(r.placement   or ""), "remarks": str(r.remarks     or "")} for r in rows]}

# @router.get("/supplier/{supplier_id}/pos")
# def supplier_pos(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT id, po_number, po_date, total_amount, advance_amount, balance_amount, status, expected_delivery, delivery_status FROM purchase_orders WHERE supplier_id = :sid ORDER BY po_date DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     return {"rows": [{"id": int(r.id), "po_number": str(r.po_number), "date": str(r.po_date or ""), "total": float(r.total_amount or 0), "advance": float(r.advance_amount or 0), "balance": float(r.balance_amount or 0), "status": str(r.status or ""), "expected": str(r.expected_delivery or ""), "delivery_status": str(r.delivery_status or "")} for r in rows]}

# @router.get("/supplier/{supplier_id}/balance")
# def supplier_balance(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     r = db.execute(_t("SELECT COUNT(*) AS total_pos, COALESCE(SUM(total_amount), 0) AS total_ordered, COALESCE(SUM(advance_amount), 0) AS total_advance, COALESCE(SUM(balance_amount), 0) AS total_balance, COALESCE(SUM(CASE WHEN LOWER(status)!='completed' THEN balance_amount ELSE 0 END), 0) AS pending_balance, COUNT(CASE WHEN LOWER(status)='completed' THEN 1 END) AS completed_pos, COUNT(CASE WHEN LOWER(status)!='completed' THEN 1 END) AS open_pos FROM purchase_orders WHERE supplier_id = :sid"), {"sid": supplier_id}).fetchone()
#     return {"total_pos": int(r.total_pos), "total_ordered": float(r.total_ordered), "total_advance": float(r.total_advance), "total_balance": float(r.total_balance), "pending_balance": float(r.pending_balance), "completed_pos": int(r.completed_pos), "open_pos": int(r.open_pos)}

# @router.get("/supplier/{supplier_id}/items")
# def supplier_items(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT i.name, i.unit, COALESCE(SUM(poi.ordered_qty), 0) AS total_ordered, COALESCE(SUM(poi.received_qty), 0) AS total_received FROM purchase_order_items poi JOIN inventories i ON poi.inventory_id = i.id JOIN purchase_orders po ON poi.purchase_order_id = po.id WHERE po.supplier_id = :sid GROUP BY i.id, i.name, i.unit ORDER BY total_ordered DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     return {"rows": [{"name": str(r.name), "unit": str(r.unit or ""), "ordered": float(r.total_ordered), "received": float(r.total_received)} for r in rows]}

# @router.get("/supplier/{supplier_id}/payments")
# def supplier_payments(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT pt.pay_amount, pt.transaction_date, po.po_number FROM po_transactions pt JOIN purchase_orders po ON pt.po_id = po.id WHERE po.supplier_id = :sid ORDER BY pt.transaction_date DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     total_paid = sum(float(r.pay_amount) for r in rows)
#     return {"total_paid": total_paid, "rows": [{"po_number": str(r.po_number), "amount": float(r.pay_amount), "date": str(r.transaction_date)[:10]} for r in rows]}

# @router.get("/po/{po_id}/items")
# def po_items(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT i.name, i.unit, poi.hsn, poi.ordered_qty, poi.received_qty, poi.unit_price, poi.discount, poi.tax_percent, poi.tax_amount, poi.line_total FROM purchase_order_items poi JOIN inventories i ON poi.inventory_id = i.id WHERE poi.purchase_order_id = :pid ORDER BY poi.id"), {"pid": po_id}).fetchall()
#     return {"rows": [{"name": str(r.name), "unit": str(r.unit or ""), "hsn": str(r.hsn or ""), "ordered": float(r.ordered_qty or 0), "received": float(r.received_qty or 0), "unit_price": float(r.unit_price or 0), "discount": float(r.discount or 0), "tax_percent": float(r.tax_percent or 0), "tax_amount": float(r.tax_amount or 0), "line_total": float(r.line_total or 0)} for r in rows]}

# @router.get("/po/{po_id}/payments")
# def po_payments(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT pay_amount, transaction_date FROM po_transactions WHERE po_id = :pid ORDER BY transaction_date DESC"), {"pid": po_id}).fetchall()
#     total_paid = sum(float(r.pay_amount) for r in rows)
#     return {"total_paid": total_paid, "rows": [{"amount": float(r.pay_amount), "date": str(r.transaction_date)[:10]} for r in rows]}

# @router.get("/po/{po_id}/status-log")
# def po_status_log(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT status, changed_at, remarks FROM po_status_logs WHERE purchase_order_id = :pid ORDER BY changed_at DESC"), {"pid": po_id}).fetchall()
#     return {"rows": [{"status": str(r.status or ""), "date": str(r.changed_at)[:16], "remarks": str(r.remarks or "")} for r in rows]}

# @router.get("/po/{po_id}/supplier")
# def po_supplier(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     row = db.execute(_t("SELECT s.* FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE p.id = :id LIMIT 1"), {"id": po_id}).fetchone()
#     if not row: return {"error": "Supplier not found for this PO"}
#     return {"supplier": {"id": int(row.id), "name": str(row.supplier_name or ""), "code": str(getattr(row, "supplier_code", "N/A") or "N/A"), "mobile": str(getattr(row, "mobile", "N/A") or "N/A"), "city": str(getattr(row, "city", "N/A") or "N/A"), "email": str(getattr(row, "email", "N/A") or "N/A"), "gstin": str(getattr(row, "gstin", "N/A") or "N/A")}}

# @router.post("/feedback")
# def chatbot_feedback(payload: dict, db: Session = Depends(get_db)):
#     try:
#         with open("chat_history.json", "a", encoding="utf-8") as f:
#             f.write(json.dumps({"type": "feedback", "request_id": payload.get("request_id"), "query": payload.get("query"), "rating": payload.get("rating"), "summary": payload.get("summary"), "timestamp": datetime.datetime.now().isoformat()}, ensure_ascii=False) + "\n")
#         return {"ok": True}
#     except Exception as e: return {"ok": False, "error": str(e)}

# @router.get("/logs")
# def view_logs():
#     log_file = "chat_history.json"
#     if not os.path.exists(log_file): return {"message": "Abhi tak koi chat nahi hui."}
#     try:
#         with open(log_file, "r", encoding="utf-8") as f: logs = [json.loads(line) for line in f if line.strip()]
#         return {"total_chats": len(logs), "latest_logs": logs[::-1]}
#     except Exception as e: return {"error": str(e)}

# @router.delete("/logs/clear")
# def clear_logs(secret_key: str = "mewar123"):
#     if secret_key != "mewar@12345": return {"error": "Galat password."}
#     try: open("chat_history.json", "w", encoding="utf-8").close(); return {"success": True, "message": "Logs clear ho gaye."}
#     except Exception as e: return {"error": str(e)}

# # ── WHATSAPP INTEGRATION ──────────────────────────────────────────────────────
# async def process_chat_message(user_text: str) -> str:
#     db = SessionLocal()
#     try:
#         request_data = ChatRequest(query=user_text, role="superadmin")
#         response_dict = chatbot(request_data, db)
#         final_whatsapp_text = ""
#         if "results" in response_dict:
#             for res in response_dict["results"]:
#                 res_type = res.get("type")
#                 if res_type == "chat": final_whatsapp_text += res.get("message", "") + "\n\n"
#                 elif res_type == "po":
#                     final_whatsapp_text += f"📄 *PO No:* {res.get('po_no')}\n🏢 *Supplier:* {res.get('supplier')}\n💰 *Total:* ₹{res.get('total', 0):,.2f}\n⏳ *Balance:* ₹{res.get('balance', 0):,.2f}\n📌 *Status:* {res.get('status')}\n\n"
#                 elif res_type == "result":
#                     if "inventory" in res:
#                         inv = res["inventory"]
#                         final_whatsapp_text += f"📦 *{inv.get('name')}*\n📊 *Total Stock:* {res.get('total_stock')}\n📍 *Location:* {inv.get('placement')}\n\n"
#                 elif res_type == "dropdown":
#                     final_whatsapp_text += res.get("message", "") + "\n"
#                     for item in res.get("items", []): final_whatsapp_text += f"🔸 {item.get('name')}\n"
#                     final_whatsapp_text += "\n*(Kripya inme se ek naam type karein)*\n\n"
#                 elif res_type == "project":
#                     final_whatsapp_text += f"🏗️ *Project:* {res.get('project_name')}\n📌 *Status:* {res.get('category')}\n💰 *Budget:* ₹{res.get('amount', 0):,.2f}\n\n"
#         if not final_whatsapp_text.strip(): final_whatsapp_text = "Maaf karna, mujhe iska jawab nahi mil paya. 😅"
#         return final_whatsapp_text.strip()
#     except Exception as e: print(f"❌ WhatsApp AI Error: {e}"); return "Bhai, mere AI dimaag mein thoda error aa gaya hai. Thodi der mein try karein! 🙏"
#     finally: db.close()

# def generate_morning_briefing():
#     db = SessionLocal()
#     try:
#         po_res = db.execute(text("SELECT COUNT(id), SUM(balance_amount) FROM purchase_orders WHERE balance_amount>0 AND LOWER(status)!='completed'")).fetchone()
#         proj_res = db.execute(text("SELECT COUNT(id) FROM projects WHERE is_deleted=0 AND (end_date < CURRENT_DATE OR deadline < CURRENT_DATE) AND LOWER(status)!='completed'")).fetchone()
#         pending_pos = po_res[0] or 0; pending_amt = po_res[1] or 0.0; overdue = proj_res[0] or 0
#         msg = f"🌅 *Good Morning! Here is your Mewar ERP Daily Briefing:* 🌅\n\n📦 *Pending Purchase Orders:* {pending_pos} Orders (Total Due: ₹{float(pending_amt):,.2f})\n"
#         if overdue > 0: msg += f"🚨 *Alert:* {overdue} Projects apne deadline se late chal rahe hain!\n"
#         else: msg += f"✅ *Projects:* Sabhi projects time par chal rahe hain.\n"
#         print("\n" + "⭐"*30); print("🤖 AUTO-TRIGGERED MORNING BRIEFING:"); print(msg); print("⭐"*30 + "\n")
#     except Exception as e: print(f"❌ Morning Briefing Error: {e}")
#     finally: db.close()


## --------------------------------------------------------------------------------------------------------------------------------------
                                       ## NEW SQL CHATBOT CODE STARTS HERE ##
##-----------------------------------------------------------------------------------------------------------------------------------------

# from asyncio import threads
# import time
# import datetime
# from fastapi import APIRouter, Depends, Query as _Query
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# import re
# import numpy as np
# import faiss
# from fastembed import TextEmbedding
# import difflib
# import json
# import os

# from app.db.database import get_db, SessionLocal
# from app.schemas.chat import ChatRequest
# from app.services.ollama_engine import ask_ollama
# from app.services.nl2sql_engine import generate_and_execute_sql,format_answer

# router = APIRouter(prefix="/chatbot", tags=["Chatbot Final"])

# # ── Role permissions ──────────────────────────────────────────────────────────
# ROLE_PERMISSIONS = {
#     "supervisor":     ["inventory", "project", "general_chat"],
#     "sales":          ["inventory", "general_chat"],
#     "purchase":       ["inventory", "supplier", "po", "general_chat"],
#     "purchase admin": ["inventory", "supplier", "po", "financials", "general_chat"],
#     "store admin":    ["inventory", "po", "project", "general_chat"],
#     "store department": ["inventory", "general_chat"],
#     "hod":            ["inventory", "project", "supplier", "po", "financials", "general_chat"],
#     "hr":             ["general_chat"],
# }

# # ── Off-topic guard (Junior's Logic) ──────────────────────────────────────────
# _ERP_KEYWORDS = {
#     "supplier", "vendor", "party", "sup",
#     "po", "order", "purchase", "transit", "delivery", "grn", "dispatch",
#     "stock", "maal", "item", "inventory", "qty", "quantity",
#     "project", "site", "crusher",
#     "balance", "payment", "invoice", "gst", "tax", "cgst", "sgst",
#     "rokra", "paisa", "kharcha", "hisab",
#     "mewar", "erp", "sale", "sales", "report", "employee", "account",
#     "slip", "request", "banao", "batao", "dikhao", "milao", "details",
#     "kitna", "kitne", "kahan", "kaisa", "kab", "lagao", "nikalo",
#     "total", "list", "count", "kitni", "sabhi", "saare",
#     "show", "find", "get", "check", "all", "mere", "mera",
# }

# _CLEARLY_OFFTOPIC = {
#     "poem", "poetry", "joke", "weather", "recipe", "cook", "song", "lyrics",
#     "translate", "movie", "cricket", "football", "game", "news", "capital of",
#     "who is the president", "write a story", "tell me a story",
# }

# def _is_off_topic(query: str) -> bool:
#     q = query.lower()
#     if len(q.split()) <= 3: return False
#     if any(kw in q for kw in _CLEARLY_OFFTOPIC): return True
#     return not any(kw in q for kw in _ERP_KEYWORDS)

# # ==========================================
# # 🧠 FAISS SEMANTIC SEARCH ENGINE SETUP
# # ==========================================
# semantic_model = None
# inv_names_list = []
# sup_names_list = []
# inv_faiss_index = None
# sup_faiss_index = None
# is_faiss_loaded = False
# proj_names_list = []
# proj_faiss_index = None
# is_loading_started = False

# def load_faiss_once(db: Session):
#     global semantic_model, inv_names_list, sup_names_list, inv_faiss_index, sup_faiss_index, is_faiss_loaded, proj_names_list, proj_faiss_index, is_loading_started
    
#     if is_faiss_loaded or is_loading_started: 
#         return
        
#     is_loading_started = True 
    
#     print("⏳ Loading Semantic Search Model... (10-15 seconds)")
#     semantic_model = TextEmbedding('BAAI/bge-small-en-v1.5', threads=1)
    
#     for attempt in range(3):
#         try:
#             print(f"🛠️ Building FAISS Memory (Attempt {attempt+1}/3)...")

#             # 1. Inventory Indexing
#             inv_data = db.execute(text("SELECT name FROM inventories WHERE name IS NOT NULL AND is_deleted = 0")).fetchall()
#             inv_names_list = [row[0] for row in inv_data if row[0]]
#             if inv_names_list:
#                 inv_embeddings = np.array(list(semantic_model.embed(inv_names_list, batch_size=50))).astype('float32')
#                 inv_faiss_index = faiss.IndexFlatL2(inv_embeddings.shape[1])
#                 inv_faiss_index.add(inv_embeddings)

#             # 2. Supplier Indexing
#             sup_data = db.execute(text("SELECT supplier_name FROM suppliers WHERE supplier_name IS NOT NULL")).fetchall()
#             sup_names_list = [row[0] for row in sup_data if row[0]]
#             if sup_names_list:
#                 sup_embeddings = np.array(list(semantic_model.embed(sup_names_list, batch_size=50))).astype('float32')
#                 sup_faiss_index = faiss.IndexFlatL2(sup_embeddings.shape[1])
#                 sup_faiss_index.add(sup_embeddings)

#             # 3. Project Indexing
#             proj_data = db.execute(text("SELECT name FROM projects WHERE name IS NOT NULL AND is_deleted = 0")).fetchall()
#             proj_names_list = [row[0] for row in proj_data if row[0]]
#             if proj_names_list:
#                 proj_embeddings = np.array(list(semantic_model.embed(proj_names_list, batch_size=50))).astype('float32')
#                 proj_faiss_index = faiss.IndexFlatL2(proj_embeddings.shape[1])
#                 proj_faiss_index.add(proj_embeddings)

#             is_faiss_loaded = True
#             is_loading_started = False
#             print(f"✅ FAISS Ready! Indexed {len(inv_names_list)} Items, {len(sup_names_list)} Suppliers & {len(proj_names_list)} Projects.")
#             return

#         except Exception as e:
#             print(f"⚠️ Attempt {attempt+1} failed: {e}")
#             try: db.rollback() 
#             except: pass
                
#             if attempt < 2: time.sleep(3)
#             else: is_loading_started = False; print("❌ All attempts failed. FAISS load error.")

# # ── Semantic matching helper ───────────────────────────────────────────────────
# def smart_match(query_text, category="inventory"):
#     if not query_text or len(query_text) < 2 or not is_faiss_loaded:
#         return query_text
#     try:
#         query_vector = np.array(list(semantic_model.embed([query_text]))).astype('float32')
#         if category == "inventory" and inv_faiss_index is not None:
#             distances, indices = inv_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 0.7:
#                 return inv_names_list[indices[0][0]]
#         elif category == "supplier" and sup_faiss_index is not None:
#             distances, indices = sup_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 0.7:
#                 return sup_names_list[indices[0][0]]
#         elif category == "project" and proj_faiss_index is not None:
#             distances, indices = proj_faiss_index.search(query_vector, 3)
#             if distances[0][0] < 1.0:
#                 return proj_names_list[indices[0][0]]
#     except Exception:
#         pass
#     return query_text

# # ── Loggers ───────────────────────────────────────────────────────────────────
# def log_query_pro(user_role, query, intents, final_results, process_time):
#     bot_reply = "No Response"
#     if isinstance(final_results, dict) and "results" in final_results:
#         for res in final_results["results"]:
#             if res.get("type") == "chat":
#                 bot_reply = res.get("message", "")
#                 break 
#     is_fail = any(w in str(bot_reply).lower() for w in ["nahi mila", "error", "samajh nahi", "maaf kijiye", "kripya", "permission nahi"])
#     log_entry = {
#         "date_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "role": user_role, "user_query": query, "intent": str(intents),
#         "bot_response": final_results["results"], "time_taken_sec": round(process_time, 2),
#         "status": "Fail ❌" if is_fail else "Success ✅"
#     }
#     try:
#         with open("chat_history.json", "a", encoding="utf-8") as f:
#             f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
#     except Exception as e: print(f"❌ File Log Error: {e}")

# # ══════════════════════════════════════════════════════════════════════════════
# # MAIN UNIFIED ENDPOINT (NEW NL2SQL ROUTING)
# # ══════════════════════════════════════════════════════════════════════════════
# @router.post("/")
# def chatbot(request: ChatRequest, db: Session = Depends(get_db)):
#     start_time = time.time()
    
#     # Background FAISS indexing
#     load_faiss_once(db) 
    
#     raw_q = request.query.strip()
#     chat_history = getattr(request, "history", []) 
#     user_role = getattr(request, "role", "guest").lower().strip()

#     # ── 1. Off-topic Guard ──
#     if _is_off_topic(raw_q) and not chat_history:
#         return {"results": [{"type": "chat", "message": "Bhai, main sirf Mewar ERP ke sawaalon mein help kar sakta hoon — Suppliers, Purchase Orders, Inventory, aur Projects. In topics par kuch poochho! 😊"}]}

#     # ── 2. Ollama AI Engine Se Parameters Nikalna ──
#     try:
#         try: 
#             ai_data = ask_ollama(raw_q, chat_history)
#         except:
#             time.sleep(1)
#             ai_data = ask_ollama(raw_q, chat_history)
#     except Exception as e:
#         print(f"❌ AI CRASHED: {str(e)}")
#         return {"results": [{"type": "chat", "message": "Bhai, mera AI brain abhi connect nahi ho pa raha. 🙏"}]}

#     intent = ai_data.get("intent", "nl2sql")
#     reasoning = ai_data.get("reasoning", "Hmm, main check karta hoon... 👍")

#     # ── 3. Simple Chat Handling (Hi/Hello) ──
#     if intent == "chat":
#         return {"results": [{"type": "chat", "message": reasoning}]}

#     # ── 4. Parameters & UI Filters Extract Karna ──
#     query_type = ai_data.get("query_type", "inventory")
#     targets = ai_data.get("search_targets", [])
#     filters = ai_data.get("filters", {})

#     # UI se aane wale Dropdown filters ko AI filters ke sath jodna
#     ui_filters = getattr(request, "ui_filters", {}) or {}
#     for key, value in ui_filters.items():
#         if value: 
#             filters[key] = value

#     # ── 5. Role Permission Check ──
#     allowed_perms = ROLE_PERMISSIONS.get(user_role, [])
#     check_type = "po" if query_type == "purchase_order" else query_type
    
#     if user_role not in ["superadmin", "super admin", "admin"]:
#         if check_type not in allowed_perms:
#             return {"results": [{"type": "chat", "message": f"Maaf kijiyega, aapke '{user_role.title()}' role ke paas {query_type} ka data dekhne ki permission nahi hai. 🛑"}]}

#     # ── 6. The Master NL2SQL Engine (AI-DRIVEN HYBRID MODE) ──
#     try:
#         low_q = raw_q.lower()
        
#         # 🚦 AI ROUTER: Ab manual keywords ki zaroorat nahi.
#         if query_type == "inventory" and intent == "search":
#             final_results = [{"type": "chat", "message": reasoning}]
            
#             try:
#                 raw_target = targets[0] if targets else ""
#                 if not raw_target: raw_target = low_q
                
#                 clean_target = re.sub(r'[?\'"!.,]', '', raw_target).strip()
#                 clean_targets = []
                
#                 if len(targets) > 1:
#                     clean_targets = targets
#                 else:
#                     if len(clean_target) > 1: clean_targets.append(smart_match(clean_target, category="inventory"))
#                     if not clean_targets and ("bearing" in low_q or "belt" in low_q): 
#                         clean_targets = ["bearing" if "bearing" in low_q else "belt"]

#                 all_inv_names = [row.name.lower() for row in db.execute(text("SELECT name FROM inventories WHERE is_deleted=0")).fetchall() if row.name]
#                 found_any = False

#                 for t in clean_targets:
#                     query_str = "SELECT id, name, model, type, classification, placement FROM inventories WHERE (LOWER(name) LIKE :q OR LOWER(model) LIKE :q) AND is_deleted = 0"
#                     items = db.execute(text(query_str + " LIMIT 30"), {"q": f"%{t}%"}).fetchall()
                    
#                     if not items:
#                         closest = difflib.get_close_matches(t, all_inv_names, n=1, cutoff=0.65)
#                         if closest: 
#                             items = db.execute(text(query_str + " LIMIT 30"), {"q": f"%{closest[0]}%"}).fetchall()
#                             t = closest[0]
                    
#                     if not items: continue
#                     found_any = True

#                     ids = tuple([i.id for i in items])
#                     if len(items) > 1:
#                         total_sum = db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id IN :ids"), {"ids": ids}).scalar() or 0
#                         final_results.append({"type": "chat", "message": f"haan mil gaya 👍 **Total {t.title()} Stock:** {total_sum:.2f} units available hain."})
#                         final_results.append({"type": "dropdown", "message": f"Mujhe {len(items)} items mile hain. Kiski details dekhni hai?", "items": [{"id": i.id, "name": f"{i.name} {i.model or ''}"} for i in items]})
#                     elif len(items) == 1:
#                         i = items[0]
#                         stock = float(db.execute(text("SELECT SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END) FROM stock_transactions WHERE inventory_id = :id"), {"id": i.id}).scalar() or 0)
#                         disp_cat = i.type if i.type else "Raw Material"
#                         disp_loc = i.placement if i.placement else "Main Store"
#                         disp_class = str(i.classification).upper() if i.classification else "FINISH"
#                         f, sf, m = (stock, 0, 0) if disp_class == "FINISH" else (0, stock, 0) if "SEMI" in disp_class else (0, 0, stock)
                        
#                         final_results.append({"type": "chat", "message": f"haan ye raha 👍 **{i.name}** ka data mil gaya:"})
#                         final_results.append({"type": "result", "inventory": {"id": i.id, "name": f"{i.name} {i.model or ''}", "category": disp_cat, "placement": disp_loc}, "total_stock": stock, "finish_stock": f, "semi_finish_stock": sf, "machining_stock": m})
                        
#                         try:
#                             cols = ["Inventory Name", "Category", "Placement", "Total Stock"]
#                             row_data = [[f"{i.name} {i.model or ''}", disp_cat, disp_loc, stock]]
#                             ai_sum = format_answer(raw_q, row_data, cols, history=chat_history)
#                             final_results.append({"type": "chat", "message": f"🤖 **AI Insight:** {ai_sum}"})
#                         except: pass
                
#                 if not found_any: 
#                     final_results.append({"type": "chat", "message": "Bhai, ye item mere system mein nahi mila. 🧐 Thoda spelling check karoge?"})
#             except Exception as e: 
#                 final_results.append({"type": "chat", "message": f"Inventory Error: {str(e)}"})
            
#             return {"results": final_results}

#         # 🧾 BAAKI SAB KE LIYE NAYA NL2SQL AI (POs, Projects, Suppliers, Shortage)
#         is_only_name = (query_type == "supplier" and not filters.get("status") and not any(w in raw_q.lower() for w in ["paisa", "balance", "po", "order", "detail", "hisab", "profile", "contact"]))

#         if is_only_name and len(targets) > 0:
#             supplier_name = targets[0]
#             return {
#                 "results": [
#                     {"type": "chat", "message": f"haan bhai, **{supplier_name.title()}** mil gaya. 👍\n\nAap inka kya dekhna chahte hain? \n\n📄 Type **'Orders'** (saare PO dekhne ke liye)\n👤 Type **'Details'** (contact aur profile ke liye)"}
#                 ]
#             }

#         # Agar user ne kuch specific pucha hai toh AI flow chalega
#         db_response = generate_and_execute_sql(
#             db=db, 
#             user_query=raw_q, 
#             query_type=query_type, 
#             targets=targets, 
#             filters=filters,
#             history=chat_history
#         )

#         if db_response["success"]:
#             rows = db_response.get("results", [])
            
#             # 📊 UNIVERSAL ERP TABLE DETECTOR
#             # Hum check karenge ki kya results mein inventory items hain
#             if len(rows) > 0 and any(key in str(rows[0]) for key in ["item_name", "inventory_id"]):
                
#                 # 1. AI Intro Message
#                 intro_msg = {"type": "chat", "message": reasoning}
                
#                 # 2. Table Header
#                 # Column check: Kya isme shortage ka data hai ya sirf quantity?
#                 is_shortage = "short_qty" in rows[0] or "shortage" in str(rows[0]).lower()
                
#                 if is_shortage:
#                     table_box = "| # | Inventory Name | Required | Stock | Short / Extra |\n"
#                     table_box += "| :--- | :--- | :---: | :---: | :--- |\n"
#                 else:
#                     table_box = "| # | Inventory Name | Total Quantity | Unit |\n"
#                     table_box += "| :--- | :--- | :---: | :---: |\n"
                
#                 for index, r in enumerate(rows, start=1):
#                     name = r.get("item_name") or r.get("name") or "N/A"
                    
#                     if is_shortage:
#                         req = f"{float(r.get('required_qty', 0)):.2f}"
#                         stock = f"{float(r.get('available_stock', 0)):.2f}"
#                         short = float(r.get("short_qty", 0))
#                         status = f"🔴 **Short: {short:.2f}**" if short > 0 else f"🟢 OK"
#                         table_box += f"| {index} | {name} | {req} | {stock} | {status} |\n"
#                     else:
#                         qty = f"{float(r.get('total_qty') or r.get('quantity') or 0):.2f}"
#                         unit = r.get("unit") or "Nos"
#                         table_box += f"| {index} | {name} | {qty} | {unit} |\n"
                
#                 return {"results": [intro_msg, {"type": "chat", "message": table_box}]}

#             # Baaki Single Search (Supplier/Inventory) ke liye normal behavior
#             return {"results": [{"type": "chat", "message": reasoning}] + rows}

#     except Exception as e:
#         print(f"❌ Chatbot Mainif d Error: {e}")
#         return {"results": [{"type": "chat", "message": "Bhai, server mein kuch technical issue aa gaya hai. Thodi der mein try karein! 😅"}]}
# # ══════════════════════════════════════════════════════════════════════════════
# # AUXILIARY ENDPOINTS (Cards, Quick Search, WhatsApp, Briefings)
# # ══════════════════════════════════════════════════════════════════════════════

# @router.get("/quick-search/supplier")
# def quick_search_supplier(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     if not q.strip(): rows = db.execute(_t("SELECT id, supplier_name, city, mobile FROM suppliers ORDER BY id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"(LOWER(supplier_name) LIKE :w{i} OR LOWER(COALESCE(city,'')) LIKE :w{i} OR COALESCE(mobile,'') LIKE :w{i})" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(f"SELECT id, supplier_name, city, mobile FROM suppliers WHERE {cond} ORDER BY supplier_name LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""), "city": str(r.city or ""), "mobile": str(r.mobile or "")} for r in rows]}

# @router.get("/quick-search/po")
# def quick_search_po(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     base = "SELECT p.id, p.po_number, p.po_date, p.total_amount, p.status, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id "
#     if not q.strip(): rows = db.execute(_t(base + "ORDER BY p.id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"(LOWER(p.po_number) LIKE :w{i} OR LOWER(COALESCE(s.supplier_name,'')) LIKE :w{i} OR LOWER(COALESCE(p.status,'')) LIKE :w{i})" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(base + f"WHERE {cond} ORDER BY p.po_date DESC LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "po_number": str(r.po_number or ""), "date": str(r.po_date or ""), "total": float(r.total_amount or 0), "status": str(r.status or ""), "supplier": str(r.supplier_name or "")} for r in rows]}

# @router.get("/quick-search/inventory")
# def quick_search_inventory(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     base = "SELECT i.id, i.name, i.unit, COALESCE(SUM(CASE WHEN LOWER(st.txn_type)='in' THEN st.quantity ELSE -st.quantity END),0) AS stock FROM inventories i LEFT JOIN stock_transactions st ON st.inventory_id=i.id WHERE i.is_deleted=0 "
#     if not q.strip(): rows = db.execute(_t(base + "GROUP BY i.id,i.name,i.unit ORDER BY i.id DESC LIMIT :l"), {"l": limit}).fetchall()
#     else:
#         words = q.strip().lower().split()
#         cond = " AND ".join(f"LOWER(i.name) LIKE :w{i}" for i in range(len(words)))
#         params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}; params["l"] = limit
#         rows = db.execute(_t(base + f"AND {cond} GROUP BY i.id,i.name,i.unit ORDER BY i.name LIMIT :l"), params).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.name or ""), "unit": str(r.unit or ""), "stock": float(r.stock or 0)} for r in rows]}

# @router.get("/po/{po_id}/card")
# def po_card(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     row = db.execute(_t("SELECT p.*, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id WHERE p.id=:id LIMIT 1"), {"id": po_id}).fetchone()
#     if not row: return {"results": [{"type": "chat", "message": "PO nahi mila."}]}
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{row.po_number}** ka detail:"}, {"type": "po", "po_id": int(row.id), "po_no": str(row.po_number or ""), "supplier": str(row.supplier_name or ""), "date": str(row.po_date or ""), "total": float(row.total_amount or 0), "advance": float(row.advance_amount or 0), "balance": float(row.balance_amount or 0), "status": str(row.status or "")}]}

# @router.get("/supplier/{supplier_id}/card")
# def supplier_card(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     s = db.execute(_t("SELECT * FROM suppliers WHERE id=:id LIMIT 1"), {"id": supplier_id}).fetchone()
#     if not s: return {"results": [{"type": "chat", "message": "Supplier nahi mila."}]}
#     inv_items = db.execute(_t("SELECT i.id, i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) AS stock FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"), {"sid": supplier_id}).fetchall()
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{s.supplier_name}** ka profile:"}, {"type": "result", "supplier": {"id": int(s.id), "name": str(s.supplier_name or ""), "code": str(getattr(s, "supplier_code", "") or ""), "mobile": str(getattr(s, "mobile", "") or ""), "city": str(getattr(s, "city", "") or ""), "email": str(getattr(s, "email", "") or ""), "gstin": str(getattr(s, "gstin", "") or "")}, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]}]}

# @router.get("/inventory/{inventory_id}/card")
# def inventory_card(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     inv = db.execute(_t("SELECT * FROM inventories WHERE id=:id LIMIT 1"), {"id": inventory_id}).fetchone()
#     if not inv: return {"results": [{"type": "chat", "message": "Item nahi mila."}]}
#     stock = float(db.execute(_t("SELECT COALESCE(SUM(CASE WHEN LOWER(txn_type)='in' THEN quantity ELSE -quantity END),0) FROM stock_transactions WHERE inventory_id=:id"), {"id": inventory_id}).scalar() or 0)
#     cls = (getattr(inv, "classification", "") or "").lower()
#     finish = 0 if ("machining" in cls or "semi" in cls) else stock; semi = stock if "semi" in cls else 0; machining= stock if "machining" in cls else 0
#     return {"results": [{"type": "chat", "message": f"ye raha 👍 **{inv.name}** ka stock:"}, {"type": "result", "inventory": {"id": int(inv.id), "name": str(inv.name or ""), "category": cls.upper(), "placement": str(getattr(inv, "placement", "") or ""), "unit": str(getattr(inv, "unit", "") or ""), "model": str(getattr(inv, "model", "") or ""), "grade": str(getattr(inv, "grade", "") or "")}, "total_stock": stock, "finish_stock": finish, "semi_finish_stock": semi, "machining_stock": machining}]}

# @router.post("/select")
# def handle_select(payload: dict, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     name = payload.get("selected", "")
#     s = db.execute(_t("SELECT * FROM suppliers WHERE supplier_name=:n LIMIT 1"), {"n": name}).fetchone()
#     if not s: return {"results": [{"type": "chat", "message": f"'{name}' nahi mila."}]}
#     inv_items = db.execute(_t("SELECT i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) as stock FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"), {"sid": s.id}).fetchall()
#     return {"results": [{"type": "chat", "message": f"ye raha **{s.supplier_name}** ka profile:"}, {"type": "result", "supplier": {"id": int(s.id), "name": str(s.supplier_name or ""), "code": str(getattr(s, "supplier_code", "") or ""), "mobile": str(getattr(s, "mobile", "") or ""), "city": str(getattr(s, "city", "") or ""), "email": str(getattr(s, "email", "") or ""), "gstin": str(getattr(s, "gstin", "") or "")}, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]}]}

# @router.get("/inventory/{inventory_id}/po-history")
# def inventory_po_history(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT po.id, po.po_number, po.po_date, po.status, s.supplier_name, poi.ordered_qty, poi.received_qty, poi.unit_price, poi.line_total FROM purchase_order_items poi JOIN purchase_orders po ON poi.purchase_order_id = po.id JOIN suppliers s ON po.supplier_id = s.id WHERE poi.inventory_id = :iid ORDER BY po.po_date DESC LIMIT 50"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"po_id": int(r.id), "po_number": str(r.po_number), "date": str(r.po_date or ""), "status": str(r.status  or ""), "supplier": str(r.supplier_name or ""), "ordered": float(r.ordered_qty  or 0), "received": float(r.received_qty or 0), "unit_price": float(r.unit_price   or 0), "line_total": float(r.line_total   or 0)} for r in rows]}

# @router.get("/inventory/{inventory_id}/suppliers")
# def inventory_suppliers(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT s.id, s.supplier_name, s.city, COUNT(DISTINCT po.id) AS po_count, COALESCE(SUM(poi.ordered_qty), 0) AS total_ordered, COALESCE(MIN(poi.unit_price), 0) AS min_price, COALESCE(MAX(poi.unit_price), 0) AS max_price FROM purchase_order_items poi JOIN purchase_orders po ON poi.purchase_order_id = po.id JOIN suppliers s ON po.supplier_id = s.id WHERE poi.inventory_id = :iid GROUP BY s.id, s.supplier_name, s.city ORDER BY total_ordered DESC"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""), "city": str(r.city or ""), "po_count": int(r.po_count), "total_ordered": float(r.total_ordered), "min_price": float(r.min_price), "max_price": float(r.max_price)} for r in rows]}

# @router.get("/inventory/{inventory_id}/stock-log")
# def inventory_stock_log(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT txn_date, txn_type, quantity, ref_type, ref_no, remarks FROM stock_transactions WHERE inventory_id = :iid ORDER BY txn_date DESC, id DESC LIMIT 100"), {"iid": inventory_id}).fetchall()
#     running = 0.0; result_rows = []
#     for r in reversed(rows):
#         qty = float(r.quantity or 0)
#         running += qty if str(r.txn_type).lower() == "in" else -qty
#         result_rows.append({"date": str(r.txn_date or ""), "type": str(r.txn_type or ""), "qty": qty, "balance": round(running, 2), "ref_type": str(r.ref_type or ""), "ref_no": str(r.ref_no or ""), "remarks": str(r.remarks or "")})
#     result_rows.reverse()   
#     return {"rows": result_rows, "current_stock": round(running, 2)}

# @router.get("/inventory/{inventory_id}/grns")
# def inventory_grns(inventory_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT g.grn_number, g.grn_date, g.invoice_no, g.remarks, gi.received_qty, gi.accepted_qty, gi.rejected_qty, gi.placement FROM grn_items gi JOIN grns g ON gi.grn_id = g.id WHERE gi.inventory_id = :iid ORDER BY g.grn_date DESC LIMIT 50"), {"iid": inventory_id}).fetchall()
#     return {"rows": [{"grn_number": str(r.grn_number  or ""), "date": str(r.grn_date or ""), "invoice_no": str(r.invoice_no  or ""), "received": float(r.received_qty  or 0), "accepted": float(r.accepted_qty  or 0), "rejected": float(r.rejected_qty  or 0), "placement": str(r.placement   or ""), "remarks": str(r.remarks     or "")} for r in rows]}

# @router.get("/supplier/{supplier_id}/pos")
# def supplier_pos(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT id, po_number, po_date, total_amount, advance_amount, balance_amount, status, expected_delivery, delivery_status FROM purchase_orders WHERE supplier_id = :sid ORDER BY po_date DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     return {"rows": [{"id": int(r.id), "po_number": str(r.po_number), "date": str(r.po_date or ""), "total": float(r.total_amount or 0), "advance": float(r.advance_amount or 0), "balance": float(r.balance_amount or 0), "status": str(r.status or ""), "expected": str(r.expected_delivery or ""), "delivery_status": str(r.delivery_status or "")} for r in rows]}

# @router.get("/supplier/{supplier_id}/balance")
# def supplier_balance(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     r = db.execute(_t("SELECT COUNT(*) AS total_pos, COALESCE(SUM(total_amount), 0) AS total_ordered, COALESCE(SUM(advance_amount), 0) AS total_advance, COALESCE(SUM(balance_amount), 0) AS total_balance, COALESCE(SUM(CASE WHEN LOWER(status)!='completed' THEN balance_amount ELSE 0 END), 0) AS pending_balance, COUNT(CASE WHEN LOWER(status)='completed' THEN 1 END) AS completed_pos, COUNT(CASE WHEN LOWER(status)!='completed' THEN 1 END) AS open_pos FROM purchase_orders WHERE supplier_id = :sid"), {"sid": supplier_id}).fetchone()
#     return {"total_pos": int(r.total_pos), "total_ordered": float(r.total_ordered), "total_advance": float(r.total_advance), "total_balance": float(r.total_balance), "pending_balance": float(r.pending_balance), "completed_pos": int(r.completed_pos), "open_pos": int(r.open_pos)}

# @router.get("/supplier/{supplier_id}/items")
# def supplier_items(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT i.name, i.unit, COALESCE(SUM(poi.ordered_qty), 0) AS total_ordered, COALESCE(SUM(poi.received_qty), 0) AS total_received FROM purchase_order_items poi JOIN inventories i ON poi.inventory_id = i.id JOIN purchase_orders po ON poi.purchase_order_id = po.id WHERE po.supplier_id = :sid GROUP BY i.id, i.name, i.unit ORDER BY total_ordered DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     return {"rows": [{"name": str(r.name), "unit": str(r.unit or ""), "ordered": float(r.total_ordered), "received": float(r.total_received)} for r in rows]}

# @router.get("/supplier/{supplier_id}/payments")
# def supplier_payments(supplier_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT pt.pay_amount, pt.transaction_date, po.po_number FROM po_transactions pt JOIN purchase_orders po ON pt.po_id = po.id WHERE po.supplier_id = :sid ORDER BY pt.transaction_date DESC LIMIT 50"), {"sid": supplier_id}).fetchall()
#     total_paid = sum(float(r.pay_amount) for r in rows)
#     return {"total_paid": total_paid, "rows": [{"po_number": str(r.po_number), "amount": float(r.pay_amount), "date": str(r.transaction_date)[:10]} for r in rows]}

# @router.get("/po/{po_id}/items")
# def po_items(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT i.name, i.unit, poi.hsn, poi.ordered_qty, poi.received_qty, poi.unit_price, poi.discount, poi.tax_percent, poi.tax_amount, poi.line_total FROM purchase_order_items poi JOIN inventories i ON poi.inventory_id = i.id WHERE poi.purchase_order_id = :pid ORDER BY poi.id"), {"pid": po_id}).fetchall()
#     return {"rows": [{"name": str(r.name), "unit": str(r.unit or ""), "hsn": str(r.hsn or ""), "ordered": float(r.ordered_qty or 0), "received": float(r.received_qty or 0), "unit_price": float(r.unit_price or 0), "discount": float(r.discount or 0), "tax_percent": float(r.tax_percent or 0), "tax_amount": float(r.tax_amount or 0), "line_total": float(r.line_total or 0)} for r in rows]}

# @router.get("/po/{po_id}/payments")
# def po_payments(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT pay_amount, transaction_date FROM po_transactions WHERE po_id = :pid ORDER BY transaction_date DESC"), {"pid": po_id}).fetchall()
#     total_paid = sum(float(r.pay_amount) for r in rows)
#     return {"total_paid": total_paid, "rows": [{"amount": float(r.pay_amount), "date": str(r.transaction_date)[:10]} for r in rows]}

# @router.get("/po/{po_id}/status-log")
# def po_status_log(po_id: int, db: Session = Depends(get_db)):
#     from sqlalchemy import text as _t
#     rows = db.execute(_t("SELECT status, changed_at, remarks FROM po_status_logs WHERE purchase_order_id = :pid ORDER BY changed_at DESC"), {"pid": po_id}).fetchall()
#     return {"rows": [{"status": str(r.status or ""), "date": str(r.changed_at)[:16], "remarks": str(r.remarks or "")} for r in rows]}

# @router.get("/po/{po_id}/supplier")
# def po_supplier(po_id: int, db: Session = Depends(get_db)): 
#     from sqlalchemy import text as _t
#     row = db.execute(_t("SELECT s.* FROM purchase_orders p JOIN suppliers s ON p.supplier_id = s.id WHERE p.id = :id LIMIT 1"), {"id": po_id}).fetchone()
#     if not row: return {"error": "Supplier not found for this PO"}
#     return {"supplier": {"id": int(row.id), "name": str(row.supplier_name or ""), "code": str(getattr(row, "supplier_code", "N/A") or "N/A"), "mobile": str(getattr(row, "mobile", "N/A") or "N/A"), "city": str(getattr(row, "city", "N/A") or "N/A"), "email": str(getattr(row, "email", "N/A") or "N/A"), "gstin": str(getattr(row, "gstin", "N/A") or "N/A")}}

# @router.post("/feedback")
# def chatbot_feedback(payload: dict, db: Session = Depends(get_db)):
#     try:
#         with open("chat_history.json", "a", encoding="utf-8") as f:
#             f.write(json.dumps({"type": "feedback", "request_id": payload.get("request_id"), "query": payload.get("query"), "rating": payload.get("rating"), "summary": payload.get("summary"), "timestamp": datetime.datetime.now().isoformat()}, ensure_ascii=False) + "\n")
#         return {"ok": True}
#     except Exception as e: return {"ok": False, "error": str(e)}

# @router.get("/logs")
# def view_logs():
#     log_file = "chat_history.json"
#     if not os.path.exists(log_file): return {"message": "Abhi tak koi chat nahi hui."}
#     try:
#         with open(log_file, "r", encoding="utf-8") as f: logs = [json.loads(line) for line in f if line.strip()]
#         return {"total_chats": len(logs), "latest_logs": logs[::-1]}
#     except Exception as e: return {"error": str(e)}

# @router.delete("/logs/clear")
# def clear_logs(secret_key: str = "mewar123"):
#     if secret_key != "mewar@12345": return {"error": "Galat password."}
#     try: open("chat_history.json", "w", encoding="utf-8").close(); return {"success": True, "message": "Logs clear ho gaye."}
#     except Exception as e: return {"error": str(e)}

# # ── WHATSAPP INTEGRATION ──────────────────────────────────────────────────────
# async def process_chat_message(user_text: str) -> str:
#     db = SessionLocal()
#     try:
#         request_data = ChatRequest(query=user_text, role="superadmin")
#         response_dict = chatbot(request_data, db)
#         final_whatsapp_text = ""
#         if "results" in response_dict:
#             for res in response_dict["results"]:
#                 res_type = res.get("type")
#                 if res_type == "chat": final_whatsapp_text += res.get("message", "") + "\n\n"
#                 elif res_type == "po":
#                     final_whatsapp_text += f"📄 *PO No:* {res.get('po_no')}\n🏢 *Supplier:* {res.get('supplier')}\n💰 *Total:* ₹{res.get('total', 0):,.2f}\n⏳ *Balance:* ₹{res.get('balance', 0):,.2f}\n📌 *Status:* {res.get('status')}\n\n"
#                 elif res_type == "result":
#                     if "inventory" in res:
#                         inv = res["inventory"]
#                         final_whatsapp_text += f"📦 *{inv.get('name')}*\n📊 *Total Stock:* {res.get('total_stock')}\n📍 *Location:* {inv.get('placement')}\n\n"
#                 elif res_type == "dropdown":
#                     final_whatsapp_text += res.get("message", "") + "\n"
#                     for item in res.get("items", []): final_whatsapp_text += f"🔸 {item.get('name')}\n"
#                     final_whatsapp_text += "\n*(Kripya inme se ek naam type karein)*\n\n"
#                 elif res_type == "project":
#                     final_whatsapp_text += f"🏗️ *Project:* {res.get('project_name')}\n📌 *Status:* {res.get('category')}\n💰 *Budget:* ₹{res.get('amount', 0):,.2f}\n\n"
#         if not final_whatsapp_text.strip(): final_whatsapp_text = "Maaf karna, mujhe iska jawab nahi mil paya. 😅"
#         return final_whatsapp_text.strip()
#     except Exception as e: print(f"❌ WhatsApp AI Error: {e}"); return "Bhai, mere AI dimaag mein thoda error aa gaya hai. Thodi der mein try karein! 🙏"
#     finally: db.close()

# def generate_morning_briefing():
#     db = SessionLocal()
#     try:
#         po_res = db.execute(text("SELECT COUNT(id), SUM(balance_amount) FROM purchase_orders WHERE balance_amount>0 AND LOWER(status)!='completed'")).fetchone()
#         proj_res = db.execute(text("SELECT COUNT(id) FROM projects WHERE is_deleted=0 AND (end_date < CURRENT_DATE OR deadline < CURRENT_DATE) AND LOWER(status)!='completed'")).fetchone()
#         pending_pos = po_res[0] or 0; pending_amt = po_res[1] or 0.0; overdue = proj_res[0] or 0
#         msg = f"🌅 *Good Morning! Here is your Mewar ERP Daily Briefing:* 🌅\n\n📦 *Pending Purchase Orders:* {pending_pos} Orders (Total Due: ₹{float(pending_amt):,.2f})\n"
#         if overdue > 0: msg += f"🚨 *Alert:* {overdue} Projects apne deadline se late chal rahe hain!\n"
#         else: msg += f"✅ *Projects:* Sabhi projects time par chal rahe hain.\n"
#         print("\n" + "⭐"*30); print("🤖 AUTO-TRIGGERED MORNING BRIEFING:"); print(msg); print("⭐"*30 + "\n")
#     except Exception as e: print(f"❌ Morning Briefing Error: {e}")
#     finally: db.close()


## --------------------------------------------------------------------------------------------------------------------------------------
#                                           TEMPORARY LIVE TESTING(ATHAK)
#---------------------------------------------------------------------------------------------------------------------------------------

# ═══════════════════════════════════════════════════════════════════════════════
# MEWAR ERP — FINAL PRODUCTION CHATBOT
#
# Two-layer architecture:
#   Layer 1 — V2 Intent Engine  : structured queries → rich card UI
#             (SupplierCard, POCard, InventoryCard, RS Form, Project cards)
#   Layer 2 — NL2SQL AI Engine  : anything V2 couldn't answer → AI writes SQL
#             (SambaNova DeepSeek V3.1 → Gemini 2.5 Flash → Groq fallback)
#
# Route prefix: /v2-chatbot  (Chat.jsx connects here)
# ═══════════════════════════════════════════════════════════════════════════════

import re
import time
import json
import os
import difflib
import datetime

from fastapi import APIRouter, Depends, Query as _Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db, SessionLocal
from app.schemas.chat import ChatRequest
from app.services.ollama_engine import ask_ollama
from app.services.nl2sql_engine import generate_sql, format_answer
from apscheduler.schedulers.background import BackgroundScheduler

router = APIRouter(prefix="/v2-chatbot", tags=["Chatbot Final"])


# ── Role permissions ──────────────────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "supervisor":     ["inventory", "project", "general_chat"],
    "sales":          ["inventory", "general_chat"],
    "purchase":       ["inventory", "supplier", "po", "general_chat"],
    "purchase admin": ["inventory", "supplier", "po", "financials", "general_chat"],
    "store admin":    ["inventory", "po", "project", "general_chat"],
    "store department": ["inventory", "general_chat"],
    "hod":            ["inventory", "project", "supplier", "po", "financials", "general_chat"],
    "hr":             ["general_chat"],
}

# ── Off-topic guard ───────────────────────────────────────────────────────────
_ERP_KEYWORDS = {
    "supplier", "vendor", "party", "sup",
    "po", "order", "purchase", "transit", "delivery", "grn", "dispatch",
    "stock", "maal", "item", "inventory", "qty", "quantity",
    "project", "site", "crusher","how many",
    "balance", "payment", "invoice", "gst", "tax", "cgst", "sgst",
    "rokra", "paisa", "kharcha", "hisab",
    "mewar", "erp", "sale", "sales", "report", "employee", "account",
    # Hindi query verbs & RS form keywords
    "slip", "request", "banao", "batao", "dikhao", "milao", "details",
    "kitna", "kitne", "kahan", "kaisa", "kab", "lagao", "nikalo",
    # general — if user is asking a "how many / total / list" ERP question
    "total", "list", "count", "kitni", "sabhi", "saare",
    # query action words — any sentence starting with these is likely ERP
    "show", "find", "get", "check", "all", "mere", "mera",
}

_POOR_SIGNALS = [
    "theek se samajh nahi", "maaf kijiye", "clear batao", "clearly batao",
    "kripya", "naam batao", "couldn't understand", "i'm sorry",
    "it seems you", "please provide", "thoda clear",
    # item / supplier not found → try NL2SQL
    "nahi mila", "nahi mili", "nahi mile", "spelling check karoge",
    "koi supplier nahi", "koi project nahi",
    # Ollama reasoning fillers with no actual data — let NL2SQL answer instead
    "ek sec", "check karta hoon", "dekh raha hoon", "dhundh raha hoon",
    "data entry nahi hui",
]


_CLEARLY_OFFTOPIC = {
    "poem", "poetry", "joke", "weather", "recipe", "cook", "song", "lyrics",
    "translate", "movie", "cricket", "football", "game", "news", "capital of",
    "who is the president", "write a story", "tell me a story",
}

def _is_off_topic(query: str) -> bool:
    q = query.lower()
    # Short queries (≤3 words) are almost always item/name lookups — always allow
    if len(q.split()) <= 3:
        return False
    # Block only if the query matches a clearly non-ERP pattern
    if any(kw in q for kw in _CLEARLY_OFFTOPIC):
        return True
    # Block longer queries that have zero ERP keywords
    return not any(kw in q for kw in _ERP_KEYWORDS)


def _is_poor_result(response: dict) -> bool:
    results = response.get("results", [])
    data_types = {
        "result", "po", "dropdown", "project",
        "po_list", "po_summary", "project_list",
        "supplier_list", "supplier_items", "supplier_payments",
    }
    if any(r.get("type") in data_types for r in results):
        return False
    chat_text = " ".join(
        r.get("message", "") for r in results if r.get("type") == "chat"
    ).lower()
    return any(sig in chat_text for sig in _POOR_SIGNALS)


# ── FAISS disabled stubs ──────────────────────────────────────────────────────
def load_faiss_once(db: Session):
    pass


def smart_match(query_text, category="inventory"):
    return query_text


# ── Slang translation ─────────────────────────────────────────────────────────
def translate_slang(text: str):
    slang_map = {
        r'\bmaal\b':   'inventory',
        r'\bstock\b':  'inventory',
        r'\bkharcha\b': 'budget',
        r'\brokra\b':  'balance_amount',
        r'\bpaisa\b':  'amount',
        r'\bkitna\b':  'total_stock',
        r'\bitem\b':   'inventory',
    }
    for slang, official in slang_map.items():
        text = re.sub(slang, official, text, flags=re.IGNORECASE)
    return text


# ── Intent detection ──────────────────────────────────────────────────────────
def advanced_intent_detector(query: str):
    q = query.lower()
    score = {"po_search": 0, "supplier_search": 0, "project_search": 0, "search": 0}

    po_words  = ["po", "order", "orders", "purchase", "transit", "raste", "pending", "dispatch", "delivery"]
    sup_words = ["supplier", "vendor", "party", "contact", "mobile", "number", "account", "details", "profile"]
    proj_words = ["project", "site", "crusher", "running", "urgent", "completed", "refurbish"]
    inv_words  = ["stock", "maal", "item", "inventory", "quantity", "kitna", "qty", "available"]
    for w in po_words:   score["po_search"]      += 2 if w in q else 0
    for w in sup_words:  score["supplier_search"] += 2 if w in q else 0
    for w in proj_words: score["project_search"]  += 2 if w in q else 0
    for w in inv_words:  score["search"]          += 2 if w in q else 0

    if any(w in q for w in ["stock", "maal", "kitna"]) and any(w in q for w in ["supplier", "party"]):
        score["search"] += 3

    best = max(score, key=score.get)
    return best if score[best] > 0 else "search"


def clean_target_ultimate(target: str):
    noise = ["dikhao", "batao", "check", "ka", "ki", "ke", "mein", "inventory",
             "stock", "orders", "po", "list", "mujhe", "hai", "bhai", "details", "contact"]
    words   = target.split()
    cleaned = [w for w in words if w.lower() not in noise]
    return " ".join(cleaned) if cleaned else target


# ── Logger ────────────────────────────────────────────────────────────────────
def log_query_pro(user_role, query, intents, final_results, process_time):
    bot_reply = "No Response"
    if isinstance(final_results, dict) and "results" in final_results:
        bot_reply = final_results["results"]

    is_fail = any(w in str(bot_reply).lower()
                  for w in ["nahi mila", "error", "samajh nahi", "maaf kijiye", "permission nahi"])

    log_entry = {
        "date_time":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "role":         user_role,
        "user_query":   query,
        "intent":       str(intents),
        "bot_response": bot_reply,
        "time_taken_sec": round(process_time, 2),
        "status":       "Fail" if is_fail else "Success",
    }
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        print(f"Log error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN UNIFIED ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════
@router.post("")
def chatbot(request: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    raw_q  = request.query.strip()
    low_q  = raw_q.lower()

    # ── Off-topic guard ───────────────────────────────────────────────────────
    # Skip guard if user has prior conversation history (follow-up questions
    # like "why are they best" don't contain ERP keywords but are valid follow-ups)
    _has_history = bool(request.history)
    if _is_off_topic(raw_q) and not _has_history:
        return {"results": [{"type": "chat", "message": (
            "Bhai, main sirf Mewar ERP ke sawaalon mein help kar sakta hoon — "
            "Suppliers, Purchase Orders, Inventory, aur Projects. "
            "In topics par kuch poochho! 😊"
        )}]}

    # ── Role ──────────────────────────────────────────────────────────────────
    user_role = (getattr(request, "role", "guest") or "guest").lower().strip()

    # ── Fast-track: bare numeric ID → inventory lookup ────────────────────────
    if low_q.isdigit() and len(low_q) < 8:
        allowed = ROLE_PERMISSIONS.get(user_role, [])
        if user_role in ("superadmin", "super admin") or "inventory" in allowed:
            try:
                inv = db.execute(
                    text("SELECT id, name, classification, placement FROM inventories WHERE id = :id"),
                    {"id": int(low_q)},
                ).fetchone()
                if inv:
                    stock = float(db.execute(
                        text("SELECT SUM(CASE WHEN LOWER(txn_type)='in' THEN quantity ELSE -quantity END) "
                             "FROM stock_transactions WHERE inventory_id = :id"),
                        {"id": inv.id},
                    ).scalar() or 0)
                    cls = str(inv.classification or "").lower()
                    m = stock if "machining" in cls else 0
                    sf = stock if "semi" in cls else 0
                    f  = 0 if ("machining" in cls or "semi" in cls) else stock
                    return {"results": [{"type": "result",
                        "inventory": {"id": inv.id, "name": inv.name,
                                      "category": cls.upper(), "placement": inv.placement or "N/A"},
                        "total_stock": stock, "finish_stock": f,
                        "semi_finish_stock": sf, "machining_stock": m}]}
            except Exception:
                pass
        else:
            return {"results": [{"type": "chat", "message":
                f"Aapka role '{user_role.title()}' hai. Aapko Item Codes se search karne ki permission nahi hai."}]}

    # ── All queries go directly to NL2SQL ────────────────────────────────────
    intents = ["nl2sql"]
    nl2_resp = _nl2sql_response(raw_q, db, history=request.history or [])
    if nl2_resp:
        process_time = time.time() - start_time
        try:
            log_query_pro(user_role, raw_q, intents, nl2_resp, process_time)
        except Exception as e:
            print(f"Logger error: {e}")
        return nl2_resp

    return {"results": [{"type": "chat", "message": (
        "Maaf kijiye, main theek se samajh nahi paaya. "
        "Kripya dobara poochho."
    )}]}


_WRITE_PATTERN = re.compile(
    r'^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|CALL|EXEC)\b',
    re.IGNORECASE,
)

# ── NL2SQL helper ─────────────────────────────────────────────────────────────
def _nl2sql_response(raw_q: str, db, history: list = None) -> dict | None:
    """Run NL2SQL pipeline. Returns formatted response or None on failure."""
    history = history or []
    try:
        sql = generate_sql(raw_q, history=history)
        if _WRITE_PATTERN.match(sql):
            print(f"[NL2SQL] BLOCKED write SQL: {sql[:120]}")
            return {"results": [{"type": "chat", "message":
                "Yeh action allowed nahi hai. Main sirf data read kar sakta hoon — koi bhi changes karne ki permission nahi hai."}]}
        try:
            result  = db.execute(text(sql))
        except Exception as exec_err:
            print(f"[NL2SQL] failed: {exec_err}\n[SQL: {sql}]")
            sql = generate_sql(raw_q, previous_sql=sql, sql_error=str(exec_err), history=history)
            if _WRITE_PATTERN.match(sql):
                print(f"[NL2SQL] BLOCKED write SQL (retry): {sql[:120]}")
                return {"results": [{"type": "chat", "message":
                    "Yeh action allowed nahi hai. Main sirf data read kar sakta hoon — koi bhi changes karne ki permission nahi hai."}]}
            print(f"[NL2SQL] retry SQL: {sql[:120]}")
            result  = db.execute(text(sql))
        columns      = list(result.keys())
        rows         = [list(row) for row in result.fetchall()]
        answer       = format_answer(raw_q, rows, columns, history=history)
        parts        = [{"type": "chat", "message": answer}]
        if rows:
            rows_as_dicts = [dict(zip(columns, row)) for row in rows]
            parts.append({"type": "nl2sql_table", "rows": rows_as_dicts, "columns": columns})
        return {"results": parts}
    except Exception as e:
        print(f"[NL2SQL] failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# AUXILIARY ENDPOINTS — Supplier / PO / Inventory card buttons
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/select")
def handle_select(payload: dict, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    name = payload.get("selected", "")
    s = db.execute(_t("SELECT * FROM suppliers WHERE supplier_name=:n LIMIT 1"), {"n": name}).fetchone()
    if not s:
        return {"results": [{"type": "chat", "message": f"'{name}' nahi mila."}]}
    inv_items = db.execute(_t(
        "SELECT i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) as stock "
        "FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id "
        "WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"
    ), {"sid": s.id}).fetchall()
    return {"results": [
        {"type": "chat", "message": f"ye raha **{s.supplier_name}** ka profile:"},
        {"type": "result", "supplier": {
            "id": int(s.id), "name": str(s.supplier_name or ""),
            "code":   str(getattr(s, "supplier_code", "") or ""),
            "mobile": str(getattr(s, "mobile", "")        or ""),
            "city":   str(getattr(s, "city", "")          or ""),
            "email":  str(getattr(s, "email", "")         or ""),
            "gstin":  str(getattr(s, "gstin", "")         or ""),
        }, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]},
    ]}


@router.get("/inventory/{inventory_id}/details")
def inventory_details(inventory_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    inv = db.execute(_t("SELECT * FROM inventories WHERE id=:id LIMIT 1"), {"id": inventory_id}).fetchone()
    if not inv:
        return {"results": [{"type": "chat", "message": "Item nahi mila."}]}
    stock = float(db.execute(_t(
        "SELECT COALESCE(SUM(CASE WHEN LOWER(txn_type)='in' THEN quantity ELSE -quantity END),0) "
        "FROM stock_transactions WHERE inventory_id=:id"
    ), {"id": inventory_id}).scalar() or 0)
    cls       = (getattr(inv, "classification", "") or "").lower()
    finish    = 0 if ("machining" in cls or "semi" in cls) else stock
    semi      = stock if "semi"      in cls else 0
    machining = stock if "machining" in cls else 0
    return {"results": [
        {"type": "chat", "message": f"ye raha **{inv.name}** ka stock:"},
        {"type": "result",
         "inventory": {"id": int(inv.id), "name": str(inv.name or ""),
                       "category": cls.upper(), "placement": str(getattr(inv, "placement", "") or ""),
                       "unit": str(getattr(inv, "unit", "") or ""), "model": str(getattr(inv, "model", "") or ""),
                       "grade": str(getattr(inv, "grade", "") or "")},
         "total_stock": stock, "finish_stock": finish,
         "semi_finish_stock": semi, "machining_stock": machining},
    ]}


@router.get("/inventory/{inventory_id}/po-history")
def inventory_po_history(inventory_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT po.po_number, po.po_date, s.supplier_name,
               poi.ordered_qty, poi.unit_price, po.status
        FROM purchase_order_items poi
        JOIN purchase_orders po ON poi.purchase_order_id=po.id
        JOIN suppliers s ON po.supplier_id=s.id
        WHERE poi.inventory_id=:iid ORDER BY po.po_date DESC LIMIT 20
    """), {"iid": inventory_id}).fetchall()
    return {"rows": [{"po": str(r.po_number), "date": str(r.po_date)[:10],
                      "supplier": str(r.supplier_name), "qty": float(r.ordered_qty or 0),
                      "price": float(r.unit_price or 0), "status": str(r.status)} for r in rows]}


@router.get("/inventory/{inventory_id}/suppliers")
def inventory_suppliers(inventory_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT DISTINCT s.id, s.supplier_name, s.mobile, s.city
        FROM stock_transactions st JOIN suppliers s ON st.supplier_id=s.id
        WHERE st.inventory_id=:iid
    """), {"iid": inventory_id}).fetchall()
    return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""),
                      "mobile": str(r.mobile or ""), "city": str(r.city or "")} for r in rows]}


@router.get("/supplier/{supplier_id}/card")
def supplier_card(supplier_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    s = db.execute(_t("SELECT * FROM suppliers WHERE id=:id LIMIT 1"), {"id": supplier_id}).fetchone()
    if not s:
        return {"results": [{"type": "chat", "message": "Supplier nahi mila."}]}
    inv_items = db.execute(_t(
        "SELECT i.name, SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) AS stock "
        "FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id "
        "WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock!=0"
    ), {"sid": supplier_id}).fetchall()
    return {"results": [
        {"type": "chat", "message": f"ye raha **{s.supplier_name}** ka profile:"},
        {"type": "result", "supplier": {
            "id": int(s.id), "name": str(s.supplier_name or ""),
            "code":   str(getattr(s, "supplier_code", "") or ""),
            "mobile": str(getattr(s, "mobile", "")        or ""),
            "city":   str(getattr(s, "city", "")          or ""),
            "email":  str(getattr(s, "email", "")         or ""),
            "gstin":  str(getattr(s, "gstin", "")         or ""),
        }, "items": [{"name": r.name, "stock": float(r.stock)} for r in inv_items]},
    ]}


@router.get("/supplier/{supplier_id}/pos")
def supplier_pos(supplier_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t(
        "SELECT p.id, p.po_number, p.po_date, p.total_amount, p.balance_amount, p.status "
        "FROM purchase_orders p WHERE p.supplier_id=:sid ORDER BY p.po_date DESC LIMIT 50"
    ), {"sid": supplier_id}).fetchall()
    return {"rows": [{"type": "po", "id": int(r.id), "po_no": str(r.po_number),
                      "date": str(r.po_date), "total": float(r.total_amount or 0),
                      "balance": float(r.balance_amount or 0), "status": str(r.status)} for r in rows]}


@router.get("/supplier/{supplier_id}/balance")
def supplier_balance(supplier_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    r = db.execute(_t(
        "SELECT COALESCE(SUM(balance_amount),0) as bal, COUNT(id) as cnt "
        "FROM purchase_orders WHERE supplier_id=:sid AND LOWER(status)!='completed'"
    ), {"sid": supplier_id}).fetchone()
    s = db.execute(_t("SELECT supplier_name FROM suppliers WHERE id=:id"), {"sid": supplier_id}).fetchone()
    name = s.supplier_name if s else "Supplier"
    return {"balance": float(r.bal or 0), "order_count": int(r.cnt or 0),
            "message": f"**{name}** ka total pending balance: **₹{float(r.bal or 0):,.2f}** ({r.cnt} orders)"}


@router.get("/supplier/{supplier_id}/items")
def supplier_items(supplier_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT i.id, i.name,
               SUM(CASE WHEN LOWER(t.txn_type)='in' THEN t.quantity ELSE -t.quantity END) AS stock
        FROM inventories i JOIN stock_transactions t ON i.id=t.inventory_id
        WHERE t.supplier_id=:sid GROUP BY i.id,i.name HAVING stock>0
    """), {"sid": supplier_id}).fetchall()
    return {"rows": [{"id": int(r.id), "name": str(r.name), "stock": float(r.stock)} for r in rows]}


@router.get("/supplier/{supplier_id}/payments")
def supplier_payments(supplier_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT pt.pay_amount, pt.transaction_date, po.po_number
        FROM po_transactions pt JOIN purchase_orders po ON pt.po_id=po.id
        WHERE po.supplier_id=:sid ORDER BY pt.transaction_date DESC LIMIT 30
    """), {"sid": supplier_id}).fetchall()
    total = sum(float(r.pay_amount) for r in rows)
    return {"total_paid": total,
            "rows": [{"amount": float(r.pay_amount), "date": str(r.transaction_date)[:10],
                      "po": str(r.po_number)} for r in rows]}


@router.get("/po/{po_id}/items")
def po_items(po_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("""
        SELECT i.name, i.unit, poi.hsn, poi.ordered_qty, poi.received_qty,
               poi.unit_price, poi.discount, poi.tax_percent, poi.tax_amount, poi.line_total
        FROM purchase_order_items poi JOIN inventories i ON poi.inventory_id=i.id
        WHERE poi.purchase_order_id=:pid ORDER BY poi.id
    """), {"pid": po_id}).fetchall()
    return {"rows": [{"name": str(r.name), "unit": str(r.unit or ""), "hsn": str(r.hsn or ""),
                      "ordered": float(r.ordered_qty or 0), "received": float(r.received_qty or 0),
                      "unit_price": float(r.unit_price or 0), "discount": float(r.discount or 0),
                      "tax_percent": float(r.tax_percent or 0), "tax_amount": float(r.tax_amount or 0),
                      "line_total": float(r.line_total or 0)} for r in rows]}


@router.get("/po/{po_id}/payments")
def po_payments(po_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows  = db.execute(_t("SELECT pay_amount, transaction_date FROM po_transactions WHERE po_id=:pid ORDER BY transaction_date DESC"), {"pid": po_id}).fetchall()
    total = sum(float(r.pay_amount) for r in rows)
    return {"total_paid": total, "rows": [{"amount": float(r.pay_amount), "date": str(r.transaction_date)[:10]} for r in rows]}


@router.get("/po/{po_id}/status-log")
def po_status_log(po_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    rows = db.execute(_t("SELECT status, changed_at, remarks FROM po_status_logs WHERE purchase_order_id=:pid ORDER BY changed_at DESC"), {"pid": po_id}).fetchall()
    return {"rows": [{"status": str(r.status or ""), "date": str(r.changed_at)[:16], "remarks": str(r.remarks or "")} for r in rows]}


@router.get("/po/{po_id}/supplier")
def po_supplier(po_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    row = db.execute(_t("SELECT s.* FROM purchase_orders p JOIN suppliers s ON p.supplier_id=s.id WHERE p.id=:id LIMIT 1"), {"id": po_id}).fetchone()
    if not row:
        return {"error": "Supplier not found"}
    return {"supplier": {"id": int(row.id), "name": str(row.supplier_name or ""),
                         "code": str(getattr(row,"supplier_code","N/A") or "N/A"),
                         "mobile": str(getattr(row,"mobile","N/A") or "N/A"),
                         "city":   str(getattr(row,"city","N/A")   or "N/A"),
                         "email":  str(getattr(row,"email","N/A")  or "N/A"),
                         "gstin":  str(getattr(row,"gstin","N/A")  or "N/A")}}


@router.get("/po/{po_id}/card")
def po_card(po_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    row = db.execute(_t("SELECT p.*, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id WHERE p.id=:id LIMIT 1"), {"id": po_id}).fetchone()
    if not row:
        return {"results": [{"type": "chat", "message": "PO nahi mila."}]}
    return {"results": [
        {"type": "chat", "message": f"ye raha **{row.po_number}** ka detail:"},
        {"type": "po", "id": int(row.id), "po_no": str(row.po_number), "supplier": str(row.supplier_name or ""),
         "date": str(row.po_date), "total": float(row.total_amount or 0),
         "advance": float(row.advance_amount or 0), "balance": float(row.balance_amount or 0),
         "status": str(row.status).capitalize()},
    ]}


# ── Quick search ──────────────────────────────────────────────────────────────

@router.get("/quick-search/supplier")
def quick_search_supplier(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    if not q.strip():
        rows = db.execute(_t("SELECT id, supplier_name, city, mobile FROM suppliers ORDER BY id DESC LIMIT :l"), {"l": limit}).fetchall()
    else:
        words = q.strip().lower().split()
        cond  = " AND ".join(f"(LOWER(supplier_name) LIKE :w{i} OR LOWER(COALESCE(city,'')) LIKE :w{i} OR COALESCE(mobile,'') LIKE :w{i})" for i in range(len(words)))
        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        params["l"] = limit
        rows = db.execute(_t(f"SELECT id, supplier_name, city, mobile FROM suppliers WHERE {cond} ORDER BY supplier_name LIMIT :l"), params).fetchall()
    return {"rows": [{"id": int(r.id), "name": str(r.supplier_name or ""), "city": str(r.city or ""), "mobile": str(r.mobile or "")} for r in rows]}


@router.get("/quick-search/po")
def quick_search_po(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    base = "SELECT p.id, p.po_number, p.po_date, p.total_amount, p.status, s.supplier_name FROM purchase_orders p LEFT JOIN suppliers s ON p.supplier_id=s.id "
    if not q.strip():
        rows = db.execute(_t(base + "ORDER BY p.id DESC LIMIT :l"), {"l": limit}).fetchall()
    else:
        words  = q.strip().lower().split()
        cond   = " AND ".join(f"(LOWER(p.po_number) LIKE :w{i} OR LOWER(COALESCE(s.supplier_name,'')) LIKE :w{i} OR LOWER(COALESCE(p.status,'')) LIKE :w{i})" for i in range(len(words)))
        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        params["l"] = limit
        rows = db.execute(_t(base + f"WHERE {cond} ORDER BY p.po_date DESC LIMIT :l"), params).fetchall()
    return {"rows": [{"id": int(r.id), "po_number": str(r.po_number or ""), "date": str(r.po_date or ""),
                      "total": float(r.total_amount or 0), "status": str(r.status or ""),
                      "supplier": str(r.supplier_name or "")} for r in rows]}


@router.get("/quick-search/inventory")
def quick_search_inventory(q: str = "", limit: int = 60, db: Session = Depends(get_db)):
    from sqlalchemy import text as _t
    base = ("SELECT i.id, i.name, i.unit, COALESCE(SUM(CASE WHEN LOWER(st.txn_type)='in' THEN st.quantity ELSE -st.quantity END),0) AS stock "
            "FROM inventories i LEFT JOIN stock_transactions st ON st.inventory_id=i.id WHERE i.is_deleted=0 ")
    if not q.strip():
        rows = db.execute(_t(base + "GROUP BY i.id,i.name,i.unit ORDER BY i.id DESC LIMIT :l"), {"l": limit}).fetchall()
    else:
        words  = q.strip().lower().split()
        cond   = " AND ".join(f"LOWER(i.name) LIKE :w{i}" for i in range(len(words)))
        params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
        params["l"] = limit
        rows = db.execute(_t(base + f"AND {cond} GROUP BY i.id,i.name,i.unit ORDER BY i.name LIMIT :l"), params).fetchall()
    return {"rows": [{"id": int(r.id), "name": str(r.name or ""), "unit": str(r.unit or ""), "stock": float(r.stock or 0)} for r in rows]}


# ── Feedback & Logs ───────────────────────────────────────────────────────────

@router.post("/feedback")
def chatbot_feedback(payload: dict, db: Session = Depends(get_db)):
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "type":       "feedback",
                "request_id": payload.get("request_id"),
                "query":      payload.get("query"),
                "rating":     payload.get("rating"),
                "summary":    payload.get("summary"),
                "timestamp":  datetime.datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/logs")
def view_logs():
    log_file = "chat_history.json"
    if not os.path.exists(log_file):
        return {"message": "Abhi tak koi chat nahi hui."}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f if line.strip()]
        return {"total_chats": len(logs), "latest_logs": logs[::-1]}
    except Exception as e:
        return {"error": str(e)}


@router.delete("/logs/clear")
def clear_logs(secret_key: str = "mewar123"):
    if secret_key != "mewar@12345":
        return {"error": "Galat password. Permission nahi hai."}
    try:
        open("chat_history.json", "w", encoding="utf-8").close()
        return {"success": True, "message": "Logs clear ho gaye."}
    except Exception as e:
        return {"error": str(e)}


# ── Morning briefing (called by APScheduler in main.py) ──────────────────────

def generate_morning_briefing():
    db = SessionLocal()
    try:
        po_res      = db.execute(text("SELECT COUNT(id), SUM(balance_amount) FROM purchase_orders WHERE balance_amount>0 AND LOWER(status)!='completed'")).fetchone()
        proj_res    = db.execute(text("SELECT COUNT(id) FROM projects WHERE is_deleted=0 AND (end_date < CURRENT_DATE OR deadline < CURRENT_DATE) AND LOWER(status)!='completed'")).fetchone()
        pending_pos = po_res[0] or 0
        pending_amt = po_res[1] or 0.0
        overdue     = proj_res[0] or 0
        msg = (f"Good Morning! Mewar ERP Daily Briefing:\n"
               f"Pending POs: {pending_pos} (Due: Rs {float(pending_amt):,.2f})\n" +
               (f"ALERT: {overdue} projects are overdue!\n" if overdue > 0 else "All projects on time.\n"))
        print(msg)
    except Exception as e:
        print(f"Morning briefing error: {e}")
    finally:
        db.close()




##ggfdgdfgd