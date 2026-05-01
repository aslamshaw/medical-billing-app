import { useState, useRef, useMemo } from "react";
import { useSuppliers } from "../features/suppliers/hooks/useSuppliers";
import { useCreateSupplier } from "../features/suppliers/hooks/useCreateSupplier";
import { useCreatePurchase } from "../features/purchase/hooks/useCreatePurchase";
import { useMedicineSearch } from "../features/inventory/hooks/useMedicineSearch";
import MedicineAutocomplete from "../features/inventory/components/MedicineAutocomplete";
import { toast } from "sonner";

export default function Purchase() {
  const { data: suppliers = [] } = useSuppliers();  // [{ "name": "ABC Pharma", ... }, { "name": MedLife Distributors", ... }]
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [supplierForm, setSupplierForm] = useState({ name: "", phone: "", address: "", });

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
      onSuccess: (data) => {
        // reset supplier form UI
        setSupplierForm({ name: "", phone: "", address: "" });
        setShowSupplierForm(false);

        // autoselect newly created supplier keeping consistent with <select> value
        if (data?.id) { setForm((prev) => ({ ...prev, supplier_id: String(data.id), })); }

        toast.success(`Supplier "${data?.name ?? ""}" created`);
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to create supplier");
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
  // Medicine name change
  // -----------------------
  const handleSelectMedicine = (item_id, med) => {
    setForm((prev) => ({
      ...prev,
      items: prev.items.map((i) => i.item_id === item_id ? { ...i, medicine_name: med.name } : i),
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
  /*
  
  A derived value is not state. It is recomputed during render and updates only because something else triggered a render.
  User changes quantity setForm(...) -> React triggers re-render -> useMemo recomputes totalAmount -> UI shows updated value
  Even if you don't use useMemo, the updated computed value would still be shown in UI correctly.
  useMemo is only for performance optimization

  */
  const itemsWithSubtotal = useMemo(() => {   // useMemo avoids computing subtotal for each item in each render
    return form.items.map((item) => {
      const qty = Number(item.quantity) || 0;
      const price = Number(item.purchase_price) || 0;

      return { ...item, subtotal: qty * price, };
    });   // [{ item_id: 1, ... , subtotal: 20 }, { item_id: 2, ... , subtotal: 15 }]
  }, [form.items]); // callback is pure, no side effects like state update and depends on form.items state

  const totalAmount = useMemo(() => {   // useMemo avoids computing total amount in each render
    return itemsWithSubtotal.reduce((sum, item) => sum + item.subtotal, 0);
  }, [itemsWithSubtotal]);  // derived dependency is fine here only because it’s reused/memoized; otherwise prefer form.items

  // -----------------------
  // Validation (FULL FORM)
  // -----------------------
  const validate = () => {
    const isInvalidNumber = (value) => { return !value || Number.isNaN(Number(value)) || Number(value) <= 0; };

    // { supplier_id: "Supplier is required", items: { "uuid-1": { med_name: "Required", ...}, "uuid-2": { med_name, } } }
    const newErrors = { items: {}, };

    if (!form.supplier_id) {
      newErrors.supplier_id = "Supplier is required";
    }

    // Track duplicates
    const seen = new Map(); // key => first item_id

    form.items.forEach((item) => {
      const itemErrors = {};    // resets for each item

      const med = item.medicine_name?.trim().toLowerCase();
      const batch = item.batch_number?.trim().toLowerCase();

      // Basic validations
      if (!item.medicine_name) itemErrors.medicine_name = "Required";
      if (!item.batch_number) itemErrors.batch_number = "Required";
      if (!item.expiry_date) itemErrors.expiry_date = "Required";

      if (isInvalidNumber(item.quantity)) itemErrors.quantity = "Invalid";
      if (isInvalidNumber(item.purchase_price)) itemErrors.purchase_price = "Invalid";
      if (isInvalidNumber(item.selling_price)) itemErrors.selling_price = "Invalid";

      // Duplicate detection (only if both exist)
      if (med && batch) {
        const key = `${med}__${batch}`;

        if (seen.has(key)) {
          const firstItemId = seen.get(key);

          // mark current item
          itemErrors.batch_number = "Duplicate batch for this medicine";

          // mark first item also (important)
          newErrors.items[firstItemId] = {
            ...(newErrors.items[firstItemId] || {}),
            batch_number: "Duplicate batch for this medicine",
          };
        } 
        else { seen.set(key, item.item_id); }
      }

      // Includes this item_id key inside newErrors.items only if that item has at least one validation error
      // Avoiding empty object for itemErrors in case of no validation error
      if (Object.keys(itemErrors).length > 0) {
        newErrors.items[item.item_id] = itemErrors;
      }
    });

    setErrors(newErrors);

    return (!newErrors.supplier_id && Object.keys(newErrors.items).length === 0); // No supplier or item error
  };

  // -----------------------
  // Field-level validation (onBlur)
  // -----------------------
  const handleItemBlur = (item_id, e) => {
    const { name, value } = e.target;

    let message = "";

    if (!value) {
      message = "Required";
    }
    else if (["quantity", "purchase_price", "selling_price"].includes(name) && Number(value) <= 0) {
      message = "Invalid";
    }

    setErrors((prev) => ({
      ...prev,
      items: { ...prev.items, [item_id]: { ...prev.items?.[item_id], [name]: message, }, },
    }));  // initially prev.items is undefined, ..undefined is fine, on first blur ...undefined[item_id] gives TypeError
  };

  // -----------------------
  // Submit
  // -----------------------
  const lockRef = useRef(false);

  const handleSubmit = async (e) => {
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
      })),
    };

    const id = toast.loading("Processing purchase...");   // toast ID is returned to modify same toast instead of creating

    mutate(payload, {
      onMutate: async () => {   // runs first before mutate, here callback is async due to artificial delay
        // await new Promise((res) => setTimeout(res, 5000)); // simulate validate step

        toast.loading("Saving...", { id });
      },

      onSuccess: async (data) => {
        // await new Promise((res) => setTimeout(res, 500)); // simulate final step

        toast.success(`Purchase #${data?.id ?? ""} created`, { id, description: `Total ₹${totalAmount}`, });

        setForm({
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

        setErrors({});
      },

      onError: (err) => { toast.error(err?.message || "Failed to create purchase", { id, }); },

      onSettled: () => { lockRef.current = false; },
    });
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Create Purchase</h2>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* Create supplier */}
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
        
        Initially option value was "" thus "Select Supplier" was selected as the form.supplier_id was also ""
        When an option from drop down is selected, onChange triggers 
        Thus, the option value i.e. supplier_id is used to update form.supplier_id
        Now the initial value form.supplier_id is now updated to e.target.value of that option.
        
        */}
        <div>
          <select value={form.supplier_id} onChange={handleSupplierSelect} className="border p-2 w-full">
            <option value="">Select Supplier</option>
            {suppliers.map((s) => (<option key={s.id} value={s.id}>{s.name}</option>))}
          </select>

          {errors.supplier_id && (<p className="text-red-500 text-sm">{errors.supplier_id}</p>)}
        </div>

        {/* Items */}
        {itemsWithSubtotal.map(item => (
          <div key={item.item_id} className="border p-4 rounded-lg space-y-3">

            <div className="grid grid-cols-6 gap-2">
              <div className="col-span-2">
                <MedicineAutocomplete
                  value={item.medicine_name}
                  // { target: { name, value } } mimics onChange callback parameter event (e) => {} for the handler usage
                  onChange={(val) => handleItemChange(item.item_id, { target: { name: "medicine_name", value: val }, })}
                  onSelect={(med) => handleSelectMedicine(item.item_id, med)}
                />

                {errors.items?.[item.item_id]?.medicine_name && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].medicine_name}
                  </p>
                )}
              </div>

              <div>
                <input
                  name="batch_number"
                  placeholder="Batch"
                  value={item.batch_number}
                  onChange={(e) => handleItemChange(item.item_id, e)}
                  onBlur={(e) => handleItemBlur(item.item_id, e)}
                  className="border p-2"
                />

                {errors.items?.[item.item_id]?.batch_number && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].batch_number}
                  </p>
                )}
              </div>

              <div>
                <input
                  type="date"
                  name="expiry_date"
                  value={item.expiry_date}
                  onChange={(e) => handleItemChange(item.item_id, e)}
                  onBlur={(e) => handleItemBlur(item.item_id, e)}
                  className="border p-2"
                />

                {errors.items?.[item.item_id]?.expiry_date && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].expiry_date}
                  </p>
                )}
              </div>

              <div>
                <input
                  type="number"
                  name="quantity"
                  placeholder="Qty"
                  value={item.quantity}
                  onChange={(e) => handleItemChange(item.item_id, e)}
                  onBlur={(e) => handleItemBlur(item.item_id, e)}
                  className="border p-2"
                />

                {errors.items?.[item.item_id]?.quantity && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].quantity}
                  </p>
                )}
              </div>

              <div>
                <input
                  type="number"
                  name="purchase_price"
                  placeholder="Buy"
                  value={item.purchase_price}
                  onChange={(e) => handleItemChange(item.item_id, e)}
                  onBlur={(e) => handleItemBlur(item.item_id, e)}
                  className="border p-2"
                />

                {errors.items?.[item.item_id]?.purchase_price && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].purchase_price}
                  </p>
                )}
              </div>

              <div>
                <input
                  type="number"
                  name="selling_price"
                  placeholder="Sell"
                  value={item.selling_price}
                  onChange={(e) => handleItemChange(item.item_id, e)}
                  onBlur={(e) => handleItemBlur(item.item_id, e)}
                  className="border p-2"
                />

                {errors.items?.[item.item_id]?.selling_price && (
                  <p className="text-red-500 text-xs">
                    {errors.items[item.item_id].selling_price}
                  </p>
                )}
              </div>

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
        <button
          type="submit"
          disabled={isPending}
          className={`px-4 py-2 text-white ${isPending ? "bg-blue-300 cursor-not-allowed" : "bg-blue-500"}`}
        >
          {isPending ? "Saving..." : "Create Purchase"}
        </button>
      </form>
    </div>
  );
}