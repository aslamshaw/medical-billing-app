import { useQuery } from "@tanstack/react-query";
import { fetchSuppliers } from "../api/supplierAPI";
import { supplierKeys } from "../queryKeys/supplierKeys";

export const useSuppliers = () => {
  return useQuery({
    queryKey: supplierKeys.lists(),
    queryFn: fetchSuppliers,
  });
};