const BASE_URL = "http://127.0.0.1:5000";

export const createPurchase = async (payload) => {
  const res = await fetch(`${BASE_URL}/inventory/purchases`, {
    method: "POST",
    headers: { "Content-Type": "application/json", },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error("Failed to create purchase");
  }

  return res.json();
};