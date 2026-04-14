import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSupplier } from "../api/supplierAPI";
import { supplierKeys } from "../queryKeys/supplierKeys";

export const useCreateSupplier = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSupplier,

    onSuccess: () => {
      // refresh supplier list instantly
      queryClient.invalidateQueries({ queryKey: supplierKeys.lists(), });
    },
  });
};