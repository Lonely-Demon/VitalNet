import { useState, useEffect } from 'react'
import { adminListFacilities, adminCreateFacility, adminToggleFacility } from '../../lib/api'

const TYPE_OPTIONS = ['PHC', 'CHC', 'District Hospital']

const EMPTY_FORM = {
  name: '', type: 'PHC', address: '', district: '',
  state: 'Tamil Nadu', pincode: '', phone: '',
}

export default function AdminFacilities() {
  const [facilities,     setFacilities]     = useState([])
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [formData,       setFormData]       = useState(EMPTY_FORM)
  const [formError,      setFormError]      = useState(null)
  const [creating,       setCreating]       = useState(false)

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

  async function handleCreate(e) {
    e.preventDefault()
    setCreating(true)
    setFormError(null)
    try {
      await adminCreateFacility(formData)
      setShowCreateForm(false)
      setFormData(EMPTY_FORM)
      await loadFacilities()
    } catch (e) {
      setFormError(e.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleToggle(id) {
    try {
      await adminToggleFacility(id)
      await loadFacilities()
    } catch (e) { alert(e.message) }
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading facilities...</div>
  if (error)   return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text font-display italic">Facilities <span className="text-text3 font-normal font-body">({facilities.length})</span></h2>
        <button
          onClick={() => setShowCreateForm(v => !v)}
          className="text-sm px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn transition-all"
        >
          {showCreateForm ? 'Cancel' : '+ Add Facility'}
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreate} className="bg-surface border border-leaf/40 rounded-lg p-5 mb-5 shadow-card">
          <h3 className="text-sm font-semibold text-text mb-4">New Facility</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Name *',    key: 'name',     type: 'text',   required: true },
              { label: 'District',  key: 'district',  type: 'text',   required: false },
              { label: 'Address',   key: 'address',   type: 'text',   required: false },
              { label: 'State',     key: 'state',     type: 'text',   required: false },
              { label: 'Pincode',   key: 'pincode',   type: 'text',   required: false },
              { label: 'Phone',     key: 'phone',     type: 'tel',    required: false },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-text3 mb-1 font-mono">{f.label}</label>
                <input
                  type={f.type}
                  required={f.required}
                  value={formData[f.key]}
                  onChange={e => setFormData(d => ({ ...d, [f.key]: e.target.value }))}
                  className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-text3 mb-1 font-mono">Type</label>
              <select
                value={formData.type}
                onChange={e => setFormData(d => ({ ...d, type: e.target.value }))}
                className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
              >
                {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          {formError && <p className="text-emergency text-xs mt-2">{formError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="mt-3 text-sm px-4 py-1.5 bg-routine text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all"
          >
            {creating ? 'Creating...' : 'Add Facility'}
          </button>
        </form>
      )}

      {/* Table */}
      <div className="bg-surface border border-leaf/40 rounded-lg overflow-hidden shadow-card">
        <table className="w-full text-sm">
          <thead className="bg-surface2 border-b border-leaf/40">
            <tr>
              {['Name', 'Type', 'District', 'Phone', 'Status', 'Actions'].map(h => (
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
                  <span className={`text-xs px-2 py-0.5 rounded-pill font-medium font-mono ${
                    f.is_active ? 'bg-routine/10 text-routine' : 'bg-surface3 text-text3'
                  }`}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggle(f.id)}
                    className={`text-xs font-medium ${
                      f.is_active
                        ? 'text-emergency hover:text-emergency/80'
                        : 'text-routine hover:text-forest'
                    }`}
                  >
                    {f.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
