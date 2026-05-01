from sqlalchemy import text
import app.extensions as ext


# -------------------------
# Create Supplier
# -------------------------
def create_supplier(data):
    """
    Creates a supplier record.

    Input
    -----
    data:
    {
        "name": "ABC Pharma",
        "phone": "9876543210",
        "address": "Chennai"
    }

    Output
    ------
    { "id": 1, "name": "ABC Pharma", "phone": "9876543210", "address": "Chennai"}

    Meaning
    -------
    Stores supplier details for later use in purchases.

    ⚠️ Current Weakness
    ------------------
    - Allows duplicate supplier names
    - No validation for phone format
    - Empty name possible

    Future Fix
    ----------
    - Add UNIQUE(name)
    - Add schema validation (Marshmallow)
    """

    with ext.engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO suppliers (name, phone, address)
                VALUES (:name, :phone, :address)
            """),
            data
        )

        supplier_id = result.lastrowid

        supplier = conn.execute(
            text("SELECT * FROM suppliers WHERE id = :id"),
            {"id": supplier_id}
        ).mappings().first()

    return dict(supplier) if supplier else None


# -------------------------
# List Suppliers
# -------------------------
def list_suppliers():
    """
    Retrieves all suppliers.

    Input
    -----
    None

    Output
    ------
    [
        {
            "id": 1,
            "name": "ABC Pharma",
            "phone": "9876543210",
            "address": "Chennai"
        }
    ]

    Meaning
    -------
    Returns all suppliers ordered by name.

    ⚠️ Current Weakness
    ------------------
    - No pagination (will break at scale)
    - No filtering/search
    """

    with ext.engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM suppliers ORDER BY name")
        )

        rows = result.mappings().all()
        return [dict(row) for row in rows]