import { useState, useRef, useMemo } from "react";
import { useCreatePurchase } from "../features/purchase/hooks/useCreatePurchase";
import { useSuppliers } from "../features/suppliers/hooks/useSuppliers";
import { useCreateSupplier } from "../features/suppliers/hooks/useCreateSupplier";
import { useMedicineSearch } from "../features/inventory/hooks/useMedicineSearch";

export default function Purchase() {
  const { data: suppliers = [] } = useSuppliers();  // [{ "name": "ABC Pharma", ... }, { "name": MedLife Distributors", ... }]
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [supplierForm, setSupplierForm] = useState({ name: "", phone: "", address: "", });

  const [medicineQuery, setMedicineQuery] = useState("");
  const { data: suggestions = [] } = useMedicineSearch(medicineQuery);

  const { mutate: createSupplier, isPending: isCreatingSupplier } = useCreateSupplier();
  const { mutate, isPending } = useCreatePurchase();

  const [errors, setErrors] = useState({});

  const [form, setForm] = useState({
    supplier_id: "",
    items: [
      {
        item_id: crypto.randomUUID(),
        medicine_name: "",
        batch_number: "",
        expiry_date: "",
        quantity: "",
        purchase_price: "",
        selling_price: "",
      },
    ],
  });

  // -----------------------
  // Supplier form change
  // -----------------------
  const handleSupplierFormChange = (e) => {
    const { name, value } = e.target;   // target input tag
    setSupplierForm(prev => ({ ...prev, [name]: value }))
  }

  // -----------------------
  // Create supplier
  // -----------------------
  const handleCreateSupplier = () => {
    // e.preventDefault(); is not needed as the submit button is not inside a form

    if (!supplierForm.name) return;

    createSupplier(supplierForm, {
      onSuccess: () => {
        setSupplierForm({ name: "", phone: "", address: "" });
        setShowSupplierForm(false);
      },
    });
  };

  // -----------------------
  // Supplier Select
  // -----------------------
  const handleSupplierSelect = (e) => {
    setForm((prev) => ({ ...prev, supplier_id: e.target.value }));
  };

  // -----------------------
  // Item change
  // -----------------------
  const handleItemChange = (item_id, e) => {
    const { name, value } = e.target;   // target input tag

    setForm((prev) => ({
      ...prev,
      items: prev.items.map((item) => item.item_id === item_id ? { ...item, [name]: value } : item),
    }));
  };

  // -----------------------
  // Add item
  // -----------------------
  const addItem = () => {
    setForm((prev) => ({
      ...prev,    // which includes both previous supplier_ids and items
      items: [
        ...prev.items,
        {
          item_id: crypto.randomUUID(),
          medicine_name: "",
          batch_number: "",
          expiry_date: "",
          quantity: "",
          purchase_price: "",
          selling_price: "",
        },
      ],
    }));
  };

  // -----------------------
  // Remove item
  // -----------------------
  const removeItem = (item_id) => {
    setForm((prev) => {
      if (prev.items.length === 1) return prev;
      return { ...prev, items: prev.items.filter((item) => item.item_id !== item_id), };
    });
  };

  // ----------------------------
  // Computed values of total
  // ----------------------------
  const itemsWithSubtotal = useMemo(() => {   // useMemo avoids computing subtotal for each item in each render
    return form.items.map((item) => {
      const qty = Number(item.quantity) || 0;
      const price = Number(item.purchase_price) || 0;

      return { ...item, subtotal: qty * price, };
    });
  }, [form.items]); // callback is pure, no side effects like state update and depends on form.items state

  const totalAmount = useMemo(() => {   // useMemo avoids computing total amount in each render
    return itemsWithSubtotal.reduce((sum, item) => sum + item.subtotal, 0);
  }, [itemsWithSubtotal]);  // derived dependency is fine here only because it’s reused/memoized; otherwise prefer form.items

  // -----------------------
  // Validation
  // -----------------------
  const validate = () => {
    const newErrors = {};

    if (!form.supplier_id) {
      newErrors.supplier_id = "Supplier is required";
    }

    form.items.forEach((item, index) => {
      const prefix = `item_${index}`;

      if (!item.medicine_name) {
        newErrors[`${prefix}_medicine_name`] = "Required";
      }

      if (!item.batch_number) {
        newErrors[`${prefix}_batch_number`] = "Required";
      }

      if (!item.expiry_date) {
        newErrors[`${prefix}_expiry_date`] = "Required";
      }

      if (!item.quantity || Number(item.quantity) <= 0) {
        newErrors[`${prefix}_quantity`] = "Invalid";
      }

      if (!item.purchase_price || Number(item.purchase_price) <= 0) {
        newErrors[`${prefix}_purchase_price`] = "Invalid";
      }

      if (!item.selling_price || Number(item.selling_price) <= 0) {
        newErrors[`${prefix}_selling_price`] = "Invalid";
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;   // newErrors object should be empty after validation checks
  };

  // -----------------------
  // Submit
  // -----------------------
  const lockRef = useRef(false);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (lockRef.current) return;

    if (!validate()) return;

    lockRef.current = true;

    const payload = {
      supplier_id: Number(form.supplier_id),
      items: form.items.map((item) => ({
        medicine_name: item.medicine_name,
        batch_number: item.batch_number,
        expiry_date: item.expiry_date,
        quantity: Number(item.quantity),
        purchase_price: Number(item.purchase_price),
        selling_price: Number(item.selling_price),
      })),    // Map transformation allows validation of data
    };

    mutate(payload, { onSettled: (..._args) => lockRef.current = false });
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Create Purchase</h2>

      {/* Create supplier */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="mb-4">

          <div className="flex justify-between items-center mb-2">
            <label className="text-sm font-medium">Supplier</label>

            <button type="button" onClick={() => setShowSupplierForm((p) => !p)} className="text-blue-500 text-sm">
              + New Supplier
            </button>
          </div>

          {showSupplierForm && (
            <div className="border p-3 mb-3 space-y-2 rounded">   {/* div instead of form to avoid nested form onSubmit */}
              <input
                name="name"
                placeholder="Name"
                value={supplierForm.name}
                onChange={handleSupplierFormChange}
                className="border p-2 w-full"
              />

              <input
                name="phone"
                placeholder="Phone"
                value={supplierForm.phone}
                onChange={handleSupplierFormChange}
                className="border p-2 w-full"
              />

              <input
                name="address"
                placeholder="Address"
                value={supplierForm.address}
                onChange={handleSupplierFormChange}
                className="border p-2 w-full"
              />

              <button
                type="button"
                disabled={isCreatingSupplier}
                onClick={handleCreateSupplier}
                className="bg-green-500 text-white px-3 py-1"
              >
                {isCreatingSupplier ? "Creating..." : "Create Supplier"}
              </button>
            </div>
          )}

        </div>

        {/* Supplier Dropdown */}
        {/* 
        
        Initially value is "" thus "Select Supplier" option is selected.
        When an option from drop down is selected, onChange triggers 
        Thus, the option value i.e. supplier_id is used to update form.supplier_id
        Now the initial value form.supplier_id is now updated to e.target.value of that option.
        
        */
        }
        <div>
          <select value={form.supplier_id} onChange={handleSupplierSelect} className="border p-2 w-full">
            <option value="">Select Supplier</option>
            {suppliers.map((s) => (<option key={s.id} value={s.id}> {s.name}</option>))}
          </select>

          {errors.supplier_id && (<p className="text-red-500 text-sm">{errors.supplier_id}</p>)}
        </div>

        {/* Items */}
        {itemsWithSubtotal.map(item => (
          <div key={item.item_id} className="border p-4 rounded-lg space-y-3">

            <div className="grid grid-cols-6 gap-2">

              <div className="relative col-span-2">
                <input
                  name="medicine_name"
                  placeholder="Medicine"
                  value={item.medicine_name}
                  onChange={(e) => {
                    handleItemChange(item.item_id, e);
                    setMedicineQuery(e.target.value);
                  }}
                  className="border p-2 w-full"
                />

                {suggestions.length > 0 && item.medicine_name === medicineQuery && (
                  <div className="absolute bg-white border w-full mt-1 max-h-40 overflow-y-auto z-10">
                    {suggestions.map((med) => (
                      <div
                        key={med.id}
                        onClick={() => {
                          setForm((prev) => ({
                            ...prev,
                            items: prev.items.map((i) => i.item_id === item.item_id ? { ...i, medicine_name: med.name } : i),
                          }));

                          setMedicineQuery("");
                        }}
                        className="p-2 hover:bg-gray-100 cursor-pointer text-sm"
                      >
                        {med.name}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <input
                name="batch_number"
                placeholder="Batch"
                value={item.batch_number}
                onChange={(e) => handleItemChange(item.item_id, e)}
                className="border p-2"
              />

              <input
                type="date"
                name="expiry_date"
                value={item.expiry_date}
                onChange={(e) => handleItemChange(item.item_id, e)}
                className="border p-2"
              />

              <input
                type="number"
                name="quantity"
                placeholder="Qty"
                value={item.quantity}
                onChange={(e) => handleItemChange(item.item_id, e)}
                className="border p-2"
              />

              <input
                type="number"
                name="purchase_price"
                placeholder="Buy"
                value={item.purchase_price}
                onChange={(e) => handleItemChange(item.item_id, e)}
                className="border p-2"
              />

              <input
                type="number"
                name="selling_price"
                placeholder="Sell"
                value={item.selling_price}
                onChange={(e) => handleItemChange(item.item_id, e)}
                className="border p-2"
              />

            </div>

            {/* Subtotal */}
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Subtotal: ₹ {item.subtotal}</span>

              <button type="button" onClick={() => removeItem(item.item_id)} className="text-red-500 text-sm">
                Remove
              </button>
            </div>
          </div>
        ))}

        {/* Add item */}
        <button type="button" onClick={addItem} className="bg-gray-200 px-3 py-1">
          + Add Item
        </button>

        {/* Total */}
        <div className="text-right font-semibold">
          Total: ₹ {totalAmount}
        </div>

        {/* Submit */}
        <button type="submit" disabled={isPending} className="bg-blue-500 text-white px-4 py-2">
          {isPending ? "Saving..." : "Create Purchase"}
        </button>
      </form>
    </div>
  );
}