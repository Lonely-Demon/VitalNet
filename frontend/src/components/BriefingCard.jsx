import { useState } from 'react'
import axios from 'axios'
import TriageBadge from './TriageBadge'

export default function BriefingCard({ caseData, onReviewed }) {
  const [expanded, setExpanded] = useState(caseData.triage_level === 'EMERGENCY')
  const [marking, setMarking] = useState(false)
  const [reviewed, setReviewed] = useState(caseData.reviewed)

  const b = caseData.briefing

  const handleMarkReviewed = async () => {
    setMarking(true)
    try {
      await axios.patch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/cases/${caseData.case_id}/review`, { reviewed: true })
      setReviewed(true)
      if (onReviewed) onReviewed(caseData.case_id)
    } catch (e) {
      console.error("Review update failed", e)
    } finally {
      setMarking(false)
    }
  }

  const timeStr = new Date(caseData.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit'
  })

  return (
    <div className={`bg-white rounded-xl shadow-sm hover:shadow-md transition-all duration-200 border border-t border-r border-b border-gray-200 border-l-4 mb-5 overflow-hidden animate-in fade-in slide-in-from-bottom-2 focus-within:ring-2 focus-within:ring-blue-100
      ${caseData.triage_level === 'EMERGENCY' ? 'border-l-red-500' :
        caseData.triage_level === 'URGENT' ? 'border-l-amber-500' : 'border-l-emerald-500'}
      ${reviewed ? 'opacity-60 saturate-50' : ''}
    `}>
      {/* Header — always visible */}
      <div
        className="p-4 cursor-pointer flex items-start justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <TriageBadge level={caseData.triage_level} />
            {reviewed && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                Reviewed
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-gray-800">
            {caseData.patient_age}
            {caseData.patient_sex === 'male' ? 'M' : caseData.patient_sex === 'female' ? 'F' : ''}
            {" · "}{caseData.location}
          </p>
          <p className="text-sm text-gray-600">{caseData.chief_complaint}</p>
          <p className="text-xs text-gray-400 mt-1">
            {timeStr} · ASHA {caseData.asha_id}
          </p>
        </div>
        <span className="text-gray-400 ml-2">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Expanded briefing */}
      {expanded && b && (
        <div className="px-5 pb-5 border-t border-gray-100 pt-4 space-y-5 bg-slate-50/30">

          <BriefingSection title="Primary Signal">
            <p className="text-sm text-slate-800 font-medium leading-relaxed">{b.primary_risk_driver}</p>
          </BriefingSection>

          <BriefingSection title="Differential Diagnoses">
            <ul className="text-sm text-slate-700 space-y-1.5 list-none">
              {(b.differential_diagnoses || []).map((d, i) => (
                <li key={i} className="flex gap-2.5 items-start">
                  <span className="text-blue-600 font-bold shrink-0">{i + 1}.</span> {d}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.red_flags?.length > 0 && (
            <BriefingSection title="⚠ Red Flags">
              <ul className="text-sm text-red-700 space-y-1">
                {b.red_flags.map((f, i) => (
                  <li key={i}>· {f}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Immediate Actions">
            <ul className="text-sm text-gray-700 space-y-1">
              {(b.recommended_immediate_actions || []).map((a, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-green-600">→</span> {a}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.recommended_tests?.length > 0 && (
            <BriefingSection title="Recommended Tests">
              <ul className="text-sm text-gray-700 space-y-1">
                {b.recommended_tests.map((t, i) => (
                  <li key={i}>· {t}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Uncertainty Flags">
            <p className="text-sm text-amber-700">{b.uncertainty_flags}</p>
          </BriefingSection>

          {/* Disclaimer — non-removable */}
          <div className="bg-slate-100/80 border border-slate-200 rounded-lg p-3 mt-2 shadow-sm">
            <p className="text-xs text-slate-500 font-medium tracking-tight">⚠ {b.disclaimer}</p>
          </div>

          {/* Actions */}
          {!reviewed && (
            <button
              onClick={handleMarkReviewed}
              disabled={marking}
              className="w-full bg-blue-700 text-white py-3 rounded-xl text-sm font-bold shadow-sm hover:shadow-md disabled:opacity-60 disabled:cursor-wait mt-3 cursor-pointer transition-all hover:bg-blue-800 focus:ring-4 focus:ring-blue-100"
            >
              {marking ? "Updating Record..." : "Mark Case as Reviewed"}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function BriefingSection({ title, children }) {
  return (
    <div>
      <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">{title}</p>
      {children}
    </div>
  )
}
