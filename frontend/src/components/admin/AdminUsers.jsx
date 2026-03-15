import { useState, useEffect } from 'react'
import {
  adminListUsers,
  adminCreateUser,
  adminUpdateUser,
  adminDeactivateUser,
  adminReactivateUser,
  adminListFacilities,
} from '../../lib/api'

const ROLE_OPTIONS = ['asha_worker', 'doctor', 'admin']

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  admin:       'Admin',
}

const ROLE_COLORS = {
  asha_worker: 'bg-leaf text-forest',
  doctor:      'bg-sand text-forest',
  admin:       'bg-surface3 text-text',
}

const EMPTY_CREATE = { email: '', password: '', full_name: '', role: 'asha_worker', facility_id: '', asha_id: '' }

export default function AdminUsers() {
  const [users,          setUsers]          = useState([])
  const [facilities,     setFacilities]     = useState([])
  const [loading,        setLoading]        = useState(true)
  const [error,          setError]          = useState(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createData,     setCreateData]     = useState(EMPTY_CREATE)
  const [createError,    setCreateError]    = useState(null)
  const [creating,       setCreating]       = useState(false)
  const [editingId,      setEditingId]      = useState(null)
  const [editData,       setEditData]       = useState({})

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [u, f] = await Promise.all([adminListUsers(), adminListFacilities()])
      setUsers(u)
      setFacilities(f)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    setCreating(true)
    setCreateError(null)
    try {
      await adminCreateUser(createData)
      setShowCreateForm(false)
      setCreateData(EMPTY_CREATE)
      await loadAll()
    } catch (e) {
      setCreateError(e.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleUpdate(userId) {
    try {
      await adminUpdateUser(userId, editData)
      setEditingId(null)
      await loadAll()
    } catch (e) {
      alert(e.message)
    }
  }

  async function handleDeactivate(userId) {
    if (!confirm('Deactivate this user?')) return
    try {
      await adminDeactivateUser(userId)
      await loadAll()
    } catch (e) { alert(e.message) }
  }

  async function handleReactivate(userId) {
    try {
      await adminReactivateUser(userId)
      await loadAll()
    } catch (e) { alert(e.message) }
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading users...</div>
  if (error)   return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text font-display italic">Users <span className="text-text3 font-normal font-body">({users.length})</span></h2>
        <button
          onClick={() => setShowCreateForm(v => !v)}
          className="text-sm px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn transition-all"
        >
          {showCreateForm ? 'Cancel' : '+ Create User'}
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreate} className="bg-surface border border-leaf/40 rounded-lg p-5 mb-5 shadow-card">
          <h3 className="text-sm font-semibold text-text mb-4">New User</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Full Name', key: 'full_name', type: 'text', required: true },
              { label: 'Email',     key: 'email',     type: 'email', required: true },
              { label: 'Password',  key: 'password',  type: 'password', required: true },
              { label: 'ASHA ID',   key: 'asha_id',   type: 'text', required: false },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-text3 mb-1 font-mono">{f.label}{f.required && ' *'}</label>
                <input
                  type={f.type}
                  required={f.required}
                  value={createData[f.key]}
                  onChange={e => setCreateData(d => ({ ...d, [f.key]: e.target.value }))}
                  className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-text3 mb-1 font-mono">Role *</label>
              <select
                required value={createData.role}
                onChange={e => setCreateData(d => ({ ...d, role: e.target.value }))}
                className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
              >
                {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-text3 mb-1 font-mono">Facility</label>
              <select
                value={createData.facility_id}
                onChange={e => setCreateData(d => ({ ...d, facility_id: e.target.value }))}
                className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
              >
                <option value="">— None —</option>
                {facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
          </div>
          {createError && <p className="text-emergency text-xs mt-2">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="mt-3 text-sm px-4 py-1.5 bg-routine text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all"
          >
            {creating ? 'Creating...' : 'Create User'}
          </button>
        </form>
      )}

      {/* Table */}
      <div className="bg-surface border border-leaf/40 rounded-lg overflow-hidden shadow-card">
        <table className="w-full text-sm">
          <thead className="bg-surface2 border-b border-leaf/40">
            <tr>
              {['Name', 'Email', 'Role', 'Facility', 'ASHA ID', 'Status', 'Actions'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-mono font-semibold text-text3 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-leaf/20">
            {users.map(u => (
              <tr key={u.id} className={u.is_active ? '' : 'opacity-50'}>
                <td className="px-4 py-3 font-medium text-text">{u.full_name || '—'}</td>
                <td className="px-4 py-3 text-text2">{u.email}</td>
                <td className="px-4 py-3">
                  {editingId === u.id ? (
                    <select
                      value={editData.role ?? u.role}
                      onChange={e => setEditData(d => ({ ...d, role: e.target.value }))}
                      className="border border-surface3 rounded px-2 py-1 text-xs bg-surface2 text-text"
                    >
                      {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                  ) : (
                    <span className={`text-xs px-2 py-0.5 rounded-pill font-medium font-mono ${ROLE_COLORS[u.role] || ROLE_COLORS.admin}`}>
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-text2">
                  {editingId === u.id ? (
                    <select
                      value={editData.facility_id ?? u.facility_id ?? ''}
                      onChange={e => setEditData(d => ({ ...d, facility_id: e.target.value }))}
                      className="border border-surface3 rounded px-2 py-1 text-xs bg-surface2 text-text"
                    >
                      <option value="">— None —</option>
                      {facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  ) : (
                    u.facility_name || '—'
                  )}
                </td>
                <td className="px-4 py-3 text-text3 font-mono">{u.asha_id || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-pill font-medium font-mono ${
                    u.is_active
                      ? 'bg-routine/10 text-routine'
                      : 'bg-surface3 text-text3'
                  }`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {editingId === u.id ? (
                      <>
                        <button onClick={() => handleUpdate(u.id)} className="text-xs text-routine hover:text-forest font-medium">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-text3 hover:text-text2">Cancel</button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => { setEditingId(u.id); setEditData({}) }}
                          className="text-xs text-sage hover:text-forest font-medium"
                        >Edit</button>
                        {u.is_active
                          ? <button onClick={() => handleDeactivate(u.id)} className="text-xs text-emergency hover:text-emergency/80 font-medium">Deactivate</button>
                          : <button onClick={() => handleReactivate(u.id)} className="text-xs text-routine hover:text-forest font-medium">Reactivate</button>
                        }
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
