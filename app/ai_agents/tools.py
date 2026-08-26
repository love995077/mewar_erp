# app/ai_agents/tools.py
from crewai.tools import tool
from sqlalchemy import text
from app.db.database import SessionLocal 
from sqlalchemy.orm import Session

@tool("Inventory Shortage Checker")
def check_inventory_shortage(project_name: str = None, is_surplus: bool = False) -> str:
    """
    Very IMPORTANT Tool. Use this tool to check for inventory shortages or surplus (extra) items in the ERP.
    - If user asks for a specific project, pass the project_name.
    - If user asks for extra/surplus stock, pass is_surplus=True.
    Returns a detailed markdown table of items.
    """
    db = SessionLocal()
    try:
        project_filter_sql = ""
        params = {}
        
        if project_name and project_name.lower() != 'none':
            project_filter_sql = " AND LOWER(p.name) LIKE :t "
            params["t"] = f"%{project_name.lower()}%"

        query = f"""
            WITH RequiredData AS (
                SELECT pi.inventory_id, SUM(pp.quantity * pi.quantity) as req_qty
                FROM projects p
                JOIN project_products pp ON p.id = pp.project_id
                JOIN product_items pi ON pp.product_id = pi.product_id
                WHERE LOWER(p.status) NOT IN ('completed', 'hold') AND p.is_deleted = 0
                {project_filter_sql}
                GROUP BY pi.inventory_id
                UNION ALL
                SELECT pji.inventory_id, SUM(pji.quantity) as req_qty
                FROM projects p
                JOIN project_item pji ON p.id = pji.project_id
                WHERE LOWER(p.status) NOT IN ('completed', 'hold') AND p.is_deleted = 0
                {project_filter_sql}
                GROUP BY pji.inventory_id
            ),
            TotalRequired AS (
                SELECT inventory_id, SUM(req_qty) as required_qty
                FROM RequiredData
                GROUP BY inventory_id
            ),
            StockData AS (
                SELECT inventory_id, 
                       COALESCE(SUM(CASE WHEN LOWER(txn_type) = 'in' THEN quantity ELSE -quantity END), 0) AS available_qty
                FROM stock_transactions
                GROUP BY inventory_id
            )
            SELECT i.name, tr.required_qty, COALESCE(sd.available_qty, 0) AS available_qty
            FROM TotalRequired tr
            JOIN inventories i ON tr.inventory_id = i.id
            LEFT JOIN StockData sd ON tr.inventory_id = sd.inventory_id
            WHERE i.is_deleted = 0
        """
        
        if is_surplus:
            query += " AND COALESCE(sd.available_qty, 0) > tr.required_qty ORDER BY (COALESCE(sd.available_qty, 0) - tr.required_qty) DESC LIMIT 15"
        else:
            query += " AND tr.required_qty > COALESCE(sd.available_qty, 0) ORDER BY (tr.required_qty - COALESCE(sd.available_qty, 0)) DESC LIMIT 15"
            
        rows = db.execute(text(query), params).fetchall()
        
        if not rows:
            return "No shortage or surplus found based on the criteria. Stock is balanced."
            
        result = "| Item Name | Required | Available | Difference |\n| :--- | :---: | :---: | :---: |\n"
        for r in rows:
            req = float(r.required_qty or 0)
            avail = float(r.available_qty or 0)
            diff = abs(req - avail)
            result += f"| {r.name} | {req} | {avail} | {diff} |\n"
            
        return result
    except Exception as e:
        return f"Database error occurred in Shortage Checker: {str(e)}"
    finally:
        db.close()

# tools.py mein get_item_purchase_history function ko isse replace karo
@tool("Supplier History Fetcher")
def get_item_purchase_history(item_name: str) -> str:
    """
    Useful to find who supplied a specific item last time and at what rate.
    """
    db = SessionLocal()
    try:
        # Aapki table structure ke hisaab se update ki gayi query
        query = text("""
            SELECT 
                s.supplier_name, 
                poi.unit_price, 
                po.created_at, 
                s.city
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.purchase_order_id = po.id
            JOIN suppliers s ON po.supplier_id = s.id
            JOIN inventories i ON poi.inventory_id = i.id
            WHERE LOWER(i.name) LIKE LOWER(:item_name)
            ORDER BY po.created_at DESC
            LIMIT 1
        """)
        
        row = db.execute(query, {"item_name": f"%{item_name}%"}).fetchone()
        
        if row:
            # Column mapping check: row[0] is supplier_name, row[1] is unit_price
            return f"Last purchased from '{row.supplier_name}' ({row.city}) at rate of ₹{row.unit_price} on {row.created_at}."
        
        return f"No purchase history found for item: {item_name}"
    except Exception as e:
        return f"Error fetching supplier history: {str(e)}"
    finally:
        db.close()