import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Calculator,
  Pill,
  Droplet,
  Activity,
  AlertTriangle,
  Info,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import {
  calculateWeightBasedDose,
  calculateOrsVolume,
  calculateIvDripRate,
  calculateMaintenanceFluid,
  PEDIATRIC_DRUG_PRESETS,
  FREQUENCY_METADATA,
  DURATION_METADATA,
} from '@vitalnet/clinical-core'

const TABS = [
  { id: 'dose', label: 'Dose by Weight', icon: Pill },
  { id: 'ors', label: 'ORS & Dehydration', icon: Droplet },
  { id: 'iv', label: 'IV Drip Rate', icon: Activity },
  { id: 'fluid', label: 'Maintenance Fluids', icon: Calculator },
]

export default function ClinicalCalculators() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('dose')

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="bg-surface rounded-xl border border-leaf/40 p-5 shadow-card animate-fade-up">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-forest/10 border border-forest/20 flex items-center justify-center text-forest">
            <Calculator size={22} aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold text-text">
              {t('calculators.title', 'Clinical Calculators')}
            </h1>
            <p className="text-xs sm:text-sm text-text2 font-body">
              {t(
                'calculators.subtitle',
                'Deterministic offline calculation tools for paediatric dosing, rehydration, and fluid management.',
              )}
            </p>
          </div>
        </div>

        {/* Sub-Tabs */}
        <div className="flex flex-wrap gap-2 mt-5 pt-4 border-t border-leaf/30">
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-forest text-sand shadow-sm font-semibold'
                    : 'bg-surface2 text-text2 hover:bg-leaf/40 hover:text-text'
                }`}
              >
                <Icon size={16} aria-hidden="true" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Active Calculator Body */}
      <div className="animate-fade-up">
        {activeTab === 'dose' && <DoseCalculator />}
        {activeTab === 'ors' && <OrsCalculator />}
        {activeTab === 'iv' && <IvDripCalculator />}
        {activeTab === 'fluid' && <MaintenanceFluidCalculator />}
      </div>

      {/* Clinical Disclaimer */}
      <div className="bg-surface2/60 border border-leaf/30 rounded-xl p-4 flex items-start gap-3 text-xs text-text3 font-body">
        <Info size={16} className="text-forest shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <p className="font-semibold text-text2">
            {t('calculators.disclaimerTitle', 'Clinical Decision-Support Advisory')}
          </p>
          <p className="mt-0.5">
            {t(
              'calculators.disclaimerBody',
              'These calculators provide arithmetic reference guidance based on WHO and standard paediatric protocols. All calculated values must be verified by a qualified clinician against local institutional guidelines and patient clinical status before administration.',
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

// ── 1. Dose by Weight Calculator Component ──────────────────────────────────

function DoseCalculator() {
  const [selectedPresetId, setSelectedPresetId] = useState('paracetamol')
  const [weightKg, setWeightKg] = useState('12')
  const [mgPerKg, setMgPerKg] = useState('15')
  const [maxMgPerDose, setMaxMgPerDose] = useState('1000')
  const [maxMgPerDay, setMaxMgPerDay] = useState('4000')
  const [maxMgPerKgPerDay, setMaxMgPerKgPerDay] = useState('60')
  const [selectedConcentrationIdx, setSelectedConcentrationIdx] = useState('0')
  const [frequency, setFrequency] = useState('Q6H')
  const [duration, setDuration] = useState('UNTIL_RESOLVED')
  const [showSteps, setShowSteps] = useState(false)

  const selectedPreset = useMemo(
    () => PEDIATRIC_DRUG_PRESETS.find((p) => p.id === selectedPresetId) || null,
    [selectedPresetId],
  )

  function handlePresetChange(presetId) {
    setSelectedPresetId(presetId)
    const preset = PEDIATRIC_DRUG_PRESETS.find((p) => p.id === presetId)
    if (preset) {
      setMgPerKg(preset.mgPerKg.toString())
      setMaxMgPerDose(preset.maxMgPerDose.toString())
      setMaxMgPerDay(preset.maxMgPerDay ? preset.maxMgPerDay.toString() : '')
      setMaxMgPerKgPerDay(preset.maxMgPerKgPerDay ? preset.maxMgPerKgPerDay.toString() : '')
      setFrequency(preset.defaultFrequency)
      setDuration(preset.defaultDuration)
      setSelectedConcentrationIdx('0')
    }
  }

  const calculationResult = useMemo(() => {
    const wt = parseFloat(weightKg)
    const doseMgKg = parseFloat(mgPerKg)
    const maxDose = parseFloat(maxMgPerDose)
    const maxDay = parseFloat(maxMgPerDay) || undefined
    const maxKgDay = parseFloat(maxMgPerKgPerDay) || undefined

    if (isNaN(wt) || wt <= 0 || isNaN(doseMgKg) || isNaN(maxDose) || maxDose <= 0) {
      return { error: 'Please enter valid positive numbers for weight, dose, and maximum cap.' }
    }

    let concMgPerMl
    if (selectedPreset && selectedPreset.concentrationOptions[parseInt(selectedConcentrationIdx, 10)]) {
      concMgPerMl = selectedPreset.concentrationOptions[parseInt(selectedConcentrationIdx, 10)].mgPerMl
    }

    try {
      return {
        data: calculateWeightBasedDose({
          weightKg: wt,
          mgPerKg: doseMgKg,
          maxMgPerDose: maxDose,
          maxMgPerDay: maxDay,
          maxMgPerKgPerDay: maxKgDay,
          frequency,
          concentrationMgPerMl: concMgPerMl,
        }),
      }
    } catch (err) {
      return { error: err.message || 'Calculation error' }
    }
  }, [weightKg, mgPerKg, maxMgPerDose, maxMgPerDay, maxMgPerKgPerDay, frequency, selectedPreset, selectedConcentrationIdx])

  const res = calculationResult.data

  return (
    <div className="bg-surface rounded-xl border border-leaf/40 p-5 shadow-card space-y-6">
      <div className="border-b border-leaf/30 pb-3">
        <h2 className="text-base font-display font-semibold text-text flex items-center gap-2">
          <Pill size={18} className="text-forest" aria-hidden="true" />
          Paediatric Dose by Weight
        </h2>
        <p className="text-xs text-text2 mt-0.5">
          Select a standard essential paediatric drug preset or customize dosing parameters.
        </p>
      </div>

      {/* Input Form Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Preset Selector */}
        <div className="sm:col-span-2">
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Drug / Protocol Preset
          </label>
          <select
            value={selectedPresetId}
            onChange={(e) => handlePresetChange(e.target.value)}
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-medium focus:outline-none focus:ring-2 focus:ring-forest/30"
          >
            {PEDIATRIC_DRUG_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.drugName} ({p.indication})
              </option>
            ))}
            <option value="custom">Custom Protocol / Other Drug</option>
          </select>
        </div>

        {/* Patient Weight */}
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Patient Weight (kg) *
          </label>
          <input
            type="number"
            min="1.0"
            max="100.0"
            step="0.1"
            value={weightKg}
            onChange={(e) => setWeightKg(e.target.value)}
            placeholder="e.g. 12"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        {/* Single Dose Rate (mg/kg) */}
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Dose Rate (mg / kg / dose) *
          </label>
          <input
            type="number"
            min="0"
            step="0.1"
            value={mgPerKg}
            onChange={(e) => setMgPerKg(e.target.value)}
            placeholder="e.g. 15"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        {/* Max Single Dose Cap */}
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Max Single Dose Cap (mg) *
          </label>
          <input
            type="number"
            min="1"
            value={maxMgPerDose}
            onChange={(e) => setMaxMgPerDose(e.target.value)}
            placeholder="e.g. 1000"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        {/* Concentration Selector */}
        {selectedPreset && selectedPreset.concentrationOptions.length > 0 && (
          <div>
            <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
              Liquid Formulation / Concentration
            </label>
            <select
              value={selectedConcentrationIdx}
              onChange={(e) => setSelectedConcentrationIdx(e.target.value)}
              className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-medium focus:outline-none focus:ring-2 focus:ring-forest/30"
            >
              {selectedPreset.concentrationOptions.map((c, idx) => (
                <option key={idx} value={idx.toString()}>
                  {c.label} ({c.mgPerMl} mg/mL)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Frequency Dropdown */}
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Dosing Frequency
          </label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-medium focus:outline-none focus:ring-2 focus:ring-forest/30"
          >
            {Object.values(FREQUENCY_METADATA).map((f) => (
              <option key={f.code} value={f.code}>
                {f.label} — {f.dosesPerDay}x/day
              </option>
            ))}
          </select>
        </div>

        {/* Duration Dropdown */}
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Treatment Duration
          </label>
          <select
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-medium focus:outline-none focus:ring-2 focus:ring-forest/30"
          >
            {Object.values(DURATION_METADATA).map((d) => (
              <option key={d.code} value={d.code}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error View */}
      {calculationResult.error && (
        <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3.5 flex items-center gap-2.5 text-xs text-urgent-ink">
          <AlertTriangle size={16} className="shrink-0 text-urgent" aria-hidden="true" />
          <span>{calculationResult.error}</span>
        </div>
      )}

      {/* Results View */}
      {res && !calculationResult.error && (
        <div className="space-y-4 pt-2 border-t border-leaf/30">
          {/* Main Output Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Single Dose Mg */}
            <div className="bg-forest/5 border border-forest/20 rounded-xl p-4 flex flex-col justify-between">
              <span className="text-xs font-mono font-semibold uppercase text-forest tracking-wider">
                Calculated Dose (Per Administration)
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-text font-mono">
                  {res.doseMg}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">mg</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                {res.frequency ? `${res.frequency} (${FREQUENCY_METADATA[res.frequency]?.description})` : 'Single dose'}
              </p>
            </div>

            {/* Liquid Volume (mL) */}
            {res.volumeMl !== null && (
              <div className="bg-surface2 border border-leaf/40 rounded-xl p-4 flex flex-col justify-between">
                <span className="text-xs font-mono font-semibold uppercase text-text2 tracking-wider">
                  Liquid Volume (Per Dose)
                </span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-display font-bold text-forest font-mono">
                    {res.volumeMl}
                  </span>
                  <span className="text-sm font-semibold text-text2 font-mono">mL</span>
                </div>
                <p className="text-xs text-text3 font-mono mt-1">
                  @ {res.concentrationMgPerMl} mg/mL concentration
                </p>
              </div>
            )}
          </div>

          {/* Warnings & Badges */}
          {(res.isCappedSingleDose || res.isCappedDailyTotal || res.warning) && (
            <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3 space-y-1.5 text-xs text-urgent-ink">
              {res.isCappedSingleDose && (
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertTriangle size={14} className="text-urgent shrink-0" aria-hidden="true" />
                  <span>Single dose capped at maximum adult ceiling ({res.maxMgPerDose} mg).</span>
                </div>
              )}
              {res.warning && (
                <div className="flex items-center gap-1.5 text-text2">
                  <Info size={14} className="text-urgent shrink-0" aria-hidden="true" />
                  <span>{res.warning}</span>
                </div>
              )}
            </div>
          )}

          {/* Preset Clinical Citation & Notes */}
          {selectedPreset && (
            <div className="bg-surface2/40 border border-leaf/30 rounded-lg p-3 text-xs space-y-1">
              <p className="text-text font-medium">{selectedPreset.notes}</p>
              <p className="text-text3 font-mono text-[11px]">Source: {selectedPreset.citation}</p>
            </div>
          )}

          {/* Worked Steps Accordion */}
          <div className="border border-leaf/30 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowSteps((v) => !v)}
              className="w-full bg-surface2 px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-text hover:bg-leaf/20 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-forest" aria-hidden="true" />
                Step-by-Step Arithmetic Breakdown
              </span>
              {showSteps ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showSteps && (
              <div className="p-4 bg-surface space-y-1.5 text-xs font-mono text-text2 border-t border-leaf/30">
                {res.steps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-text3 shrink-0">[{idx + 1}]</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 2. WHO ORS & Rehydration Calculator Component ───────────────────────────

function OrsCalculator() {
  const [plan, setPlan] = useState('PLAN_B')
  const [weightKg, setWeightKg] = useState('8')
  const [ageMonths, setAgeMonths] = useState('10')
  const [showSteps, setShowSteps] = useState(false)

  const result = useMemo(() => {
    const wt = parseFloat(weightKg)
    const age = parseFloat(ageMonths) || undefined
    if (isNaN(wt) || wt <= 0) {
      return { error: 'Please enter a valid positive patient weight.' }
    }
    try {
      return {
        data: calculateOrsVolume({
          weightKg: wt,
          plan,
          ageMonths: age,
        }),
      }
    } catch (err) {
      return { error: err.message || 'Calculation error' }
    }
  }, [weightKg, plan, ageMonths])

  const res = result.data

  return (
    <div className="bg-surface rounded-xl border border-leaf/40 p-5 shadow-card space-y-6">
      <div className="border-b border-leaf/30 pb-3">
        <h2 className="text-base font-display font-semibold text-text flex items-center gap-2">
          <Droplet size={18} className="text-forest" aria-hidden="true" />
          WHO Diarrhoea & Rehydration Protocol
        </h2>
        <p className="text-xs text-text2 mt-0.5">
          Standardized WHO oral and intravenous rehydration schedules for acute diarrhoea and dehydration.
        </p>
      </div>

      {/* Plan Selection Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          {
            id: 'PLAN_A',
            title: 'Plan A: No Dehydration',
            desc: 'Home fluids + 10 mL/kg ORS per loose stool',
            color: 'border-routine/40 text-routine-ink',
          },
          {
            id: 'PLAN_B',
            title: 'Plan B: Some Dehydration',
            desc: '75 mL/kg ORS orally over 4 hours',
            color: 'border-urgent/40 text-urgent-ink',
          },
          {
            id: 'PLAN_C',
            title: 'Plan C: Severe Dehydration',
            desc: '100 mL/kg IV Ringer’s Lactate resuscitation',
            color: 'border-emergency/40 text-emergency-ink',
          },
        ].map((p) => {
          const isSelected = plan === p.id
          return (
            <button
              key={p.id}
              onClick={() => setPlan(p.id)}
              className={`text-left p-3.5 rounded-xl border-2 transition-all cursor-pointer ${
                isSelected
                  ? `${p.color} bg-forest/5 border-forest font-semibold shadow-sm`
                  : 'border-leaf/30 bg-surface2 hover:bg-leaf/20 text-text2'
              }`}
            >
              <p className="text-xs sm:text-sm font-semibold">{p.title}</p>
              <p className="text-[11px] text-text3 mt-1 font-body leading-relaxed">{p.desc}</p>
            </button>
          )
        })}
      </div>

      {/* Parameters Input */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Patient Weight (kg) *
          </label>
          <input
            type="number"
            min="1.0"
            max="100.0"
            step="0.1"
            value={weightKg}
            onChange={(e) => setWeightKg(e.target.value)}
            placeholder="e.g. 8"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Patient Age (months, for Plan C timing)
          </label>
          <input
            type="number"
            min="0"
            max="120"
            value={ageMonths}
            onChange={(e) => setAgeMonths(e.target.value)}
            placeholder="e.g. 10"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>
      </div>

      {/* Error View */}
      {result.error && (
        <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3.5 flex items-center gap-2.5 text-xs text-urgent-ink">
          <AlertTriangle size={16} className="shrink-0 text-urgent" aria-hidden="true" />
          <span>{result.error}</span>
        </div>
      )}

      {/* Results View */}
      {res && !result.error && (
        <div className="space-y-4 pt-2 border-t border-leaf/30">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-forest/5 border border-forest/20 rounded-xl p-4">
              <span className="text-xs font-mono font-semibold uppercase text-forest tracking-wider">
                {plan === 'PLAN_A' ? 'Target Per Stool Replacement' : 'Total Rehydration Target'}
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-text font-mono">
                  {res.totalVolumeMl}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">mL</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                Duration: {res.durationHours} hours ({res.rateMlPerHour} mL/hour)
              </p>
            </div>

            <div className="bg-surface2 border border-leaf/40 rounded-xl p-4 flex flex-col justify-between">
              <span className="text-xs font-mono font-semibold uppercase text-text2 tracking-wider">
                Clinical Reassessment Schedule
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-display font-bold text-text font-mono">
                  Every {res.reassessmentMinutes >= 60 ? `${res.reassessmentMinutes / 60} hr` : `${res.reassessmentMinutes} min`}
                </span>
              </div>
              <p className="text-xs text-text3 font-body mt-1">
                Check skin pinch, radial pulse, and mental status
              </p>
            </div>
          </div>

          {/* Action Guidance Card */}
          <div className="bg-surface2/60 border border-leaf/40 rounded-xl p-4 space-y-2">
            <p className="text-xs font-semibold text-text uppercase tracking-wider font-mono flex items-center gap-1.5">
              <Info size={14} className="text-forest" />
              Treatment Guidelines ({res.planName})
            </p>
            <p className="text-xs text-text2 font-body leading-relaxed">{res.guidance}</p>
          </div>

          {/* Step-by-step math */}
          <div className="border border-leaf/30 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowSteps((v) => !v)}
              className="w-full bg-surface2 px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-text hover:bg-leaf/20 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-forest" aria-hidden="true" />
                Calculation Protocol Details
              </span>
              {showSteps ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showSteps && (
              <div className="p-4 bg-surface space-y-1.5 text-xs font-mono text-text2 border-t border-leaf/30">
                {res.steps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-text3 shrink-0">[{idx + 1}]</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 3. IV Drip Rate Calculator Component ────────────────────────────────────

function IvDripCalculator() {
  const [volumeMl, setVolumeMl] = useState('500')
  const [durationHours, setDurationHours] = useState('4')
  const [durationMinutes, setDurationMinutes] = useState('0')
  const [dropFactor, setDropFactor] = useState('20')
  const [showSteps, setShowSteps] = useState(false)

  const result = useMemo(() => {
    const vol = parseFloat(volumeMl)
    const hrs = parseFloat(durationHours) || 0
    const mins = parseFloat(durationMinutes) || 0
    const df = parseInt(dropFactor, 10)

    if (isNaN(vol) || vol <= 0 || (hrs === 0 && mins === 0)) {
      return { error: 'Please enter valid volume and duration values greater than zero.' }
    }

    try {
      return {
        data: calculateIvDripRate({
          volumeMl: vol,
          durationHours: hrs,
          durationMinutes: mins,
          dropFactor: df,
        }),
      }
    } catch (err) {
      return { error: err.message || 'Calculation error' }
    }
  }, [volumeMl, durationHours, durationMinutes, dropFactor])

  const res = result.data

  return (
    <div className="bg-surface rounded-xl border border-leaf/40 p-5 shadow-card space-y-6">
      <div className="border-b border-leaf/30 pb-3">
        <h2 className="text-base font-display font-semibold text-text flex items-center gap-2">
          <Activity size={18} className="text-forest" aria-hidden="true" />
          IV Drip & Infusion Rate Calculator
        </h2>
        <p className="text-xs text-text2 mt-0.5">
          Calculates gravity drops per minute (gtt/min) and continuous volumetric infusion rates (mL/hr).
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Total Infusion Volume (mL) *
          </label>
          <input
            type="number"
            min="1"
            step="10"
            value={volumeMl}
            onChange={(e) => setVolumeMl(e.target.value)}
            placeholder="e.g. 500"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Duration (Hours)
          </label>
          <input
            type="number"
            min="0"
            step="0.5"
            value={durationHours}
            onChange={(e) => setDurationHours(e.target.value)}
            placeholder="e.g. 4"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Drop Factor (gtt / mL) *
          </label>
          <select
            value={dropFactor}
            onChange={(e) => setDropFactor(e.target.value)}
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-medium focus:outline-none focus:ring-2 focus:ring-forest/30"
          >
            <option value="20">20 gtt/mL (Standard Macrodrip — Adult / General)</option>
            <option value="15">15 gtt/mL (Macrodrip — Dense fluids)</option>
            <option value="10">10 gtt/mL (Macrodrip — Blood giving set)</option>
            <option value="60">60 gtt/mL (Microdrip — Paediatric set)</option>
          </select>
        </div>
      </div>

      {result.error && (
        <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3.5 flex items-center gap-2.5 text-xs text-urgent-ink">
          <AlertTriangle size={16} className="shrink-0 text-urgent" aria-hidden="true" />
          <span>{result.error}</span>
        </div>
      )}

      {res && !result.error && (
        <div className="space-y-4 pt-2 border-t border-leaf/30">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-forest/5 border border-forest/20 rounded-xl p-4">
              <span className="text-xs font-mono font-semibold uppercase text-forest tracking-wider">
                Gravity Drip Rate
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-4xl font-display font-bold text-text font-mono">
                  {res.dripRateGttPerMin}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">drops / min (gtt/min)</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                Count ~{Math.round(res.dripRateGttPerMin / 4)} drops every 15 seconds
              </p>
            </div>

            <div className="bg-surface2 border border-leaf/40 rounded-xl p-4 flex flex-col justify-between">
              <span className="text-xs font-mono font-semibold uppercase text-text2 tracking-wider">
                Volumetric Pump Rate
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-forest font-mono">
                  {res.infusionRateMlPerHour}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">mL / hour</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                Total duration: {res.durationHours} hr ({res.durationMinutes} min)
              </p>
            </div>
          </div>

          <div className="border border-leaf/30 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowSteps((v) => !v)}
              className="w-full bg-surface2 px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-text hover:bg-leaf/20 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-forest" aria-hidden="true" />
                Calculation Breakdown
              </span>
              {showSteps ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showSteps && (
              <div className="p-4 bg-surface space-y-1.5 text-xs font-mono text-text2 border-t border-leaf/30">
                {res.steps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-text3 shrink-0">[{idx + 1}]</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 4. Holliday-Segar Maintenance Fluid Calculator Component ────────────────

function MaintenanceFluidCalculator() {
  const [weightKg, setWeightKg] = useState('15')
  const [ageYears, setAgeYears] = useState('4')
  const [showSteps, setShowSteps] = useState(false)

  const result = useMemo(() => {
    const wt = parseFloat(weightKg)
    const age = parseFloat(ageYears) || undefined
    if (isNaN(wt) || wt <= 0) {
      return { error: 'Please enter a valid positive patient weight.' }
    }
    try {
      return {
        data: calculateMaintenanceFluid(wt, age),
      }
    } catch (err) {
      return { error: err.message || 'Calculation error' }
    }
  }, [weightKg, ageYears])

  const res = result.data

  return (
    <div className="bg-surface rounded-xl border border-leaf/40 p-5 shadow-card space-y-6">
      <div className="border-b border-leaf/30 pb-3">
        <h2 className="text-base font-display font-semibold text-text flex items-center gap-2">
          <Calculator size={18} className="text-forest" aria-hidden="true" />
          Holliday-Segar 4-2-1 Maintenance Fluid
        </h2>
        <p className="text-xs text-text2 mt-0.5">
          Calculates 24-hour baseline maintenance fluid volume and hourly infusion rates based on the Holliday-Segar formula.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Patient Weight (kg) *
          </label>
          <input
            type="number"
            min="1.0"
            max="100.0"
            step="0.1"
            value={weightKg}
            onChange={(e) => setWeightKg(e.target.value)}
            placeholder="e.g. 15"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-text2 uppercase tracking-wider mb-1">
            Patient Age (years)
          </label>
          <input
            type="number"
            min="0"
            max="18"
            value={ageYears}
            onChange={(e) => setAgeYears(e.target.value)}
            placeholder="e.g. 4"
            className="w-full bg-surface2 border border-leaf/40 rounded-lg px-3 py-2 text-sm text-text font-mono focus:outline-none focus:ring-2 focus:ring-forest/30"
          />
        </div>
      </div>

      {result.error && (
        <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3.5 flex items-center gap-2.5 text-xs text-urgent-ink">
          <AlertTriangle size={16} className="shrink-0 text-urgent" aria-hidden="true" />
          <span>{result.error}</span>
        </div>
      )}

      {res && !result.error && (
        <div className="space-y-4 pt-2 border-t border-leaf/30">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-forest/5 border border-forest/20 rounded-xl p-4">
              <span className="text-xs font-mono font-semibold uppercase text-forest tracking-wider">
                24-Hour Maintenance Fluid
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-text font-mono">
                  {res.totalDailyVolumeMl}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">mL / 24 hours</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                Based on {res.weightKg} kg patient weight
              </p>
            </div>

            <div className="bg-surface2 border border-leaf/40 rounded-xl p-4 flex flex-col justify-between">
              <span className="text-xs font-mono font-semibold uppercase text-text2 tracking-wider">
                Continuous Hourly Rate
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-display font-bold text-forest font-mono">
                  {res.hourlyRateMlPerHour}
                </span>
                <span className="text-sm font-semibold text-text2 font-mono">mL / hour</span>
              </div>
              <p className="text-xs text-text3 font-mono mt-1">
                4-2-1 Rule: 4 mL/kg (1-10kg) + 2 mL/kg (11-20kg) + 1 mL/kg (&gt;20kg)
              </p>
            </div>
          </div>

          {/* Adult Advisory */}
          {res.isAdultAdvisory && (
            <div className="bg-urgent/10 border border-urgent/30 rounded-lg p-3.5 flex items-start gap-2 text-xs text-urgent-ink">
              <Info size={16} className="text-urgent shrink-0 mt-0.5" aria-hidden="true" />
              <span>{res.advisory}</span>
            </div>
          )}

          {/* 3-Tier Breakdown Table */}
          <div className="bg-surface2/60 border border-leaf/40 rounded-xl p-4">
            <p className="text-xs font-semibold text-text uppercase tracking-wider font-mono mb-3">
              Holliday-Segar Tier Breakdown
            </p>
            <div className="space-y-2">
              {res.breakdown.map((tier, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs bg-surface p-2.5 rounded-lg border border-leaf/20"
                >
                  <span className="font-medium text-text">{tier.segment} ({tier.weightKg} kg)</span>
                  <span className="font-mono text-text2">
                    {tier.dailyMl} mL/day ({tier.hourlyMl} mL/hr)
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Step-by-step */}
          <div className="border border-leaf/30 rounded-lg overflow-hidden">
            <button
              onClick={() => setShowSteps((v) => !v)}
              className="w-full bg-surface2 px-4 py-2.5 flex items-center justify-between text-xs font-semibold text-text hover:bg-leaf/20 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-forest" aria-hidden="true" />
                Calculation Steps
              </span>
              {showSteps ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showSteps && (
              <div className="p-4 bg-surface space-y-1.5 text-xs font-mono text-text2 border-t border-leaf/30">
                {res.steps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-text3 shrink-0">[{idx + 1}]</span>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
