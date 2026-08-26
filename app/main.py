# import os
# from contextlib import asynccontextmanager
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from apscheduler.schedulers.background import BackgroundScheduler
# from app.services.love_brain import load_core_services
# load_core_services()

# # Database
# from app.db.database import get_db

# # Routers & Background Tasks
# from app.routers.chatbot import router as chatbot_router, load_faiss_once, generate_morning_briefing
# from app.routers.auth import router as auth_router
# from app.routers.inventory_dropdown import router as inventory_router
# from app.routers.inventory_smart import router as inventory_smart_router


# #whatsapp router
# from app.routers.whatsapp import router as whatsapp_router

# # ==========================================
# # 🚀 LIFESPAN (Server start aur stop hone ka logic)
# # ==========================================
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("🚀 App starting up...")
    
#     # 1. 🧠 FAISS Memory Load Karna
#     print("🔄 Loading FAISS Memory...")
#     db_gen = get_db()
#     db = next(db_gen) 
#     try:
#         load_faiss_once(db)
#         print("✅ FAISS Memory Loaded successfully!")
#     except Exception as e:
#         print(f"⚠️ FAISS Load Error: {e}")
#     finally:
#         db_gen.close()

#     # 2. ⏰ Scheduler (Automation) Start Karna
#     scheduler = BackgroundScheduler()
#     # LIVE MODE: Roz subah 9:00 baje report banayega
#     scheduler.add_job(generate_morning_briefing, 'cron', hour=9, minute=0)
#     scheduler.start()
#     print("⏰ Background Automation Scheduler Started!")
    
#     # -----------------------------------
#     yield  # <-- Yahan aapka main server mast chalta rahega
#     # -----------------------------------
    
#     # 3. 🛑 Server Band hone par sab safe close karna
#     scheduler.shutdown()
#     print("🛑 Server and Scheduler Stopped Safely!")


# # Initialize FastAPI with the lifespan event
# app = FastAPI(title="Mewar ERP API", lifespan=lifespan)

# # ==========================================
# # 🛡️ CORS SETTINGS (Bulletproof for Meeting)
# # ==========================================
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], 
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ==========================================
# # 🔗 INCLUDE ROUTERS
# # ==========================================
# app.include_router(chatbot_router)
# app.include_router(auth_router)
# app.include_router(inventory_router)
# app.include_router(inventory_smart_router)

# # Agar WhatsApp integrate kar liya hai toh iska '#' hata dena:

# app.include_router(whatsapp_router,prefix="/whatsapp")

# # ==========================================
# # 🟢 ROOT ENDPOINT
# # ==========================================
# @app.get("/")
# def root():
#     return {"message": "Mewar ERP API is running perfectly! 🚀"}

 #------------------------------------------------------------------------------------------------------------------------------
 # ============================================================================================================================   

# #athak code

# import os
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# # ==========================================
# # 🚀 ROUTER IMPORTS
# # ==========================================
# #from app.routers.chatbot import router as chatbot_router
# from app.routers.auth import router as auth_router
# from app.routers.inventory_dropdown import router as inventory_router
# from app.routers.inventory_smart import router as inventory_smart_router
# from app.routers.chatbot import router as chatbot_router

# # Initialize FastAPI
# app = FastAPI(title="Mewar ERP API", redirect_slashes=True)

# # ==========================================
# # 🛡️ CORS SETTINGS
# # ==========================================
# _cors_raw = os.getenv(
#     "CORS_ORIGINS",
#     "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
# ).strip()

# # If CORS_ORIGINS is "*", allow all origins (public API)
# if _cors_raw == "*":
#     allowed_origins = ["*"]
#     _allow_credentials = False   # browsers reject credentials + wildcard
# else:
#     allowed_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
#     _allow_credentials = True

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=allowed_origins,
#     allow_credentials=_allow_credentials,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ==========================================
# # 🔗 INCLUDE ROUTERS
# # ==========================================
# app.include_router(chatbot_router)
# app.include_router(auth_router)
# app.include_router(inventory_router)
# app.include_router(inventory_smart_router)

# # ==========================================
# # 🟢 ROOT ENDPOINT
# # ==========================================
# @app.get("/")
# def root():
#     return {"message": "Mewar ERP API running"}


#------------------------------------------------------------------------------------------------------------------------------
 # ============================================================================================================================  

import os
import json
import asyncio
import time             # <-- NAYA IMPORT: PR Number generation ke liye
import datetime         # <-- NAYA IMPORT: Date save karne ke liye
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from sqlalchemy import text  
from pydantic import BaseModel      # <-- NAYA IMPORT: Data Validation ke liye
from typing import List, Optional   # <-- NAYA IMPORT: Lists handle karne ke liye

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
# 🛡️ CORS SETTINGS (UPDATED FOR LOCAL & LIVE)
# ==========================================
# Yahan humne Local (5500) aur Live (HF Space) dono add kar diye hain
allowed_origins = [
    "http://127.0.0.1:5500",                 # Local Testing URL 1
    "http://localhost:5500",                 # Local Testing URL 2
    "http://localhost:5173",                 # Default Vue/React port
    "http://127.0.0.1:5173",
    "http://localhost:3000",                 # Default Node port
    "https://love14-mewar-erp-bot.hf.space", # Live Hugging Face Space
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
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
# 📊 REAL-TIME KPI API FOR DASHBOARD
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

        # 3. Low Stock Items (MySQL 5.7 Compatible Subquery)
        low_stock_query = text("""
            SELECT COUNT(*) FROM (
                SELECT tr.inventory_id, 
                ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0) - COALESCE(p_po.incoming_qty, 0)) as shortage 
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
                    ) AS ReqUnion GROUP BY inventory_id
                ) tr 
                LEFT JOIN (
                    SELECT inventory_id, SUM(quantity) as cons_qty
                    FROM stock_transactions
                    WHERE LOWER(txn_type) = 'out'
                      AND (project_id IN (SELECT id FROM projects WHERE status = 'in_progress') OR machine_id IN (
                          SELECT DISTINCT machine_id FROM stock_transactions 
                          WHERE project_id IN (SELECT id FROM projects WHERE status = 'in_progress') AND machine_id IS NOT NULL
                      ))
                    GROUP BY inventory_id
                ) c ON tr.inventory_id = c.inventory_id
                LEFT JOIN (
                    SELECT inventory_id,
                        (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)
                        -
                        SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail
                    FROM stock_transactions GROUP BY inventory_id
                ) a ON tr.inventory_id = a.inventory_id 
                LEFT JOIN (
                    SELECT poi.inventory_id, SUM(poi.ordered_qty) as incoming_qty
                    FROM purchase_order_items poi
                    JOIN purchase_orders po ON poi.purchase_order_id = po.id
                    WHERE po.status IN ('Draft', 'Submitted', 'Approved', 'Pending') 
                    GROUP BY poi.inventory_id
                ) p_po ON tr.inventory_id = p_po.inventory_id
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

# ==========================================
# ⚡ NEW: AUTO-PR GENERATION API (CHATBOT INTEGRATION)
# ==========================================
class PRItemSchema(BaseModel):
    item_name: str
    qty: float

class PRCreateSchema(BaseModel):
    priority: Optional[str] = "NORMAL"
    status: Optional[str] = "DRAFT"
    requested_by: Optional[int] = 9  # 🟢 Default name set kiya
    items: List[PRItemSchema]

@app.post("/api/purchase_request/store")
def store_purchase_request(payload: PRCreateSchema, db: Session = Depends(get_db)):
    """
    Yeh endpoint chatbot ke 'Generate PR' button se selected items ka data lega,
    database mein ek nayi Purchase Request (PR) aur uske items save karega.
    """
    try:
        # 1. Unique PR Number generate karna
        last_pr = db.execute(text("SELECT pr_no FROM purchase_requests ORDER BY id DESC LIMIT 1")).fetchone()
        if last_pr and last_pr[0]:
            try:
                last_num = int(last_pr[0].split('-')[-1])
                new_pr_no = f"PR-{last_num + 1}"
            except:
                new_pr_no = f"PR-{int(time.time())}"
        else:
            new_pr_no = "PR-101"

        request_date = datetime.date.today().strftime("%Y-%m-%d")
        total_qty = sum(item.qty for item in payload.items)

        # 2. Main `purchase_requests` table mein entry insert karna (WITH requested_by)
        insert_pr_query = text("""
            INSERT INTO purchase_requests (pr_no, request_date, requested_by, priority, status, total_qty, created_at, updated_at)
            VALUES (:pr_no, :request_date, :requested_by, :priority, :status, :total_qty, NOW(), NOW())
        """)
        
        db.execute(insert_pr_query, {
            "pr_no": new_pr_no,
            "request_date": request_date,
            "requested_by": payload.requested_by,  # 🟢 Parameter pass kiya
            "priority": payload.priority,
            "status": payload.status,
            "total_qty": total_qty
        })
        
        # Abhi insert hui PR ki ID nikalna
        pr_id_res = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
        pr_id = pr_id_res[0]

        # 3. Har ek selected item ko `purchase_request_items` table mein dalna
        for item in payload.items:
            inv = db.execute(
                text("SELECT id FROM inventories WHERE name LIKE :name AND is_deleted=0 LIMIT 1"),
                {"name": f"%{item.item_name}%"}
            ).fetchone()
            
            inventory_id = inv[0] if inv else 1

            insert_item_query = text("""
                INSERT INTO purchase_request_items 
                (purchase_request_id, item_id, description, requested_qty, uom, status, created_at)
                VALUES (:pr_id, :inv_id, :desc, :qty, 'Nos', 'Pending', NOW())
            """)
            
            db.execute(insert_item_query, {
                "pr_id": pr_id,
                "inv_id": inventory_id,
                "desc": item.item_name,
                "qty": item.qty
            })

        db.commit()

        print(f"✅ Success: Generated {new_pr_no} with {len(payload.items)} items!")
        return {
            "status": "success",
            "message": "Purchase Request successfully generated!",
            "pr_no": new_pr_no,
            "pr_id": pr_id
        }

    except Exception as e:
        db.rollback()
        print(f"❌ PR Generation Error: {str(e)}")
        return {"status": "error", "message": str(e)}



@app.delete("/api/purchase_request/delete/{pr_no}")
def delete_test_pr(pr_no: str, db: Session = Depends(get_db)):
    """
    Yeh API test ki hui PR ko safely database se uda degi.
    Use karne ke liye: http://.../docs par jakar test kar sakte hain.
    """
    try:
        # 1. Pehle check karo ki PR exist karti hai ya nahi
        pr = db.execute(
            text("SELECT id FROM purchase_requests WHERE pr_no = :pr_no"), 
            {"pr_no": pr_no}
        ).fetchone()
        
        if not pr:
            return {"status": "error", "message": f"Bhai, {pr_no} database mein nahi mili!"}
        
        pr_id = pr[0]
        
        # 2. Pehle child table (items) se delete karo taaki Foreign Key error na aaye
        db.execute(
            text("DELETE FROM purchase_request_items WHERE purchase_request_id = :pr_id"), 
            {"pr_id": pr_id}
        )
        
        # 3. Fir main table se delete kar do
        db.execute(
            text("DELETE FROM purchase_requests WHERE id = :pr_id"), 
            {"pr_id": pr_id}
        )
        
        # 4. Changes save karo
        db.commit()
        
        print(f"🧹 Kachra saaf! {pr_no} successfully deleted.")
        return {"status": "success", "message": f"{pr_no} humesha ke liye delete ho gayi!"}

    except Exception as e:
        db.rollback()
        print(f"❌ Delete Error: {str(e)}")
        return {"status": "error", "message": str(e)}

    
# ---------------------------------------------------------
# 🚀 ROUTES: FOR AGENT 3D DASHBOARD
# ---------------------------------------------------------
@app.get("/agent")
def serve_agent_dashboard():
    # Ye route hit hote hi aapki nayi HTML file serve ho jayegi
    return FileResponse("agent_ui/agent_dashboard.html")

@app.get("/command_center/command_center.html")
def serve_command_center():
    # Ye route Gen UI button click hone par html file return karega
    return FileResponse("command_center/command_center.html")

@app.get("/object_0.glb")
def serve_3d_model():
    # Ye route browser ko 3D file dega
    return FileResponse("agent_ui/object_0.glb")

@app.get("/chat")
def serve_chatbot_ui():
    return FileResponse("frontend/mewar.html")