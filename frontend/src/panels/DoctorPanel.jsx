import { useState } from 'react'
import NavBar from '../components/NavBar'
import Dashboard from '../pages/Dashboard'
import ReferralsPanel from '../components/ReferralsPanel'
import { PushPrompt } from '../components/PushPrompt'

const TABS = [
  { id: 'pending',   label: 'Pending Review' },
  { id: 'all',       label: 'All Cases' },
  { id: 'referrals', label: 'Referrals' },
]

export default function DoctorPanel() {
  const [activeTab, setActiveTab] = useState('pending')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      {activeTab === 'referrals' ? (
        <div className="max-w-2xl mx-auto p-4 mt-6">
          <ReferralsPanel />
        </div>
      ) : (
        // Pass activeTab to Dashboard so it can filter:
        // - 'pending': reviewed_at IS NULL (unreviewed only)
        // - 'all':     no filter
        <Dashboard filter={activeTab} />
      )}
      <PushPrompt />
    </div>
  )
}
