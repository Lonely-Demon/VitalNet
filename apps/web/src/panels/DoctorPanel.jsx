import { lazy, Suspense, useState } from 'react'
import NavBar from '../components/NavBar'
import Dashboard from '../pages/Dashboard'
import TabLoadingFallback from '../components/TabLoadingFallback'
import { PushPrompt } from '../components/PushPrompt'

const ReferralsPanel = lazy(() => import('../components/ReferralsPanel'))
const OutbreakSignals = lazy(() => import('../components/OutbreakSignals'))
const ProtocolAssistant = lazy(() => import('../components/ProtocolAssistant'))

const TABS = [
  { id: 'pending',   label: 'Pending Review' },
  { id: 'all',       label: 'All Cases' },
  { id: 'referrals', label: 'Referrals' },
  { id: 'outbreak',  label: 'Outbreak Signals' },
  { id: 'protocol',  label: 'Protocol Assistant' },
]

export default function DoctorPanel() {
  const [activeTab, setActiveTab] = useState('pending')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <Suspense fallback={<TabLoadingFallback />}>
        {activeTab === 'referrals' ? (
          <div className="max-w-2xl mx-auto p-4 mt-6">
            <ReferralsPanel />
          </div>
        ) : activeTab === 'outbreak' ? (
          <div className="max-w-2xl mx-auto p-4 mt-6">
            <OutbreakSignals />
          </div>
        ) : activeTab === 'protocol' ? (
          <div className="max-w-2xl mx-auto p-4 mt-6">
            <ProtocolAssistant canCurate />
          </div>
        ) : (
          // Pass activeTab to Dashboard so it can filter:
          // - 'pending': reviewed_at IS NULL (unreviewed only)
          // - 'all':     no filter
          <Dashboard filter={activeTab} />
        )}
      </Suspense>
      <PushPrompt />
    </div>
  )
}
