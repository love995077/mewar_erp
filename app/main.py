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

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ==========================================
# 🚀 ROUTER IMPORTS
# ==========================================
#from app.routers.chatbot import router as chatbot_router
from app.routers.auth import router as auth_router
from app.routers.inventory_dropdown import router as inventory_router
from app.routers.inventory_smart import router as inventory_smart_router
from app.routers.chatbot import router as chatbot_router

# Initialize FastAPI
app = FastAPI(title="Mewar ERP API", redirect_slashes=False)

# ==========================================
# 🛡️ CORS SETTINGS
# ==========================================
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

# ==========================================
# 🔗 INCLUDE ROUTERS
# ==========================================
app.include_router(chatbot_router)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(inventory_smart_router)

# ==========================================
# 🟢 ROOT ENDPOINT
# ==========================================
@app.get("/")
def root():
    return {"message": "Mewar ERP API running"}




#hello