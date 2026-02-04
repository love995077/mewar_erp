import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Mewar ERP Chatbot", layout="wide")
st.title("🤖 Mewar ERP Inventory Chatbot Assistant")

# -----------------------
# Initialize chat history
# -----------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------
# Input form (SAFE)
# -----------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Ask something like: 'bearing', 'bearing 608', 'bearing and C.I. Welding'"
    )
    send = st.form_submit_button("Send")

# -----------------------
# Process message
# -----------------------
if send and user_input.strip():

    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        res = requests.post(
            f"{API_BASE}/chatbot/",
            json={"query": user_input}
        )

        if res.status_code == 200:
            data = res.json()
            bot_msg = data.get("message", "No response")  # ✅ FIX
        else:
            bot_msg = "❌ Backend error"

    except Exception as e:
        bot_msg = f"❌ Server not running: {e}"

    st.session_state.messages.append({
        "role": "assistant",
        "content": bot_msg
    })

# -----------------------
# Display chat
# -----------------------
st.markdown("---")
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"**🧑 You:** {msg['content']}")
    else:
        st.markdown(f"**🤖 Assistant:** {msg['content']}")

st.markdown("---")
st.caption("Mewar ERP Chatbot • Inventory Assistant")
