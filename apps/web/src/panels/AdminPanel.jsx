import { lazy, Suspense, useState } from 'react'
import NavBar from '../components/NavBar'
import AnalyticsDashboard from '../components/AnalyticsDashboard'
import TabLoadingFallback from '../components/TabLoadingFallback'

const OutbreakSignals = lazy(() => import('../components/OutbreakSignals'))
const ProtocolAssistant = lazy(() => import('../components/ProtocolAssistant'))
const AdminUsers = lazy(() => import('../components/admin/AdminUsers'))
const AdminFacilities = lazy(() => import('../components/admin/AdminFacilities'))

const TABS = [
  { id: 'analytics',  label: 'Analytics' },
  { id: 'outbreak',   label: 'Outbreak Signals' },
  { id: 'protocol',   label: 'Protocol Assistant' },
  { id: 'users',      label: 'Staff Management' },
  { id: 'facilities', label: 'My PHC' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('analytics')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Suspense fallback={<TabLoadingFallback />}>
          {activeTab === 'analytics'  && <AnalyticsDashboard />}
          {activeTab === 'outbreak'   && <OutbreakSignals />}
          {activeTab === 'protocol'   && <ProtocolAssistant canCurate />}
          {activeTab === 'users'      && <AdminUsers />}
          {activeTab === 'facilities' && <AdminFacilities />}
        </Suspense>
      </main>
    </div>
  )
}
