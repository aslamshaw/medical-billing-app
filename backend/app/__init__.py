from flask import Flask
from config import Config
from .extensions import init_engine
from .schemas import init_db
from flask_cors import CORS


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)

    # Load config values from Config class into app.config
    """
    app.config is a dict-like configuration object provided by Flask. 
    It is an instance of flask.config.Config.
    The method from_object(Config) copies all UPPERCASE attributes 
    from the given Config class into app.config as key-value pairs.

    class Config:
        SECRET_KEY = "dev-secret-key"           ->          app.config["SECRET_KEY"] = "dev-secret-key"
        DATABASE_URL = "sqlite:///..."          ->          app.config["DATABASE_URL"] = "sqlite:///..."
    """
    app.config.from_object(Config)

    # Initialize database engine
    init_engine(app.config["DATABASE_URL"], echo=app.config["SQLALCHEMY_ECHO"])

    # Initialize database tables after engine is created
    init_db()

    # Register blueprints
    from .inventory import inventory_bp
    from .billing import billing_bp
    from .reports import reports_bp

    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    return app
