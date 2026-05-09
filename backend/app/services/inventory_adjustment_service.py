from sqlalchemy import text
from datetime import datetime
import app.extensions as ext


# ------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------

def cas_adjust_batch_stock(conn, batch_id, adjustment, reason):
    """
    Performs a single Compare And Set based stock update attempt.

    Input
    ------
    batch_id    : int
    adjustment  : int
    reason      : str

    Output
    ------
    {
        "old_stock": int,
        "new_stock": int | None
    }

    NOTE:
    This function does NOT retry.
    It represents ONE atomic attempt only.
    """

    batch = conn.execute(
        text("""
            SELECT stock
            FROM medicine_batches
            WHERE id = :id
        """),
        {"id": batch_id}
    ).mappings().first()

    if not batch:
        raise Exception("Batch not found")

    # Before updating the stock extract that stale stock as old_stock
    old_stock = batch["stock"]
    new_stock = old_stock + adjustment

    # The updated stock should always be positive thus deduct quantity should be smaller than the stock present
    if new_stock < 0:
        raise Exception("INSUFFICIENT_STOCK")

    result = conn.execute(
        text("""
            UPDATE medicine_batches
            SET stock = :new_stock
            WHERE id = :batch_id
              AND stock = :old_stock
        """),
        {
            "batch_id": batch_id,
            "old_stock": old_stock,
            "new_stock": new_stock
        }
    )

    # CAS condition `stock = :old_stock` would fail if a concurrent update changed the stock, no rows would be updated
    if result.rowcount == 0:
        raise Exception("CAS_CONFLICT")

    conn.execute(
        text("""
            INSERT INTO stock_adjustments
            (batch_id, old_stock, new_stock, reason, created_at)
            VALUES
            (:batch_id, :old_stock, :new_stock, :reason, :created_at)
        """),
        {
            "batch_id": batch_id,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "reason": reason,
            "created_at": datetime.utcnow().isoformat()
        }
    )

    return {
        "old_stock": old_stock,
        "new_stock": new_stock
    }


# ------------------------------------------------------------
# Try Adjust Batch Stock
# ------------------------------------------------------------
def try_adjust_batch_stock(batch_id, adjustment, reason):
    """
    Adjust stock of a medicine batch using delta-based updates
    with concurrency-safe Compare-And-Set (CAS) protection + retry layer.

    Input
    ------
    batch_id   : int  -> ID of batch to update
    adjustment : int  -> stock delta (+ increase, - decrease)
    reason     : str  -> reason for adjustment

    Allowed reasons:
        - DAMAGED
        - LOST
        - EXPIRED
        - RESTOCK
        - SALE_ADJUSTMENT

    Output
    ------
    {
        "batch_id": 1,
        "old_stock": 10,
        "adjustment": -2,
        "new_stock": 8,
        "reason": "SALE_ADJUSTMENT"
    }
    """

    if not isinstance(adjustment, int):
        raise Exception("Adjustment must be an integer")

    if reason not in {"DAMAGED", "LOST", "EXPIRED", "RESTOCK", "SALE_ADJUSTMENT"}:
        raise Exception("Invalid reason")

    with ext.engine.begin() as conn:

        result = cas_adjust_batch_stock(conn, batch_id, adjustment, reason)

        return {
            "batch_id": batch_id,
            "old_stock": result["old_stock"],
            "adjustment": adjustment,
            "new_stock": result["new_stock"],
            "reason": reason
        }


# ------------------------------------------------------------
# PUBLIC API: Adjust Batch Stock
# ------------------------------------------------------------
MAX_RETRIES = 3


def adjust_batch_stock(batch_id, adjustment, reason):

    for attempt in range(MAX_RETRIES):
        try:
            return try_adjust_batch_stock(batch_id, adjustment, reason)

        except Exception as e:
            if "CAS_CONFLICT" in str(e) and attempt < MAX_RETRIES - 1:
                continue
            raise

    raise Exception("Stock update failed after retries")



"""
This function uses CAS (Compare-And-Set) instead of blind UPDATE.

CAS pattern:
    UPDATE ... WHERE id = X AND stock = OLD_VALUE

Meaning:
    "Only update if the value has NOT changed since I last read it"


WHY THIS IS REQUIRED (CRITICAL)
------------------------------------------------------------

Without CAS:

    Initial stock = 10

    Request A wants: -5
    Request B wants: -7

    A reads stock = 10
    B reads stock = 10

    A computes new_stock = 10 - 5 = 5
    B computes new_stock = 10 - 7 = 3

    A updates stock → 5
    B updates stock → 3  → overwrites A silently

Final state becomes:
    stock = 3

Problem:
    A's adjustment (-5) is LOST

Correct result should have been:
    10 - 5 - 7 = -2 (or rejected if negative not allowed)

This is called:
    LOST UPDATE PROBLEM


HOW CAS FIXES THIS
------------------------------------------------------------

We enforce:

    UPDATE medicine_batches
    SET stock = :new_stock
    WHERE id = :batch_id
      AND stock = :old_stock

Now:

Initial state:
    stock = 10

Request A:
    reads stock = 10
    computes new_stock = 5
    updates → SUCCESS

Request B:
    still has old_stock = 10
    tries to set new_stock = 3
    BUT database stock is now 5

    UPDATE ... WHERE stock = 10 → FAILS

Result:
    - only one update succeeds
    - second update detects conflict
    - caller retries with fresh stock


RETRY FLOW (IMPORTANT)
------------------------------------------------------------

On retry:

    Request B reads updated stock = 5
    computes new_stock = 5 - 7 = -2
    → rejected (negative stock not allowed)

So:
    - no overwrite
    - no lost adjustment
    - business rules preserved


SQLITE BEHAVIOR NOTE (IMPORTANT)
------------------------------------------------------------

SQLite does NOT support:
    SELECT ... FOR UPDATE

So we cannot rely on:
    pessimistic locking

Instead we use:
    optimistic locking (CAS pattern)
"""