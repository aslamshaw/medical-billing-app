from sqlalchemy import text
import app.extensions as ext


def fetch_all(query, params=None):
    # Each statement runs in autocommit mode with engine.connect()
    # Readonly operations like SELECTing data, we don’t want to start a full transaction which is heavier
    with ext.engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.mappings().all()
        # Convert [RowMapping(...), RowMapping(...)] -> [dict, dict, dict], so that JSON can parse it
        return [dict(row) for row in rows]


def fetch_one(query, params=None):
    # Each statement runs in autocommit mode with engine.connect()
    # Readonly operations like SELECTing data, we don’t want to start a full transaction which is heavier
    with ext.engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        row = result.mappings().first()
        # Convert RowMapping({...}) -> dict({...}), so that JSON can parse it
        return dict(row) if row else None


def execute_write(query, params=None):
    # Begins a transaction automatically; commits at the end if no exception, otherwise rolls back
    # Required for INSERT, UPDATE, DELETE, or any operation that modifies state
    # Automatic roll-back prevents half-written billing records
    with ext.engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        return result.rowcount


def create_table_if_not_exists(table_name, columns: dict):

    cols = []

    for name, col_type in columns.items():
        cols.append(f"{name} {col_type}")

    column_sql = ", ".join(cols)

    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {column_sql}
    )
    """

    execute_write(query)
    """
    Call:
    create_table_if_not_exists( "medicines",
    {"id": "INTEGER PRIMARY KEY AUTOINCREMENT", "name": "TEXT", "price": "REAL", "stock": "INTEGER"})
    
    Query:
    f"CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        stock INTEGER
    )"
    
    Execution:
    conn.execute("
    CREATE TABLE IF NOT EXISTS medicines 
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        stock INTEGER)
    ")
    """


def insert_record(table, data: dict):
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f":{k}" for k in data.keys()])

    query = f"""
    INSERT INTO {table} ({columns})
    VALUES ({placeholders})
    """

    execute_write(query, data)
    """
    Call:
    insert_record("medicines",{"name": "Paracetamol", "price": 20, "stock": 100})
    
    Query:
    f"INSERT INTO medicines (name, price, stock) VALUES (:name, :price, :stock)"
    
    Execution:
    conn.execute("INSERT INTO medicines (name, price, stock) VALUES (:name, :price, :stock)", {
    "name": "Paracetamol",
    "price": 20,
    "stock": 100
    })
    """


"""
WHY WE SHOULD NOT USE:

    from app.extensions import engine

AND SHOULD PREFER:

    import app.extensions as ext
    ext.engine

------------------------------------------------------------
CORE PYTHON BEHAVIOR
------------------------------------------------------------

There are two different import styles in Python:

1) Importing the MODULE

    import app.extensions as ext

This gives us a reference to the entire module object.
When we access:

    ext.engine

Python reads the current value stored inside the module.

If the module later updates the variable, we will see the
updated value.


2) Importing the VARIABLE

    from app.extensions import engine

This copies the value of the variable at the moment
the import happens.

Conceptually Python does something like:

    engine = app.extensions.engine

This means our file now holds a separate reference
to that value. If the module later changes the value,
our imported variable does NOT update.


------------------------------------------------------------
WHY THIS MATTERS IN OUR PROJECT
------------------------------------------------------------

In this project the SQLAlchemy engine is initialized
later during application startup.

Inside app/extensions.py:

    engine = None

Then during application creation:

    create_app()
        -> init_engine()
            -> engine = create_engine(...)

So the engine variable changes during runtime.


------------------------------------------------------------
POTENTIAL PROBLEM FLOW
------------------------------------------------------------

A typical Flask import chain can look like this:

    run.py
        ↓
    from app import create_app
        ↓
    Python loads app/__init__.py
        ↓
    app/__init__.py imports blueprints
        ↓
    blueprints import services
        ↓
    services import engine

Example:

    # medicine_service.py
    from app.extensions import engine

At this moment:

    engine == None

because create_app() has not executed yet.

Later the application starts:

    app = create_app()

which sets:

    app.extensions.engine = Engine(...)

BUT the service module already imported the old value:

    engine = None

So when the service tries to run:

    with engine.connect() as conn:

we get a runtime error:

    AttributeError: 'NoneType' object has no attribute 'connect'


------------------------------------------------------------
WHY IMPORTING THE MODULE FIXES THIS
------------------------------------------------------------

If we instead do:

    import app.extensions as ext

then use:

    ext.engine.connect()

Python always looks up the current value stored inside
the module.

FLOW:

start:
    ext.engine = None

after create_app():
    ext.engine = Engine(...)

Because we access the module each time, we always get
the updated engine object.


------------------------------------------------------------
MENTAL MODEL
------------------------------------------------------------

Think of it like this:

    import module
        → you keep the BOX

    from module import variable
        → you take a SNAPSHOT of what's inside the box

If the box contents change later, the snapshot does not.


------------------------------------------------------------
PROJECT RULE
------------------------------------------------------------

Always import the module:

    import app.extensions as ext

Use:

    ext.engine.connect()

Avoid importing the variable:

    from app.extensions import engine

This prevents stale references and hard-to-debug
initialization order issues.
"""