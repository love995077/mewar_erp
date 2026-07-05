from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db

router = APIRouter()

# ========================================================
# THE ACTION API (INSERT INTO ERP DATABASE)
# ========================================================
@router.post("/api/confirm-po")
def confirm_po_in_db(payload: dict, db: Session = Depends(get_db)):
    try:
        po_num = payload.get("po_number")
        sup_id = payload.get("supplier_id")
        tot_amt = payload.get("total_amount")
        inv_id = payload.get("inventory_id")
        qty = payload.get("ordered_qty")
        price = payload.get("unit_price")
        
        # 1. Master Table mein Insert (Fix: remaining_amount kiya hai)
        insert_po = text("""
            INSERT INTO purchase_orders 
            (po_number, supplier_id, po_date, total_qty, total_amount, remaining_amount, status, created_at) 
            VALUES (:po, :sup, CURDATE(), :qty, :tot, :tot, 'Approved', NOW())
        """)
        db.execute(insert_po, {"po": po_num, "sup": sup_id, "qty": qty, "tot": tot_amt})
        
        # 2. Get the new PO ID
        po_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        
        # 3. Items Table mein Insert
        insert_poi = text("""
            INSERT INTO purchase_order_items
            (purchase_order_id, inventory_id, ordered_qty, unit_price, taxable_total, line_total, created_at)
            VALUES (:po_id, :inv_id, :qty, :price, :tot, :tot, NOW())
        """)
        db.execute(insert_poi, {"po_id": po_id, "inv_id": inv_id, "qty": qty, "price": price, "tot": tot_amt})
        
        db.commit()
        return {"status": "success", "message": f"PO {po_num} inserted!"}
    
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    

@router.get("/api/delete-test-po")
def delete_test_po(db: Session = Depends(get_db)):
    try:
        # 1. Pehle Items delete karo
        db.execute(text("DELETE FROM purchase_order_items WHERE purchase_order_id = (SELECT id FROM purchase_orders WHERE po_number = 'MHEL/PO-AI/070517/26-27')"))
        # 2. Phir Main PO delete karo
        db.execute(text("DELETE FROM purchase_orders WHERE po_number = 'MHEL/PO-AI/070517/26-27'"))
        
        db.commit()
        return {"status": "success", "message": "Test PO Successfully Deleted!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}