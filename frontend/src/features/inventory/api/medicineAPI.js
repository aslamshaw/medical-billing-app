const BASE_URL = "http://127.0.0.1:5000";

export const searchMedicines = async (query) => {
  if (!query || query.trim().length < 1) return [];

  const res = await fetch(
    `${BASE_URL}/inventory/medicines/search?q=${encodeURIComponent(query)}`
  );

  if (!res.ok) {
    throw new Error("Failed to search medicines");
  }

  return res.json();
};