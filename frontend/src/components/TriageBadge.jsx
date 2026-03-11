const COLORS = {
  EMERGENCY: "bg-red-600 text-white shadow-sm border border-red-700/30",
  URGENT: "bg-amber-500 text-gray-900 shadow-sm border border-amber-600/30",
  ROUTINE: "bg-emerald-600 text-white shadow-sm border border-emerald-700/30",
}

export default function TriageBadge({ level }) {
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold tracking-wide ${COLORS[level] || "bg-gray-200 text-gray-700"}`}>
      {level}
    </span>
  )
}
