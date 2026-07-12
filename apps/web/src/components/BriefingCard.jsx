import { useState } from 'react'
import { ChevronUp, ChevronDown, ArrowRight, Check, Flag, TriangleAlert } from 'lucide-react'
import { reviewCase, overrideTriage, recordCaseOutcome, listActiveFacilities, createReferral, getPatientSummary } from '../lib/api'
import TriageBadge from './TriageBadge'

const TIERS = ['ROUTINE', 'URGENT', 'EMERGENCY']
const SUMMARY_LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'ta', label: 'Tamil' },
]
const DISPOSITIONS = [
  { value: 'treated_discharged', label: 'Treated & discharged' },
  { value: 'admitted', label: 'Admitted' },
  { value: 'referred_higher_facility', label: 'Referred to higher facility' },
  { value: 'deceased', label: 'Deceased' },
  { value: 'unknown', label: 'Unknown' },
]

export default function BriefingCard({ caseData, onReviewed }) {
  const [expanded, setExpanded] = useState(caseData.triage_level === 'EMERGENCY')
  const [marking, setMarking] = useState(false)
  const [reviewed, setReviewed] = useState(caseData.reviewed_at !== null)

  const [showOverride, setShowOverride] = useState(false)
  const [overrideTier, setOverrideTier] = useState(caseData.triage_level)
  const [overrideReason, setOverrideReason] = useState('')
  const [overriding, setOverriding] = useState(false)
  const [overrideState, setOverrideState] = useState({
    triage: caseData.overridden_triage || null,
    reason: caseData.override_reason || null,
  })

  const [showOutcome, setShowOutcome] = useState(false)
  const [outcomeSeverity, setOutcomeSeverity] = useState(caseData.triage_level)
  const [outcomeDisposition, setOutcomeDisposition] = useState('treated_discharged')
  const [outcomeNotes, setOutcomeNotes] = useState('')
  const [recordingOutcome, setRecordingOutcome] = useState(false)
  const [outcomeRecorded, setOutcomeRecorded] = useState(false)

  const [summaryLanguage, setSummaryLanguage] = useState('en')
  const [patientSummary, setPatientSummary] = useState(null)   // { summary, generated } once fetched
  const [loadingSummary, setLoadingSummary] = useState(false)
  const [summaryError, setSummaryError] = useState(null)

  const [showReferral, setShowReferral] = useState(false)
  const [facilities, setFacilities] = useState(null)   // null = not yet loaded
  const [facilitiesError, setFacilitiesError] = useState(null)
  const [referralFacilityId, setReferralFacilityId] = useState('')
  const [referralReason, setReferralReason] = useState('')
  const [referralUrgency, setReferralUrgency] = useState(overrideState.triage || caseData.triage_level)
  const [referring, setReferring] = useState(false)
  const [referred, setReferred] = useState(null)   // { facilityName } once created

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

  const handleGetPatientSummary = async () => {
    setLoadingSummary(true)
    setSummaryError(null)
    try {
      const result = await getPatientSummary(caseData.id, summaryLanguage)
      setPatientSummary(result)
    } catch (e) {
      setSummaryError(e.message || 'Could not generate a summary right now.')
    } finally {
      setLoadingSummary(false)
    }
  }

  const handleOverride = async () => {
    if (!overrideReason.trim()) return
    setOverriding(true)
    try {
      await overrideTriage(caseData.id, { overridden_triage: overrideTier, override_reason: overrideReason.trim() })
      setOverrideState({ triage: overrideTier, reason: overrideReason.trim() })
      setShowOverride(false)
    } catch (e) {
      console.error("Triage override failed", e)
    } finally {
      setOverriding(false)
    }
  }

  const handleRecordOutcome = async () => {
    setRecordingOutcome(true)
    try {
      await recordCaseOutcome(caseData.id, {
        actual_severity: outcomeSeverity,
        patient_disposition: outcomeDisposition,
        outcome_notes: outcomeNotes.trim() || null,
      })
      setOutcomeRecorded(true)
      setShowOutcome(false)
    } catch (e) {
      console.error("Recording outcome failed", e)
    } finally {
      setRecordingOutcome(false)
    }
  }

  const handleOpenReferral = async () => {
    setShowReferral(true)
    if (facilities === null) {
      try {
        const data = await listActiveFacilities()
        setFacilities(data)
        if (data.length > 0) setReferralFacilityId(data[0].id)
      } catch (e) {
        setFacilitiesError(e.message)
      }
    }
  }

  const handleCreateReferral = async () => {
    if (!referralFacilityId || !referralReason.trim()) return
    setReferring(true)
    try {
      await createReferral(caseData.id, {
        receiving_facility_id: referralFacilityId,
        reason: referralReason.trim(),
        urgency: referralUrgency,
      })
      const target = facilities?.find((f) => f.id === referralFacilityId)
      setReferred({ facilityName: target?.name || 'the receiving facility' })
      setShowReferral(false)
    } catch (e) {
      console.error("Referral failed", e)
      setFacilitiesError(e.message)
    } finally {
      setReferring(false)
    }
  }

  const timeStr = new Date(caseData.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit'
  })

  const tierBg = caseData.triage_level === 'EMERGENCY'
    ? 'bg-emergency'
    : caseData.triage_level === 'URGENT'
    ? 'bg-urgent'
    : 'bg-routine'

  return (
    <div className={`flex bg-surface rounded-xl shadow-card hover:shadow-card-hover transition-all duration-200 border border-leaf/40 mb-5 overflow-hidden animate-fade-up
      ${reviewed ? 'opacity-60 saturate-50' : ''}
      ${caseData.triage_level === 'EMERGENCY' ? 'animate-pulse-ring' : ''}
    `}>
      {/* Triage-tag signature: a perforated severity edge, echoing a real
          mass-casualty tag torn along a dotted line to the tier that
          applies — see docs/DECISIONS.md §34. */}
      <div className={`w-[7px] shrink-0 tag-perforated ${tierBg}`} aria-hidden="true"></div>
      <div className="flex-1 min-w-0">
      {/* Header — always visible */}
      <div
        className="p-4 cursor-pointer flex items-start justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <TriageBadge level={caseData.triage_level} />
            {overrideState.triage && overrideState.triage !== caseData.triage_level && (
              <span className="text-xs text-forest bg-leaf/40 px-2 py-0.5 rounded font-mono inline-flex items-center gap-1">
                <ArrowRight size={12} aria-hidden="true" />{overrideState.triage} (adjusted)
              </span>
            )}
            {reviewed && (
              <span className="text-xs text-text3 bg-surface2 px-2 py-0.5 rounded font-mono">
                Reviewed
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-text">
            {caseData.patient_name && <>{caseData.patient_name} · </>}
            {caseData.patient_age}
            {caseData.patient_sex === 'male' ? 'M' : caseData.patient_sex === 'female' ? 'F' : ''}
            {" · "}{caseData.patient_location}
          </p>
          <p className="text-sm text-text2">{caseData.chief_complaint}</p>
          <p className="text-xs text-text3 mt-1 font-mono">
            {timeStr}
            {caseData.triage_model_version && <> · model v{caseData.triage_model_version}</>}
          </p>
          {(caseData.needs_review || caseData.low_confidence || caseData.human_review_requested || caseData.deterioration_alert) && (
            <p className="text-xs text-urgent font-bold mt-1 flex items-start gap-1.5">
              {caseData.human_review_requested || caseData.contraindication_flags?.length > 0 || caseData.deterioration_alert
                ? <Flag size={13} className="shrink-0 mt-0.5" aria-hidden="true" />
                : <TriangleAlert size={13} className="shrink-0 mt-0.5" aria-hidden="true" />}
              {caseData.human_review_requested
                ? 'Review requested by submitter'
                : caseData.contraindication_flags?.length > 0
                ? 'Possible contraindication flagged — see below'
                : caseData.deterioration_alert
                ? 'Repeated severe visits — see below'
                : 'Model uncertain — clinician review recommended'}
            </p>
          )}
        </div>
        <span className="text-text3 ml-2">{expanded ? <ChevronUp size={18} aria-hidden="true" /> : <ChevronDown size={18} aria-hidden="true" />}</span>
      </div>

      {/* Expanded briefing */}
      {expanded && b && (
        <div className="px-5 pb-5 border-t border-leaf/40 pt-4 space-y-5 bg-surface2/30">

          {caseData.contraindication_flags?.length > 0 && (
            <BriefingSection title="Contraindication Flags">
              <ul className="text-sm text-emergency space-y-1.5">
                {caseData.contraindication_flags.map((flag, i) => <li key={i}>· {flag}</li>)}
              </ul>
            </BriefingSection>
          )}

          {caseData.deterioration_alert && (
            <BriefingSection title="Deterioration Alert">
              <p className="text-sm text-emergency">
                {caseData.deterioration_visit_count ?? 2}+ URGENT/EMERGENCY visits from this patient
                within the last 7 days, including this one — consider whether this presentation
                needs closer follow-up than a single visit would suggest.
              </p>
            </BriefingSection>
          )}

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
                  <ArrowRight size={14} className="text-routine shrink-0 mt-0.5" aria-hidden="true" /> {a}
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

          {caseData.human_review_requested && caseData.human_review_reason && (
            <BriefingSection title="Review Requested By Submitter">
              <p className="text-sm text-text2">{caseData.human_review_reason}</p>
            </BriefingSection>
          )}

          {overrideState.triage && (
            <BriefingSection title="Clinician Override">
              <p className="text-sm text-text2">
                Adjusted to <strong className="text-forest">{overrideState.triage}</strong>: {overrideState.reason}
              </p>
            </BriefingSection>
          )}

          {/* Disclaimer — non-removable */}
          <div className="bg-surface2 border border-leaf/40 rounded-lg p-3 mt-2 shadow-card">
            <p className="text-xs text-text3 font-medium tracking-tight font-mono">{b.disclaimer}</p>
          </div>

          {/* Patient-facing plain-language summary — restates the briefing
              above, never re-derives it. For the ASHA worker to read aloud
              so consent is informed, not just captured. */}
          <BriefingSection title="Explain to Patient">
            {patientSummary ? (
              <div>
                <p className="text-sm text-text leading-relaxed">{patientSummary.summary}</p>
                {!patientSummary.generated && (
                  <p className="text-xs text-text3 mt-2 italic">Standard wording — a tailored summary wasn't available right now.</p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <select
                  value={summaryLanguage}
                  onChange={(e) => setSummaryLanguage(e.target.value)}
                  aria-label="Summary language"
                  className="border border-surface3 rounded-md px-2 py-1.5 text-sm bg-surface"
                >
                  {SUMMARY_LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
                <button
                  onClick={handleGetPatientSummary}
                  disabled={loadingSummary}
                  className="bg-sage text-white px-4 py-1.5 rounded-pill text-sm font-medium disabled:opacity-50 cursor-pointer"
                >
                  {loadingSummary ? 'Generating…' : 'Show patient-friendly summary'}
                </button>
                {summaryError && <span className="text-xs text-emergency">{summaryError}</span>}
              </div>
            )}
          </BriefingSection>

          {/* Triage override */}
          {!overrideState.triage && (
            showOverride ? (
              <fieldset className="p-3 rounded-lg border border-leaf/40 bg-surface2 space-y-2">
                <legend className="block text-xs font-mono font-bold text-text3 uppercase tracking-widest">
                  Correct triage tier
                </legend>
                <select
                  value={overrideTier}
                  onChange={(e) => setOverrideTier(e.target.value)}
                  aria-label="Correct triage tier"
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface"
                >
                  {TIERS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Why does this case need a different tier?"
                  aria-label="Why does this case need a different tier?"
                  rows={2}
                  maxLength={500}
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleOverride}
                    disabled={overriding || !overrideReason.trim()}
                    className="flex-1 bg-forest text-white py-2 rounded-pill text-sm font-medium disabled:opacity-50 cursor-pointer"
                  >
                    {overriding ? 'Saving…' : 'Save override'}
                  </button>
                  <button
                    onClick={() => setShowOverride(false)}
                    className="px-4 py-2 text-sm text-text2 cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </fieldset>
            ) : (
              <button
                onClick={() => setShowOverride(true)}
                className="block text-xs text-text3 hover:text-forest underline cursor-pointer"
              >
                Correct the triage tier
              </button>
            )
          )}

          {/* Record outcome — shown only after review */}
          {reviewed && !outcomeRecorded && (
            showOutcome ? (
              <fieldset className="p-3 rounded-lg border border-leaf/40 bg-surface2 space-y-2">
                <legend className="block text-xs font-mono font-bold text-text3 uppercase tracking-widest">
                  Record patient outcome
                </legend>
                <select
                  value={outcomeSeverity}
                  onChange={(e) => setOutcomeSeverity(e.target.value)}
                  aria-label="Actual severity"
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface"
                >
                  {TIERS.map(t => <option key={t} value={t}>Actual severity: {t}</option>)}
                </select>
                <select
                  value={outcomeDisposition}
                  onChange={(e) => setOutcomeDisposition(e.target.value)}
                  aria-label="Patient disposition"
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface"
                >
                  {DISPOSITIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
                <textarea
                  value={outcomeNotes}
                  onChange={(e) => setOutcomeNotes(e.target.value)}
                  placeholder="Outcome notes (optional)"
                  aria-label="Outcome notes (optional)"
                  rows={2}
                  maxLength={1000}
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleRecordOutcome}
                    disabled={recordingOutcome}
                    className="flex-1 bg-forest text-white py-2 rounded-pill text-sm font-medium disabled:opacity-50 cursor-pointer"
                  >
                    {recordingOutcome ? 'Saving…' : 'Save outcome'}
                  </button>
                  <button
                    onClick={() => setShowOutcome(false)}
                    className="px-4 py-2 text-sm text-text2 cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </fieldset>
            ) : (
              <button
                onClick={() => setShowOutcome(true)}
                className="block text-xs text-text3 hover:text-forest underline cursor-pointer"
              >
                Record patient outcome
              </button>
            )
          )}
          {outcomeRecorded && (
            <p className="text-xs text-forest font-medium inline-flex items-center gap-1">
              <Check size={13} aria-hidden="true" />Outcome recorded
            </p>
          )}

          {/* Inter-facility referral (FEATURES_ROADMAP §2.3) */}
          {referred ? (
            <p className="text-xs text-forest font-medium inline-flex items-center gap-1">
              <Check size={13} aria-hidden="true" />Referred to {referred.facilityName}
            </p>
          ) : (
            showReferral ? (
              <fieldset className="p-3 rounded-lg border border-leaf/40 bg-surface2 space-y-2">
                <legend className="block text-xs font-mono font-bold text-text3 uppercase tracking-widest">
                  Refer to another facility
                </legend>
                {facilitiesError && <p className="text-xs text-emergency">{facilitiesError}</p>}
                {facilities === null ? (
                  <p className="text-xs text-text3">Loading facilities…</p>
                ) : (
                  <select
                    value={referralFacilityId}
                    onChange={(e) => setReferralFacilityId(e.target.value)}
                    aria-label="Receiving facility"
                    className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface"
                  >
                    {facilities.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}{f.district ? ` — ${f.district}` : ''}
                        {f.capacity_status && f.capacity_status !== 'available' ? ` (${f.capacity_status})` : ''}
                        {typeof f.open_case_count === 'number' ? ` · ${f.open_case_count} open` : ''}
                      </option>
                    ))}
                  </select>
                )}
                <select
                  value={referralUrgency}
                  onChange={(e) => setReferralUrgency(e.target.value)}
                  aria-label="Referral urgency"
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface"
                >
                  {TIERS.map(t => <option key={t} value={t}>Urgency: {t}</option>)}
                </select>
                <textarea
                  value={referralReason}
                  onChange={(e) => setReferralReason(e.target.value)}
                  placeholder="Reason for referral"
                  aria-label="Reason for referral"
                  rows={2}
                  maxLength={1000}
                  className="w-full border border-surface3 rounded-md px-3 py-2 text-sm bg-surface resize-none"
                />
                <div className="flex gap-2">
                  <button
                    onClick={handleCreateReferral}
                    disabled={referring || !referralFacilityId || !referralReason.trim()}
                    className="flex-1 bg-forest text-white py-2 rounded-pill text-sm font-medium disabled:opacity-50 cursor-pointer"
                  >
                    {referring ? 'Referring…' : 'Confirm referral'}
                  </button>
                  <button
                    onClick={() => setShowReferral(false)}
                    className="px-4 py-2 text-sm text-text2 cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </fieldset>
            ) : (
              <button
                onClick={handleOpenReferral}
                className="block text-xs text-text3 hover:text-forest underline cursor-pointer"
              >
                Refer to another facility
              </button>
            )
          )}

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
