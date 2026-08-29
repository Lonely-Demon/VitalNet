import { useState, useEffect } from 'react'
import { adminListFacilities, updateFacilityCapacity } from '../../lib/api'

const CAPACITY_OPTIONS = ['available', 'limited', 'full']

export default function AdminFacilities() {
  const [facilities, setFacilities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => { loadFacilities() }, [])

  async function loadFacilities() {
    setLoading(true)
    setError(null)
    try {
      setFacilities(await adminListFacilities())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleCapacityChange(id, capacityStatus) {
    setFacilities(fs => fs.map(f => f.id === id ? { ...f, capacity_status: capacityStatus } : f))
    try {
      await updateFacilityCapacity(id, capacityStatus)
    } catch (e) {
      alert(e.message)
      await loadFacilities()
    }
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading facility info...</div>
  if (error)   return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text font-display font-bold">Assigned Facility Details</h2>
        <span className="text-xs text-text3 font-mono bg-surface2 px-2.5 py-1 rounded-pill">
          Read-Only Operational Scope
        </span>
      </div>

      <div className="bg-surface border border-leaf/40 rounded-lg overflow-hidden shadow-card">
        <table className="w-full text-sm">
          <thead className="bg-surface2 border-b border-leaf/40">
            <tr>
              {['Facility Name', 'Type', 'District', 'Phone', 'Capacity Status', 'Status'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-mono font-semibold text-text3 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-leaf/20">
            {facilities.map(f => (
              <tr key={f.id} className={f.is_active ? '' : 'opacity-50'}>
                <td className="px-4 py-3 font-medium text-text">{f.name}</td>
                <td className="px-4 py-3 text-text2 font-mono">{f.type}</td>
                <td className="px-4 py-3 text-text2">{f.district || '—'}</td>
                <td className="px-4 py-3 text-text3 font-mono">{f.phone || '—'}</td>
                <td className="px-4 py-3">
                  <select
                    value={f.capacity_status || 'available'}
                    onChange={(e) => handleCapacityChange(f.id, e.target.value)}
                    aria-label={`${f.name} capacity`}
                    className="text-xs border border-surface3 rounded-md px-2 py-1 bg-surface capitalize font-mono"
                  >
                    {CAPACITY_OPTIONS.map(c => <option key={c} value={c} className="capitalize">{c}</option>)}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-pill font-medium font-mono ${
                    f.is_active ? 'bg-routine/10 text-routine-ink' : 'bg-surface3 text-text3'
                  }`}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
