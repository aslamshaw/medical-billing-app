import os
from pathlib import Path
from app.models import execute_write, create_table_if_not_exists
import app.extensions as ext


def find_project_root():
    current = Path(__file__).resolve()  # backend/app/schemas.py -> .../backend/app/schemas.py
    for parent in current.parents:
        print(parent)   # ...\backend\app -> ...\backend
        if (parent / "instance").exists():  # \backend\instance check
            return parent   # D:\PROJECTS\Main_Projects\medical-billing-app\backend
    raise RuntimeError("Project root not found")


# 1. Finding project root

BASE_DIR = find_project_root()  # os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

db_path = os.path.join(BASE_DIR, "instance", "app.sqlite3")
database_url = f"sqlite:///{db_path}"   # "sqlite:///instance/app.sqlite3" if running from Python Console
ext.init_engine(database_url)


# 2. Create tables

# suppliers table
create_table_if_not_exists("suppliers", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "name": "TEXT",
    "phone": "TEXT",
    "address": "TEXT"
})

# purchases table
create_table_if_not_exists("purchases", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "supplier_id": "INTEGER REFERENCES suppliers(id)",
    "created_at": "TEXT",
    "total_amount": "REAL"
})

# purchase_items table
create_table_if_not_exists("purchase_items", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "purchase_id": "INTEGER REFERENCES purchases(id)",
    "medicine_name": "TEXT",
    "batch_number": "TEXT",
    "expiry_date": "TEXT",
    "quantity": "INTEGER",
    "purchase_price": "REAL",
    "selling_price": "REAL",
    "subtotal": "REAL"
})

# medicines table
create_table_if_not_exists("medicines", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "name": "TEXT UNIQUE"
})

# medicine_batches table
create_table_if_not_exists("medicine_batches", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "medicine_id": "INTEGER REFERENCES medicines(id)",
    "batch_number": "TEXT",
    "expiry_date": "TEXT",
    "purchase_price": "REAL",
    "selling_price": "REAL",
    "stock": "INTEGER CHECK(stock >= 0)",
    "UNIQUE(medicine_id, batch_number)": ""
})

# bills table
create_table_if_not_exists("bills", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "created_at": "TEXT",
    "total_amount": "REAL"
})

# bill_items table
create_table_if_not_exists("bill_items", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "bill_id": "INTEGER REFERENCES bills(id)",
    "medicine_id": "INTEGER",
    "quantity": "INTEGER",
    "weighted_average_price": "REAL",
    "subtotal": "REAL"
})

# bill_item_batches table
create_table_if_not_exists("bill_item_batches", {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "bill_item_id": "INTEGER REFERENCES bill_items(id)",
    "batch_id": "INTEGER REFERENCES medicine_batches(id)",
    "quantity": "INTEGER",
    "price": "REAL",
    "batch_subtotal": "REAL"
})

print("✅ Database initialized and tables created successfully!")
