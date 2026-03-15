const COLORS = {
  EMERGENCY: "bg-emergency/10 text-emergency border border-emergency/30 font-mono",
  URGENT: "bg-urgent/10 text-urgent border border-urgent/30 font-mono",
  ROUTINE: "bg-routine/10 text-routine border border-routine/30 font-mono",
}

export default function TriageBadge({ level }) {
  return (
    <span className={`inline-block px-3 py-1 rounded-pill text-sm font-bold tracking-wide ${COLORS[level] || "bg-surface3 text-text2"}`}>
      {level}
    </span>
  )
}
