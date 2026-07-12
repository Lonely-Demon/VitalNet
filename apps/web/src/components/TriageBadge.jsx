const COLORS = {
  EMERGENCY: "bg-emergency",
  URGENT: "bg-urgent",
  ROUTINE: "bg-routine",
}

export default function TriageBadge({ level }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded text-xs font-display font-bold tracking-wide uppercase text-white ${COLORS[level] || "bg-text3"}`}>
      {level}
    </span>
  )
}
