export default function TabLoadingFallback() {
  return (
    <div className="min-h-[12rem] flex items-center justify-center" role="status" aria-live="polite">
      <div className="w-6 h-6 border-2 border-forest border-t-transparent rounded-full animate-spin" aria-hidden="true" />
      <span className="sr-only">Loading section</span>
    </div>
  )
}
