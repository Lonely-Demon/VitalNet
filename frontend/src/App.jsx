import { useState } from 'react'
import IntakeForm from './pages/IntakeForm'
import Dashboard from './pages/Dashboard'

export default function App() {
  const [page, setPage] = useState('form')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-blue-700 text-white px-4 py-3 flex gap-4 items-center">
        <span className="font-bold text-lg tracking-tight">VitalNet</span>
        <button
          onClick={() => setPage('form')}
          className={`px-3 py-1 rounded text-sm cursor-pointer ${page === 'form' ? 'bg-blue-900' : 'hover:bg-blue-600'}`}
        >
          ASHA Intake
        </button>
        <button
          onClick={() => setPage('dashboard')}
          className={`px-3 py-1 rounded text-sm cursor-pointer ${page === 'dashboard' ? 'bg-blue-900' : 'hover:bg-blue-600'}`}
        >
          Doctor Dashboard
        </button>
      </nav>

      {page === 'form' ? <IntakeForm /> : <Dashboard />}
    </div>
  )
}
