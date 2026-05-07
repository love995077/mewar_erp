import os
import requests
import modal
from fastapi import APIRouter, Request, Query, Response

# 👇 NAYE IMPORTS: Ab hum process_chat_message ki jagah seedha Chatbot ko bula rahe hain
from app.routers.chatbot import chatbot
from app.schemas.chat import ChatRequest
from app.db.database import SessionLocal

router = APIRouter(tags=["WhatsApp"])

# ==========================================
# 🧠 PERMANENT MEMORY (MODAL DICT)
# ==========================================
history_store = modal.Dict.from_name("mewar-chat-history", create_if_missing=True)

# ==========================================
# 🔑 TOKENS
# ==========================================
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# ==========================================
# 1. WEBHOOK VERIFICATION
# ==========================================
@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("✅ WhatsApp Webhook Verified!")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

# ==========================================
# 2. MESSAGE RECEIVE & REPLY (CUSTOM TRANSLATOR)
# ==========================================
@router.post("/webhook")
async def receive_message(request: Request):
    try:
        data = await request.json()
        
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        msg_info = value["messages"][0]
                        sender_phone = msg_info["from"]
                        
                        if "text" in msg_info:
                            user_text = msg_info["text"]["body"]
                            print(f"📩 Message aaya {sender_phone} se: {user_text}")

                            # --------------------------------------------------
                            # 🧠 MEMORY LOGIC
                            # --------------------------------------------------
                            try:
                                raw_history = history_store.get(sender_phone, [])
                            except:
                                raw_history = []
                            
                            last_user_msg = ""
                            for h in reversed(raw_history):
                                if h['role'] == 'user':
                                    last_user_msg = h['content']
                                    break

                            trigger_words = ["details", "detail", "order", "orders", "sab", "budget", "stage", "profile"]
                            if last_user_msg and user_text.lower().strip() in trigger_words:
                                full_msg = f"{last_user_msg} {user_text}"
                            else:
                                full_msg = user_text

                            # --------------------------------------------------
                            # 🤖 ASLI AI & CUSTOM TRANSLATOR (YAHAN HAI JADOO)
                            # --------------------------------------------------
                            reply_text = ""
                            db = SessionLocal()
                            try:
                                # Seedha main AI brain ko query bhej rahe hain
                                req_data = ChatRequest(query=full_msg, role="superadmin")
                                response_dict = chatbot(req_data, db)
                                
                                # JSON Data ko WhatsApp Text mein yahi convert kar rahe hain
                                if "results" in response_dict:
                                    for res in response_dict["results"]:
                                        res_type = res.get("type")
                                        
                                        if res_type == "chat":
                                            reply_text += res.get("message", "") + "\n\n"
                                            
                                        elif res_type == "po":
                                            reply_text += f"📄 *PO No:* {res.get('po_no')}\n🏢 *Supplier:* {res.get('supplier')}\n💰 *Total:* ₹{res.get('total', 0):,.2f}\n⏳ *Balance:* ₹{res.get('balance', 0):,.2f}\n📌 *Status:* {res.get('status')}\n\n"
                                            
                                        elif res_type == "result":
                                            if "inventory" in res:
                                                inv = res["inventory"]
                                                reply_text += f"📦 *{inv.get('name')}*\n📊 *Total Stock:* {res.get('total_stock')}\n📍 *Location:* {inv.get('placement')}\n\n"
                                            
                                            # ✅ SUPPLIER CARD WALA DATA AB YAHAN SE HANDLE HOGA
                                            elif "supplier" in res:
                                                sup = res["supplier"]
                                                reply_text += f"🏢 *{sup.get('name')}*\n🆔 *Code:* {sup.get('code')}\n📞 *Mobile:* {sup.get('mobile')}\n📍 *Location:* {sup.get('city')}\n🧾 *GSTIN:* {sup.get('gstin')}\n\n"
                                                
                                                items = res.get("items", [])
                                                if items:
                                                    reply_text += "📦 *Inventory from this Supplier:*\n"
                                                    for item in items:
                                                        reply_text += f"🔸 {item.get('name')}: *{item.get('stock')}*\n"
                                                    reply_text += "\n"
                                                    
                                        elif res_type == "project":
                                            reply_text += f"🏗️ *Project:* {res.get('project_name')}\n📌 *Status:* {res.get('category')}\n💰 *Budget:* ₹{res.get('amount', 0):,.2f}\n\n"

                                if not reply_text.strip():
                                    reply_text = "Maaf karna, mujhe iska jawab nahi mil paya. 😅"

                            except Exception as e:
                                print(f"⚠️ AI Error: {e}")
                                reply_text = "Maaf karna, main abhi sochne mein thoda confuse ho gaya. Thodi der mein try karein!"
                            finally:
                                db.close() # Connection close

                            # --------------------------------------------------
                            # 📝 MEMORY SAVE KARO
                            # --------------------------------------------------
                            updated_history = raw_history + [
                                {"role": "user", "content": full_msg}, 
                                {"role": "assistant", "content": reply_text.strip()}
                            ]
                            history_store[sender_phone] = updated_history[-8:]

                            # --------------------------------------------------
                            # 📲 WHATSAPP PAR BHEJO
                            # --------------------------------------------------
                            send_whatsapp_message(sender_phone, reply_text.strip())
                            
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        
    return Response(content="ok", status_code=200)

# ==========================================
# 🚀 SEND FUNCTION
# ==========================================
def send_whatsapp_message(to_phone: str, message: str):
    token = os.getenv("WHATSAPP_TOKEN") 
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"✅ Reply bhej diya gaya {to_phone} ko")
    else:
        print(f"❌ Reply fail ho gaya: {response.text}")