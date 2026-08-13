import { useState } from 'react'
import NavBar from '../components/NavBar'
import AdminUsers from '../components/admin/AdminUsers'
import AdminFacilities from '../components/admin/AdminFacilities'
import AdminStats from '../components/admin/AdminStats'
import AdminAuditLog from '../components/admin/AdminAuditLog'
import AnalyticsDashboard from '../components/AnalyticsDashboard'
import OutbreakSignals from '../components/OutbreakSignals'
import ProtocolAssistant from '../components/ProtocolAssistant'

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
        {activeTab === 'analytics'  && <AnalyticsDashboard />}
        {activeTab === 'outbreak'   && <OutbreakSignals />}
        {activeTab === 'protocol'   && <ProtocolAssistant canCurate />}
        {activeTab === 'users'      && <AdminUsers />}
        {activeTab === 'facilities' && <AdminFacilities />}
      </main>
    </div>
  )
}
