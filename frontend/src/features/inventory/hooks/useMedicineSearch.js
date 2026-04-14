import { useQuery } from "@tanstack/react-query";
import { searchMedicines } from "../api/medicineAPI";
import { medicineKeys } from "../queryKeys/medicineKeys";

export const useMedicineSearch = (query) => {
  return useQuery({
    queryKey: medicineKeys.search(query),
    queryFn: () => searchMedicines(query),

    enabled: !!query && query.trim().length > 0,

    staleTime: 5 * 60 * 1000, // small cache reuse
  });
};