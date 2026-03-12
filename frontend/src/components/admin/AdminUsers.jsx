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
  asha_worker: 'bg-emerald-100 text-emerald-800',
  doctor:      'bg-blue-100 text-blue-800',
  admin:       'bg-slate-100 text-slate-700',
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

  if (loading) return <div className="text-center py-16 text-slate-400 text-sm">Loading users...</div>
  if (error)   return <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">{error}</div>

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-slate-800">Users <span className="text-slate-400 font-normal">({users.length})</span></h2>
        <button
          onClick={() => setShowCreateForm(v => !v)}
          className="text-sm px-3 py-1.5 bg-slate-800 text-white rounded-md hover:bg-slate-700 transition-colors"
        >
          {showCreateForm ? 'Cancel' : '+ Create User'}
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <form onSubmit={handleCreate} className="bg-white border border-slate-200 rounded-lg p-5 mb-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">New User</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Full Name', key: 'full_name', type: 'text', required: true },
              { label: 'Email',     key: 'email',     type: 'email', required: true },
              { label: 'Password',  key: 'password',  type: 'password', required: true },
              { label: 'ASHA ID',   key: 'asha_id',   type: 'text', required: false },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs text-slate-500 mb-1">{f.label}{f.required && ' *'}</label>
                <input
                  type={f.type}
                  required={f.required}
                  value={createData[f.key]}
                  onChange={e => setCreateData(d => ({ ...d, [f.key]: e.target.value }))}
                  className="w-full border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-400"
                />
              </div>
            ))}
            <div>
              <label className="block text-xs text-slate-500 mb-1">Role *</label>
              <select
                required value={createData.role}
                onChange={e => setCreateData(d => ({ ...d, role: e.target.value }))}
                className="w-full border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Facility</label>
              <select
                value={createData.facility_id}
                onChange={e => setCreateData(d => ({ ...d, facility_id: e.target.value }))}
                className="w-full border border-slate-200 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                <option value="">— None —</option>
                {facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </div>
          </div>
          {createError && <p className="text-red-600 text-xs mt-2">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="mt-3 text-sm px-4 py-1.5 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50 transition-colors"
          >
            {creating ? 'Creating...' : 'Create User'}
          </button>
        </form>
      )}

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {['Name', 'Email', 'Role', 'Facility', 'ASHA ID', 'Status', 'Actions'].map(h => (
                <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map(u => (
              <tr key={u.id} className={u.is_active ? '' : 'opacity-50'}>
                <td className="px-4 py-3 font-medium text-slate-800">{u.full_name || '—'}</td>
                <td className="px-4 py-3 text-slate-500">{u.email}</td>
                <td className="px-4 py-3">
                  {editingId === u.id ? (
                    <select
                      value={editData.role ?? u.role}
                      onChange={e => setEditData(d => ({ ...d, role: e.target.value }))}
                      className="border border-slate-200 rounded px-2 py-1 text-xs"
                    >
                      {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                  ) : (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[u.role] || ROLE_COLORS.admin}`}>
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {editingId === u.id ? (
                    <select
                      value={editData.facility_id ?? u.facility_id ?? ''}
                      onChange={e => setEditData(d => ({ ...d, facility_id: e.target.value }))}
                      className="border border-slate-200 rounded px-2 py-1 text-xs"
                    >
                      <option value="">— None —</option>
                      {facilities.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  ) : (
                    u.facility_name || '—'
                  )}
                </td>
                <td className="px-4 py-3 text-slate-400">{u.asha_id || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    u.is_active
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-slate-100 text-slate-400'
                  }`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {editingId === u.id ? (
                      <>
                        <button onClick={() => handleUpdate(u.id)} className="text-xs text-emerald-600 hover:text-emerald-800 font-medium">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-slate-400 hover:text-slate-600">Cancel</button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => { setEditingId(u.id); setEditData({}) }}
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                        >Edit</button>
                        {u.is_active
                          ? <button onClick={() => handleDeactivate(u.id)} className="text-xs text-red-500 hover:text-red-700 font-medium">Deactivate</button>
                          : <button onClick={() => handleReactivate(u.id)} className="text-xs text-emerald-600 hover:text-emerald-800 font-medium">Reactivate</button>
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
