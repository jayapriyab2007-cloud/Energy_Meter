import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function CampusManagement({ admin }) {
  const [subTab, setSubTab] = useState('blocks')
  const [blocks, setBlocks] = useState([])
  const [floors, setFloors] = useState([])
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Form states
  const [blockName, setBlockName] = useState('')
  const [blockDesc, setBlockDesc] = useState('')
  const [floorBlockId, setFloorBlockId] = useState('')
  const [floorNumber, setFloorNumber] = useState('')
  const [floorLabel, setFloorLabel] = useState('')
  const [deptName, setDeptName] = useState('')
  const [deptBlockId, setDeptBlockId] = useState('')

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [b, f, d] = await Promise.all([
        api('/blocks'),
        api('/floors'),
        api('/departments'),
      ])
      setBlocks(b || [])
      setFloors(f || [])
      setDepartments(d || [])
      if (b && b.length > 0) {
        if (!floorBlockId) setFloorBlockId(b[0].id)
        if (!deptBlockId) setDeptBlockId(b[0].id)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleAddBlock = async (e) => {
    e.preventDefault()
    if (!blockName) return
    try {
      await api('/blocks', {
        method: 'POST',
        body: { name: blockName, description: blockDesc || null },
      })
      setBlockName('')
      setBlockDesc('')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteBlock = async (id) => {
    if (!confirm('Delete this block?')) return
    try {
      await api(`/blocks/${id}`, { method: 'DELETE' })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleAddFloor = async (e) => {
    e.preventDefault()
    if (!floorBlockId || !floorNumber) return
    try {
      await api('/floors', {
        method: 'POST',
        body: { block_id: Number(floorBlockId), number: Number(floorNumber), label: floorLabel || null },
      })
      setFloorNumber('')
      setFloorLabel('')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteFloor = async (id) => {
    if (!confirm('Delete this floor?')) return
    try {
      await api(`/floors/${id}`, { method: 'DELETE' })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleAddDepartment = async (e) => {
    e.preventDefault()
    if (!deptName) return
    try {
      await api('/departments', {
        method: 'POST',
        body: { name: deptName, block_id: deptBlockId ? Number(deptBlockId) : null },
      })
      setDeptName('')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDeleteDepartment = async (id) => {
    if (!confirm('Delete this department?')) return
    try {
      await api(`/departments/${id}`, { method: 'DELETE' })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <h2>Campus management</h2>
      <p style={{ color: 'var(--mut)', marginBottom: 16 }}>
        Manage blocks, floors, and departments.
      </p>

      {error && <div className="card alert High" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="row" style={{ marginBottom: 16 }}>
        <button
          className={`btn ${subTab === 'blocks' ? '' : 'alt'}`}
          onClick={() => setSubTab('blocks')}
        >
          Blocks ({blocks.length})
        </button>
        <button
          className={`btn ${subTab === 'floors' ? '' : 'alt'}`}
          onClick={() => setSubTab('floors')}
        >
          Floors ({floors.length})
        </button>
        <button
          className={`btn ${subTab === 'departments' ? '' : 'alt'}`}
          onClick={() => setSubTab('departments')}
        >
          Departments ({departments.length})
        </button>
      </div>

      {subTab === 'blocks' && (
        <div className="card">
          <b>Blocks</b>
          {admin && (
            <form onSubmit={handleAddBlock} className="row" style={{ marginTop: 12, marginBottom: 16 }}>
              <input
                aria-label="Block name"
                placeholder="Block name (e.g. E)"
                value={blockName}
                onChange={(e) => setBlockName(e.target.value)}
                required
              />
              <input
                aria-label="Block description"
                placeholder="Description"
                value={blockDesc}
                onChange={(e) => setBlockDesc(e.target.value)}
              />
              <button className="btn" type="submit">Add block</button>
            </form>
          )}

          <table className="tt" style={{ width: '100%', marginTop: 8 }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Description</th>
                {admin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {blocks.length === 0 ? (
                <tr><td colSpan={admin ? 4 : 3} style={{ textAlign: 'center' }}>No blocks found</td></tr>
              ) : (
                blocks.map((b) => (
                  <tr key={b.id}>
                    <td>{b.id}</td>
                    <td><b>{b.name}</b></td>
                    <td>{b.description || '—'}</td>
                    {admin && (
                      <td>
                        <button className="btn alt" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => handleDeleteBlock(b.id)}>Delete</button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'floors' && (
        <div className="card">
          <b>Floors</b>
          {admin && (
            <form onSubmit={handleAddFloor} className="row" style={{ marginTop: 12, marginBottom: 16 }}>
              <select
                aria-label="Select block"
                value={floorBlockId}
                onChange={(e) => setFloorBlockId(e.target.value)}
              >
                {blocks.map((b) => (
                  <option key={b.id} value={b.id}>Block {b.name}</option>
                ))}
              </select>
              <input
                aria-label="Floor number"
                type="number"
                min="1"
                placeholder="Floor number"
                value={floorNumber}
                onChange={(e) => setFloorNumber(e.target.value)}
                required
              />
              <input
                aria-label="Floor label"
                placeholder="Label (optional)"
                value={floorLabel}
                onChange={(e) => setFloorLabel(e.target.value)}
              />
              <button className="btn" type="submit">Add floor</button>
            </form>
          )}

          <table className="tt" style={{ width: '100%', marginTop: 8 }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Block</th>
                <th>Number</th>
                <th>Label</th>
                {admin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {floors.length === 0 ? (
                <tr><td colSpan={admin ? 5 : 4} style={{ textAlign: 'center' }}>No floors found</td></tr>
              ) : (
                floors.map((f) => {
                  const blk = blocks.find((b) => b.id === f.block_id)
                  return (
                    <tr key={f.id}>
                      <td>{f.id}</td>
                      <td>Block {blk ? blk.name : f.block_id}</td>
                      <td>Floor {f.number}</td>
                      <td>{f.label || '—'}</td>
                      {admin && (
                        <td>
                          <button className="btn alt" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => handleDeleteFloor(f.id)}>Delete</button>
                        </td>
                      )}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {subTab === 'departments' && (
        <div className="card">
          <b>Departments</b>
          {admin && (
            <form onSubmit={handleAddDepartment} className="row" style={{ marginTop: 12, marginBottom: 16 }}>
              <input
                aria-label="Department name"
                placeholder="Department name"
                value={deptName}
                onChange={(e) => setDeptName(e.target.value)}
                required
              />
              <select
                aria-label="Department block"
                value={deptBlockId}
                onChange={(e) => setDeptBlockId(e.target.value)}
              >
                <option value="">No specific block</option>
                {blocks.map((b) => (
                  <option key={b.id} value={b.id}>Block {b.name}</option>
                ))}
              </select>
              <button className="btn" type="submit">Add department</button>
            </form>
          )}

          <table className="tt" style={{ width: '100%', marginTop: 8 }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Department name</th>
                <th>Assigned block</th>
                {admin && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {departments.length === 0 ? (
                <tr><td colSpan={admin ? 4 : 3} style={{ textAlign: 'center' }}>No departments found</td></tr>
              ) : (
                departments.map((d) => {
                  const blk = blocks.find((b) => b.id === d.block_id)
                  return (
                    <tr key={d.id}>
                      <td>{d.id}</td>
                      <td><b>{d.name}</b></td>
                      <td>{blk ? `Block ${blk.name}` : 'Unassigned'}</td>
                      {admin && (
                        <td>
                          <button className="btn alt" style={{ padding: '2px 8px', fontSize: 12 }} onClick={() => handleDeleteDepartment(d.id)}>Delete</button>
                        </td>
                      )}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

