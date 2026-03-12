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

  if (loading) return <div className="text-center py-16 text-slate-400 text-sm">Loading facilities...</div>
  if (error)   return <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-slate-800">Facilities <span className="text-slate-400 font-normal">({facilities.length})</span></h2>
        <button
          onClick={() => setShowCreateForm(v => !v)}
          className="text-sm px-3 py-1.5 bg-slate-800 text-white rounded-md hover:bg-slate-700 transition-colors"
        >
          {showCreateForm ? 'Cancel' : '+ Add Facility'}
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreate} className="bg-white border border-slate-200 rounded-lg p-5 mb-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">New Facility</h3>
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
                <label className="block text-xs text-slate-500 mb-1">{f.label}</label>
                <input
                  type={f.type}
                  required={f.required}
                  value={formData[f.key]}
                  onChange={e => setFormData(d => ({ ...d, [f.key]: e.target.value }))}
                  className="w-full border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-400"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-slate-500 mb-1">Type</label>
              <select
                value={formData.type}
                onChange={e => setFormData(d => ({ ...d, type: e.target.value }))}
                className="w-full border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          {formError && <p className="text-red-600 text-xs mt-2">{formError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="mt-3 text-sm px-4 py-1.5 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {creating ? 'Creating...' : 'Add Facility'}
          </button>
        </form>
      )}

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {['Name', 'Type', 'District', 'Phone', 'Status', 'Actions'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {facilities.map(f => (
              <tr key={f.id} className={f.is_active ? '' : 'opacity-50'}>
                <td className="px-4 py-3 font-medium text-slate-800">{f.name}</td>
                <td className="px-4 py-3 text-slate-500">{f.type}</td>
                <td className="px-4 py-3 text-slate-500">{f.district || '—'}</td>
                <td className="px-4 py-3 text-slate-400">{f.phone || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    f.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'
                  }`}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleToggle(f.id)}
                    className={`text-xs font-medium ${
                      f.is_active
                        ? 'text-red-500 hover:text-red-700'
                        : 'text-emerald-600 hover:text-emerald-800'
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
