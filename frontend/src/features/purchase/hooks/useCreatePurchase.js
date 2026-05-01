import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPurchase } from "../api/purchaseAPI";
import { inventoryKeys } from "../../inventory/queryKeys/inventoryKeys";

export const useCreatePurchase = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createPurchase,

    onSuccess: () => {
      // Invalidate inventory query so it refetches fresh data, which updates cache, causing inventory pages' UI to re-render
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists(), });
    },

    retry: false,
  });
};


/*

When you create a purchase on the Purchase page, you don’t directly show inventory data there, 
but the mutation’s onSuccess invalidates the inventory query:

  queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });

This marks the inventory cache as stale. Now:
If the Inventory page is mounted, it immediately refetches and updates the UI.
If the Inventory page is not mounted, the cache is just marked stale, 
so the next time the user visits the Inventory page, it will fetch fresh data automatically.

The nuance here is that mutations on one page can proactively trigger updates on other pages, 
keeping the UI consistent without prop drilling, Redux, or manual events.

*/