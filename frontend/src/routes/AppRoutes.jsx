import { Routes, Route } from "react-router-dom";
import RouteLayout from "../layouts/RouteLayout";

import Dashboard from "../pages/Dashboard";
import Purchase from "../pages/Purchase";
import Inventory from "../pages/Inventory";
import Billing from "../pages/Billing";

function AppRoutes() {
  return (
    <Routes>
      <Route element={<RouteLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="purchase" element={<Purchase />} />
        <Route path="inventory" element={<Inventory />} />
        <Route path="billing" element={<Billing />} />
      </Route>
    </Routes>
  );
}

export default AppRoutes;