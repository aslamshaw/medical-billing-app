from sqlalchemy import text
import app.extensions as ext


def init_db():
    with ext.engine.begin() as conn:

        # -------------------------
        # suppliers
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT
        )
        """))

        # -------------------------
        # medicines (soft delete)
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """))

        # -------------------------
        # medicine_batches
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medicine_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL
                REFERENCES medicines(id) ON DELETE RESTRICT,
            batch_number TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock INTEGER NOT NULL CHECK(stock >= 0),
            UNIQUE(medicine_id, batch_number)
        )
        """))

        # -------------------------
        # purchases
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER
                REFERENCES suppliers(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            total_amount REAL NOT NULL
        )
        """))

        # -------------------------
        # purchase_items
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL
                REFERENCES purchases(id) ON DELETE CASCADE,
            medicine_id INTEGER NOT NULL
                REFERENCES medicines(id) ON DELETE RESTRICT,
            medicine_name TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            subtotal REAL NOT NULL
        )
        """))

        # -------------------------
        # bills
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            total_amount REAL NOT NULL
        )
        """))

        # -------------------------
        # bill_items
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL
                REFERENCES bills(id) ON DELETE CASCADE,
            medicine_id INTEGER NOT NULL
                REFERENCES medicines(id) ON DELETE RESTRICT,
            quantity INTEGER NOT NULL,
            weighted_average_price REAL NOT NULL,
            subtotal REAL NOT NULL
        )
        """))

        # -------------------------
        # bill_item_batches
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_item_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_item_id INTEGER NOT NULL
                REFERENCES bill_items(id) ON DELETE CASCADE,
            batch_id INTEGER NOT NULL
                REFERENCES medicine_batches(id) ON DELETE RESTRICT,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            batch_subtotal REAL NOT NULL
        )
        """))

        # -------------------------
        # bill_requests (idempotency)
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK(status IN ('PROCESSING', 'COMPLETED')),
            bill_id INTEGER
                REFERENCES bills(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """))

        # -------------------------
        # stock_adjustments (audit-safe)
        # -------------------------
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL
                REFERENCES medicine_batches(id) ON DELETE RESTRICT,
            old_stock INTEGER NOT NULL,
            new_stock INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """))

    print("✅ Database initialized and tables created successfully!")