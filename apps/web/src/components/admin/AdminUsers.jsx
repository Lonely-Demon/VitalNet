import { useState, useEffect } from 'react'
import {
  adminListUsers,
  adminCreateUser,
  adminUpdateUser,
  adminDeactivateUser,
  adminReactivateUser,
  adminBulkCreateUsers,
  adminListFacilities,
} from '../../lib/api'

// Minimal RFC4180-ish CSV parser: handles quoted fields (incl. embedded
// commas/newlines) and "" escaped quotes. Sufficient for admin-authored
// onboarding sheets exported from Excel/Sheets.
function parseCsv(text) {
  const rows = []
  let row = []
  let field = ''
  let inQuotes = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++ } else { inQuotes = false }
      } else {
        field += c
      }
    } else if (c === '"') {
      inQuotes = true
    } else if (c === ',') {
      row.push(field); field = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(field); field = ''
      if (row.some((f) => f !== '')) rows.push(row)
      row = []
    } else {
      field += c
    }
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row) }
  return rows
}

const CSV_ROLE_OPTIONS = ['asha_worker', 'doctor', 'admin', 'supervisor']

function validateCsvRow(row, facilitiesByName) {
  const errors = []
  if (!row.full_name) errors.push('missing full_name')
  if (!row.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.email)) errors.push('invalid email')
  if (!row.password || row.password.length < 12) errors.push('password must be 12+ chars')
  if (!CSV_ROLE_OPTIONS.includes(row.role)) errors.push('role must be asha_worker/doctor/admin/supervisor')

  let facility_id = row.facility_id || ''
  if (row.facility && !facility_id) {
    const match = facilitiesByName.get(row.facility.trim().toLowerCase())
    if (match) facility_id = match
    else errors.push(`unknown facility "${row.facility}"`)
  }
  if ((row.role === 'asha_worker' || row.role === 'doctor' || row.role === 'supervisor') && !facility_id) {
    errors.push('facility is required for this role')
  }
  return { errors, facility_id }
}

const ROLE_OPTIONS = ['asha_worker', 'doctor', 'supervisor', 'admin']

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  supervisor:  'Supervisor',
  admin:       'Admin',
}

const ROLE_COLORS = {
  asha_worker: 'bg-leaf text-forest',
  doctor:      'bg-sand text-forest',
  supervisor:  'bg-urgent/10 text-urgent',
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
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [bulkRows,       setBulkRows]       = useState([])   // [{ full_name, email, role, facility_id, asha_id, errors }]
  const [bulkImporting,  setBulkImporting]  = useState(false)
  const [bulkResults,    setBulkResults]    = useState(null)
  const [bulkError,      setBulkError]      = useState(null)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [u, f] = await Promise.all([adminListUsers(), adminListFacilities()])
      setUsers(u.data || [])
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

  function handleCsvFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setBulkError(null)
    setBulkResults(null)
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = parseCsv(String(reader.result))
        if (parsed.length < 2) {
          setBulkError('CSV must have a header row plus at least one data row')
          setBulkRows([])
          return
        }
        const header = parsed[0].map((h) => h.trim().toLowerCase())
        const facilitiesByName = new Map(facilities.map((f) => [f.name.toLowerCase(), f.id]))
        const rows = parsed.slice(1).map((cols) => {
          const raw = {}
          header.forEach((key, i) => { raw[key] = (cols[i] || '').trim() })
          const { errors, facility_id } = validateCsvRow(raw, facilitiesByName)
          return { ...raw, facility_id, errors }
        })
        setBulkRows(rows)
      } catch {
        setBulkError('Could not parse this file as CSV')
        setBulkRows([])
      }
    }
    reader.readAsText(file)
  }

  async function handleBulkImport() {
    const validRows = bulkRows.filter((r) => r.errors.length === 0)
    if (validRows.length === 0) return
    setBulkImporting(true)
    setBulkError(null)
    try {
      const payload = validRows.map((r) => ({
        email: r.email,
        password: r.password,
        full_name: r.full_name,
        role: r.role,
        facility_id: r.facility_id || null,
        asha_id: r.asha_id || null,
      }))
      const report = await adminBulkCreateUsers(payload)
      setBulkResults(report)
      await loadAll()
    } catch (e) {
      setBulkError(e.message)
    } finally {
      setBulkImporting(false)
    }
  }

  function resetBulkImport() {
    setShowBulkImport(false)
    setBulkRows([])
    setBulkResults(null)
    setBulkError(null)
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading users...</div>
  if (error)   return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text font-display font-bold">Users <span className="text-text3 font-normal font-body">({users.length})</span></h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { resetBulkImport(); setShowBulkImport(v => !v) }}
            className="text-sm px-3 py-1.5 bg-surface2 text-text border border-leaf/40 rounded-pill hover:bg-surface3 transition-all"
          >
            {showBulkImport ? 'Cancel' : 'Bulk Import (CSV)'}
          </button>
          <button
            onClick={() => setShowCreateForm(v => !v)}
            className="text-sm px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn transition-all"
          >
            {showCreateForm ? 'Cancel' : '+ Create User'}
          </button>
        </div>
      </div>

      {/* Bulk CSV Import (FEATURES_ROADMAP §1b.4) */}
      {showBulkImport && (
        <div className="bg-surface border border-leaf/40 rounded-lg p-5 mb-5 shadow-card">
          <h3 className="text-sm font-semibold text-text mb-2">Bulk Import Users</h3>
          <p className="text-xs text-text3 mb-3">
            CSV columns: <code className="font-mono">full_name,email,password,role,facility,asha_id</code>.
            {' '}<code className="font-mono">role</code> must be asha_worker/doctor/admin.
            {' '}<code className="font-mono">facility</code> should match a facility name exactly (or use <code className="font-mono">facility_id</code> directly).
          </p>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={handleCsvFile}
            className="text-sm text-text2 mb-3"
          />
          {bulkError && <p className="text-emergency text-xs mb-3">{bulkError}</p>}

          {bulkRows.length > 0 && !bulkResults && (
            <>
              <div className="overflow-x-auto mb-3 max-h-80 overflow-y-auto border border-leaf/20 rounded-lg">
                <table className="w-full text-xs">
                  <thead className="bg-surface2 border-b border-leaf/40 sticky top-0">
                    <tr>
                      {['Name', 'Email', 'Role', 'Facility', 'Status'].map(h => (
                        <th key={h} className="px-3 py-2 text-left font-mono font-semibold text-text3 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-leaf/20">
                    {bulkRows.map((r, i) => (
                      <tr key={i} className={r.errors.length ? 'bg-emergency/5' : ''}>
                        <td className="px-3 py-2 text-text">{r.full_name || '—'}</td>
                        <td className="px-3 py-2 text-text2">{r.email || '—'}</td>
                        <td className="px-3 py-2 text-text2">{r.role || '—'}</td>
                        <td className="px-3 py-2 text-text2">{r.facility || r.facility_id || '—'}</td>
                        <td className="px-3 py-2">
                          {r.errors.length
                            ? <span className="text-emergency font-medium">{r.errors.join('; ')}</span>
                            : <span className="text-routine font-medium">Ready</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-text3 mb-2">
                {bulkRows.filter(r => r.errors.length === 0).length} of {bulkRows.length} rows will be imported.
                Rows with errors are skipped — fix and re-upload if needed.
              </p>
              <button
                onClick={handleBulkImport}
                disabled={bulkImporting || bulkRows.every(r => r.errors.length > 0)}
                className="text-sm px-4 py-1.5 bg-routine text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all"
              >
                {bulkImporting ? 'Importing…' : `Import ${bulkRows.filter(r => r.errors.length === 0).length} Users`}
              </button>
            </>
          )}

          {bulkResults && (
            <div>
              <p className="text-sm text-text mb-2">
                <span className="text-routine font-semibold">{bulkResults.succeeded} created</span>
                {bulkResults.failed > 0 && <span className="text-emergency font-semibold">, {bulkResults.failed} failed</span>}
              </p>
              <div className="overflow-x-auto max-h-60 overflow-y-auto border border-leaf/20 rounded-lg">
                <table className="w-full text-xs">
                  <tbody className="divide-y divide-leaf/20">
                    {bulkResults.results.map((r) => (
                      <tr key={r.row}>
                        <td className="px-3 py-2 text-text2">{r.email}</td>
                        <td className={`px-3 py-2 font-medium ${r.status === 'created' ? 'text-routine' : 'text-emergency'}`}>
                          {r.status === 'created' ? 'Created' : r.detail}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                onClick={resetBulkImport}
                className="mt-3 text-sm px-4 py-1.5 bg-surface2 text-text border border-leaf/40 rounded-pill hover:bg-surface3 transition-all"
              >
                Done
              </button>
            </div>
          )}
        </div>
      )}

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
                <label htmlFor={`create-${f.key}`} className="block text-xs text-text3 mb-1 font-mono">{f.label}{f.required && ' *'}</label>
                <input
                  id={`create-${f.key}`}
                  type={f.type}
                  required={f.required}
                  value={createData[f.key]}
                  onChange={e => setCreateData(d => ({ ...d, [f.key]: e.target.value }))}
                  className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
                />
              </div>
            ))}
            <div>
              <label htmlFor="create-role" className="block text-xs text-text3 mb-1 font-mono">Role *</label>
              <select
                id="create-role"
                required value={createData.role}
                onChange={e => setCreateData(d => ({ ...d, role: e.target.value }))}
                className="w-full border border-surface3 rounded-md px-3 py-1.5 text-sm bg-surface2 focus:outline-none focus:ring-1 focus:ring-sage text-text"
              >
                {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="create-facility" className="block text-xs text-text3 mb-1 font-mono">Facility</label>
              <select
                id="create-facility"
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
