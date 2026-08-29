import { useState, useEffect } from 'react'
import {
  supervisorListFacilities,
  supervisorCreateFacility,
  supervisorToggleFacility,
  supervisorListAdmins,
  supervisorCreateAdmin,
  supervisorUpdateAdmin,
  supervisorDeactivateAdmin,
  supervisorReactivateAdmin,
} from '@/api/supervisorManagement'

const TYPE_OPTIONS = ['PHC', 'CHC', 'District Hospital']
const EMPTY_FACILITY = {
  name: '', type: 'PHC', address: '', district: '', state: 'Tamil Nadu', pincode: '', phone: '',
}
const EMPTY_ADMIN = { email: '', password: '', full_name: '', facility_id: '' }

export default function SupervisorManagement() {
  const [subTab, setSubTab] = useState('phcs') // 'phcs' | 'admins'

  // PHC State
  const [facilities, setFacilities] = useState([])
  const [loadingFacilities, setLoadingFacilities] = useState(true)
  const [facError, setFacError] = useState(null)
  const [showCreateFac, setShowCreateFac] = useState(false)
  const [facForm, setFacForm] = useState(EMPTY_FACILITY)
  const [creatingFac, setCreatingFac] = useState(false)
  const [facFormError, setFacFormError] = useState(null)

  // Admin State
  const [admins, setAdmins] = useState([])
  const [loadingAdmins, setLoadingAdmins] = useState(true)
  const [adminError, setAdminError] = useState(null)
  const [showCreateAdmin, setShowCreateAdmin] = useState(false)
  const [adminForm, setAdminForm] = useState(EMPTY_ADMIN)
  const [creatingAdmin, setCreatingAdmin] = useState(false)
  const [adminFormError, setAdminFormError] = useState(null)
  const [editingAdminId, setEditingAdminId] = useState(null)
  const [editAdminData, setEditAdminData] = useState({})

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    loadFacilities()
    loadAdmins()
  }

  async function loadFacilities() {
    setLoadingFacilities(true)
    setFacError(null)
    try {
      const data = await supervisorListFacilities()
      setFacilities(data || [])
    } catch (e) {
      setFacError(e.message)
    } finally {
      setLoadingFacilities(false)
    }
  }

  async function loadAdmins() {
    setLoadingAdmins(true)
    setAdminError(null)
    try {
      const res = await supervisorListAdmins()
      setAdmins(res.data || [])
    } catch (e) {
      setAdminError(e.message)
    } finally {
      setLoadingAdmins(false)
    }
  }

  // PHC Actions
  async function handleCreateFacility(e) {
    e.preventDefault()
    setCreatingFac(true)
    setFacFormError(null)
    try {
      await supervisorCreateFacility(facForm)
      setShowCreateFac(false)
      setFacForm(EMPTY_FACILITY)
      await loadFacilities()
    } catch (e) {
      setFacFormError(e.message)
    } finally {
      setCreatingFac(false)
    }
  }

  async function handleToggleFacility(id) {
    setFacError(null)
    try {
      await supervisorToggleFacility(id)
      await loadFacilities()
    } catch (e) {
      setFacError(e.message)
    }
  }

  // Admin Actions
  async function handleCreateAdmin(e) {
    e.preventDefault()
    setCreatingAdmin(true)
    setAdminFormError(null)
    try {
      await supervisorCreateAdmin(adminForm)
      setShowCreateAdmin(false)
      setAdminForm(EMPTY_ADMIN)
      await loadAdmins()
    } catch (e) {
      setAdminFormError(e.message)
    } finally {
      setCreatingAdmin(false)
      setAdminForm(d => ({ ...d, password: '' })) // Clear password input immediately
    }
  }

  async function handleUpdateAdmin(id) {
    setAdminError(null)
    try {
      await supervisorUpdateAdmin(id, editAdminData)
      setEditingAdminId(null)
      setEditAdminData({})
      await loadAdmins()
    } catch (e) {
      setAdminError(e.message)
    }
  }

  async function handleDeactivateAdmin(id) {
    if (!confirm('Soft-deactivate this administrator?')) return
    setAdminError(null)
    try {
      await supervisorDeactivateAdmin(id)
      await loadAdmins()
    } catch (e) {
      setAdminError(e.message)
    }
  }

  async function handleReactivateAdmin(id) {
    setAdminError(null)
    try {
      await supervisorReactivateAdmin(id)
      await loadAdmins()
    } catch (e) {
      setAdminError(e.message)
    }
  }

  const activeFacilities = facilities.filter(f => f.is_active)

  return (
    <div className="space-y-6">
      {/* Capability Selector */}
      <div className="flex items-center gap-2 border-b border-leaf/40 pb-2">
        <button
          onClick={() => setSubTab('phcs')}
          className={`px-3 py-1.5 text-xs font-mono font-medium rounded-pill transition-colors ${
            subTab === 'phcs' ? 'bg-forest text-white' : 'bg-surface2 text-text2 hover:text-text'
          }`}
        >
          PHCs ({facilities.length})
        </button>
        <button
          onClick={() => setSubTab('admins')}
          className={`px-3 py-1.5 text-xs font-mono font-medium rounded-pill transition-colors ${
            subTab === 'admins' ? 'bg-forest text-white' : 'bg-surface2 text-text2 hover:text-text'
          }`}
        >
          PHC Administrators ({admins.length})
        </button>
      </div>

      {/* ── 1. PHCs Management Area ── */}
      {subTab === 'phcs' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text font-display">PHC Governance</h3>
            <button
              onClick={() => setShowCreateFac(v => !v)}
              className="text-xs px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn transition-all"
            >
              {showCreateFac ? 'Cancel' : '+ Create PHC'}
            </button>
          </div>

          {facError && (
            <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-2.5 text-emergency text-xs font-medium">
              {facError}
            </div>
          )}

          {showCreateFac && (
            <form onSubmit={handleCreateFacility} className="bg-surface border border-leaf/40 rounded-lg p-4 shadow-card">
              <h4 className="text-xs font-semibold text-text mb-3 font-mono">New Primary Health Centre</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {[
                  { label: 'Name *', key: 'name', type: 'text', required: true },
                  { label: 'District', key: 'district', type: 'text', required: false },
                  { label: 'Address', key: 'address', type: 'text', required: false },
                  { label: 'State', key: 'state', type: 'text', required: false },
                  { label: 'Pincode', key: 'pincode', type: 'text', required: false },
                  { label: 'Phone', key: 'phone', type: 'tel', required: false },
                ].map(f => (
                  <div key={f.key}>
                    <label htmlFor={`sup-fac-${f.key}`} className="block text-text3 mb-1 font-mono">{f.label}</label>
                    <input
                      id={`sup-fac-${f.key}`}
                      type={f.type}
                      required={f.required}
                      value={facForm[f.key]}
                      onChange={e => setFacForm(d => ({ ...d, [f.key]: e.target.value }))}
                      className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text focus:outline-none focus:ring-1 focus:ring-sage"
                    />
                  </div>
                ))}
                <div>
                  <label htmlFor="sup-fac-type" className="block text-text3 mb-1 font-mono">Type</label>
                  <select
                    id="sup-fac-type"
                    value={facForm.type}
                    onChange={e => setFacForm(d => ({ ...d, type: e.target.value }))}
                    className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text"
                  >
                    {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>
              {facFormError && <p className="text-emergency text-xs mt-2">{facFormError}</p>}
              <button
                type="submit"
                disabled={creatingFac}
                className="mt-3 text-xs px-4 py-1.5 bg-routine text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all font-mono"
              >
                {creatingFac ? 'Creating...' : 'Save PHC'}
              </button>
            </form>
          )}

          {loadingFacilities ? (
            <div className="text-center py-10 text-text3 text-xs">Loading PHCs...</div>
          ) : (
            <div className="bg-surface border border-leaf/40 rounded-lg overflow-hidden shadow-card">
              <table className="w-full text-xs">
                <tbody className="divide-y divide-leaf/20">
                  {facilities.map(f => (
                    <tr key={f.id} className={f.is_active ? '' : 'opacity-50'}>
                      <td className="px-4 py-2.5 font-medium text-text">{f.name}</td>
                      <td className="px-4 py-2.5 text-text2 font-mono">{f.type}</td>
                      <td className="px-4 py-2.5 text-text2">{f.district || '—'}</td>
                      <td className="px-4 py-2.5 text-text3 font-mono">{f.phone || '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded-pill font-mono ${
                          f.is_active ? 'bg-routine/10 text-routine-ink' : 'bg-surface3 text-text3'
                        }`}>
                          {f.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button
                          onClick={() => handleToggleFacility(f.id)}
                          className={`font-medium ${
                            f.is_active ? 'text-emergency hover:text-emergency/80' : 'text-routine hover:text-forest'
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
          )}
        </div>
      )}

      {/* ── 2. PHC Administrators Management Area ── */}
      {subTab === 'admins' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text font-display">PHC Administrator Accounts</h3>
            <button
              onClick={() => setShowCreateAdmin(v => !v)}
              className="text-xs px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn transition-all"
            >
              {showCreateAdmin ? 'Cancel' : '+ Create Administrator'}
            </button>
          </div>

          {adminError && (
            <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-2.5 text-emergency text-xs font-medium">
              {adminError}
            </div>
          )}

          {showCreateAdmin && (
            <form onSubmit={handleCreateAdmin} className="bg-surface border border-leaf/40 rounded-lg p-4 shadow-card">
              <h4 className="text-xs font-semibold text-text mb-3 font-mono">New PHC Administrator</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label htmlFor="sup-adm-name" className="block text-text3 mb-1 font-mono">Full Name *</label>
                  <input
                    id="sup-adm-name"
                    type="text"
                    required
                    value={adminForm.full_name}
                    onChange={e => setAdminForm(d => ({ ...d, full_name: e.target.value }))}
                    className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text focus:outline-none focus:ring-1 focus:ring-sage"
                  />
                </div>
                <div>
                  <label htmlFor="sup-adm-email" className="block text-text3 mb-1 font-mono">Email *</label>
                  <input
                    id="sup-adm-email"
                    type="email"
                    required
                    value={adminForm.email}
                    onChange={e => setAdminForm(d => ({ ...d, email: e.target.value }))}
                    className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text focus:outline-none focus:ring-1 focus:ring-sage"
                  />
                </div>
                <div>
                  <label htmlFor="sup-adm-pass" className="block text-text3 mb-1 font-mono">Password *</label>
                  <input
                    id="sup-adm-pass"
                    type="password"
                    required
                    value={adminForm.password}
                    onChange={e => setAdminForm(d => ({ ...d, password: e.target.value }))}
                    className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text focus:outline-none focus:ring-1 focus:ring-sage"
                  />
                </div>
                <div>
                  <label htmlFor="sup-adm-fac" className="block text-text3 mb-1 font-mono">Assigned Active PHC *</label>
                  <select
                    id="sup-adm-fac"
                    required
                    value={adminForm.facility_id}
                    onChange={e => setAdminForm(d => ({ ...d, facility_id: e.target.value }))}
                    className="w-full border border-surface3 rounded px-2.5 py-1.5 bg-surface2 text-text"
                  >
                    <option value="">— Select Active PHC —</option>
                    {activeFacilities.map(f => (
                      <option key={f.id} value={f.id}>{f.name} ({f.district})</option>
                    ))}
                  </select>
                </div>
              </div>
              {adminFormError && <p className="text-emergency text-xs mt-2">{adminFormError}</p>}
              <button
                type="submit"
                disabled={creatingAdmin}
                className="mt-3 text-xs px-4 py-1.5 bg-routine text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all font-mono"
              >
                {creatingAdmin ? 'Creating...' : 'Create Account'}
              </button>
            </form>
          )}

          {loadingAdmins ? (
            <div className="text-center py-10 text-text3 text-xs">Loading administrators...</div>
          ) : (
            <div className="bg-surface border border-leaf/40 rounded-lg overflow-hidden shadow-card">
              <table className="w-full text-xs">
                <thead className="bg-surface2 border-b border-leaf/40">
                  <tr>
                    {['Name', 'Email', 'Assigned PHC', 'Status', 'Actions'].map(h => (
                      <th key={h} className="px-4 py-2 text-left font-mono font-semibold text-text3 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-leaf/20">
                  {admins.map(a => (
                    <tr key={a.id} className={a.is_active ? '' : 'opacity-50'}>
                      <td className="px-4 py-2.5 font-medium text-text">
                        {editingAdminId === a.id ? (
                          <input
                            type="text"
                            value={editAdminData.full_name ?? a.full_name}
                            onChange={e => setEditAdminData(d => ({ ...d, full_name: e.target.value }))}
                            className="border border-surface3 rounded px-2 py-0.5 text-xs bg-surface2 text-text"
                          />
                        ) : (
                          a.full_name || '—'
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-text2 font-mono">{a.email}</td>
                      <td className="px-4 py-2.5 text-text2">
                        {editingAdminId === a.id ? (
                          <select
                            value={editAdminData.facility_id ?? a.facility_id ?? ''}
                            onChange={e => setEditAdminData(d => ({ ...d, facility_id: e.target.value }))}
                            className="border border-surface3 rounded px-2 py-0.5 text-xs bg-surface2 text-text"
                          >
                            <option value="">— Select Active PHC —</option>
                            {activeFacilities.map(f => (
                              <option key={f.id} value={f.id}>{f.name}</option>
                            ))}
                          </select>
                        ) : (
                          a.facility_name || '—'
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`px-2 py-0.5 rounded-pill font-mono ${
                          a.is_active ? 'bg-routine/10 text-routine-ink' : 'bg-surface3 text-text3'
                        }`}>
                          {a.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          {editingAdminId === a.id ? (
                            <>
                              <button onClick={() => handleUpdateAdmin(a.id)} className="text-routine hover:text-forest font-medium">Save</button>
                              <button onClick={() => setEditingAdminId(null)} className="text-text3 hover:text-text2">Cancel</button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => { setEditingAdminId(a.id); setEditAdminData({ full_name: a.full_name, facility_id: a.facility_id }) }}
                                className="text-sage hover:text-forest font-medium"
                              >Edit</button>
                              {a.is_active ? (
                                <button onClick={() => handleDeactivateAdmin(a.id)} className="text-emergency hover:text-emergency/80 font-medium">Deactivate</button>
                              ) : (
                                <button onClick={() => handleReactivateAdmin(a.id)} className="text-routine hover:text-forest font-medium">Reactivate</button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
