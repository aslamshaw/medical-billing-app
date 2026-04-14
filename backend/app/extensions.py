from sqlalchemy import create_engine, event


engine = None


def init_engine(url):
    global engine
    engine = create_engine(url, echo=True)

    # attach event listener here, after engine is ready, as a callback based invocation
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
