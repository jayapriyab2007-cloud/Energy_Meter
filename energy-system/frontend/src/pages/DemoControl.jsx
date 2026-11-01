import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function DemoControl({ admin }) {
  const [status, setStatus] = useState(null)
  const [virtualTime, setVirtualTime] = useState('')
  const [scenarioRes, setScenarioRes] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const loadStatus = async () => {
    try {
      const res = await api('/demo/status')
      setStatus(res)
      if (res.virtual_clock) {
        setVirtualTime(res.virtual_clock.slice(0, 16))
      }
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const handleSetClock = async (e) => {
    e.preventDefault()
    if (!virtualTime) return
    setLoading(true)
    setError('')
    try {
      await api('/demo/clock', {
        method: 'POST',
        body: { virtual_time: new Date(virtualTime).toISOString() },
      })
      loadStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRunScenario = async (scenarioId) => {
    setLoading(true)
    setError('')
    setScenarioRes(null)
    try {
      const res = await api('/demo/scenario', {
        method: 'POST',
        body: { scenario: scenarioId },
      })
      setScenarioRes(res)
      loadStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('Reset demo state, virtual clock, and clear all test alerts?')) return
    setLoading(true)
    setError('')
    setScenarioRes(null)
    try {
      const res = await api('/demo/reset', { method: 'POST' })
      alert(res.message)
      loadStatus()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <h2>Demo control & scenarios</h2>
      <p style={{ color: 'var(--mut)', marginBottom: 16 }}>
        Interactive demo orchestration for College Campus electricity monitoring. All readings are simulated estimates.
      </p>

      {error && <div className="card alert High" style={{ marginBottom: 14 }}>{error}</div>}

      {scenarioRes && (
        <div className="card alert High" style={{ marginBottom: 16, background: '#fdf3f2' }}>
          <b>Scenario {scenarioRes.scenario} executed successfully!</b>
          <p style={{ margin: '6px 0' }}>{scenarioRes.details}</p>
          <small style={{ color: 'var(--mut)' }}>
            Virtual Clock set to: {scenarioRes.virtual_time?.replace('T', ' ')} · Alert status:{' '}
            {scenarioRes.alert_created ? 'Triggered (see Alerts tab)' : 'Suppressed'}
          </small>
        </div>
      )}

      <div className="grid2" style={{ marginBottom: 16 }}>
        <div className="card">
          <b>Virtual demo clock</b>
          <p style={{ color: 'var(--mut)', fontSize: 13, margin: '6px 0 12px' }}>
            Set the simulator clock to any weekday or hour to test scenarios deterministically at any real time of day.
          </p>
          <form onSubmit={handleSetClock} className="row">
            <input
              type="datetime-local"
              aria-label="Virtual clock datetime"
              value={virtualTime}
              onChange={(e) => setVirtualTime(e.target.value)}
              required
            />
            <button className="btn" type="submit" disabled={loading}>
              Update clock
            </button>
          </form>
          {status?.virtual_clock && (
            <p style={{ fontSize: 12, color: 'var(--teal)', marginTop: 8 }}>
              Active virtual time: <b>{status.virtual_clock.replace('T', ' ')}</b>
            </p>
          )}
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <b>Reset demo state</b>
            <p style={{ color: 'var(--mut)', fontSize: 13, margin: '6px 0 12px' }}>
              Clears injected loads, removes scenario alerts, resets virtual clock to 08:00, and leaves seeded baseline history intact.
            </p>
          </div>
          <div>
            <button className="btn alt" onClick={handleReset} disabled={loading} style={{ borderColor: 'var(--red)', color: 'var(--red)' }}>
              Reset demo
            </button>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <b>Pre-configured demo scenarios</b>
        <p style={{ color: 'var(--mut)', fontSize: 13, margin: '6px 0 14px' }}>
          Each scenario injects realistic loads and sets the virtual clock to trigger exact college timetable anomalies:
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
          <div style={{ border: '1px solid var(--line)', borderRadius: 6, padding: 12 }}>
            <span className="tag High" style={{ float: 'right' }}>Main Demo</span>
            <b style={{ display: 'block', marginBottom: 4 }}>Scenario 1: B101 Seminar Hall</b>
            <p style={{ fontSize: 13, color: 'var(--mut)', margin: '0 0 10px' }}>
              Equipment left on during Free period (Weekday 11:00). Injects 4.8 kW (AC, projector, sound system).
            </p>
            <button className="btn" onClick={() => handleRunScenario(1)} disabled={loading}>
              Run Seminar Hall demo
            </button>
          </div>

          <div style={{ border: '1px solid var(--line)', borderRadius: 6, padding: 12 }}>
            <span className="tag Medium" style={{ float: 'right' }}>Night-time</span>
            <b style={{ display: 'block', marginBottom: 4 }}>Scenario 2: Night-time draw</b>
            <p style={{ fontSize: 13, color: 'var(--mut)', margin: '0 0 10px' }}>
              B101 Seminar Hall at 22:00 night-time with 3.0 kW draw. Triggers out-of-hours alert.
            </p>
            <button className="btn alt" onClick={() => handleRunScenario(2)} disabled={loading}>
              Run Night-time scenario
            </button>
          </div>

          <div style={{ border: '1px solid var(--line)', borderRadius: 6, padding: 12 }}>
            <span className="tag" style={{ float: 'right' }}>CSE Lab</span>
            <b style={{ display: 'block', marginBottom: 4 }}>Scenario 3: Room A204 free slot</b>
            <p style={{ fontSize: 13, color: 'var(--mut)', margin: '0 0 10px' }}>
              A204 CSE Lab during scheduled 10:00 Free period with 2.4 kW. Triggers free-period alert.
            </p>
            <button className="btn alt" onClick={() => handleRunScenario(3)} disabled={loading}>
              Run A204 scenario
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

