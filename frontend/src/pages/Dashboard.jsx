import { useState, useEffect } from 'react'
import axios from 'axios'
import BriefingCard from '../components/BriefingCard'

export default function Dashboard() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCases = async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
      const res = await axios.get(`${API_BASE}/api/cases`)
      setCases(res.data)
      setError(null)
    } catch (e) {
      setError("Failed to load cases. Check backend connection.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
    // Poll every 30 seconds
    const interval = setInterval(fetchCases, 30000)
    return () => clearInterval(interval)
  }, [])

  const emergency = cases.filter(c => c.triage_level === 'EMERGENCY')
  const urgent = cases.filter(c => c.triage_level === 'URGENT')
  const routine = cases.filter(c => c.triage_level === 'ROUTINE')

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-4 mt-8 text-center text-gray-500">
        Loading cases...
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-4 mt-6">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-gray-100">
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Doctor Dashboard</h1>
        <button onClick={fetchCases} className="text-sm font-medium text-blue-600 bg-blue-50 px-4 py-2 rounded-lg hover:bg-blue-100 transition-colors shadow-sm cursor-pointer">
          Refresh Queue
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg shadow-sm mb-6 text-sm">
          {error}
        </div>
      )}

      {cases.length === 0 && !error && (
        <div className="text-center bg-white border border-dashed border-gray-300 rounded-xl p-12 shadow-sm mt-8">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-xl font-medium text-slate-800 tracking-tight">Queue is Empty</p>
          <p className="text-sm text-slate-500 mt-2">New cases submitted by ASHAs will appear here</p>
        </div>
      )}

      {/* Emergency first */}
      {emergency.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-bold text-red-600 uppercase tracking-widest mb-3 flex items-center gap-2">
            Emergency <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{emergency.length}</span>
          </h2>
          {emergency.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}

      {urgent.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-bold text-amber-600 uppercase tracking-widest mb-3 flex items-center gap-2">
            Urgent <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{urgent.length}</span>
          </h2>
          {urgent.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}

      {routine.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-bold text-emerald-700 uppercase tracking-widest mb-3 flex items-center gap-2">
            Routine <span className="bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">{routine.length}</span>
          </h2>
          {routine.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}
    </div>
  )
}
