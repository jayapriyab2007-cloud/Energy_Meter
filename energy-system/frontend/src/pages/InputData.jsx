import { useState, useEffect } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api'

function toDateTimeLocal(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export default function InputData({ setTab }) {
  const [rooms, setRooms] = useState([])
  const [selectedRoomName, setSelectedRoomName] = useState('')
  const [powerKw, setPowerKw] = useState('2.4')
  const [readingTime, setReadingTime] = useState(toDateTimeLocal(new Date()))
  const [repeatCount, setRepeatCount] = useState(3)
  const [intervalMin, setIntervalMin] = useState(5)
  const [voltage, setVoltage] = useState('230')
  const [currentA, setCurrentA] = useState('10.4')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  const [simRunning, setSimRunning] = useState(false)
  const [liveData, setLiveData] = useState(null)
  const [roomAlerts, setRoomAlerts] = useState([])

  // Load rooms
  useEffect(() => {
    api('/rooms')
      .then((data) => {
        setRooms(data || [])
        if (data && data.length > 0) {
          // Default to B101 Seminar Hall or A204 if available
          const preferred = data.find((r) => r.name === 'B101') || data.find((r) => r.name === 'A204') || data[0]
          setSelectedRoomName(preferred.name)
        }
      })
      .catch((err) => setError('Failed to load rooms: ' + err.message))
  }, [])

  // Check simulator status
  const checkSim = () => {
    api('/sim/status')
      .then((res) => setSimRunning(!!res?.on))
      .catch(() => {})
  }

  useEffect(() => {
    checkSim()
    const timer = setInterval(checkSim, 3000)
    return () => clearInterval(timer)
  }, [])

  const stopSimulator = async () => {
    try {
      await api('/sim/stop', { method: 'POST' })
      setSimRunning(false)
    } catch (err) {
      setError('Failed to stop simulator: ' + err.message)
    }
  }

  // Selected room object
  const currentRoom = rooms.find((r) => r.name === selectedRoomName)

  // Live telemetry chart for selected room (refresh every 2s)
  useEffect(() => {
    if (!currentRoom) return
    let active = true

    const fetchLive = () => {
      api(`/rooms/${currentRoom.id}/live`)
        .then((data) => {
          if (active) setLiveData(data)
        })
        .catch(() => {})

      api('/alerts')
        .then((data) => {
          if (active && Array.isArray(data)) {
            const forRoom = data.filter((a) => a.room_id === currentRoom.id)
            setRoomAlerts(forRoom)
          }
        })
        .catch(() => {})
    }

    fetchLive()
    const timer = setInterval(fetchLive, 2000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [currentRoom])

  // Submit manual reading
  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)

    try {
      const payload = {
        room: selectedRoomName,
        power_kw: parseFloat(powerKw),
        repeat_count: parseInt(repeatCount, 10),
        interval_min: parseFloat(intervalMin),
      }
      if (readingTime) {
        payload.ts = new Date(readingTime).toISOString()
      }
      if (voltage !== '') payload.voltage = parseFloat(voltage)
      if (currentA !== '') payload.current_a = parseFloat(currentA)

      const res = await api('/manual-readings', {
        method: 'POST',
        body: payload,
      })
      setResult(res)

      // Refresh live chart immediately
      if (currentRoom) {
        api(`/rooms/${currentRoom.id}/live`).then((d) => setLiveData(d)).catch(() => {})
        api('/alerts').then((d) => {
          if (Array.isArray(d)) setRoomAlerts(d.filter((a) => a.room_id === currentRoom.id))
        }).catch(() => {})
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Group rooms by block and floor
  const blocks = ['A', 'B', 'C', 'D']
  const floors = [1, 2, 3, 4]

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <h2>Input data (Manual Telemetry)</h2>
        <span className="tag" style={{ background: '#e0f2fe', color: '#0369a1', border: '1px solid #bae6fd' }}>
          Admin Hardware Testing Mode
        </span>
      </div>

      <p style={{ color: 'var(--mut)', marginBottom: 16 }}>
        Inject manual test readings into any room to test meter ingestion, timetable validation, and real-time anomaly alerts before hardware deployment.
      </p>

      {simRunning && (
        <div
          className="card"
          style={{
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#fffbeb',
            border: '1px solid #fde68a',
            color: '#92400e',
          }}
        >
          <div>
            <b>Notice:</b> The simulator is also writing to this room. Stop it for a clean test.
          </div>
          <button className="btn alt" type="button" onClick={stopSimulator}>
            Stop simulator
          </button>
        </div>
      )}

      {error && (
        <div className="card" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: 'var(--red)', marginBottom: 16 }}>
          <b>Error:</b> {error}
        </div>
      )}

      {/* Manual Input Form */}
      <div className="card" style={{ marginBottom: 20 }}>
        <b style={{ fontSize: 16, display: 'block', marginBottom: 12 }}>Configure Test Reading</b>

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Room (Block & Floor)
              </label>
              <select
                style={{ width: '100%' }}
                value={selectedRoomName}
                onChange={(e) => setSelectedRoomName(e.target.value)}
              >
                {blocks.map((b) => {
                  const bRooms = rooms.filter((r) => r.block === b)
                  if (!bRooms.length) return null
                  return (
                    <optgroup key={b} label={`Block ${b}`}>
                      {floors.map((fl) => {
                        const flRooms = bRooms.filter((r) => r.floor === fl)
                        if (!flRooms.length) return null
                        return flRooms.map((r) => (
                          <option key={r.name} value={r.name}>
                            {r.name} · Floor {r.floor} · {r.type} ({r.department || 'General'})
                          </option>
                        ))
                      })}
                    </optgroup>
                  )
                })}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Power draw (kW, required 0-100)
              </label>
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                required
                style={{ width: '100%' }}
                value={powerKw}
                onChange={(e) => setPowerKw(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Timestamp of latest reading
              </label>
              <input
                type="datetime-local"
                style={{ width: '100%' }}
                value={readingTime}
                onChange={(e) => setReadingTime(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Number of readings to send
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                {[1, 3, 6].map((cnt) => (
                  <button
                    type="button"
                    key={cnt}
                    className={`btn ${repeatCount === cnt ? '' : 'alt'}`}
                    style={{ flex: 1, padding: '6px 0' }}
                    onClick={() => setRepeatCount(cnt)}
                  >
                    {cnt} reading{cnt > 1 ? 's' : ''}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Interval between readings (min)
              </label>
              <input
                type="number"
                min="0.5"
                max="60"
                step="0.5"
                style={{ width: '100%' }}
                value={intervalMin}
                onChange={(e) => setIntervalMin(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Voltage (V, optional)
              </label>
              <input
                type="number"
                min="0"
                max="500"
                step="1"
                placeholder="230"
                style={{ width: '100%' }}
                value={voltage}
                onChange={(e) => setVoltage(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                Current (A, optional)
              </label>
              <input
                type="number"
                min="0"
                max="500"
                step="0.1"
                placeholder="10.4"
                style={{ width: '100%' }}
                value={currentA}
                onChange={(e) => setCurrentA(e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="btn" type="submit" disabled={loading} style={{ minWidth: 140 }}>
              {loading ? 'Ingesting...' : 'Submit reading'}
            </button>
            <span style={{ fontSize: 13, color: 'var(--mut)' }}>
              Data source: <b>manual</b> · Ingests through unified anomaly detection pipeline
            </span>
          </div>
        </form>
      </div>

      {/* Submission Result */}
      {result && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            background: result.new_alerts_count > 0 ? '#fff1f2' : '#f0fdf4',
            border: `1px solid ${result.new_alerts_count > 0 ? '#fecdd3' : '#bbf7d0'}`,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <b style={{ fontSize: 16 }}>
              {result.new_alerts_count > 0 ? '⚠️ Anomaly Alert Generated!' : '✅ Readings Ingested Successfully'}
            </b>
            {setTab && (
              <button className="btn alt" type="button" onClick={() => setTab('Alerts')}>
                View Alerts tab →
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, fontSize: 14 }}>
            <div>
              <span style={{ color: 'var(--mut)' }}>Room:</span> <b>{result.room}</b>
            </div>
            <div>
              <span style={{ color: 'var(--mut)' }}>Readings written:</span> <b>{result.readings_stored}</b>
            </div>
            <div>
              <span style={{ color: 'var(--mut)' }}>Timetable status at time:</span>{' '}
              <span className={`tag ${result.timetable_status}`}>{result.timetable_status}</span>
            </div>
            <div>
              <span style={{ color: 'var(--mut)' }}>Expected baseline draw:</span>{' '}
              <b>{result.normal_baseline_kw} kW</b>
            </div>
          </div>

          {result.alerts && result.alerts.length > 0 && (
            <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #fecdd3' }}>
              <b>Alert Details:</b>
              {result.alerts.map((alt) => (
                <div key={alt.id} style={{ marginTop: 6, fontSize: 13 }}>
                  • <span className={`tag ${alt.severity}`}>{alt.kind}</span> ({alt.severity} severity): {alt.explanation}
                  <div style={{ color: 'var(--mut)', marginTop: 2, paddingLeft: 12 }}>
                    Suggested action: {alt.action}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Live Chart for Room */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
          <b>
            Live telemetry: {selectedRoomName} {currentRoom && `(${currentRoom.type})`} — Power (kW)
          </b>
          <div className="row">
            <span className="tag" style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: 600 }}>
              manual
            </span>
            <span className="tag">simulated</span>
            <span className="tag" style={{ background: '#f0fdf4', color: '#166534' }}>
              hardware
            </span>
            <span className="tag alt">Refreshed every 2s</span>
          </div>
        </div>

        {liveData && liveData.points && liveData.points.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={liveData.points}>
              <CartesianGrid stroke="#e3eaef" />
              <XAxis dataKey="t" minTickGap={25} />
              <YAxis unit=" kW" domain={[0, 'auto']} />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const pt = payload[0].payload
                    return (
                      <div
                        style={{
                          background: '#fff',
                          padding: '8px 12px',
                          border: '1px solid var(--line)',
                          borderRadius: 6,
                          fontSize: 12,
                        }}
                      >
                        <div>
                          <b>Time:</b> {pt.t}
                        </div>
                        <div>
                          <b>Power:</b> {pt.kw} kW
                        </div>
                        <div>
                          <b>Status:</b> {pt.status}
                        </div>
                        <div>
                          <b>Source:</b>{' '}
                          <span
                            className="tag"
                            style={{
                              background: pt.source === 'manual' ? '#e0f2fe' : pt.source === 'hardware' ? '#f0fdf4' : '#e3eaef',
                              color: pt.source === 'manual' ? '#0369a1' : pt.source === 'hardware' ? '#166534' : 'inherit',
                              fontWeight: pt.source === 'manual' ? 700 : 'normal',
                            }}
                          >
                            {pt.source}
                          </span>
                        </div>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Line dataKey="kw" stroke="#0e7c86" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ padding: 30, textAlign: 'center', color: 'var(--mut)' }}>
            No telemetry points loaded yet for {selectedRoomName}.
          </div>
        )}

        {/* Recent readings table */}
        {liveData && liveData.points && liveData.points.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <b style={{ fontSize: 13, color: 'var(--mut)', display: 'block', marginBottom: 6 }}>
              Recent readings (last 6 points):
            </b>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
              {liveData.points.slice(-6).reverse().map((pt, idx) => (
                <div
                  key={idx}
                  style={{
                    background: pt.source === 'manual' ? '#f0f9ff' : '#f8fafc',
                    border: `1px solid ${pt.source === 'manual' ? '#bae6fd' : '#e2e8f0'}`,
                    padding: '6px 10px',
                    borderRadius: 6,
                    fontSize: 12,
                    minWidth: 120,
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{pt.kw} kW</div>
                  <div style={{ color: 'var(--mut)', fontSize: 11 }}>{pt.t}</div>
                  <div style={{ marginTop: 4 }}>
                    <span
                      className="tag"
                      style={{
                        padding: '1px 6px',
                        fontSize: 10,
                        background: pt.source === 'manual' ? '#e0f2fe' : '#e2e8f0',
                        color: pt.source === 'manual' ? '#0369a1' : 'inherit',
                        fontWeight: pt.source === 'manual' ? 700 : 400,
                      }}
                    >
                      {pt.source}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Room's Recent Alerts */}
      <div className="card">
        <b style={{ fontSize: 16, display: 'block', marginBottom: 10 }}>
          Recent Alerts for Room {selectedRoomName}
        </b>
        {roomAlerts.length === 0 ? (
          <p style={{ color: 'var(--mut)', fontSize: 13, margin: 0 }}>
            No alerts on record for {selectedRoomName}.
          </p>
        ) : (
          <div>
            {roomAlerts.slice(0, 5).map((a) => (
              <div key={a.id} className={`card alert ${a.severity}`} style={{ padding: 10, marginBottom: 8 }}>
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                  <div>
                    <span className={`tag ${a.severity}`}>{a.kind}</span>
                    <span style={{ marginLeft: 8, fontWeight: 600, fontSize: 13 }}>
                      {a.power ? `${a.power} kW` : ''} vs baseline {a.baseline ? `${a.baseline} kW` : ''}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--mut)' }}>
                    {a.ts ? new Date(a.ts).toLocaleString() : ''} · <b>{a.status}</b>
                  </span>
                </div>
                <div style={{ fontSize: 13 }}>{a.explanation}</div>
                {a.action && (
                  <div style={{ fontSize: 12, color: 'var(--mut)', marginTop: 4 }}>
                    Suggested action: {a.action}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

