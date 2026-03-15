import { useState } from 'react'
import NavBar from '../components/NavBar'
import AdminUsers from '../components/admin/AdminUsers'
import AdminFacilities from '../components/admin/AdminFacilities'
import AdminStats from '../components/admin/AdminStats'
import AnalyticsDashboard from '../components/AnalyticsDashboard'

const TABS = [
  { id: 'analytics',  label: 'Analytics' },
  { id: 'users',      label: 'Users' },
  { id: 'facilities', label: 'Facilities' },
  { id: 'system',     label: 'System' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('analytics')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'analytics'  && <AnalyticsDashboard />}
        {activeTab === 'users'      && <AdminUsers />}
        {activeTab === 'facilities' && <AdminFacilities />}
        {activeTab === 'system'     && <AdminStats />}
      </main>
    </div>
  )
}
