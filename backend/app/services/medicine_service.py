from app.models import insert_record, fetch_one, fetch_all, execute_write


# -------------------------
# Create Medicine + Batch
# -------------------------
def create_medicine(data):
    raise Exception("Direct medicine creation disabled. Use purchase API.")
    """
    Input
    -----
    {
        "name": "Crocin",
        "batch_number": "B101",
        "expiry_date": "2026-01-01",
        "purchase_price": 18,
        "selling_price": 25,
        "stock": 50
    }

    Meaning
    -------
    Adds a medicine batch. If the medicine does not exist in the
    medicines table, it will be created first.

    Output
    ------
    {
        "message": "Medicine batch added"
    }
    """

    # check if medicine exists
    medicine = fetch_one(
        "SELECT * FROM medicines WHERE name=:name",
        {"name": data["name"]}
    )

    if not medicine:

        insert_record("medicines", {"name": data["name"]})

        # fetch again to get generated primary key i.e. medicine_id
        medicine = fetch_one(
            "SELECT * FROM medicines WHERE name=:name",
            {"name": data["name"]}
        )

    # prepare batch data using medicine_id and input data for insertion into the medicine_batches table
    batch_data = {
        "medicine_id": medicine["id"],
        "batch_number": data["batch_number"],
        "expiry_date": data["expiry_date"],
        "purchase_price": data["purchase_price"],
        "selling_price": data["selling_price"],
        "stock": data["stock"]
    }

    insert_record("medicine_batches", batch_data)

    return {"message": "Medicine batch added"}


# -------------------------
# List All Medicines
# -------------------------
def list_medicines():
    """
    Input
    -----
    None

    Output
    ------
    [
        {
            "id": 1,
            "name": "Crocin",
            "total_stock": 80
        },
        {
            "id": 2,
            "name": "Paracetamol",
            "total_stock": 120,
            "valid_stock": 110
        }
    ]

    Meaning
    -------
    Returns all medicines with their total stock calculated
    from all batches.
    """

    return fetch_all(
        """
        SELECT
            m.id,
            m.name,
            COALESCE(SUM(b.stock),0) as total_stock,
            COALESCE(SUM(
              CASE
                WHEN DATE(b.expiry_date) >= DATE('now')
                THEN b.stock
                ELSE 0
              END
            ), 0) AS valid_stock
        FROM medicines m
        LEFT JOIN medicine_batches b
        ON m.id = b.medicine_id
        GROUP BY m.id
        ORDER BY m.name
        """
    )


# -------------------------
# Search Medicines
# -------------------------
def search_medicines(keyword):
    """
    Input
    -----
    keyword : str

    Example
    -------
    "cro"

    Output
    ------
    [
        {
            "id": 1,
            "name": "Crocin"
        }
    ]

    Meaning
    -------
    Returns medicines whose names match the search keyword.
    We did left join instead of adding medicine name in medicine_batches table because that would be
    duplication of column. Never store the same fact in multiple places.
    Medicine name depends only on medicine_id so it belongs only in medicines, not in medicine_batches.
    """

    return fetch_all(
        """
        SELECT * FROM medicines
        WHERE name LIKE :keyword
        ORDER BY name
        """,
        {"keyword": f"%{keyword}%"}
    )


# -------------------------
# Update Medicine Name
# -------------------------
def update_medicine(medicine_id, data):
    """
    Input
    -----
    medicine_id : int

    data :
    {
        "name": "Crocin 500mg"
    }

    Output
    ------
    {
        "message": "Medicine updated"
    }

    Meaning
    -------
    Updates the medicine name in the medicines table.
    """

    query = """
    UPDATE medicines
    SET name=:name
    WHERE id=:id
    """

    execute_write(
        query,
        {
            "id": medicine_id,
            "name": data["name"]
        }
    )

    return {"message": "Medicine updated"}


# -------------------------
# Delete Medicine + Batches
# -------------------------
def delete_medicine(medicine_id):
    """
    Input
    -----
    medicine_id : int

    Example
    -------
    3

    Output
    ------
    {
        "message": "Medicine deleted"
    }

    Meaning
    -------
    Deletes the medicine and all its batches from the database.
    """

    execute_write(
        "DELETE FROM medicine_batches WHERE medicine_id=:id",
        {"id": medicine_id}
    )

    execute_write(
        "DELETE FROM medicines WHERE id=:id",
        {"id": medicine_id}
    )

    return {"message": "Medicine deleted"}
