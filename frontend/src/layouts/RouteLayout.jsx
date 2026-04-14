import { Outlet, Link, useLocation } from "react-router-dom";

export default function RouteLayout() {
  const location = useLocation();   // We want to highlight tab based on location name

  // Use location.pathname.includes(to); to highlight /inventory even if location name is /inventory/123
  const navItem = (to, label) => {    // Helper function to avoid making <Link /> manually
    const isActive = location.pathname === to;    // Is this sidebar item the current page
    return (
      <Link
        to={to}
        className={`block px-3 py-2 rounded-lg text-sm font-medium 
        ${isActive ? "bg-blue-100 text-blue-600" : "text-gray-700 hover:bg-gray-100"}`}
      >
        {label}
      </Link>
    );
  };

  return (
    <div className="flex h-screen bg-gray-50">

      {/* Sidebar */}
      <aside className="w-60 bg-white border-r p-4">
        <h1 className="text-lg font-bold mb-6">MedBill</h1>

        <nav className="space-y-2">             {/* If location.pathname = "/inventory", each nav item runs */}
          {navItem("/", "Dashboard")}           {/* → false */}
          {navItem("/purchase", "Purchase")}    {/* → false */}
          {navItem("/inventory", "Inventory")}  {/* → True */}
          {navItem("/billing", "Billing")}      {/* → false */}
        </nav>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col">

        {/* Header */}
        <header className="h-14 bg-white border-b flex items-center px-6">
          <h2 className="text-sm text-gray-600">
            {location.pathname === "/" ? "Dashboard" : location.pathname.replace("/", "").toUpperCase()}
          </h2>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </main>

      </div>
    </div>
  );
}