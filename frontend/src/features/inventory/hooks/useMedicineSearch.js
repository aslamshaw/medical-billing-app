import { useQuery } from "@tanstack/react-query";
import { searchMedicines } from "../api/medicineAPI";
import { medicineKeys } from "../queryKeys/medicineKeys";

export const useMedicineSearch = (query) => {
  return useQuery({
    queryKey: medicineKeys.search(query),

    // queryFn: (ctx = { queryKey: [...], signal: AbortSignal, meta: ... }) => searchMedicines(query, ctx.signal)
    // it can be deconstructed like below where excluding signal extra properties are ignored
    queryFn: ({ signal }) => searchMedicines(query, signal),  // queryFn callback gives you ctx object

    enabled: !!query && query.trim().length > 0,

    staleTime: 5 * 60 * 1000,
    keepPreviousData: true, // prevents flicker
  });
};