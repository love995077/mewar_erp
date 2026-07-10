import os
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv

# 👉 1. Aapke DB aur NL2SQL Engine ko import karna
from app.db.database import get_db
from app.services.nl2sql_engine import generate_sql  # <-- Agar path alag ho toh theek kar lena

# 🔥 THE GHOST BUSTER FIX 🔥
load_dotenv(override=True)
api_key = os.getenv("OPENAI_API_KEY", "").strip()

# Terminal me check karne ke liye ki konsi key utha raha hai
print(f"🚀 Gen UI is using API Key: {api_key[:15]}... (Ye nayi wali honi chahiye!)")

router = APIRouter()
# Nayi key explicitly pass kar rahe hain
client = AsyncOpenAI(api_key=api_key)

class CommandRequest(BaseModel):
    command: str

@router.post("/api/generate-ui")
async def generate_3d_ui(req: CommandRequest, db: Session = Depends(get_db)):
    user_prompt = req.command
    
    # =========================================================
    # STEP 1: ASK NL2SQL TO WRITE QUERY & FETCH REAL DATA
    # =========================================================
    try:
        # Aapke nl2sql_engine.py se SQL banwao
        sql_query = generate_sql(user_query=user_prompt)
        
        # Database mein query run karo
        result = db.execute(text(sql_query))
        rows = result.fetchall()
        columns = result.keys()
        
        # Data ko JSON string mein convert karo taaki AI padh sake
        real_data = []
        for row in rows:
            real_data.append(dict(zip(columns, row)))
            
        data_str = json.dumps(real_data, default=str)
        
    except Exception as e:
        print(f"DB Error: {e}")
        data_str = "Error fetching data from database. Make sure the query is correct."
        sql_query = "N/A"

    # =========================================================
    # STEP 2: GIVE REAL DATA TO UI ENGINE TO DESIGN CHARTS
    # =========================================================
    
    # 🔥 THE BRAIN UPGRADE: AI ko 6 Charts sikhana 🔥
    system_instruction = f"""
    You are a highly advanced Generative UI Engine.
    The user asked: "{user_prompt}"
    
    The Database executed this SQL: {sql_query}
    And returned this REAL DATA: {data_str}
    
    Your job is to visualize this REAL DATA.
    Respond ONLY with a JSON object. No markdown, no extra text.
    
    You must strictly output JSON in this exact format:
    {{
        "type": "chart",
        "chart_type": "<SELECT_ONE_FROM_BELOW>",
        "data": [<LIST_OF_NUMBERS>],
        "labels": ["<LIST_OF_STRINGS>"],
        "message": "A cool, short confirmation message"
    }}

    🧠 RULES FOR SELECTING 'chart_type':
    1. "metric" - Use this if the answer is just a SINGLE number (e.g., "Total inventory is 4065" or "Total sales"). Send the number in the 'data' array (e.g., [4065]) and a title in the 'labels' array.
    2. "bar" - Use this for comparisons, ranking, or Top 5 / Bottom 5 queries.
    3. "pie" - Use this for distribution, shares, or percentages (e.g., "Division of purchases").
    4. "line" - Use this for trends over time.
    5. "funnel" - Use this for stages or drop-offs (e.g., "Inquiries to PO conversion").
    6. "gauge" - Use this for progress towards a target. The 'data' array MUST have exactly 2 numbers: [current_value, target_value].

    Extract the numerical values into the 'data' array and the names/categories into the 'labels' array based on the REAL DATA provided.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini", # Superfast model
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": system_instruction}
            ]
        )
        
        ui_json = json.loads(response.choices[0].message.content)
        return ui_json

    except Exception as e:
        print(f"OpenAI Error: {e}")
        # Default Hologram Metric if something crashes
        return {
            "type": "chart",
            "chart_type": "metric",
            "message": "Error connecting to AI Brain.",
            "data": [0],
            "labels": ["System Error"]
        }