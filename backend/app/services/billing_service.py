from datetime import datetime, date, timedelta
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import app.extensions as ext


# -------------------------
# Helper: CAS check
# -------------------------
def cas_deduct_batch_stock(conn, batch_id, deduct_qty):
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
    new_stock = old_stock - deduct_qty

    # The updated stock should always be positive thus deduct quantity should be smaller than the stock present
    if new_stock < 0:
        raise Exception("INSUFFICIENT_STOCK")

    result = conn.execute(
        text("""
            UPDATE medicine_batches
            SET stock = :new_stock
            WHERE id = :id AND stock = :old_stock
        """),
        {
            "id": batch_id,
            "old_stock": old_stock,
            "new_stock": new_stock
        }
    )

    # CAS condition `stock = :old_stock` would fail if a concurrent update changed the stock, no rows would be updated
    if result.rowcount == 0:
        raise Exception("CAS_CONFLICT")

    return None


# -------------------------
# Helper: Deduct stock FEFO
# -------------------------
def deduct_stock_fefo(conn, medicine_id, qty, *, deduct=True):
    """
    Deducts 'qty' units of a medicine using FEFO (First Expiry First Out) logic.

    Batches are selected in ascending order of expiry date, ensuring that
    stock closest to expiration is used first. Expired batches are ignored.
    Works correctly even if expiry_date includes time.

    Parameters
    ----------
    conn : SQLAlchemy connection
        Active database connection. Must be inside a transaction when deduct=True.
    medicine_id : int
        ID of the medicine to process.
    qty : int
        Quantity required.

    deduct : bool (default=True)
        Controls whether the function performs actual stock mutation.

        - True  → COMMIT MODE
          Updates database stock (used during billing).
          Requires an active transaction (engine.begin()).

        - False → SIMULATION MODE
          Does NOT modify database.
          Used for previewing FEFO allocation before billing.

    Returns
    -------
    list of dict
        [
            {
                "batch_id": 3,
                "deducted": 10,
                "price": 25,
                "expiry_date": "2026-01-01"
            },
            {
                "batch_id": 5,
                "deducted": 5,
                "price": 26,
                "expiry_date": "2026-03-01"
            }
        ]

    Raises
    ------
    Exception
        If sufficient non-expired stock is not available,
        or if a concurrency conflict occurs during update.

    ---------------------------------------------------------------------

    Why the 'deduct' flag exists

    The same FEFO logic is reused for two different purposes:

    1. Simulation (Preview)
       Determine how stock *would be allocated* without actually changing it.

    2. Commit (Billing)
       Perform real stock deduction and persist the result.

    This avoids duplicating logic and ensures consistency between preview
    and actual billing behavior.

    ---------------------------------------------------------------------

    Two-Step Billing Workflow

    This design enables a structured and safer billing process:

    1. Preview Phase (Simulation)
       The system simulates FEFO allocation before bill creation, showing how the
       requested quantities will be distributed across available batches based on expiry.
       No stock is modified during this step.

    2. Validation Step
       The user verifies that the simulated allocation aligns with the actual physical
       inventory. This helps identify discrepancies such as damaged, missing, or
       incorrectly recorded stock.

    3. Commit Phase (Actual Billing)
       Once validated, the system proceeds with bill creation. FEFO runs in commit mode,
       deducting stock, inserting bill and batch records, and generating the final receipt.

    This separation improves reliability by avoiding premature stock mutation and
    introduces a practical validation layer between system data and real-world inventory.

    Production notes:
    ------------------
    - Expiry date validation is intentionally deferred; frontend already restricts input via HTML date field,
      and strict ISO (YYYY-MM-DD) enforcement will be added later at the schema/serialization layer (like Marshmallow).
    """

    today = date.today().isoformat()

    # Fetch non-expired batches in FEFO order
    batches = conn.execute(
        text("""
            SELECT *
            FROM medicine_batches
            WHERE medicine_id = :medicine_id
              AND stock > 0
              AND DATE(expiry_date) >= DATE(:today)
            ORDER BY DATE(expiry_date) ASC
        """),
        {"medicine_id": medicine_id, "today": today}
    ).mappings().all()

    remaining = qty
    deductions = []

    for batch in batches:
        if remaining <= 0:
            break

        available = batch["stock"]
        deduct_qty = min(available, remaining)

        # ---------------------------------------------------------
        # ONLY COMMIT MODE ACTUALLY MODIFIES DATABASE
        # ---------------------------------------------------------
        if deduct:
            # FIX: CAS-based deduction replaces stock >= deduct logic
            cas_deduct_batch_stock(conn, batch["id"], deduct_qty)

        # Record deduction with price (same for simulate and commit)
        deductions.append({
            "batch_id": batch["id"],
            "deducted": deduct_qty,
            "price": batch["selling_price"],
            "expiry_date": batch["expiry_date"]
        })

        remaining -= deduct_qty

    if remaining > 0:
        raise Exception(f"Insufficient non-expired stock for medicine_id {medicine_id}")

    return deductions


# -------------------------
# FEFO Preview (NO stock mutation)
# -------------------------
def preview_fefo(cart_items):
    """
    Simulates FEFO allocation for a cart without modifying stock.

    Input
    -----
    cart_items: [
        {"medicine_id": 1, "quantity": 15},
        {"medicine_id": 2, "quantity": 5}
    ]

    Output
    ------
    {
        "items": [
            {
                "medicine_id": 1,
                "requested_qty": 10,
                "allocations": [
                    {"batch_id": 5, "qty": 6, "expiry_date": "2025-01-01"},
                    {"batch_id": 8, "qty": 4, "expiry_date": "2025-03-01"}
                ]
            }
        ],
        "total": 120,
        "note": "Stock allocation may change during billing due to concurrent updates"
    }

    Note:
    A transaction is a safety wrapper, either ALL database changes succeed, or NONE of them are applied.

    conn.connect() → just opens a pipe to the database

    conn.begin() → starts a “protected block” where changes are grouped
    conn.in_transaction() → tells you if you're currently inside that block

    That is why to simulate FEFO engine.connect() is used.

    Purpose:
    -------
    The preview window allows the pharmacist to inspect FEFO-based batch allocation
    and verify it against physical inventory before billing.

    This step is advisory only. Stock may differ from database due to real-world
    issues (damage, missing items) or concurrent billing by other users.

    For this reason, preview data is NOT passed to commit. The commit phase always
    recomputes FEFO using the latest database state, ensuring correctness.

    Example:
    1. Preview: Batch X → 6, Batch Y → 4 (for 10 units)
    2. Another user sells 5 units from Batch X
    3. Commit recomputes:
       Batch X → 1, Batch Y → 4, Batch Z → 5

    This guarantees correctness under concurrency and prevents stale allocations.
    """

    results = []
    total = 0

    with ext.engine.connect() as conn:  # .connect is used to avoid transactions
        for item in cart_items:
            medicine_id = item["medicine_id"]
            qty = item["quantity"]

            # Validate medicine existence
            medicine = conn.execute(
                text("SELECT id FROM medicines WHERE id = :id AND is_active = 1"),
                {"id": medicine_id}
            ).mappings().first()

            if not medicine:
                raise Exception(f"Invalid medicine_id {medicine_id}")

            # FEFO simulation
            allocations = deduct_stock_fefo(conn, medicine_id, qty, deduct=False)

            # Price is assumed consistent per batch allocation
            item_total = sum(a["deducted"] * a["price"] for a in allocations)
            total += item_total

            results.append({
                "medicine_id": medicine_id,
                "requested_qty": qty,
                "subtotal": item_total,
                "allocations": [
                    {
                        "batch_id": a["batch_id"],
                        "qty": a["deducted"],
                        "price": a["price"],
                        "batch_subtotal": a["deducted"] * a["price"],
                        "expiry_date": a["expiry_date"]
                    }
                    for a in allocations
                ]
            })

    return {
        "items": results,
        "total": total,
        "note": "Stock allocation may change during billing due to concurrent updates"
    }


# -------------------------
# Helper: Reserve bill request and return request status
# -------------------------
PROCESSING_TIMEOUT_SECONDS = 300  # 5 minutes


def reserve_idempotency_key(conn, idempotency_key):
    """
    Attempts to reserve an idempotency key safely.

    Returns:
        "RESERVED"
        "COMPLETED"
        "PROCESSING"

    Strategy
    --------
    1. Try inserting PROCESSING row
    2. If insert succeeds:
           -> this request owns processing
    3. If insert conflicts:
           -> inspect existing row
    4. COMPLETED:
           -> safe replay
    5. PROCESSING but fresh:
           -> another worker still active
    6. PROCESSING but stale:
           -> attempt CAS-style takeover
    """

    now = datetime.utcnow()

    # 1. Try to reserve key
    # First request: bill_id is not yet created i.e. null also bill_request status is "PROCESSING"
    # created_at and updated_at are both the current request's created time.
    try:
        conn.execute(
            text("""
                INSERT INTO bill_requests
                (idempotency_key, status, created_at, updated_at)
                VALUES
                (:key, 'PROCESSING', :now, :now)
            """),
            {
                "key": idempotency_key,
                "now": now.isoformat()
            }
        )

        # Successfully reserved as the bill_request status is "PROCESSING"
        # This worker own the billing job. Now this request continues into stock deduction -> bill creation
        return "RESERVED"

    # 2. Key already exist, get the existing bill_request of that key
    except IntegrityError:

        existing = conn.execute(
            text("""
                SELECT id, status, updated_at
                FROM bill_requests
                WHERE idempotency_key = :key
            """),
            {"key": idempotency_key}
        ).mappings().first()

        if not existing:
            raise Exception("Idempotency row missing after conflict")

        # 3. Existing bill_request has already been completed i.e. bill is created
        if existing["status"] == "COMPLETED":
            return "COMPLETED"

        # 4. Request is still in process
        # Get the existing updated_at and calculate time passed since the existing request and this current request
        existing_updated_at = existing["updated_at"]
        age_seconds = (now - datetime.fromisoformat(existing_updated_at)).total_seconds()

        # 4a Fresh processing request: Current request is under timeout
        # Another worker is probably still actively billing, raise Exception for this request
        if age_seconds <= PROCESSING_TIMEOUT_SECONDS:
            return "PROCESSING"

        # 4b Stale processing request: Current request is above timeout
        # Existing worker is dead. Someone must recover it.
        # Attempt CAS-style takeover, only recover ownership if updated_at has NOT changed by concurrent stale requests.
        # This prevents two retry requests from simultaneously taking ownership.
        # Update the updated_at for the existing bill_request with this stale processing request's created time.
        result = conn.execute(
            text("""
                UPDATE bill_requests
                SET updated_at = :now
                WHERE id = :id
                  AND updated_at = :old_updated_at
            """),
            {
                "id": existing["id"],
                "now": now.isoformat(),
                "old_updated_at": existing_updated_at
            }
        )

        # CAS Success: For the existing bill_request, updated_at time has been updated
        # This worker now takes the ownership and continues making the bill as the bill_request is reserved
        if result.rowcount == 1:
            return "RESERVED"

        # CAS Filed: Another concurrent stale processing request already took the ownership
        # This request lost the race to a concurrent request
        return "PROCESSING"


# -------------------------
# Helper: Set request status as completed
# -------------------------
def mark_bill_request_completed(conn, idempotency_key, bill_id):

    conn.execute(
        text("""
            UPDATE bill_requests
            SET
                status = 'COMPLETED',
                bill_id = :bill_id
            WHERE idempotency_key = :key
        """),
        {
            "bill_id": bill_id,
            "key": idempotency_key
        }
    )


# -------------------------
# Helper: Get the completed bill
# -------------------------
def get_completed_bill(conn, idempotency_key):

    row = conn.execute(
        text("""
            SELECT
                br.bill_id,
                b.total_amount
            FROM bill_requests br
            JOIN bills b
                ON br.bill_id = b.id
            WHERE br.idempotency_key = :key
              AND br.status = 'COMPLETED'
        """),
        {"key": idempotency_key}
    ).mappings().first()

    return dict(row) if row else None


# -------------------------
# Try Create Bill
# -------------------------
def try_create_bill(idempotency_key, cart_items):
    """
    Processes a cart of medicines, deducts stock FEFO,
    inserts bill and bill_items, returns bill id and total.

    Input
    -----
    cart_items: [
        {"medicine_id": 1, "quantity": 15},
        {"medicine_id": 2, "quantity": 5}
    ]

    Output
    ------
    {"bill_id": 3, "total": 450}

    Retry-safe billing (idempotency key):
    ------------------------------------
    Network failures or client retries can cause duplicate billing requests.
    To prevent duplicate bills and double stock deduction, each request will
    later include an idempotency_key that ensures the same request is processed
    only once.

    Example:
    1. Client sends request with idempotency_key = "abc123"
    2. Server creates Bill ID = 101 and stores the key
    3. Network timeout occurs before response is received
    4. Client retries same request with idempotency_key = "abc123"
    5. Server detects existing bill and returns Bill ID = 101 (no re-processing)


    Production notes:
    ------------------
    - Moving to MySQL will introduce row-level locking and transactional isolation
      to further reduce race conditions during stock updates.
    - Authentication will be added to track which user performs billing and
      stock adjustments for auditability.
    - To match preview stock with committed stock, preview stock can be temporarily reserved
      for a period of 2–5 minutes, during which the pharmacist can check the physical stock.
      If the time expires, the reservation becomes stale, and the preview stock may not match the committed stock
      due to concurrent updates to that medicine’s stock by other users.
    """
    total = 0

    with ext.engine.begin() as conn:

        # 1. Store the bill request with idempotency_key
        # For first request status = "RESERVED", but bill_requests's status column is "PROCESSING"
        status = reserve_idempotency_key(conn, idempotency_key)

        # Duplicate completed request
        if status == "COMPLETED":

            existing_bill = get_completed_bill(conn, idempotency_key)

            if not existing_bill:
                raise Exception("Completed request missing bill")

            return {
                "bill_id": existing_bill["bill_id"],
                "total": existing_bill["total_amount"],
                "idempotent_replay": True
            }

        # This won't trigger for the first request as status === "RESERVED"
        # Other requests with same key would fetch existing bill_request's status which is "PROCESSING"
        # Thus, that request would get this error
        if status == "PROCESSING":
            raise Exception("Request already processing")

        # 2. Create the zero total amount bill for updating later
        result = conn.execute(
            text("""
                    INSERT INTO bills (created_at, total_amount)
                    VALUES (:created_at, :total_amount)
                """),
            {
                "created_at": datetime.utcnow().isoformat(),
                "total_amount": 0
            }
        )
        bill_id = result.lastrowid  # get bill_id of the latest inserted row

        # 3. Process each cart item
        for item in cart_items:
            medicine_id = item["medicine_id"]
            qty = item["quantity"]

            # Defencive check for positive quantity
            if qty <= 0:
                raise Exception("Quantity must be positive")

            # Defencive check for medicine_id existence
            medicine = conn.execute(
                text("SELECT id FROM medicines WHERE id = :id AND is_active = 1"),
                {"id": medicine_id}
            ).mappings().first()

            if not medicine:
                raise Exception(f"Medicine {medicine_id} is inactive or does not exist")

            # Deduct stock (FEFO) with CAS
            deductions = deduct_stock_fefo(conn, medicine_id, qty, deduct=True)

            # -----------------------------
            # SINGLE LOOP (optimized)
            # -----------------------------
            batch_rows = []
            subtotal = 0

            for d in deductions:
                d["batch_subtotal"] = d["deducted"] * d["price"]
                subtotal += d["batch_subtotal"]

                batch_rows.append({
                    "batch_id": d["batch_id"],
                    "quantity": d["deducted"],
                    "price": d["price"],
                    "batch_subtotal": d["batch_subtotal"]
                })

            weighted_average_price = subtotal / qty

            # Insert bill_item
            result = conn.execute(
                text("""
                        INSERT INTO bill_items
                        (bill_id, medicine_id, quantity, weighted_average_price, subtotal)
                        VALUES
                        (:bill_id, :medicine_id, :quantity, :weighted_average_price, :subtotal)
                    """),
                {
                    "bill_id": bill_id,
                    "medicine_id": medicine_id,
                    "quantity": qty,
                    "weighted_average_price": weighted_average_price,
                    "subtotal": subtotal
                }
            )

            bill_item_id = result.lastrowid  # latest bill item's auto incremented id as an integer

            # Attach bill_item_id to each row
            for row in batch_rows:
                row["bill_item_id"] = bill_item_id  # same bill_item_id throughout the rows

            # Bulk insert batch breakdown
            conn.execute(
                text("""
                        INSERT INTO bill_item_batches
                        (bill_item_id, batch_id, quantity, price, batch_subtotal)
                        VALUES
                        (:bill_item_id, :batch_id, :quantity, :price, :batch_subtotal)
                    """),
                batch_rows
            )

            total += subtotal

        # 4. Update bill total
        conn.execute(
            text("""
                    UPDATE bills
                    SET total_amount = :total
                    WHERE id = :id
                """),
            {"total": total, "id": bill_id}
        )

        # 5. Mark bill request status as completed
        mark_bill_request_completed(conn, idempotency_key, bill_id)

    return {"bill_id": bill_id, "total": total}


# -------------------------
# Create Bill
# -------------------------
MAX_RETRIES = 3  # centralized retry control


def create_bill(idempotency_key, cart_items):
    # While logging, user can change a stock and gets logged but this change can be rollback leaving incomplete log.
    # Retry the whole process of creating complete bill instead of just retrying per item deducts make logs accurate.
    for attempt in range(MAX_RETRIES):
        try:
            return try_create_bill(idempotency_key, cart_items)

        # ONLY retry CAS / concurrency failures
        except Exception as e:
            if "CAS_CONFLICT" in str(e) and attempt < MAX_RETRIES - 1:
                continue
            raise
    return None


# -------------------------
# Get Bill with Items
# -------------------------
def get_bill(bill_id):
    """
    Retrieve a bill with multiple items, each with batch-level breakdown:

    {
        "bill": {"id": 1, "created_at": "...", "total_amount": 3250},
        "items": [
            {
                "id": 1,
                "bill_id": 1,
                "medicine_id": 2,
                "quantity": 70,
                "weighted_average_price": 26.43,
                "subtotal": 1850,
                "batches": [
                    {"id": 1, "bill_item_id": 1, "batch_id": 2, "batch_number": "B104",
                     "expiry_date": "2026-01-01", "quantity": 50, "price": 25, "batch_subtotal": 1250},
                    {"id": 2, "bill_item_id": 1, "batch_id": 1, "batch_number": "B103",
                     "expiry_date": "2027-01-01", "quantity": 20, "price": 30, "batch_subtotal": 600}
                ]
            },
            {
                "id": 2,
                "bill_id": 1,
                "medicine_id": 3,
                "quantity": 30,
                "weighted_average_price": 46.67,
                "subtotal": 1400,
                "batches": [
                    {"id": 3, "bill_item_id": 2, "batch_id": 3, "batch_number": "B201",
                     "expiry_date": "2026-12-01", "quantity": 30, "price": 46.67, "batch_subtotal": 1400}
                ]
            }
        ]
    }
    """

    # 1. Fetch bill (same as before)
    with ext.engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM bills WHERE id = :id"),
            {"id": bill_id}
        ).mappings().first()

        bill = dict(result) if result else None

    if not bill:
        return {"error": "Bill not found"}

    # 2. Fetch ALL items + batches in ONE query
    with ext.engine.connect() as conn:
        rows = conn.execute(
            text("""
                    SELECT
                        bi.id AS bill_item_id,
                        bi.bill_id,
                        bi.medicine_id,
                        bi.quantity,
                        bi.weighted_average_price,
                        bi.subtotal,

                        bib.id AS batch_row_id,
                        bib.batch_id,
                        bib.quantity AS batch_qty,
                        bib.price,
                        bib.batch_subtotal,

                        mb.batch_number,
                        mb.expiry_date

                    FROM bill_items bi
                    LEFT JOIN bill_item_batches bib
                        ON bi.id = bib.bill_item_id
                    LEFT JOIN medicine_batches mb
                        ON bib.batch_id = mb.id

                    WHERE bi.bill_id = :bill_id
                    ORDER BY bi.id, DATE(mb.expiry_date) ASC
                """),
            {"bill_id": bill_id}
        ).mappings().all()

    # 3. Rebuild nested structure
    items_map = {}

    for row in rows:
        item_id = row["bill_item_id"]

        # Create item if not exists as each bill_item_id can correspond to multiple batch_ids.
        # When a bill_item_id is encountered for the first time,
        # we create its full entry in the map and add the batch from that row.
        # For subsequent rows with the same bill_item_id,
        # we only append the batch information to the existing entry's batches list.
        if item_id not in items_map:
            items_map[item_id] = {
                "id": item_id,
                "bill_id": row["bill_id"],
                "medicine_id": row["medicine_id"],
                "quantity": row["quantity"],
                "weighted_average_price": row["weighted_average_price"],
                "subtotal": row["subtotal"],
                "batches": []
            }

        # Add batch if exists
        if row["batch_id"] is not None:
            items_map[item_id]["batches"].append({
                "id": row["batch_row_id"],
                "bill_item_id": item_id,
                "batch_id": row["batch_id"],
                "batch_number": row["batch_number"],
                "expiry_date": row["expiry_date"],
                "quantity": row["batch_qty"],
                "price": row["price"],
                "batch_subtotal": row["batch_subtotal"]
            })

    # Convert the non JSON serializable dict_values object which is an iterator → Python list
    items = list(items_map.values())

    return {
        "bill": bill,
        "items": items
    }


"""
Atomicity
--------------

Atomic = all-or-nothing execution of a single unit of work

"with .connect() / begin() ensures rollback → atomic" -> gives transaction-level atomicity
If anything fails → everything rolls back

But for concurrent requests this transaction fails.


Concurrent transactions
------------------------------

In deduct_stock_fefo function we do:
    available = batch["stock"]
    deduct = min(available, remaining)
    UPDATE stock = stock - deduct

It is doing:
    read → decide → write

It means, for a transaction A, between “read” and “write”, another concurrent transaction B can occur.
There is no row locking for transaction A which would prevent transaction B to wait for its querying.
Thus two transactions can read the same stock at the same time and both think they can deduct.

medicine_batches initially:

| id | medicine_id | batch_number | expiry_date | stock |
| -- | ----------- | ------------ | ----------- | ----- |
| 1  | 101         | B1           | 2026-01-01  | 10    |


Two concurrent requests:
Request A: { "medicine_id": 101, "quantity": 10 }
Request B: { "medicine_id": 101, "quantity": 10 }

Both A and B execute:
SELECT * FROM medicine_batches WHERE stock > 0

Both see:
stock = 10

Each thinks it can take 10, so both prepare:
deduct = 10

Transaction A:
UPDATE medicine_batches SET stock = stock - 10 WHERE id = 1; -> stock becomes: 0

Transaction B (still thinks stock = 10 even though Transaction A deducted the stock to 0):
UPDATE medicine_batches SET stock = stock - 10 WHERE id = 1; -> stock becomes: -10

It never re-check stock at update time.

During each update it checks if the current stock >= stock needed to be deducted:
    UPDATE medicine_batches
    SET stock = stock - :deduct
    WHERE id = :id AND stock >= :deduct

Now the database guarantees:
Condition check (stock >= :deduct)
AND update (stock = stock - deduct)
happen together, indivisibly

If stock >= :deduct was true during the initial read but fails during the UPDATE, 
then another transaction must have modified the stock in between.

After UPDATE failure we conclude that the initial stock assumption was wrong, so instead of billing we throw error:
if result.rowcount == 0:        # i.e. no updated rows detected
    raise Exception(f"Stock conflict detected for batch {batch['id']}. Try again.")

It detects that the atomic update failed
Signals to your code: “Hey, we lost the race, abort this transaction”
Prevents you from continuing using stale or invalid data

Fixing UPDATE and checking raising error for unsuccessful UPDATE solves incorrect stock assessment
but it does not solve concurrent race condition discussed before.


Row locking
-----------------
Imagine the same scenario as before.

| batch_id | medicine_id | stock |
| -------- | ----------- | ----- |
| 1        | 1           | 10    |
| 2        | 1           | 5     |

Two users:
User A wants 12 units
User B wants 5 units

If we do read → calculate → update without locking:
Both read stock = 10 and 5
Both compute deductions
Both update stock → overselling or negative stock

This is exactly the same problem we had in SQLite, but now with MySQL we have better tools to prevent it.

This with statement is ONE transaction:

with ext.engine.begin() as conn:
    for item in cart_items:
        deduct_stock_fefo(conn, medicine_id, qty)

Lock batches using FOR UPDATE in deduct_stock_fefo function:
    batches = conn.execute(
        text(""
            SELECT *
            FROM medicine_batches
            WHERE medicine_id = :medicine_id
              AND stock > 0
              AND DATE(expiry_date) >= :today
            ORDER BY expiry_date ASC
            FOR UPDATE
        ""),
        {"medicine_id": medicine_id, "today": today}
    ).mappings().all()

Thus, all medicines processed inside that transaction, commit happens only once at the end.

SELECT ... FOR UPDATE is a row-level lock acquisition command 
used in transactional databases like PostgreSQL and MySQL (InnoDB).
When one transaction reads a row → others must wait, no more “two people reading the same stock and fighting later”.

You are telling the database:
“Give me these rows and lock them for writing, so that no other transaction can modify them until I commit or rollback.”

The database scans for rows matching the WHERE condition.
For each row found, it marks it as locked in the internal lock table.
Other transactions that try to SELECT ... FOR UPDATE on the same rows will wait until the first transaction commits.

Example:

Transaction A request payload:

POST /billing/create
Content-Type: application/json

{
    "items": [
        {"medicine_id": 1, "quantity": 10},
        {"medicine_id": 2, "quantity": 5},
        {"medicine_id": 5, "quantity": 2}
    ]
}

Transaction B request payload (concurrent):

POST /billing/create
Content-Type: application/json

{
    "items": [
        {"medicine_id": 1, "quantity": 3},
        {"medicine_id": 3, "quantity": 7}
    ]
}

Behavior of Transaction A
1. Transaction A begins.

2. Processing medicine_id = 1:
   - Executes SELECT ... FOR UPDATE
   - Locks all rows corresponding to medicine_id = 1

3. Processing medicine_id = 2:
   - Executes SELECT ... FOR UPDATE
   - Locks all rows corresponding to medicine_id = 2

4. Processing medicine_id = 5:
   - Executes SELECT ... FOR UPDATE
   - Locks all rows corresponding to medicine_id = 5

5. Transaction A completes processing all items.

6. Commit occurs when the `with` block exits:
   - All updates are finalized
   - All acquired locks (1, 2, 5) are released simultaneously

Behavior of Transaction B (concurrent)
1. Transaction B begins while Transaction A is still active.

2. Processing medicine_id = 1:
   - Executes SELECT ... FOR UPDATE
   - Attempts to acquire lock on rows for medicine_id = 1

3. Since Transaction A already holds the lock on medicine_id = 1:
   - Transaction B is blocked (waits)

4. Transaction B remains blocked until Transaction A commits.

5. After Transaction A commits:
   - Locks on medicine_id = 1, 2, and 5 are released
   - Transaction B acquires lock on medicine_id = 1

6. Transaction B proceeds to process medicine_id = 3 normally.

Key Observations
- Each transaction operates within a single atomic unit of work.
- Locks are acquired incrementally as each SELECT ... FOR UPDATE is executed.
- SELECT ... FOR UPDATE does not perform commits; it only acquires row-level locks.
- All locks are held until the transaction commits.
- Lock contention occurs only when multiple transactions attempt to access the same rows.
- Transaction B waits because it attempts to lock a row (medicine_id = 1) already locked by Transaction A.
- Since Transaction A releases locks only at commit, 
  Transaction B effectively waits for the entire transaction of A to complete.

Conclusion
Transaction B is not blocked due to a global lock or the overall billing process.
It is blocked specifically because it attempts to acquire a lock on a row already
locked by Transaction A. Because Transaction A holds that lock until the end of
its transaction, Transaction B must wait until Transaction A completes and commits.

Instead of:
read → compute → update

We move to:
lock → read → compute → update → commit

Let's say some Transaction X uses plain SELECT (no lock) concurrent to Transaction A:
SELECT * FROM medicine_batches WHERE medicine_id = 1;

Snapshot is taken at the first SELECT in Transaction X.
All subsequent reads in Transaction X see the same snapshot.
Hence, Transaction X sees a consistent snapshot of the last committed data at the time of its first read, 
not Transaction A’s snapshot or uncommitted changes.


Deadlock
----------------

billing_service.py → create_bill()

for item in cart_items:
    deductions = deduct_stock_fefo(conn, medicine_id, qty) -> Inside this we have SELECT ... FOR UPDATE
    This locks rows for that medicine.

medicine_batches:
| id | medicine_id | stock |
| -- | ----------- | ----- |
| 1  | 1           | 10    |
| 2  | 2           | 10    |

Transaction A
[
  { "medicine_id": 1, "quantity": 5 },
  { "medicine_id": 2, "quantity": 5 }
]
Transaction B
[
  { "medicine_id": 2, "quantity": 5 },
  { "medicine_id": 1, "quantity": 5 }
]

Step 1 — A locks medicine 1
SELECT ... WHERE medicine_id = 1 FOR UPDATE
Lock acquired on medicine 1 rows. Now A “owns” medicine_id = 1 rows

Step 2 — B locks medicine 2
SELECT ... WHERE medicine_id = 2 FOR UPDATE
Lock acquired on medicine 2 rows. Now B “owns”  medicine_id = 2 row

Step 3 — A tries medicine 2
SELECT ... WHERE medicine_id = 2 FOR UPDATE
BLOCKED (because B holds that lock) -> A is now waiting for B

Step 4 — B tries medicine 1
SELECT ... WHERE medicine_id = 1 FOR UPDATE
BLOCKED (because A holds that lock) -> B is now waiting for A

| Transaction | Waiting for |
| ----------- | ----------- |
| A           | B           |
| B           | A           |

If both the transactions were in order of medicine_id 1 -> then 2 
then when all the medicine_ids get's processed in 

cart_items = sorted(cart_items, key=lambda x: x["medicine_id"])
for item in cart_items:
    ...


FEFO Concurrency Scenario and Retry Behavior
----------

In the FEFO (First Expiry First Out) logic, batches are first selected
and sorted in ascending order based on their expiry date.

However, between the SELECT (read) phase and the UPDATE (write) phase,
a concurrent user may modify the stock of one or more batches. This
creates a race condition where the initially selected data becomes stale.

Example scenario:

Initial state:
| batch_id | stock |
|----------|-------|
| A        | 10    |
| B        | 10    |

Two concurrent users:
- User 1 requests 15 units
- User 2 requests 5 units

Step 1: Both users read the same batch state
A → 10
B → 10

Step 2: User 1 processes first
- Deduct 10 from batch A → success (A = 0)
- Deduct 5 from batch B → success (B = 5)

Step 3: User 2 processes using stale data
- Attempts to deduct 5 from batch A
- This fails because A now has 0 stock
- The UPDATE condition (stock >= deduct) fails, resulting in rowcount == 0
- An exception is raised: "Stock conflict detected"

This failure occurs even though sufficient stock still exists in batch B,
which is the next valid batch according to FEFO.

Retry behavior:

With retry logic implemented, the entire FEFO deduction process is
re-executed:

- The SELECT query runs again
- Batch A is excluded because stock = 0 (filtered by stock > 0)
- Only batch B is selected
- Deduction is attempted on batch B
- The UPDATE succeeds, and the operation completes correctly

Key takeaway:

Retrying allows the system to discard the stale plan and recompute
the FEFO allocation using the latest database state, ensuring that
valid stock is not incorrectly rejected due to concurrency.

"""