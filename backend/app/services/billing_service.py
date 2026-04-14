from datetime import datetime, date
from sqlalchemy import text
import app.extensions as ext
from app.models import fetch_one, fetch_all


# -------------------------
# Helper: Deduct stock FEFO
# -------------------------
def deduct_stock_fefo(conn, medicine_id, qty):
    """
    Deducts 'qty' units of a medicine using FEFO (First Expiry First Out) logic.
    Skips expired batches. Works even if expiry_date includes time.

    Input
    -----
    conn : SQLAlchemy connection
    medicine_id : int
    qty : int

    Output
    ------
    [
        {"batch_id": 3, "deducted": 10, "price": 25},
        {"batch_id": 5, "deducted": 5, "price": 26}
    ]
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
        deduct = min(available, remaining)

        # Check available stock again before updating
        result = conn.execute(
            text("""
                    UPDATE medicine_batches
                    SET stock = stock - :deduct
                    WHERE id = :id AND stock >= :deduct
                 """),
            {"deduct": deduct, "id": batch["id"]}
        )

        # Successful update check
        if result.rowcount == 0:
            raise Exception(f"Stock conflict detected for batch {batch['id']}. Try again.")

        # Record deduction with price
        deductions.append({
            "batch_id": batch["id"],
            "deducted": deduct,
            "price": batch["selling_price"]
        })

        remaining -= deduct

    if remaining > 0:
        raise Exception(f"Insufficient non-expired stock for medicine_id {medicine_id}")

    return deductions


# -------------------------
# Create Bill
# -------------------------
def create_bill(cart_items):
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
    """
    total = 0

    with ext.engine.begin() as conn:
        # 1. Create the bill
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
        bill_id = result.lastrowid

        # 2. Process each cart item
        for item in cart_items:
            medicine_id = item["medicine_id"]
            qty = item["quantity"]

            # Defencive check for positive quantity
            if qty <= 0:
                raise Exception("Quantity must be positive")

            # Defencive check for medicine_id existence
            medicine = conn.execute(
                text("SELECT id FROM medicines WHERE id=:id"),
                {"id": medicine_id}
            ).first()

            if not medicine:
                raise Exception(f"Invalid medicine_id {medicine_id}")

            # Deduct stock (FEFO)
            deductions = deduct_stock_fefo(conn, medicine_id, qty)

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

            weighted_average_price = round(subtotal / qty, 2)

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

            bill_item_id = result.lastrowid     # latest bill item's auto incremented id as an integer

            # Attach bill_item_id to each row
            for row in batch_rows:
                row["bill_item_id"] = bill_item_id      # same bill_item_id throughout the rows

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

        # 3. Update bill total
        conn.execute(
            text("""
                    UPDATE bills
                    SET total_amount = :total
                    WHERE id = :id
                """),
            {"total": total, "id": bill_id}
        )

    return {"bill_id": bill_id, "total": total}


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
    bill = fetch_one(
        "SELECT * FROM bills WHERE id = :id",
        {"id": bill_id}
    )

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
    


"""