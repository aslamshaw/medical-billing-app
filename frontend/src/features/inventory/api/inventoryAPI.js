const BASE_URL = "http://127.0.0.1:5000";

export const fetchMedicines = async () => {
  const res = await fetch(`${BASE_URL}/inventory/medicines`);

  if (!res.ok) {
    throw new Error("Failed to fetch medicines");
  }

  return res.json();
};