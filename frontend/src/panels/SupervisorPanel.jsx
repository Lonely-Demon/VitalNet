import { useState } from 'react'
import NavBar from '../components/NavBar'
import TeamMetrics from '../components/TeamMetrics'
import OutbreakSignals from '../components/OutbreakSignals'

const TABS = [
  { id: 'team',     label: 'Team Metrics' },
  { id: 'outbreak', label: 'Outbreak Signals' },
]

export default function SupervisorPanel() {
  const [activeTab, setActiveTab] = useState('team')

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'team'     && <TeamMetrics />}
        {activeTab === 'outbreak' && <OutbreakSignals />}
      </main>
    </div>
  )
}
