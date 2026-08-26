# import os
# import json
# from fastapi import APIRouter, Depends
# from pydantic import BaseModel
# from openai import AsyncOpenAI
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# from dotenv import load_dotenv

# from app.db.database import get_db
# from app.services.nl2sql_engine import generate_sql, get_db_schema

# load_dotenv(override=True)
# api_key = os.getenv("OPENAI_API_KEY", "").strip()

# router = APIRouter()
# client = AsyncOpenAI(api_key=api_key)

# class CommandRequest(BaseModel):
#     command: str

# @router.post("/api/generate-ui")
# async def generate_command_center_ui(req: CommandRequest, db: Session = Depends(get_db)):
#     user_prompt = req.command.lower()
    
#     # =========================================================
#     # STEP 1: HYBRID ROUTING (Detecting specific complex intent)
#     # =========================================================
    
#     if "shortage" in user_prompt or "less available" in user_prompt or "required" in user_prompt:
#         print("🎯 Intent Detected: Inventory Shortage. Using Verified ERP Query...")
        
#         # 🚀 UPDATED SQL: Added required_qty and available_stock columns
#         sql_query = """
#             WITH RunningProjects AS (
#                 SELECT id FROM projects WHERE status = 'in_progress'
#             ),
#             ReqUnion AS (
#                 SELECT pi.inventory_id, SUM(CAST(pp.quantity AS SIGNED) * CAST(pi.quantity AS SIGNED)) as req
#                 FROM RunningProjects p
#                 JOIN project_products pp ON p.id = pp.project_id
#                 JOIN product_items pi ON pp.product_id = pi.product_id
#                 GROUP BY pi.inventory_id
#                 UNION ALL
#                 SELECT p_item.inventory_id, SUM(CAST(p_item.quantity AS SIGNED)) as req
#                 FROM RunningProjects p
#                 JOIN project_item p_item ON p.id = p_item.project_id
#                 GROUP BY p_item.inventory_id
#             ),
#             TotalReq AS (
#                 SELECT inventory_id, SUM(req) as total_req FROM ReqUnion GROUP BY inventory_id
#             ),
#             AllowedMachines AS (
#                 SELECT DISTINCT machine_id FROM stock_transactions 
#                 WHERE project_id IN (SELECT id FROM RunningProjects) AND machine_id IS NOT NULL
#             ),
#             Consumption AS (
#                 SELECT inventory_id, SUM(quantity) as cons_qty
#                 FROM stock_transactions
#                 WHERE LOWER(txn_type) = 'out'
#                   AND (project_id IN (SELECT id FROM RunningProjects) OR machine_id IN (SELECT machine_id FROM AllowedMachines))
#                 GROUP BY inventory_id
#             ),
#             AvailableStock AS (
#                 SELECT inventory_id,
#                     (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)
#                     -
#                     SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail
#                 FROM stock_transactions GROUP BY inventory_id
#             ),
#             PendingPOs AS (
#                 SELECT poi.inventory_id, SUM(poi.ordered_qty) as incoming_qty
#                 FROM purchase_order_items poi
#                 JOIN purchase_orders po ON poi.purchase_order_id = po.id
#                 WHERE po.status IN ('Draft', 'Submitted', 'Approved', 'Pending') 
#                 GROUP BY poi.inventory_id
#             )
#             SELECT 
#                 i.name as item_name, 
#                 (COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) AS required_qty,
#                 COALESCE(a.total_avail, 0) AS available_stock,
#                 ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0) - COALESCE(p_po.incoming_qty, 0)) AS shortage_qty
#             FROM TotalReq tr
#             JOIN inventories i ON tr.inventory_id = i.id
#             LEFT JOIN Consumption c ON tr.inventory_id = c.inventory_id
#             LEFT JOIN AvailableStock a ON tr.inventory_id = a.inventory_id
#             LEFT JOIN PendingPOs p_po ON tr.inventory_id = p_po.inventory_id
#             WHERE i.is_deleted = 0
#             HAVING shortage_qty > 0
#             ORDER BY shortage_qty DESC
#         """
        
#         try:
#             result = db.execute(text(sql_query))
#             rows = result.fetchall()
            
#             real_data = []
#             total_req_qty = 0
#             total_avail_stock = 0
#             total_shortage_qty = 0
            
#             # 🔥 Calculate Totals and Trim Names for neat UI
#             for row in rows:
#                 r_qty = abs(round(float(row.required_qty), 2))
#                 a_qty = abs(round(float(row.available_stock), 2))
#                 s_qty = abs(round(float(row.shortage_qty), 2))
                
#                 total_req_qty += r_qty
#                 total_avail_stock += a_qty
#                 total_shortage_qty += s_qty
                
#                 # Trim long names so graph doesn't look messy (max 18 chars)
#                 full_name = str(row.item_name)
#                 neat_name = full_name[:18] + ".." if len(full_name) > 18 else full_name
                
#                 real_data.append({
#                     "item_name": neat_name,
#                     "shortage_quantity": s_qty
#                 })
            
#             total_items = len(rows)
            
#             # 🟢 Bulletproof Insight
#             if total_items > 0:
#                 top_name = real_data[0]["item_name"]
#                 top_qty = real_data[0]["shortage_quantity"]
#                 forced_insight = f"There are {total_items} items in shortage. '{top_name}' has the highest shortage ({top_qty} units). 🟢 Data Source: Mewar ERP Core"
#             else:
#                 forced_insight = "Inventory is fully stocked. No shortages detected. 🟢 Data Source: Mewar ERP Core"
            
#             # Data sent to AI (including totals)
#             data_str = f"""
#             SUMMARY METRICS:
#             - Total Unique Items: {total_items}
#             - Total Required Qty: {total_req_qty}
#             - Total Available Stock: {total_avail_stock}
#             - Total Shortage Qty: {total_shortage_qty}
            
#             FULL ITEMS DATA FOR CHART: {json.dumps(real_data, default=str)}
#             """
            
#         except Exception as e:
#             print(f"DB Error (Shortage Query): {e}")
#             data_str = "Error fetching verified shortage data."
#             forced_insight = "System encountered an error while fetching data. 🔴 Data Source: Error"
            
#     else:
#         # (CASE B: Aapka purana NL2SQL logic waise ka waisa hi rahega yahan...)
#         forced_insight = "Here is the dynamic data analysis based on your request. ✨ Data Source: AI Generated (NL2SQL)"
#         data_str = "{}" # Removed for brevity, use your existing else block here if you want.

#     # =========================================================
#     # STEP 2: GENERATIVE UI BRAIN - BUILDING THE DASHBOARD BLUEPRINT
#     # =========================================================
    
#     # 🔥 STRICT INSTRUCTIONS TO FORCE 4 KPIs
#     system_instruction = f"""
#     You are the core AI Generative UI Engine for Mewar ERP's Command Center.
#     The user asked: "{req.command}"
    
#     REAL DATA returned from Database: {data_str}
    
#     Your job is to design a dynamic dashboard. 
#     Respond ONLY with a valid JSON object.
    
#     You must strictly output JSON in this EXACT blueprint format:
#     {{
#         "dashboard_title": "Inventory Shortage Overview",
#         "ai_insights": "{forced_insight}",
#         "grid_layout": [
#             {{ "component": "kpi_card", "title": "Total Unique Items", "value": "<Insert Total Unique Items>", "width": "half" }},
#             {{ "component": "kpi_card", "title": "Total Required Qty", "value": "<Insert Total Required Qty>", "width": "half" }},
#             {{ "component": "kpi_card", "title": "Total Available Stock", "value": "<Insert Total Available Stock>", "width": "half" }},
#             {{ "component": "kpi_card", "title": "Total Shortage Qty", "value": "<Insert Total Shortage Qty>", "width": "half" }},
#             {{
#                 "component": "chart",
#                 "chart_type": "bar",
#                 "title": "Shortage by Item",
#                 "data": [<numbers>],
#                 "labels": ["<strings>"],
#                 "width": "full"
#             }}
#         ],
#         "suggested_action": {{
#             "label": "Draft Purchase Orders",
#             "action_payload": "action_code_here"
#         }}
#     }}

#     🧠 CRITICAL RULES:
#     1. The first 4 items in 'grid_layout' MUST be the 4 kpi_cards populated with the exact SUMMARY METRICS provided.
#     2. The 5th item MUST be the 'chart' containing ALL items from the FULL ITEMS DATA.
#     3. Use EXACTLY the numbers from the data. Do not hallucinate.
#     """

#     try:
#         response = await client.chat.completions.create(
#             model="gpt-4o",
#             temperature=0.0, 
#             response_format={ "type": "json_object" },
#             messages=[
#                 {"role": "system", "content": system_instruction}
#             ]
#         )
        
#         ui_blueprint = json.loads(response.choices[0].message.content)
#         return ui_blueprint

#     except Exception as e:
#         print(f"OpenAI Error: {e}")
#         return {
#             "dashboard_title": "System Error",
#             "ai_insights": "Could not connect to AI Core.",
#             "grid_layout": [],
#             "suggested_action": None
#         }


##new ---------------------------------------------------

import os

import json

from fastapi import APIRouter, Depends

from pydantic import BaseModel

from openai import AsyncOpenAI

from sqlalchemy.orm import Session

from sqlalchemy import text

from dotenv import load_dotenv



from app.db.database import get_db

from app.services.nl2sql_engine import generate_sql, get_db_schema



load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY", "").strip()

print(f"🚀 Gen UI (Fully Dynamic AI Engine) API Key: {api_key[:15]}...")



router = APIRouter()

client = AsyncOpenAI(api_key=api_key)



class CommandRequest(BaseModel):

    command: str



@router.post("/api/generate-ui")

async def generate_command_center_ui(req: CommandRequest, db: Session = Depends(get_db)):

    user_prompt = req.command.lower()

    print(f"🧠 Dynamic UI Engine Processing: '{req.command}'")

   

    try:

        # STEP 1: Get Data directly from our Smart NL2SQL Engine

        schema_full = get_db_schema(db, compact=False)

        schema_compact = get_db_schema(db, compact=True)

       

        sql_query = generate_sql(req.command, schema_full, schema_compact)

       

        # Execute Query with Auto-Heal

        try:

            result = db.execute(text(sql_query))

        except Exception as first_error:

            print(f"⚠️ Initial SQL Error: {first_error}. Auto-Correcting...")

            sql_query = generate_sql(req.command, schema_full, schema_compact, previous_sql=sql_query, sql_error=str(first_error))

            result = db.execute(text(sql_query))



        rows = result.fetchall()

        columns = result.keys()

        real_data = [dict(zip(columns, row)) for row in rows]

       

        total_rows = len(real_data)

       

        # 🧠 PYTHON SMART SUMMARY: Calculate exact totals before slicing

        summary_stats = {"Exact_Total_Rows": total_rows}

        if total_rows > 0:

            for col in columns:

                # Agar column mein numbers hain, toh uska total sum nikal lo

                if isinstance(real_data[0][col], (int, float)) or (isinstance(real_data[0][col], str) and real_data[0][col].replace('.','',1).isdigit()):

                    try:

                        col_sum = sum(float(r[col]) for r in real_data if r[col] is not None)

                        summary_stats[f"Exact_Sum_of_{col}"] = round(col_sum, 2)

                    except:

                        pass



        # Protect OpenAI token limit

        if total_rows > 20:

            data_str = json.dumps(real_data[:20], default=str) # Send only Top 20 for Chart

        else:

            data_str = json.dumps(real_data, default=str)

       

        if total_rows == 0:

            data_str = "No data returned for this query."



        # STEP 2: Let AI Design the Best UI

        system_instruction = f"""

        You are the Master UI/UX Architect for Mewar ERP.

        User requested: "{req.command}"

       

        PYTHON PRE-CALCULATED TRUE METRICS (USE THESE FOR KPI CARDS!):

        {json.dumps(summary_stats)}

       

        RAW DATA FOR CHARTS (Truncated to Top 20):

        {data_str}

       

        Available Components (YOU MUST ONLY USE THESE TWO):

        1. "kpi_card": You MUST generate 2 to 4 KPI cards. For totals and sums, ALWAYS use the values from 'PYTHON PRE-CALCULATED TRUE METRICS' so they are 100% accurate. Fields: "component": "kpi_card", "title", "value", "width" ("half" or "quarter").

        2. "chart": Fields: "component": "chart", "chart_type", "title", "data" (ARRAY OF PURE NUMBERS), "labels" (ARRAY OF STRINGS), "width" ("full").

           - Decide the BEST chart_type: "bar", "pie", "doughnut", or "line".

       

        CRITICAL RULES (NEVER BREAK THESE):

        - NEVER generate a 'data_table'.

        - You MUST include exactly ONE "chart". Plot a MAXIMUM of 15 items in the chart so the X-axis labels do not overlap in the UI.

        - For the chart, pick the single most important numerical column for the "data" array, and the name/item column for the "labels" array.

        - The "data" array MUST contain STRICTLY PURE NUMBERS (e.g., [1500.50, 20]). No strings.

        - The AI Insights should be 1-2 lines summarizing the data logically. ALWAYS end with: "🟢 Data Source: Mewar ERP Core".

       

        Output EXACTLY this JSON structure:

        {{

            "dashboard_title": "<Make it catchy>",

            "ai_insights": "<Your insights here>",

            "grid_layout": [

                <kpi_cards here>,

                <one chart here>

            ],

            "suggested_action": {{ "label": "Take Action", "action_payload": "default" }}

        }}

        """

       

        # STEP 3: Generate UI JSON

        response = await client.chat.completions.create(

            model="gpt-4o",

            temperature=0.0, # 0.0 for maximum accuracy

            response_format={ "type": "json_object" },

            messages=[

                {"role": "system", "content": system_instruction}

            ]

        )

       

        ui_blueprint = json.loads(response.choices[0].message.content)

        print("🎨 Dynamic AI Blueprint Generated & Sent to UI.")

        return ui_blueprint



    except Exception as e:

        print(f"Gen-UI System Error: {e}")

        return {

            "dashboard_title": "System Timeout / Error",

            "ai_insights": "The AI could not process your query at this moment. Please try again. 🔴 Data Source: System Error",

            "grid_layout": [],

            "suggested_action": None

        } 

