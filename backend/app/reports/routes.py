from flask import jsonify
from . import reports_bp


@reports_bp.route("/health")
def health():
    return jsonify({"status": "reports ok"})
