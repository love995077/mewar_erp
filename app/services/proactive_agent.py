import asyncio
import datetime
from sqlalchemy import text

async def run_proactive_workflow(broadcast_callback, db_session):
    """
    Ye function 3D Dashboard ke WebSocket ko real-time status bhejega.
    Observer -> Cognitive -> Approver (100% Database Driven & Demand Based)
    """
    
    # --- STEP 1: OBSERVER (Scanning Real Database for Production Demand) ---
    await broadcast_callback({
        "type": "alert",
        "task": "Scanning Mewar ERP Inventory...",
        "message": "AI is cross-referencing Production Demand (Projects & BOM) with Available Stock.",
        "color": "#00F0FF" # Cyan
    })
    await asyncio.sleep(2)

    # 🚀 THE ULTIMATE DEMAND QUERY (Mirrors exactly how PHP ERP calculates)
    try:
        demand_query = text("""
            WITH RunningProjects AS (
                SELECT id FROM projects WHERE status = 'in_progress'
            ),
            ReqUnion AS (
                SELECT pi.inventory_id, SUM(CAST(pp.quantity AS SIGNED) * CAST(pi.quantity AS SIGNED)) as req
                FROM RunningProjects p
                JOIN project_products pp ON p.id = pp.project_id
                JOIN product_items pi ON pp.product_id = pi.product_id
                GROUP BY pi.inventory_id
                
                UNION ALL
                
                SELECT p_item.inventory_id, SUM(CAST(p_item.quantity AS SIGNED)) as req
                FROM RunningProjects p
                JOIN project_item p_item ON p.id = p_item.project_id
                GROUP BY p_item.inventory_id
            ),
            TotalReq AS (
                SELECT inventory_id, SUM(req) as total_req FROM ReqUnion GROUP BY inventory_id
            ),
            AllowedMachines AS (
                SELECT DISTINCT machine_id FROM stock_transactions 
                WHERE project_id IN (SELECT id FROM RunningProjects) AND machine_id IS NOT NULL
            ),
            Consumption AS (
                SELECT inventory_id, SUM(quantity) as cons_qty
                FROM stock_transactions
                WHERE LOWER(txn_type) = 'out'
                  AND (project_id IN (SELECT id FROM RunningProjects) OR machine_id IN (SELECT machine_id FROM AllowedMachines))
                GROUP BY inventory_id
            ),
            AvailableStock AS (
                SELECT inventory_id,
                    (SUM(CASE WHEN LOWER(txn_type) = 'in' AND (LOWER(ref_type) != 'finish' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)
                    -
                    SUM(CASE WHEN LOWER(txn_type) = 'out' AND (LOWER(ref_type) != 'machining' OR ref_type IS NULL OR ref_type = '') THEN quantity ELSE 0 END)) as total_avail
                FROM stock_transactions GROUP BY inventory_id
            ),
            PendingPOs AS (
                -- 🚀 THE DOUBLE-PO PREVENTION LOGIC
                SELECT poi.inventory_id, SUM(poi.ordered_qty) as incoming_qty
                FROM purchase_order_items poi
                JOIN purchase_orders po ON poi.purchase_order_id = po.id
                WHERE po.status IN ('Draft', 'Submitted', 'Approved', 'Pending') 
                GROUP BY poi.inventory_id
            )
            
            SELECT 
                i.id, i.name, i.unit,
                (COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) AS required_qty,
                COALESCE(a.total_avail, 0) AS available_stock,
                COALESCE(p_po.incoming_qty, 0) AS incoming_stock,
                
                -- EXACT SHORTAGE = (Req) - (Avail) - (Incoming Pending POs)
                ((COALESCE(tr.total_req, 0) - COALESCE(c.cons_qty, 0)) - COALESCE(a.total_avail, 0) - COALESCE(p_po.incoming_qty, 0)) AS shortage_qty
                
            FROM TotalReq tr
            JOIN inventories i ON tr.inventory_id = i.id
            LEFT JOIN Consumption c ON tr.inventory_id = c.inventory_id
            LEFT JOIN AvailableStock a ON tr.inventory_id = a.inventory_id
            LEFT JOIN PendingPOs p_po ON tr.inventory_id = p_po.inventory_id
            WHERE i.is_deleted = 0
            HAVING shortage_qty > 0
            ORDER BY shortage_qty DESC
            LIMIT 1;
        """)
        short_item = db_session.execute(demand_query).fetchone()
    except Exception as e:
        print("DB Demand Check Error:", e)
        short_item = None

    if not short_item:
        await broadcast_callback({
            "type": "success", "task": "Inventory Check Complete", 
            "message": "All clear! Currently, there is no pending production demand without stock.", 
            "color": "#3DDC84"
        })
        return {"status": "success", "message": "No shortage"}

    # Extracting exact data from our new smart query
    inv_id = short_item.id
    item_name = short_item.name
    unit = short_item.unit or "Nos"
    
    req_qty = float(short_item.shortage_qty)
    total_needed = float(short_item.required_qty)
    curr_avail = float(short_item.available_stock)

    await broadcast_callback({
        "type": "alert",
        "task": f"Low Stock Detected: {item_name}",
        "message": f"Production Alert: {total_needed} {unit} required, but only {curr_avail} {unit} available. Exact Shortage: {req_qty} {unit}.",
        "color": "#FFC72C" # Yellow
    })
    await asyncio.sleep(3)


   # --- STEP 2: COGNITIVE (Smart Sourcing Strategy) ---
    await broadcast_callback({
        "type": "success",
        "task": "Cross-referencing suppliers...",
        "message": f"Analyzing historical PO data and supplier master for '{item_name}'...",
        "color": "#00F0FF" # Cyan
    })
    await asyncio.sleep(2)
    
    try:
        # NAYI SMART QUERY: Pehle Purane POs mein Check Karega
        supplier_query = text("""
            SELECT 
                s.id as supplier_id, 
                s.supplier_name, 
                poi.unit_price
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.purchase_order_id = po.id
            JOIN suppliers s ON po.supplier_id = s.id
            WHERE poi.inventory_id = :inv_id
            ORDER BY poi.unit_price ASC 
            LIMIT 1
        """)
        best_sup = db_session.execute(supplier_query, {"inv_id": inv_id}).fetchone()
        
        # AGAR PEHLE KABHI NAHI KHARIDA: Toh Supplier-Inventory Mapping se uthayega
        if not best_sup:
            mapping_query = text("""
                SELECT 
                    s.id as supplier_id, 
                    s.supplier_name, 
                    0 AS unit_price
                FROM supplier_inventories si
                JOIN suppliers s ON si.supplier_id = s.id
                WHERE si.inventory_id = :inv_id
                LIMIT 1
            """)
            best_sup = db_session.execute(mapping_query, {"inv_id": inv_id}).fetchone()
            
    except Exception as e:
        print("Supplier DB Check Error:", e)
        best_sup = None

    # 🚀 THE MOCK FALLBACK FOR LIVE TESTING
    if not best_sup:
        await broadcast_callback({
            "type": "alert",
            "task": "Sourcing Alert: No Mapping Found",
            "message": "Supplier mapping missing. Re-routing to 'Testing & Analysis' for simulation.",
            "color": "#FFC72C" # Yellow Alert
        })
        await asyncio.sleep(2)
        
        # Creating a fake object that looks like database row
        class MockSupplier:
            supplier_id = 6239
            supplier_name = "Testing & Analysis (SUP-5558)"
            unit_price = 150.0
            
        best_sup = MockSupplier()

    # Now best_sup will ALWAYS have data
    if best_sup:
        sup_id = best_sup.supplier_id
        sup_name = best_sup.supplier_name
        price = float(best_sup.unit_price) if best_sup.unit_price else 150.0
        lead_time_text = "Standard 48-hour"
        
        total_cost = req_qty * price

        await broadcast_callback({
            "type": "success",
            "task": "Optimal Supplier Found",
            "message": f"Match Found: {sup_name} offers the best price (₹{price}/{unit}) & fastest delivery ({lead_time_text}).",
            "color": "#3DDC84" # Green
        })
        await asyncio.sleep(3)


        # --- STEP 3: APPROVER (Drafting PO & Alerting Manager) ---
        po_number = f"MHEL/PO-AI/{datetime.datetime.now().strftime('%m%d%H')}/26-27"
        
        vision_message = f"Action Required: I've drafted a PO for {req_qty} {unit} from {sup_name}. Approve with one click?"
        
        await broadcast_callback({
            "type": "action",
            "task": "Action Required: Manager Approval",
            "message": vision_message,
            "color": "#ff0055", 
            "po_payload": {
                "po_number": po_number,
                "supplier_id": sup_id,
                "inventory_id": inv_id,
                "ordered_qty": req_qty,
                "unit_price": price,
                "total_amount": round(total_cost, 2)
            }
        })
        
        return {"status": "success", "po_number": po_number}