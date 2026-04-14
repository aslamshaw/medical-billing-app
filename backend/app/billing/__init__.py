from flask import Blueprint

billing_bp = Blueprint("billing", __name__)

from . import routes


"""
If you did:

from . import routes

billing_bp = Blueprint(...)

it would fail because routes.py imports billing_bp.
"""