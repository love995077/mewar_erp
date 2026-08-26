import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.append(root_dir)

import streamlit as st
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

# Tool imports - Dono tools ab active hain
from app.ai_agents.tools import check_inventory_shortage, get_item_purchase_history

# ==========================================
# ⚙️ 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Mewar AI Command Center", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .agent-card { border: 1px solid #444; border-radius: 10px; padding: 15px; background-color: #1e1e2e; color: white; text-align: center; }
    .status-online { color: #00ff00; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 2. AI SYSTEM SETUP
# ==========================================
@st.cache_resource
def setup_ai():
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2")
    if not api_key: return None
    os.environ["GROQ_API_KEY"] = api_key
    return LLM(model="groq/llama-3.3-70b-versatile")

ai_brain = setup_ai()

# 👨‍💼 AGENTS INITIALIZATION
# 1. Store Admin
store_agent = Agent(
    role="Store Admin",
    goal="Identify accurate inventory shortages for projects.",
    backstory="You are the guardian of Mewar Hitech's warehouse. You use tools to see what is missing.",
    tools=[check_inventory_shortage],
    llm=ai_brain,
    verbose=True
)

# 2. Purchase Manager (Ab ye Live hai!)
purchase_agent = Agent(
    role="Purchase Manager",
    goal="Provide buying recommendations based on historical supplier rates.",
    backstory="""You are the expert buyer. You receive shortage lists, then you check purchase history 
    to see who supplied that item last and at what price, helping the boss make a decision.""",
    tools=[get_item_purchase_history],
    llm=ai_brain,
    verbose=True
)

# ==========================================
# 🖥️ 3. UI LAYOUT & SIDEBAR
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2042/2042407.png", width=80)
    st.title("AI Command Center")
    st.divider()
    st.markdown("### 🤖 Agents Live: 2/4")
    st.markdown("- 🟢 **Store Admin** (Online)")
    st.markdown("- 🟢 **Purchase Manager** (Online)") # Status updated!
    st.markdown("- 🔴 **Sales Officer** (Coming Soon)")
    st.markdown("- 🔴 **Project HOD** (Coming Soon)")
    st.divider()
    st.caption("Mewar Hitech ERP v2.0")

# ==========================================
# 📊 4. MAIN DASHBOARD AREA
# ==========================================
st.title("🏭 Mewar Hitech - War Room")

col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Active AI Agents", value="2", delta="Purchase Live")
col2.metric(label="Tasks Done", value="16", delta="6 New")
col3.metric(label="System", value="Connected", delta="DB Active")
col4.metric(label="Latency", value="0.9s", delta="-0.3s")

st.divider()

tab1, tab2, tab3 = st.tabs(["📦 Store Operations", "💸 Purchase Advice", "⚙️ System Logs"])

# --------- TAB 1: STORE OPERATIONS ---------
with tab1:
    st.markdown("### 🕵️‍♂️ Check Shortage")
    with st.container(border=True):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            p_name = st.text_input("Project Name", placeholder="e.g., Shree Balaji", key="store_p")
            is_surplus = st.toggle("Check Surplus?")
        with col_b:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Run Shortage Check", use_container_width=True):
                with st.status("Agent working...", expanded=False) as s:
                    t1 = Task(description=f"Check {('surplus' if is_surplus else 'shortage')} for {p_name or 'factory'}.", 
                              expected_output="A markdown table.", agent=store_agent)
                    crew = Crew(agents=[store_agent], tasks=[t1])
                    res = crew.kickoff()
                    s.update(label="Done!", state="complete")
                st.markdown(str(res))

# --------- TAB 2: PURCHASE ADVICE (The New Feature!) ---------
with tab2:
    st.markdown("### 💸 Smart Purchase Recommendation")
    st.info("Ye Agent pehle shortage check karega, fir har item ka pichla rate dhundega.")
    
    with st.container(border=True):
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            purchase_project = st.text_input("Project for Purchase Advice", placeholder="e.g., Shree Balaji", key="purch_p")
        with col_p2:
            st.markdown("<br>", unsafe_allow_html=True)
            po_btn = st.button("📝 Generate Advice", type="primary", use_container_width=True)

    if po_btn:
        with st.status("🔗 Sequential Workflow Started...", expanded=True) as status:
            st.write("👨‍💼 **Store Admin:** Finding shortage list...")
            
            # Task 1: Store Admin finds shortage
            task_shortage = Task(
                description=f"Identify all items in shortage for the project '{purchase_project or 'overall factory'}'.",
                expected_output="A list of items that are currently short.",
                agent=store_agent
            )

            st.write("💰 **Purchase Manager:** Checking historical rates and suppliers...")
            # Task 2: Purchase Manager takes Task 1 output and finds rates
            task_purchase = Task(
                description="""Take the list of items from the Store Admin. For EACH item, use your 'Supplier History Fetcher' tool 
                to find the last supplier and rate. Then, present a final summary table with: 
                Item Name, Last Supplier, Last Rate, and a Recommendation.""",
                expected_output="A final purchase advice report with a markdown table.",
                agent=purchase_agent
            )

            # Sequential Process: T1 finishes, then T2 starts
            crew = Crew(
                agents=[store_agent, purchase_agent],
                tasks=[task_shortage, task_purchase],
                process=Process.sequential,
                verbose=True
            )
            
            final_advice = crew.kickoff()
            status.update(label="✅ Advice Generated!", state="complete")

        st.success("Purchase Admin has completed the analysis.")
        with st.container(border=True):
            st.markdown("### 📋 Official Purchase Advice")
            st.markdown(str(final_advice))

# --------- TAB 3: LOGS ---------
with tab3:
    st.markdown("### 📝 Live Logs")
    st.code("System Online\nAll Agents Ready\nWaiting for delegation...", language="bash")