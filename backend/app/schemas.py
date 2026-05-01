from sqlalchemy import text
import app.extensions as ext


def init_db():
    with ext.engine.begin() as conn:

        # suppliers
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            address TEXT
        )
        """))

        # purchases
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER REFERENCES suppliers(id),
            created_at TEXT,
            total_amount REAL
        )
        """))

        # purchase_items
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER REFERENCES purchases(id),
            medicine_name TEXT,
            batch_number TEXT,
            expiry_date TEXT,
            quantity INTEGER,
            purchase_price REAL,
            selling_price REAL,
            subtotal REAL
        )
        """))

        # medicines
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
        """))

        # medicine_batches
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS medicine_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER REFERENCES medicines(id),
            batch_number TEXT,
            expiry_date TEXT,
            purchase_price REAL,
            selling_price REAL,
            stock INTEGER CHECK(stock >= 0),
            UNIQUE(medicine_id, batch_number)
        )
        """))

        # bills
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            total_amount REAL
        )
        """))

        # bill_items
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER REFERENCES bills(id),
            medicine_id INTEGER,
            quantity INTEGER,
            weighted_average_price REAL,
            subtotal REAL
        )
        """))

        # bill_item_batches
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS bill_item_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_item_id INTEGER REFERENCES bill_items(id),
            batch_id INTEGER REFERENCES medicine_batches(id),
            quantity INTEGER,
            price REAL,
            batch_subtotal REAL
        )
        """))

        # stock_adjustments
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS stock_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            batch_id INTEGER NOT NULL,
            old_stock INTEGER NOT NULL,
            new_stock INTEGER NOT NULL,

            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,

            FOREIGN KEY (batch_id) REFERENCES medicine_batches(id)
        )
        """))

    print("✅ Database initialized and tables created successfully!")