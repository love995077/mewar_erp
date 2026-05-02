from fastapi import FastAPI
from app.routers.chatbot import router as chatbot_router, load_faiss_once
from app.routers.auth import router as auth_router
# from app.routers.supplier import router as supplier_router
from app.routers.inventory_dropdown import router as inventory_router
# from app.routers.supplier_search import router as supplier_search_router
from app.routers.inventory_smart import router as inventory_smart_router
from app.db.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.routers.chatbot import generate_morning_briefing, BackgroundScheduler

app = FastAPI()

# 🛡️ CORS Setup (Add this)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Sab jagah se access allow karne ke liye
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_faiss_in_background():
    print("🔄 Background Thread Started for FAISS...")
    db_gen = get_db()
    db = next(db_gen) 
    try:
        load_faiss_once(db)
    except Exception as e:
        print(f"⚠️ Background Load Error: {e}")
    finally:
        db_gen.close()

@app.on_event("startup")
def startup_event():
    print("🚀 App starting up... Initializing FAISS memory.")
    db_gen = get_db()
    db = next(db_gen) 
    try:
        load_faiss_once(db)
    finally:
        db_gen.close()

app.include_router(chatbot_router)
app.include_router(auth_router)
# app.include_router(supplier_router)
app.include_router(inventory_router)
# app.include_router(supplier_search_router)
app.include_router(inventory_smart_router)

@app.get("/")
def root():
    return {"message": "Mewar ERP API running"}


# ⏰ SCHEDULER START KARENGE
scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    # TEST MODE: Har 1 minute me chalega
    #scheduler.add_job(generate_morning_briefing, 'interval', minutes=1)
    
    #LIVE MODE: Jab final karna ho toh isko use karenge (Subah 9 baje)
    scheduler.add_job(generate_morning_briefing, 'cron', hour=9, minute=0)
    
    scheduler.start()
    print("⏰ Proactive Automation Scheduler Started!")

 #------------------------------------------------------------------------------------------------------------------------------
 # ============================================================================================================================   

# #athak code

# import os
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# # ==========================================
# # 🚀 ROUTER IMPORTS
# # ==========================================
# from app.routers.chatbot import router as chatbot_router
# from app.routers.auth import router as auth_router
# from app.routers.inventory_dropdown import router as inventory_router
# from app.routers.inventory_smart import router as inventory_smart_router

# # Initialize FastAPI
# app = FastAPI(title="Mewar ERP API")

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