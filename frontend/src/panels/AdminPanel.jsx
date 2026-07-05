import { useState } from 'react'
import NavBar from '../components/NavBar'
import AdminUsers from '../components/admin/AdminUsers'
import AdminFacilities from '../components/admin/AdminFacilities'
import AdminStats from '../components/admin/AdminStats'
import AdminAuditLog from '../components/admin/AdminAuditLog'
import AnalyticsDashboard from '../components/AnalyticsDashboard'
import OutbreakSignals from '../components/OutbreakSignals'

const TABS = [
  { id: 'analytics',  label: 'Analytics' },
  { id: 'outbreak',   label: 'Outbreak Signals' },
  { id: 'users',      label: 'Users' },
  { id: 'facilities', label: 'Facilities' },
  { id: 'system',     label: 'System' },
  { id: 'audit',      label: 'Audit Log' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('analytics')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'analytics'  && <AnalyticsDashboard />}
        {activeTab === 'outbreak'   && <OutbreakSignals />}
        {activeTab === 'users'      && <AdminUsers />}
        {activeTab === 'facilities' && <AdminFacilities />}
        {activeTab === 'system'     && <AdminStats />}
        {activeTab === 'audit'      && <AdminAuditLog />}
      </main>
    </div>
  )
}
