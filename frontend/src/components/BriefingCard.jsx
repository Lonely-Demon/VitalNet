import { useState } from 'react'
import { reviewCase } from '../lib/api'
import TriageBadge from './TriageBadge'

export default function BriefingCard({ caseData, onReviewed }) {
  const [expanded, setExpanded] = useState(caseData.triage_level === 'EMERGENCY')
  const [marking, setMarking] = useState(false)
  const [reviewed, setReviewed] = useState(caseData.reviewed_at !== null)

  // briefing is already a JSONB object from Supabase — no JSON.parse needed
  const b = caseData.briefing

  const handleMarkReviewed = async () => {
    setMarking(true)
    try {
      await reviewCase(caseData.id)
      setReviewed(true)
      if (onReviewed) onReviewed(caseData.id)
    } catch (e) {
      console.error("Review update failed", e)
    } finally {
      setMarking(false)
    }
  }

  const timeStr = new Date(caseData.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit'
  })

  const borderColor = caseData.triage_level === 'EMERGENCY'
    ? 'border-l-emergency'
    : caseData.triage_level === 'URGENT'
    ? 'border-l-urgent'
    : 'border-l-routine'

  return (
    <div className={`bg-surface rounded-xl shadow-card hover:shadow-card-hover transition-all duration-200 border border-leaf/40 border-l-4 mb-5 overflow-hidden animate-fade-up
      ${borderColor}
      ${reviewed ? 'opacity-60 saturate-50' : ''}
      ${caseData.triage_level === 'EMERGENCY' ? 'animate-pulse-ring' : ''}
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
              <span className="text-xs text-text3 bg-surface2 px-2 py-0.5 rounded font-mono">
                Reviewed
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-text">
            {caseData.patient_age}
            {caseData.patient_sex === 'male' ? 'M' : caseData.patient_sex === 'female' ? 'F' : ''}
            {" · "}{caseData.patient_location}
          </p>
          <p className="text-sm text-text2">{caseData.chief_complaint}</p>
          <p className="text-xs text-text3 mt-1 font-mono">
            {timeStr}
          </p>
        </div>
        <span className="text-text3 ml-2">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Expanded briefing */}
      {expanded && b && (
        <div className="px-5 pb-5 border-t border-leaf/40 pt-4 space-y-5 bg-surface2/30">

          <BriefingSection title="Primary Signal">
            <p className="text-sm text-text font-medium leading-relaxed">{b.primary_risk_driver}</p>
          </BriefingSection>

          <BriefingSection title="Differential Diagnoses">
            <ul className="text-sm text-text2 space-y-1.5 list-none">
              {(b.differential_diagnoses || []).map((d, i) => (
                <li key={i} className="flex gap-2.5 items-start">
                  <span className="text-sage font-bold shrink-0">{i + 1}.</span> {d}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.red_flags?.length > 0 && (
            <BriefingSection title="Red Flags">
              <ul className="text-sm text-emergency space-y-1">
                {b.red_flags.map((f, i) => (
                  <li key={i}>· {f}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Immediate Actions">
            <ul className="text-sm text-text2 space-y-1">
              {(b.recommended_immediate_actions || []).map((a, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-routine">→</span> {a}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.recommended_tests?.length > 0 && (
            <BriefingSection title="Recommended Tests">
              <ul className="text-sm text-text2 space-y-1">
                {b.recommended_tests.map((t, i) => (
                  <li key={i}>· {t}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Uncertainty Flags">
            <p className="text-sm text-urgent">{b.uncertainty_flags}</p>
          </BriefingSection>

          {/* Disclaimer — non-removable */}
          <div className="bg-surface2 border border-leaf/40 rounded-lg p-3 mt-2 shadow-card">
            <p className="text-xs text-text3 font-medium tracking-tight font-mono">{b.disclaimer}</p>
          </div>

          {/* Actions */}
          {!reviewed && (
            <button
              onClick={handleMarkReviewed}
              disabled={marking}
              className="w-full bg-forest text-white py-3 rounded-pill text-sm font-bold shadow-btn hover:shadow-card-hover disabled:opacity-60 disabled:cursor-wait mt-3 cursor-pointer transition-all active:scale-[0.98]"
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
      <p className="text-xs font-mono font-bold text-text3 uppercase tracking-widest mb-2">{title}</p>
      {children}
    </div>
  )
}
