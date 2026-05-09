from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import app.extensions as ext
"""
SQLAlchemy returns RowMapping objects when using:

    conn.execute(text(query), params)

To make results JSON serializable, we explicitly convert them to dicts.

For multiple rows:
    result = conn.execute(text(query), params)
    rows = result.mappings().all()
    → rows is: [RowMapping(...), RowMapping(...)]
    → convert with:
        [dict(row) for row in rows]

For single row:
    result = conn.execute(text(query), params)
    row = result.mappings().first()
    → RowMapping(...) or None
    → convert with:
        dict(row) if row else None

Note: RowMapping can work like python dict but it is unsafe for JSON.
"""


# -------------------------
# Helper function
# -------------------------
def create_or_get_medicine(conn, medicine_name: str):
    """
    Race-condition safe implementation.

    Strategy:
    1. Try to insert directly (atomic operation)
    2. If it already exists → ignore conflict
    3. Fetch the row (single source of truth)
    """

    # 1. Normalize input (important for duplicates)
    name = medicine_name.strip().lower()

    # 2. Try atomic insert (instead of throwing error for inserting existing medicine name by concurrent user)
    conn.execute(
        text("""
            INSERT INTO medicines (name)
            VALUES (:name)
            ON CONFLICT(name) DO NOTHING
        """),
        {"name": name}
    )

    # 3. Fetch the record (single read path)
    medicine = conn.execute(
        text("""
            SELECT id, name, is_active
            FROM medicines
            WHERE name = :name
        """),
        {"name": name}
    ).mappings().first()

    if not medicine:
        raise Exception(f"Medicine retrieval failed: {name}")

    return dict(medicine)


def create_or_restock_batch(conn, medicine_id, item):
    """
    Creates a new batch OR restocks existing batch.

    Rules
    -----
    - Same medicine_id + batch_number is treated as the same physical batch
    - Existing batch metadata must match exactly
    - Only stock can increase

    Raises
    ------
    Exception
        If existing batch metadata conflicts
    """

    try:
        # Try creating batch directly
        result = conn.execute(
            text("""
                    INSERT INTO medicine_batches
                    (medicine_id, batch_number, expiry_date,
                     purchase_price, selling_price, stock)
                    VALUES
                    (:medicine_id, :batch_number, :expiry_date,
                     :purchase_price, :selling_price, :stock)
                """),
            {
                "medicine_id": medicine_id,
                "batch_number": item["batch_number"],
                "expiry_date": item["expiry_date"],
                "purchase_price": item["purchase_price"],
                "selling_price": item["selling_price"],
                "stock": item["quantity"]
            }
        )

        return {
            "batch_id": result.lastrowid,
            "action": "created"
        }

    # If INSERT fails due to UNIQUE(medicine_id, batch_number)
    except IntegrityError:

        # Check if another concurrent request already created it
        existing_batch = conn.execute(
            text("""
                    SELECT *
                    FROM medicine_batches
                    WHERE medicine_id = :medicine_id
                      AND batch_number = :batch_number
                """),
            {
                "medicine_id": medicine_id,
                "batch_number": item["batch_number"]
            }
        ).mappings().first()

        if not existing_batch:
            raise Exception("Batch retrieval failed after conflict")

        # Validate metadata consistency, same batch should have expiry date and pricing exactly same
        if (
                existing_batch["expiry_date"] != item["expiry_date"]
                or existing_batch["purchase_price"] != item["purchase_price"]
                or existing_batch["selling_price"] != item["selling_price"]
        ):
            raise Exception(
                f"Batch metadata mismatch for batch {item['batch_number']}"
            )

        # Restock existing batch
        conn.execute(
            text("""
                    UPDATE medicine_batches
                    SET stock = stock + :qty
                    WHERE id = :id
                """),
            {
                "qty": item["quantity"],
                "id": existing_batch["id"]
            }
        )

        return {
            "batch_id": existing_batch["id"],
            "action": "restocked"
        }


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
    - purchase_item either creates OR restocks batch

    ⚠️ Known Limitations
    -------------------
    - supplier_id is not validated
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
            {"id": supplier_id}).mappings().first()

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

            # 3. resolve medicine
            """
            Get medicine id and medicine name from medicines table to use in purchase_items table
            instead of using medicine name from the frontend as we normalized the medicine name.
            User inputs dolo -> database matches normalized name -> returns the corresponding row from medicines table.
            """
            medicine = create_or_get_medicine(conn, item["medicine_name"])

            if medicine is None:
                raise Exception(f"Medicine creation/retrieval failed: {item['medicine_name']}")

            # Entry for purchase_items is created even for existing medicine batch, medicine_batches is updated later
            conn.execute(
                text("""
                    INSERT INTO purchase_items
                    (purchase_id, medicine_id, medicine_name, batch_number, expiry_date,
                     quantity, purchase_price, selling_price, subtotal)
                    VALUES
                    (:purchase_id, :medicine_id, :medicine_name, :batch_number, :expiry_date,
                     :quantity, :purchase_price, :selling_price, :subtotal)
                """),
                {
                    "purchase_id": purchase_id,
                    "medicine_id": medicine["id"],
                    "medicine_name": medicine["name"],  # better than user input i.e. item["medicine_name"]
                    "batch_number": item["batch_number"],
                    "expiry_date": item["expiry_date"],
                    "quantity": item["quantity"],
                    "purchase_price": item["purchase_price"],
                    "selling_price": item["selling_price"],
                    "subtotal": subtotal
                }
            )

            # 4. Create or restock batch
            create_or_restock_batch(conn, medicine["id"], item)

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
