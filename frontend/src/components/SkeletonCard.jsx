export default function SkeletonCard() {
  return (
    <div className="bg-surface rounded-xl shadow-card border border-leaf/40 border-l-4 mb-5 overflow-hidden animate-pulse">
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="h-4 bg-surface2 rounded-full w-20 animate-pulse"></div>
          <div className="h-4 bg-surface2 rounded-full w-16 animate-pulse"></div>
        </div>
        <div className="space-y-2">
          <div className="h-3 bg-surface2 rounded-full w-3/4 animate-pulse"></div>
          <div className="h-3 bg-surface2 rounded-full w-1/2 animate-pulse"></div>
        </div>
        <div className="flex justify-between items-center mt-3">
          <div className="h-3 bg-surface2 rounded-full w-24 animate-pulse"></div>
          <div className="h-6 bg-surface2 rounded-full w-6 animate-pulse"></div>
        </div>
      </div>
    </div>
  )
}