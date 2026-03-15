import { useState } from 'react'
import NavBar from '../components/NavBar'
import Dashboard from '../pages/Dashboard'

const TABS = [
  { id: 'pending', label: 'Pending Review' },
  { id: 'all',     label: 'All Cases' },
]

export default function DoctorPanel() {
  const [activeTab, setActiveTab] = useState('pending')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      {/*
        Pass activeTab to Dashboard so it can filter:
        - 'pending': reviewed_at IS NULL (unreviewed only)
        - 'all':     no filter
      */}
      <Dashboard filter={activeTab} />
    </div>
  )
}
