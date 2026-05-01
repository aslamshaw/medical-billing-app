import { useState, useEffect } from "react";
import { useMedicineSearch } from "../hooks/useMedicineSearch";

// small reusable debounce hook
function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return debounced;
}

// self-contained smart input field through state isolation by avoiding shared medicineQuery state for all item input
export default function MedicineAutocomplete({ value, onChange, onSelect }) {
  /*

  The prop value === item.medicine_name is different for each MedicineAutocomplete component based on item object

  Consider this structure:
    form.items = [
      { item_id: 1, medicine_name: "" },
      { item_id: 2, medicine_name: "" }
    ]

  When you type in row 1:
    handleItemChange(1, "paracetamol")

  You update only:
    form.items[0].medicine_name

  So React state becomes:
    form.items = [
      { item_id: 1, medicine_name: "paracetamol" },
      { item_id: 2, medicine_name: "" }
    ]
  
  value prop for item 2 is not changed thus no suggestions drop down is showed.
  Thus, you can technically use value prop instead of local query for debounce and input's onChange.

  But this creates UI related bugs:
  
  1. Persisted form state (source of truth) -> item.medicine_name
      Used for submission
      Represents confirmed data
      Should be stable and predictable

  2. Ephemeral typing state (UI behavior) -> local state query when user is currently typing
      Changes every keystroke
      Drives autocomplete
      Needs debouncing, cancellation, etc.

  Thus using value prop directly as a state to update on input change would create unncessary renders and flickers.
  Form state must NEVER be used as a live search driver.

  CASE 1: Selection behavior breaks

  const debouncedValue = useDebounce(value, 300);
  const { data: suggestions } = useMedicineSearch(debouncedValue);  

  input value = "para"
  debouncedValue = "para"
  suggestions = ["Paracetamol", "Paracip"]
  dropdown shows suggestions based on "para"

  onSelect(med) → setForm(... medicine_name = "Paracetamol") → parent sets medicine_name

  previous debouncedValue = "para"
  new value = "Paracetamol"
  after 300ms → debouncedValue = "Paracetamol" → useMedicineSearch("Paracetamol")
  dropdown flicker due to updated suggestions state and shows suggestions based on "Paracetamol"


  CASE 2: Stale dropdown after fast typing with slow network i.e. Race Condition

  Query	    Response time
  "pa"	 -> 400ms
  "par"	 -> 100ms
  "para" ->	300ms

  So responses arrive out of order:
    "par" returns first   -> UI shows suggestions for "par"
    "para" returns later  -> Then suddenly updates to "para"
    "pa" returns last     -> Then incorrectly reverts to "pa" results

  Need signal in queryFn for useQuery.

  */
  const [query, setQuery] = useState(value || "");

  // debounced query
  const debouncedQuery = useDebounce(query, 300); // each keystroke within the delay period clears previous set request 

  const [isSelecting, setIsSelecting] = useState(false);

  // React Query call (controlled)
  // only the latest debouncedQuery is used to fetch suggestions
  const { data: suggestions = [] } = useMedicineSearch(debouncedQuery);

  /*
  keep internal state synced if parent updates value

  local query	setQuery(val) -> immediate update
  parent form -onChange(val) > async batch update
  
  So for a brief moment:
    query = "par"
    value = "pa"

  local input already shows latest keystroke but parent is at least 1–2 renders behind

  While query is "para", user selects the medicine name triggering handleSelect -> onSelect -> handleSelectMedicine updates:
    form.items[].medicine_name = "Paracetamol"

  Now query and form.items[].medicine_name are different.
  Whenever parent changes the value, useEffect setQuery forces local query to match it

  Without that sync:
    Input still shows "para"
    Dropdown disappears (because selection happened)
    But form actually contains "Paracetamol"

  */
  useEffect(() => {
    setQuery(value || "");
  }, [value]);

  const handleChange = (e) => {
    const val = e.target.value;
    setIsSelecting(false);
    /*
    
    Since we are syncing query and form.items[].medicine_name for that item on each key stroke,
    value and query would be same until you select the suggestion where for a brief moment they are different
    but useEffect make sures that they are synced after onSelect.
    
    */
    setQuery(val); // IMMEDIATELY triggers re-render of the componenT
    onChange(val); // SLOW Async update parent form, triggers re-render of parent and child through setForm
  };

  const handleSelect = (med) => {
    setIsSelecting(true);
    setQuery(med.name);
    onSelect(med);
  };

  return (
    <div className="relative">
      <input value={query} onChange={handleChange} placeholder="Medicine" className="border p-2 w-full" />

      {suggestions.length > 0 && query && !isSelecting && (
        <div className="absolute bg-white border w-full mt-1 max-h-40 overflow-y-auto z-10">
          {suggestions.map((med) => (
            <div key={med.id} onClick={() => handleSelect(med)} className="p-2 hover:bg-gray-100 cursor-pointer text-sm">
              {med.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}