from flask import jsonify, request
from . import billing_bp
from app.services.billing_service import create_bill, get_bill, preview_fefo


@billing_bp.route("/health")
def health():
    return jsonify({"status": "billing ok"})


@billing_bp.route("/preview", methods=["POST"])
def preview():
    data = request.get_json()

    try:
        result = preview_fefo(data["items"])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@billing_bp.route("/create", methods=["POST"])
def create():

    data = request.get_json()

    try:
        result = create_bill(data["items"])
        return jsonify(result), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@billing_bp.route("/<int:bill_id>", methods=["GET"])
def get(bill_id):

    bill = get_bill(bill_id)

    return jsonify(bill)
