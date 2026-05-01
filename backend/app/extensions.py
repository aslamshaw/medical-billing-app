from sqlalchemy import create_engine, event

# engine is ONLY global to extensions.py
# By doing "import app.extensions as ext" and "ext.engine" you are referencing that global engine from another file
engine = None


def init_engine(url, echo=False):
    global engine

    engine = create_engine(
        url,
        echo=echo,
        future=True,  # modern SQLAlchemy behavior
        connect_args={"check_same_thread": False}  # needed for SQLite + Flask
    )

    # Enable SQLite pragmas
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()

        # enforce foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")

        # better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")

        # prevent immediate lock failure
        cursor.execute("PRAGMA busy_timeout=5000")

        cursor.close()
