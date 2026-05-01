import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.sqlite3')}"
    )
    SQLALCHEMY_ECHO = False
    JSON_SORT_KEYS = False
