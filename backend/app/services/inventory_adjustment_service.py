from sqlalchemy import text
from datetime import datetime
import app.extensions as ext


# -------------------------
# Adjust Batch Stock (SAFE VERSION - SQLite CAS based)
# -------------------------
def adjust_batch_stock(batch_id, new_stock, reason):
    """
    Adjust stock of a medicine batch with concurrency-safe update and audit logging.

    This function is designed for SQLite MVP but uses a production-safe pattern
    called Compare-And-Set (CAS) to avoid race conditions.

    Input
    ------
    batch_id   : int  -> ID of batch to update
    new_stock  : int  -> final stock value after adjustment
    reason     : str  -> reason for adjustment

    Allowed reasons:
    - DAMAGED
    - LOST
    - EXPIRED

    Output
    ------
    {
        "batch_id": 1,
        "old_stock": 10,
        "new_stock": 5,
        "reason": "DAMAGED"
    }
    """
    # ------------------------------------------------------------
    # STEP 1: validate input
    # ------------------------------------------------------------

    if new_stock < 0:
        raise Exception("Stock cannot be negative")

    if reason not in {"DAMAGED", "LOST", "EXPIRED"}:
        raise Exception("Invalid reason")

    with ext.engine.begin() as conn:

        # ---------------------------------------------------------
        # STEP 2: read current stock (needed for CAS comparison)
        # ---------------------------------------------------------
        #
        # We must fetch current value so we can use it in:
        #   WHERE stock = :old_stock
        #
        # NOTE:
        # This read is NOT protected from concurrent writes.
        # Protection happens at UPDATE time (CAS check).
        # ---------------------------------------------------------
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

        old_stock = batch["stock"]

        # ---------------------------------------------------------
        # STEP 3: CAS UPDATE (CRITICAL PART)
        # ---------------------------------------------------------
        #
        # This is the concurrency safety mechanism.
        #
        # The condition:
        #   AND stock = :old_stock
        #
        # means:
        #   "Only update if no other transaction changed stock"
        #
        # This prevents:
        #   - lost updates
        #   - stale writes
        #   - silent overwrites
        # ---------------------------------------------------------
        result = conn.execute(
            text("""
                UPDATE medicine_batches
                SET stock = :new_stock
                WHERE id = :batch_id
                  AND stock = :old_stock
            """),
            {
                "new_stock": new_stock,
                "batch_id": batch_id,
                "old_stock": old_stock
            }
        )

        # ---------------------------------------------------------
        # STEP 4: concurrency failure detection
        # ---------------------------------------------------------
        #
        # If rowcount == 0, it means:
        #   - stock was modified by another request
        #   - CAS condition failed
        #
        # So we MUST abort safely.
        # ---------------------------------------------------------
        if result.rowcount == 0:
            raise Exception(
                "Stock update failed due to concurrent modification. Retry required."
            )

        # ---------------------------------------------------------
        # STEP 5: audit log (ONLY after successful update)
        # ---------------------------------------------------------
        #
        # IMPORTANT:
        # We only log AFTER confirming update succeeded.
        #
        # Why?
        # If we log before checking rowcount, we could store:
        #   - fake stock changes
        #   - non-existent updates
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # STEP 6: response
        # ---------------------------------------------------------
        return {
            "batch_id": batch_id,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "reason": reason
        }


"""
This function uses CAS (Compare-And-Set) instead of blind UPDATE.

CAS pattern:
    UPDATE ... WHERE id = X AND stock = OLD_VALUE

Meaning:
    "Only update if the value has NOT changed since I last read it"


WHY THIS IS REQUIRED (CRITICAL)
------------------------------------------------------------

Without CAS:

    Request A reads stock = 10
    Request B reads stock = 10

    A sets stock = 5
    B sets stock = 3  → overwrites A silently

Final state becomes:
    stock = 3 (A's update LOST)

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

Scenario:

Initial state:
    stock = 10

Request A:
    reads stock = 10
    tries UPDATE WHERE stock = 10 → SUCCESS → sets 5

Request B:
    still thinks stock = 10
    tries UPDATE WHERE stock = 10 → FAILS (row changed)

Result:
    - only one update wins
    - second update is rejected
    - no silent overwrite


SQLITE BEHAVIOR NOTE (IMPORTANT)
------------------------------------------------------------

SQLite does NOT support:
    SELECT ... FOR UPDATE (row locking)

So we cannot rely on:
    pessimistic locking

Instead we use:
    optimistic locking (CAS pattern)
"""