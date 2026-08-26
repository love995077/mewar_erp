import os
import requests
import modal
from fastapi import APIRouter, Request, Query, Response, BackgroundTasks # ✅ Naya Import Add kiya

from app.routers.chatbot import chatbot
from app.schemas.chat import ChatRequest
from app.db.database import SessionLocal

router = APIRouter(tags=["WhatsApp"])

history_store = modal.Dict.from_name("mewar-chat-history", create_if_missing=True)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

# ==========================================
# 🧠 ASYNC BACKGROUND TASK (Heavy AI Work)
# ==========================================
async def process_ai_logic(sender_phone: str, user_text: str):
    try:
        raw_history = await history_store.get.aio(sender_phone, [])
        
        last_user_msg = ""
        for h in reversed(raw_history):
            if h['role'] == 'user':
                last_user_msg = h['content']
                break

        # ✅ JUGAD: Agar naya message bilkul independent (naya topic) lag raha hai,
        # toh purani history ko ignore kar do taaki AI confuse na ho.
        independent_phrases = ["pending po", "sare po", "all po", "inventory batao", "stock check"]
        
        # Agar user ka naya message independent hai, toh last_user_msg ko khali kar do
        if any(phrase in user_text.lower() for phrase in independent_phrases):
            full_msg = user_text # Sirf naya message bhejenge (purani history ignore)
        else:
            trigger_words = ["details", "detail", "order", "orders", "sab", "budget", "stage", "profile"]
            if last_user_msg and user_text.lower().strip() in trigger_words:
                full_msg = f"{last_user_msg} {user_text}"
            else:
                full_msg = user_text

        reply_text = ""
        db = SessionLocal()
        try:
            # ✅ Step 1: Basic cleaning
            clean_msg = full_msg.lower().replace("sare ", "all ").replace("saare ", "all ")
            
            # 🚀 Step 2: THE PERMANENT FIX (HIDDEN PROMPT ONLY FOR WHATSAPP)
            # User ko ye nahi dikhega, par AI ko piche se gaali pad jayegi ki sahi column me dhoonde!
            hidden_instruction = " [System Note: Ignore chat history context if it's unrelated. If user asks for pending, draft (or typos like 'deaft'), strictly filter using the 'status' column (e.g. WHERE status='Pending' or 'Draft'). NEVER search status words inside po_number or supplier_name.]"
            
            final_query = clean_msg + hidden_instruction

            # ✅ Step 3: AI ko final_query bhejo
            req_data = ChatRequest(query=final_query, role="superadmin")
            response_dict = chatbot(req_data, db)
            
            if "results" in response_dict:
                all_results = response_dict["results"]
                
                # Data aur Chat messages ko alag karo
                data_results = [r for r in all_results if r.get("type") != "chat"]
                
                # 1. Pehle Chat message add karo ("hmm, dekhta hoon...")
                for res in all_results:
                    if res.get("type") == "chat":
                        reply_text += res.get("message", "") + "\n\n"
                
                # 2. Data items ko sirf Top 5 tak limit karo (WhatsApp Limit ke liye)
                limit = 5
                for res in data_results[:limit]:
                    res_type = res.get("type")
                    if res_type == "po":
                        reply_text += f"📄 *PO No:* {res.get('po_no')}\n🏢 *Supplier:* {res.get('supplier')}\n💰 *Total:* ₹{res.get('total', 0):,.2f}\n⏳ *Balance:* ₹{res.get('balance', 0):,.2f}\n📌 *Status:* {res.get('status')}\n\n"
                    elif res_type == "result":
                        if "inventory" in res:
                            inv = res["inventory"]
                            reply_text += f"📦 *{inv.get('name')}*\n📊 *Total Stock:* {res.get('total_stock')}\n📍 *Location:* {inv.get('placement')}\n\n"
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
                        reply_text += f"🏗️ *Project:* {res.get('project_name')}\n📌 *Status:* {res.get('category')}\n📈 *Completion Stage:* {res.get('stage', '0%')}\n💰 *Budget:* ₹{res.get('amount', 0):,.2f}\n\n"
                
                # 3. Agar 5 se zyada PO hain, toh Warning laga do
                if len(data_results) > limit:
                    reply_text += f"⚠️ *Note:* Total {len(data_results)} records mili hain, par WhatsApp par sirf top {limit} dikhayi gayi hain. Baaki list web dashboard par check karein.\n"

            if not reply_text.strip():
                reply_text = "Maaf karna, mujhe iska jawab nahi mil paya. 😅"

        except Exception as e:
            print(f"⚠️ AI Error: {e}")
            reply_text = "Maaf karna, system mein thodi dikkat aayi. Thodi der mein try karein!"
        finally:
            db.close()

        # 4. WhatsApp Limit Check (Safe side ke liye)
        if len(reply_text) > 4000:
            reply_text = reply_text[:3990] + "...\n(Message bada hone ki wajah se poora nahi dikh raha)"

        updated_history = raw_history + [
            {"role": "user", "content": full_msg}, 
            {"role": "assistant", "content": reply_text.strip()}
        ]
        await history_store.put.aio(sender_phone, updated_history[-8:])

        send_whatsapp_message(sender_phone, reply_text.strip())

    except Exception as e:
        print(f"❌ Background Task Error: {e}")

# ==========================================
# 2. FAST WEBHOOK (Meta ko turant free karo)
# ==========================================
@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
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
                            print(f"📩 Message aaya: {user_text}")
                            
                            # ✅ JADOO YAHAN HAI: Pura process background mein daal do
                            background_tasks.add_task(process_ai_logic, sender_phone, user_text)

    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        
    # ✅ TURANT META KO BOL DO "MESSGE MIL GAYA, RETRY MAT KARNA"
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
    print(f"🚀 WhatsApp API Response: {response.text}") # Ye terminal mein error bata dega agar koi hogi