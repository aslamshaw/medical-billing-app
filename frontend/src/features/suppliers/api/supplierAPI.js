const BASE_URL = "http://127.0.0.1:5000";

export const fetchSuppliers = async () => {
  const res = await fetch(`${BASE_URL}/inventory/suppliers`);

  if (!res.ok) {
    throw new Error("Failed to fetch suppliers");
  }

  return res.json();
};

export const createSupplier = async (payload) => {
  const res = await fetch(`${BASE_URL}/inventory/suppliers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error("Failed to create supplier");
  }

  return res.json();
};

/*

res.json() is not awaited as the function already returns a Promise, 
so returning another Promise (res.json()) is perfectly fine, TanStack Query will await it anyway.

*/