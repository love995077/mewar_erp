# from fastapi import FastAPI
# from app.routers.chatbot import router as chatbot_router, load_faiss_once
# from app.routers.auth import router as auth_router
# # from app.routers.supplier import router as supplier_router
# from app.routers.inventory_dropdown import router as inventory_router
# # from app.routers.supplier_search import router as supplier_search_router
# from app.routers.inventory_smart import router as inventory_smart_router
# from app.db.database import get_db
# from fastapi.middleware.cors import CORSMiddleware
# from app.routers.chatbot import generate_morning_briefing, BackgroundScheduler

# app = FastAPI()

# # 🛡️ CORS Setup (Add this)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], # Sab jagah se access allow karne ke liye
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# def run_faiss_in_background():
#     print("🔄 Background Thread Started for FAISS...")
#     db_gen = get_db()
#     db = next(db_gen) 
#     try:
#         load_faiss_once(db)
#     except Exception as e:
#         print(f"⚠️ Background Load Error: {e}")
#     finally:
#         db_gen.close()

# @app.on_event("startup")
# def startup_event():
#     print("🚀 App starting up... Initializing FAISS memory.")
#     db_gen = get_db()
#     db = next(db_gen) 
#     try:
#         load_faiss_once(db)
#     finally:
#         db_gen.close()

# app.include_router(chatbot_router)
# app.include_router(auth_router)
# # app.include_router(supplier_router)
# app.include_router(inventory_router)
# # app.include_router(supplier_search_router)
# app.include_router(inventory_smart_router)

# @app.get("/")
# def root():
#     return {"message": "Mewar ERP API running"}


# # ⏰ SCHEDULER START KARENGE
# scheduler = BackgroundScheduler()

# @app.on_event("startup")
# def start_scheduler():
#     # TEST MODE: Har 1 minute me chalega
#     #scheduler.add_job(generate_morning_briefing, 'interval', minutes=1)
    
#     #LIVE MODE: Jab final karna ho toh isko use karenge (Subah 9 baje)
#     scheduler.add_job(generate_morning_briefing, 'cron', hour=9, minute=0)
    
#     scheduler.start()
#     print("⏰ Proactive Automation Scheduler Started!")

 #------------------------------------------------------------------------------------------------------------------------------
 # ============================================================================================================================   


import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine
#from app.middleware.rate_limit import RateLimitMiddleware
from app.routers.auth import router as auth_router
from app.routers.inventory_dropdown import router as inventory_router
from app.routers.inventory_smart import router as inventory_smart_router
#from app.routers.v2_chatbot import router as v2_chatbot_router
#from app.services.v2_ollama_engine import health_check as llm_health
#from app.services.entity_resolver import cache_stats as resolver_stats

#from fastapi import FastAPI
from app.routers.chatbot import router as chatbot_router, load_faiss_once
from app.routers.auth import router as auth_router
# from app.routers.supplier import router as supplier_router
#from app.routers.inventory_dropdown import router as inventory_router
# from app.routers.supplier_search import router as supplier_search_router
#from app.routers.inventory_smart import router as inventory_smart_router
from app.db.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.routers.chatbot import generate_morning_briefing, BackgroundScheduler

app = FastAPI()

_cors_raw = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
).strip()

# If CORS_ORIGINS is "*", allow all origins (public API)
if _cors_raw == "*":
    allowed_origins = ["*"]
    _allow_credentials = False   # browsers reject credentials + wildcard
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

# Per-IP rate limit on chatbot to protect upstream LLM tokens & DB pool.
#


app.include_router(chatbot_router)
app.include_router(auth_router)
# app.include_router(supplier_router)
app.include_router(inventory_router)
# app.include_router(supplier_search_router)
app.include_router(inventory_smart_router)

@app.get("/")
def root():
    return {"message": "Mewar ERP API running"}


# @app.get("/health")
# def health():
#     """Liveness + dependency health for load balancers / uptime monitors."""
#     db_ok = True
#     db_err = None
#     try:
#         with engine.connect() as conn:
#             conn.execute(text("SELECT 1"))
#     except Exception as e:
#         db_ok = False
#         db_err = str(e)[:200]
#     llm = llm_health()
#     status = "ok" if db_ok and (llm.get("openrouter") or llm.get("cerebras") or llm.get("ollama")) else "degraded"
#     return {
#         "status": status,
#         "db": {"ok": db_ok, "error": db_err},
#         "llm": llm,
#         "entity_cache": resolver_stats(),
#     }

# @app.get("/che     ck-db")
# def check_db(db: Session = Depends(get_db)):
#     result = db.execute(text("SHOW TABLES;"))
#     tables = result.fetchall()
#     return [row[0] for row in tables]

# @app.get("/inventory")
# def get_inventory(db: Session = Depends(get_db)):
#     result = db.execute(text("SELECT * FROM inventories;"))
#     rows = result.fetchall()
#     return {
#         "table": "inventories",
#         "count": len(rows),
#         "data": [dict(row._mapping) for row in rows]
#     }