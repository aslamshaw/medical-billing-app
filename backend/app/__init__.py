from flask import Flask
from config import Config
from .extensions import init_engine
from flask_cors import CORS


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)

    app.config.from_object(Config)

    # Initialize database engine
    init_engine(app.config["DATABASE_URL"])

    # Register blueprints
    from .inventory import inventory_bp
    from .billing import billing_bp
    from .reports import reports_bp

    app.register_blueprint(inventory_bp, url_prefix="/inventory")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    return app
