from sqlalchemy import text
import app.extensions as ext


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

    with ext.engine.connect() as conn:
        result = conn.execute(
            text("""
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
            """)
        )

        rows = result.mappings().all()
        return [dict(row) for row in rows]


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

    with ext.engine.connect() as conn:
        result = conn.execute(
            text("""
            SELECT * FROM medicines
            WHERE name LIKE :keyword
            ORDER BY name
            """),
            {"keyword": f"%{keyword}%"}
        )

        rows = result.mappings().all()
        return [dict(row) for row in rows]


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

    with ext.engine.begin() as conn:
        result = conn.execute(
            text("""
            UPDATE medicines
            SET name=:name
            WHERE id=:id
            """),
            {
                "id": medicine_id,
                "name": data["name"]
            }
        )

        if result.rowcount == 0:
            raise Exception(f"Medicine with id {medicine_id} not found")

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

    with ext.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM medicine_batches WHERE medicine_id=:id"),
            {"id": medicine_id}
        )

        result = conn.execute(
            text("DELETE FROM medicines WHERE id=:id"),
            {"id": medicine_id}
        )

        if result.rowcount == 0:
            raise Exception(f"Medicine with id {medicine_id} not found")

    return {"message": "Medicine deleted"}