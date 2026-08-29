import { lazy, Suspense, useState } from 'react'
import NavBar from '../components/NavBar'
import TeamMetrics from '../components/TeamMetrics'
import TabLoadingFallback from '../components/TabLoadingFallback'

const OutbreakSignals = lazy(() => import('../components/OutbreakSignals'))
const ProtocolAssistant = lazy(() => import('../components/ProtocolAssistant'))
const SupervisorManagement = lazy(() => import('../components/supervisor/SupervisorManagement'))
const ClinicalCalculators = lazy(() => import('../components/ClinicalCalculators'))

const TABS = [
  { id: 'team',        label: 'Team Metrics' },
  { id: 'outbreak',    label: 'Outbreak Signals' },
  { id: 'calculators', label: 'Calculators' },
  { id: 'protocol',    label: 'Protocol Assistant' },
  { id: 'management',  label: 'Management' },
]

export default function SupervisorPanel() {
  const [activeTab, setActiveTab] = useState('team')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Suspense fallback={<TabLoadingFallback />}>
          {activeTab === 'team'        && <TeamMetrics />}
          {activeTab === 'outbreak'    && <OutbreakSignals />}
          {activeTab === 'calculators' && <ClinicalCalculators />}
          {activeTab === 'protocol'    && <ProtocolAssistant canCurate />}
          {activeTab === 'management'  && <SupervisorManagement />}
        </Suspense>
      </main>
    </div>
  )
}
