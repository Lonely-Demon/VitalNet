import { lazy, Suspense, useState } from 'react'
import NavBar from '../components/NavBar'

// ROOT-PERF-001: tab content is lazy loaded to keep initial admin shell light.
const AdminUsers = lazy(() => import('../components/admin/AdminUsers'))
const AdminFacilities = lazy(() => import('../components/admin/AdminFacilities'))
const AdminStats = lazy(() => import('../components/admin/AdminStats'))
const AnalyticsDashboard = lazy(() => import('../components/AnalyticsDashboard'))

const TABS = [
  { id: 'analytics',  label: 'Analytics' },
  { id: 'users',      label: 'Users' },
  { id: 'facilities', label: 'Facilities' },
  { id: 'system',     label: 'System' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('analytics')

  const renderTab = () => {
    if (activeTab === 'analytics') return <AnalyticsDashboard />
    if (activeTab === 'users') return <AdminUsers />
    if (activeTab === 'facilities') return <AdminFacilities />
    return <AdminStats />
  }

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Suspense fallback={<div className="text-sm text-text3">Loading admin view...</div>}>
          {renderTab()}
        </Suspense>
      </main>
    </div>
  )
}
