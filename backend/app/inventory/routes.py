from flask import jsonify, request
from . import inventory_bp      # inventory bluprint decorator still needs to be imported
from app.services.supplier_service import (
    create_supplier,
    list_suppliers
)
from app.services.purchase_service import create_purchase
from app.services.medicine_service import (
    list_medicines,
    search_medicines,
    update_medicine,
    delete_medicine
)
from app.services.inventory_adjustment_service import adjust_batch_stock


@inventory_bp.route("/health")
def health():
    return jsonify({"status": "inventory ok"})


@inventory_bp.route("/suppliers", methods=["POST"])
def add_supplier():

    data = request.get_json()

    try:
        result = create_supplier(data)
        return jsonify(result), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@inventory_bp.route("/suppliers", methods=["GET"])
def get_suppliers():

    suppliers = list_suppliers()

    return jsonify(suppliers)


@inventory_bp.route("/purchases", methods=["POST"])
def add_purchase():

    data = request.get_json()

    try:
        result = create_purchase(data)
        return jsonify(result), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@inventory_bp.route("/medicines", methods=["GET"])
def get_medicines():

    medicines = list_medicines()

    return jsonify(medicines)


@inventory_bp.route("/medicines/search", methods=["GET"])
def search():

    keyword = request.args.get("q", "")

    medicines = search_medicines(keyword)

    return jsonify(medicines)


@inventory_bp.route("/medicines/<int:medicine_id>", methods=["PUT"])
def update(medicine_id):

    data = request.get_json()

    try:
        result = update_medicine(medicine_id, data)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@inventory_bp.route("/medicines/<int:medicine_id>", methods=["DELETE"])
def remove(medicine_id):

    result = delete_medicine(medicine_id)

    return jsonify(result)


@inventory_bp.route("/batches/<int:batch_id>/adjust", methods=["POST"])
def adjust_stock(batch_id):

    data = request.get_json()

    try:
        result = adjust_batch_stock(batch_id, data["new_stock"], data["reason"])

        return jsonify(result), 200

    except KeyError:
        return jsonify({"error": "new_stock and reason are required"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400
