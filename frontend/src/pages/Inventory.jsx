import { useInventory } from "../features/inventory/hooks/useInventory";

export default function Inventory() {
  const { data, isLoading, isError, error } = useInventory();

  if (isLoading) return <p>Loading...</p>;
  if (isError) return <p className="text-red-500">{error.message}</p>;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Inventory</h2>

      <ul className="space-y-2">
        {data.map((med) => (
          <li key={med.id} className="p-4 bg-white border rounded-lg flex justify-between">
            <span>{med.name}</span>
            <span className="text-sm text-gray-600">Stock: {med.valid_stock}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}