import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function MeterManagement({ admin }) {
  const [meters, setMeters] = useState([])
  const [levelFilter, setLevelFilter] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // New meter form state
  const [meterId, setMeterId] = useState('')
  const [name, setName] = useState('')
  const [level, setLevel] = useState('building')
  const [block, setBlock] = useState('A')
  const [floor, setFloor] = useState('')
  const [roomId, setRoomId] = useState('')
  const [source, setSource] = useState('simulated')

  const loadMeters = async () => {
    setLoading(true)
    setError('')
    try {
      const q = levelFilter ? `?measurement_level=${levelFilter}` : ''
      const res = await api('/meters' + q)
      setMeters(res || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMeters()
  }, [levelFilter])

  const toggleEnable = async (meter) => {
    const action = meter.enabled ? 'disable' : 'enable'
    try {
      await api(`/meters/${meter.id}/${action}`, { method: 'PATCH' })
      loadMeters()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleAddMeter = async (e) => {
    e.preventDefault()
    try {
      const payload = {
        meter_id: meterId,
        name,
        measurement_level: level,
        data_source: source,
        block: block || null,
        floor: floor ? Number(floor) : null,
        room_id: roomId ? Number(roomId) : null,
        enabled: true,
      }
      await api('/meters', { method: 'POST', body: payload })
      setMeterId('')
      setName('')
      loadMeters()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <h2>Meter management</h2>
      <p style={{ color: 'var(--mut)', marginBottom: 16 }}>
        Monitor and configure campus electricity meters. Simulated and hardware sources are clearly distinguished.
      </p>

      {error && <div className="card alert High" style={{ marginBottom: 12 }}>{error}</div>}

      <div className="row" style={{ marginBottom: 16 }}>
        <label htmlFor="level-filter" style={{ color: 'var(--mut)', fontSize: 14 }}>Filter by level:</label>
        <select
          id="level-filter"
          aria-label="Filter meters by measurement level"
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
        >
          <option value="">All measurement levels</option>
          <option value="building">Building level</option>
          <option value="floor">Floor level</option>
          <option value="room">Room level</option>
        </select>
        <span style={{ color: 'var(--mut)', fontSize: 13, marginLeft: 'auto' }}>
          Showing {meters.length} meters
        </span>
      </div>

      {admin && (
        <div className="card" style={{ marginBottom: 16 }}>
          <b>Register new meter</b>
          <form onSubmit={handleAddMeter} className="row" style={{ marginTop: 12, gap: 10 }}>
            <input
              aria-label="Meter identifier"
              placeholder="Meter ID (e.g. METER_B_MAIN)"
              value={meterId}
              onChange={(e) => setMeterId(e.target.value)}
              required
            />
            <input
              aria-label="Meter friendly name"
              placeholder="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <select
              aria-label="Measurement level"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="building">Building level</option>
              <option value="floor">Floor level</option>
              <option value="room">Room level</option>
            </select>
            <input
              aria-label="Block"
              placeholder="Block (e.g. A)"
              style={{ width: 80 }}
              value={block}
              onChange={(e) => setBlock(e.target.value)}
            />
            {level === 'floor' && (
              <input
                aria-label="Floor number"
                type="number"
                placeholder="Floor"
                style={{ width: 80 }}
                value={floor}
                onChange={(e) => setFloor(e.target.value)}
                required
              />
            )}
            {level === 'room' && (
              <input
                aria-label="Room ID"
                type="number"
                placeholder="Room ID"
                style={{ width: 80 }}
                value={roomId}
                onChange={(e) => setRoomId(e.target.value)}
                required
              />
            )}
            <select
              aria-label="Data source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            >
              <option value="simulated">Simulated</option>
              <option value="hardware">Hardware (ESP32)</option>
            </select>
            <button className="btn" type="submit">Create meter</button>
          </form>
        </div>
      )}

      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="tt" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Meter ID</th>
              <th>Name</th>
              <th>Level</th>
              <th>Location</th>
              <th>Data source</th>
              <th>Status</th>
              {admin && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {meters.length === 0 ? (
              <tr><td colSpan={admin ? 8 : 7} style={{ textAlign: 'center' }}>No meters found</td></tr>
            ) : (
              meters.map((m) => (
                <tr key={m.id}>
                  <td>{m.id}</td>
                  <td><b>{m.meter_id}</b></td>
                  <td>{m.name}</td>
                  <td>
                    <span className="tag" style={{ textTransform: 'capitalize' }}>
                      {m.measurement_level}
                    </span>
                  </td>
                  <td>
                    {m.measurement_level === 'building' && `Block ${m.block || '—'}`}
                    {m.measurement_level === 'floor' && `Block ${m.block}, Floor ${m.floor}`}
                    {m.measurement_level === 'room' && `Room ID ${m.room_id || '—'}`}
                  </td>
                  <td>
                    <span className={`tag ${m.data_source === 'hardware' ? 'Medium' : ''}`}>
                      {m.data_source}
                    </span>
                  </td>
                  <td>
                    <span className={`tag ${m.enabled ? '' : 'High'}`}>
                      {m.enabled ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  {admin && (
                    <td>
                      <button
                        className="btn alt"
                        style={{ padding: '2px 8px', fontSize: 12 }}
                        onClick={() => toggleEnable(m)}
                      >
                        {m.enabled ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

