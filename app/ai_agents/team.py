import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from app.ai_agents.tools import check_inventory_shortage

# 🔑 .env file load karein taaki GROQ_API_KEY_1 mil jaye
load_dotenv(override=True)

# 🧠 1. LLM Setup (Aapka Groq Engine)
# Hum aapka wahi model use karenge jo aapne v4_llm_engine mein likha hai
api_key = os.getenv("GROQ_API_KEY_1") or os.getenv("GROQ_API_KEY_2")

if not api_key:
    raise ValueError("Bhai, .env mein Groq API key nahi mili!")

ai_brain = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=api_key
)

# 👨‍💼 2. AGENT: Store Admin
store_admin_agent = Agent(
    role="Store Admin",
    goal="Ensure inventory is properly managed and shortages are reported accurately for any project.",
    backstory="""You are a highly experienced Store Admin at Mewar Hitech ERP. 
    You are responsible for managing the inventory, tracking what materials are required for running projects, 
    and reporting any shortages immediately to the management. You always use your tools to check real data before answering.""",
    verbose=True,
    allow_delegation=False,
    tools=[check_inventory_shortage],
    llm=ai_brain  # Groq ka dimaag yahan laga diya
)

# 📝 3. TASK (Kaam kya karna hai)
shortage_task = Task(
    description="Check the current inventory shortage for the 'Shree Balaji' project. Tell me what items we need to buy.",
    expected_output="A brief summary and a markdown table showing the exact items that are short.",
    agent=store_admin_agent
)

# 🤝 4. CREW (The Team)
erp_crew = Crew(
    agents=[store_admin_agent],
    tasks=[shortage_task],
    verbose=True,
    process=Process.sequential
)

# 🚀 RUN KAREIN!
if __name__ == "__main__":
    print("🤖 Store Admin AI (Powered by Groq) is starting the work... Please wait.\n")
    result = erp_crew.kickoff()
    
    print("\n=========================================")
    print("📝 FINAL REPORT FROM STORE ADMIN:")
    print("=========================================")
    print(result)