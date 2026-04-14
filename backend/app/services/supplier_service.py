from app.models import insert_record, fetch_all


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
    {
        "message": "Supplier created"
    }

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

    insert_record("suppliers", data)

    return {"message": "Supplier created"}


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

    return fetch_all("SELECT * FROM suppliers ORDER BY name")
