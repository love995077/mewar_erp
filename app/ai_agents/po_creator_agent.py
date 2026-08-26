from langchain.tools import tool
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI # Agar aap OpenAI use kar rahe ho, ya fir Llama ka engine
import json

# ==========================================
# STEP 1: DEFINE AGENT TOOLS (The Superpowers)
# ==========================================

@tool
def check_low_stock() -> str:
    """Checks the Mewar ERP inventory database for items below their minimum reorder level."""
    # Real app mein ye db/inventory.py se aayega
    # Abhi ke liye hum dummy data return kar rahe hain
    return json.dumps({
        "status": "low_stock",
        "item_name": "Cement",
        "current_stock": 50,
        "reorder_level": 100,
        "required_qty": 150
    })

@tool
def get_best_supplier(item_name: str) -> str:
    """Cross-references suppliers for a given item to find the best price and fastest delivery."""
    # Real app mein ye db/supplier.py se SQL query chalayega
    return json.dumps({
        "supplier_name": "UltraTech Traders",
        "price_per_unit": 300,
        "lead_time_hours": 48
    })

@tool
def draft_purchase_order(supplier_name: str, item_name: str, quantity: int, price: float) -> str:
    """Drafts a purchase order in the database and returns a summary for manager approval."""
    # Real app mein ye DB mein 'Draft' status ke sath PO insert karega
    po_number = "PO-1042"
    total_cost = quantity * price
    
    # Manager ke liye Approval Message generate karna
    approval_message = (
        f"🚨 *Stock Alert:* {item_name} is running low.\n"
        f"✅ *Action Taken:* I’ve drafted order #{po_number} for {supplier_name}.\n"
        f"📦 *Details:* {quantity} units @ ₹{price}/unit (Total: ₹{total_cost}).\n"
        f"🚚 *Delivery:* Within 48 hours.\n\n"
        f"Reply 'YES' to approve with one click."
    )
    return approval_message

# ==========================================
# STEP 2: ORCHESTRATE THE AGENT
# ==========================================

def run_proactive_po_workflow():
    # LLM Initialize karo (Aap LlamaEngine bhi pass kar sakte ho jo pehle se bana hai)
    llm = ChatOpenAI(temperature=0, model="gpt-4") 
    
    # Agent ko uske tools de do
    tools = [check_low_stock, get_best_supplier, draft_purchase_order]
    
    # Agent setup
    agent = initialize_agent(
        tools=tools, 
        llm=llm, 
        agent=AgentType.OPENAI_FUNCTIONS, 
        verbose=True # Isey True rakhna taaki terminal me Agent ki thinking dikhe
    )
    
    # Agent ko uska Task (Prompt) do
    system_prompt = """
    You are an autonomous AI Agent for Mewar ERP. Your job is to ensure stock levels are maintained.
    Follow these exact steps:
    1. Check if any items are running low in stock.
    2. If an item is low, find the best supplier for that specific item based on price and lead time.
    3. Draft a purchase order for the required quantity using the best supplier's details.
    4. Return the final approval message to be sent to the manager.
    """
    
    print("🤖 Agent is checking ERP systems...")
    response = agent.run(system_prompt)
    
    return response

# Test run karne ke liye
if __name__ == "__main__":
    final_message = run_proactive_po_workflow()
    print("\n====================================")
    print("📲 MESSAGE SENT TO MANAGER (WHATSAPP):")
    print("====================================")
    print(final_message)