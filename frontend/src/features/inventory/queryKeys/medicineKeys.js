export const medicineKeys = {
  all: ["medicines"],

  search: (q) => [...medicineKeys.all, "search", q],
};