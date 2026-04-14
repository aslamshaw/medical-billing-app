from datetime import datetime
from sqlalchemy import text
import app.extensions as ext
from app.models import fetch_one, insert_record


# -------------------------
# Helper function
# -------------------------
def get_or_create_medicine(conn, medicine_name):

    medicine = conn.execute(
        text("SELECT * FROM medicines WHERE name=:name"),
        {"name": medicine_name}
    ).mappings().first()

    if not medicine:
        conn.execute(
            text("INSERT INTO medicines (name) VALUES (:name)"),
            {"name": medicine_name}
        )

        medicine = conn.execute(
            text("SELECT * FROM medicines WHERE name=:name"),
            {"name": medicine_name}
        ).mappings().first()

    return medicine


# -------------------------
# Create Purchase
# -------------------------
def create_purchase(data):
    """
    Creates a purchase, its items, and updates inventory by creating batches.

    Input
    -----
    data:
    {
        "supplier_id": 1,
        "items": [
            {
                "medicine_name": "Crocin",
                "batch_number": "B301",
                "expiry_date": "2027-01-01",
                "quantity": 50,
                "purchase_price": 18,
                "selling_price": 25
            }
        ]
    }

    Output
    ------
    {
        "purchase_id": 1,
        "total": 900
    }

    Meaning
    -------
    Records medicines purchased from a supplier and converts them into
    inventory by:

    1. Creating a purchase record
    2. Storing purchase_items (invoice-level data)
    3. Resolving or creating the medicine in the medicines table
    4. Creating corresponding medicine_batches (inventory-level data)

    This ensures that inventory is derived directly from purchases.

    Current Behavior
    ----------------
    - Inventory IS updated via medicine_batches
    - Medicines are auto-created if not already present
    - Each purchase_item generates a new batch

    ⚠️ Known Limitations
    -------------------
    - supplier_id is not validated
    - duplicate (medicine_id, batch_number) entries are allowed
    - expiry_date format is not validated
    - no normalization of medicine names (case/spacing issues possible)
    - negative or invalid numeric values are not validated

    ⚠️ Architectural Notes
    ---------------------
    - purchase_items store medicine_name (not medicine_id)
      → allows flexible ingestion from supplier invoices
      → but duplicates source of truth with medicines table

    - medicine_batches represent actual inventory
      → billing system consumes from these batches using FEFO

    Future Improvements
    -------------------
    - enforce UNIQUE(medicine_id, batch_number)
    - validate inputs using schemas (Marshmallow/Pydantic)
    - normalize medicine names (lowercase/trim)
    - migrate purchase_items to use medicine_id
    - add foreign key constraints (when moving beyond SQLite)
    """

    supplier_id = data["supplier_id"]
    items = data["items"]

    total = 0

    with ext.engine.begin() as conn:

        # Defencive check for supplier_id existence
        supplier = conn.execute(
            text("SELECT id FROM suppliers WHERE id=:id"),
            {"id": supplier_id}
        ).first()

        if not supplier:
            raise Exception("Invalid supplier_id")

        # 1. Create purchase
        result = conn.execute(
            text("""
                INSERT INTO purchases (supplier_id, created_at, total_amount)
                VALUES (:supplier_id, :created_at, :total_amount)
            """),
            {
                "supplier_id": supplier_id,
                "created_at": datetime.utcnow().isoformat(),
                "total_amount": 0
            }
        )

        purchase_id = result.lastrowid

        # 2. Insert items
        for item in items:

            subtotal = item["quantity"] * item["purchase_price"]
            total += subtotal

            conn.execute(
                text("""
                    INSERT INTO purchase_items
                    (purchase_id, medicine_name, batch_number, expiry_date,
                     quantity, purchase_price, selling_price, subtotal)
                    VALUES
                    (:purchase_id, :medicine_name, :batch_number, :expiry_date,
                     :quantity, :purchase_price, :selling_price, :subtotal)
                """),
                {
                    "purchase_id": purchase_id,
                    "medicine_name": item["medicine_name"],
                    "batch_number": item["batch_number"],
                    "expiry_date": item["expiry_date"],
                    "quantity": item["quantity"],
                    "purchase_price": item["purchase_price"],
                    "selling_price": item["selling_price"],
                    "subtotal": subtotal
                }
            )

            # 3. resolve medicine
            medicine = get_or_create_medicine(conn, item["medicine_name"])

            # 4. create batch
            conn.execute(
                text("""
                    INSERT INTO medicine_batches
                    (medicine_id, batch_number, expiry_date,
                     purchase_price, selling_price, stock)
                    VALUES
                    (:medicine_id, :batch_number, :expiry_date,
                     :purchase_price, :selling_price, :stock)
                """),
                {
                    "medicine_id": medicine["id"],
                    "batch_number": item["batch_number"],
                    "expiry_date": item["expiry_date"],
                    "purchase_price": item["purchase_price"],
                    "selling_price": item["selling_price"],
                    "stock": item["quantity"]
                }
            )

        # 5. Update total
        conn.execute(
            text("""
                UPDATE purchases
                SET total_amount = :total
                WHERE id = :id
            """),
            {
                "total": total,
                "id": purchase_id
            }
        )

    return {"purchase_id": purchase_id, "total": total}
