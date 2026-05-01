const BASE_URL = "http://127.0.0.1:5000";

export const searchMedicines = async (query, signal) => {
  if (!query || query.trim().length < 1) return [];

  const res = await fetch(
    `${BASE_URL}/inventory/medicines/search?q=${encodeURIComponent(query)}`,
    { signal }   // Abort controller
  );

  if (!res.ok) {
    throw new Error("Failed to search medicines");
  }

  return res.json();
};