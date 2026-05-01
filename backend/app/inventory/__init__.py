from flask import Blueprint

inventory_bp = Blueprint("inventory", __name__)

"""
Forcing Python to execute routes.py, so that the decorators run and register endpoints on the blueprint
"""
from . import routes
