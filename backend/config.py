import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = "dev-secret-key"

    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.sqlite3')}"

    SQLALCHEMY_ECHO = True  # dev only, turn off later

    JSON_SORT_KEYS = False
