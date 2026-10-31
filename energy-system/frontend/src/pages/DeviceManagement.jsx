import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function DeviceManagement({ admin }) {
  const [devices, setDevices] = useState([])
  const [meters, setMeters] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Registration modal/form state
  const [name, setName] = useState('')
  const [meterId, setMeterId] = useState('')
  const [registeredKey, setRegisteredKey] = useState(null)

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [d, m] = await Promise.all([
        api('/devices'),
        api('/meters'),
      ])
      setDevices(d || [])
      setMeters(m || [])
      if (m && m.length > 0 && !meterId) {
        setMeterId(m[0].id)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const timer = setInterval(loadData, 5000)
    return () => clearInterval(timer)
  }, [])

  const handleRegister = async (e) => {
    e.preventDefault()
    if (!name || !meterId) return
    try {
      const res = await api('/devices', {
        method: 'POST',
        body: { name, meter_id: Number(meterId) },
      })
      setRegisteredKey(res)
      setName('')
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this device?')) return
    try {
      await api(`/devices/${id}`, { method: 'DELETE' })
      loadData()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <>
      <h2>IoT device management</h2>
      <p style={{ color: 'var(--mut)', marginBottom: 16 }}>
        Monitor hardware nodes (ESP32) and credentials. Offline devices indicate missing telemetry, not zero consumption.
      </p>

      {error && <div className="card alert High" style={{ marginBottom: 12 }}>{error}</div>}

      {registeredKey && (
        <div className="card" style={{ marginBottom: 16, borderColor: 'var(--teal)', background: '#eaf5f6' }}>
          <b>Device registered successfully!</b>
          <p style={{ margin: '8px 0', fontSize: 13 }}>
            Copy this unique key now. It is stored securely hashed and will <b>never be shown again</b>:
          </p>
          <div className="row">
            <code style={{ background: '#fff', padding: '6px 12px', border: '1px solid var(--line)', borderRadius: 4, flex: 1, userSelect: 'all' }}>
              {registeredKey.plaintext_key}
            </code>
            <button className="btn" onClick={() => setRegisteredKey(null)}>Done</button>
          </div>
        </div>
      )}

      {admin && (
        <div className="card" style={{ marginBottom: 16 }}>
          <b>Register new IoT device</b>
          <form onSubmit={handleRegister} className="row" style={{ marginTop: 12, gap: 10 }}>
            <input
              aria-label="Device friendly name"
              placeholder="Device name (e.g. ESP32_Room_A101)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <select
              aria-label="Assign to meter"
              value={meterId}
              onChange={(e) => setMeterId(e.target.value)}
            >
              {meters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.meter_id} ({m.name} - {m.measurement_level})
                </option>
              ))}
            </select>
            <button className="btn" type="submit">Register device</button>
          </form>
        </div>
      )}

      <div className="card" style={{ overflowX: 'auto' }}>
        <table className="tt" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>ID</th>
              <th>Device name</th>
              <th>Associated meter</th>
              <th>Connection</th>
              <th>Last contact</th>
              <th>Enabled</th>
              {admin && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr><td colSpan={admin ? 7 : 6} style={{ textAlign: 'center' }}>No devices registered</td></tr>
            ) : (
              devices.map((d) => {
                const assignedMeter = meters.find((m) => m.id === d.meter_id)
                return (
                  <tr key={d.id}>
                    <td>{d.id}</td>
                    <td><b>{d.name}</b></td>
                    <td>
                      {assignedMeter
                        ? `${assignedMeter.meter_id} (${assignedMeter.measurement_level})`
                        : `Meter #${d.meter_id}`}
                    </td>
                    <td>
                      <span className={`tag ${d.online ? '' : 'High'}`}>
                        {d.online ? 'Online' : 'Offline'}
                      </span>
                    </td>
                    <td>
                      {d.last_seen
                        ? new Date(d.last_seen * 1000).toLocaleTimeString()
                        : 'Never'}
                    </td>
                    <td>{d.enabled ? 'Yes' : 'No'}</td>
                    {admin && (
                      <td>
                        <button
                          className="btn alt"
                          style={{ padding: '2px 8px', fontSize: 12 }}
                          onClick={() => handleDelete(d.id)}
                        >
                          Remove
                        </button>
                      </td>
                    )}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

