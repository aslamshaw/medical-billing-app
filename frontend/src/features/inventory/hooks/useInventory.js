import { useQuery } from "@tanstack/react-query";
import { fetchMedicines } from "../api/inventoryAPI";
import { inventoryKeys } from "../queryKeys/inventoryKeys";

export const useInventory = () => {
  return useQuery({
    queryKey: inventoryKeys.lists(),
    queryFn: fetchMedicines,
  });
};