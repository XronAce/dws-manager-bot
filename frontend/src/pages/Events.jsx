import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import Banner from '../components/Banner.jsx'
import Occurrences from '../components/Occurrences.jsx'
import { withServerTime } from '../lib/servertime.js'
import DateTimeField from '../components/DateTimeField.jsx'

// Weekday names in the viewer's language; the indices stay 0 = Monday, which
// is what the API stores.
/** Matches the announcement cards: no seconds, no year, weekday included. */
const fmtWhen = (iso) =>
  new Intl.DateTimeFormat(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit',
  }).format(new Date(iso))

const DAYS = (() => {
  const f = new Intl.DateTimeFormat(undefined, { weekday: 'short' })
  return Array.from({ length: 7 }, (_, i) => f.format(new Date(2024, 0, 1 + i)))
})()

const EMPTY = {
  key: '',
  name: '',
  description: '',
  enabled: true,
  schedule_type: 'weekly',
  weekdays: [],
  rotation_days: 5,
  reference_date: '',
  fixed_dates: [],
  start_time: '20:00',
  duration_minutes: 60,
  timezone: 'Asia/Seoul',
  signup_enabled: true,
}

function toPayload(form) {
  return {
    ...form,
    weekdays: form.schedule_type === 'weekly' ? form.weekdays.map(Number) : null,
    rotation_days: form.schedule_type === 'rotation' ? Number(form.rotation_days) : null,
    reference_date:
      form.schedule_type === 'rotation' && form.reference_date
        ? new Date(form.reference_date).toISOString()
        : null,
    fixed_dates: form.schedule_type === 'fixed' ? form.fixed_dates : null,
    duration_minutes: Number(form.duration_minutes),
    description: form.description || null,
  }
}

export default function Events() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(null)
  const [preview, setPreview] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState({})
  const [openDates, setOpenDates] = useState(null)

  const refresh = () => api.listEvents().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { refresh() }, [])

  const set = (field) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [field]: value }))
  }

  const toggleDay = (index) =>
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(index)
        ? f.weekdays.filter((d) => d !== index)
        : [...f.weekdays, index].sort(),
    }))

  // Ask the API what this schedule would actually produce, so a rotation can be
  // sanity-checked before it is saved.
  async function runPreview() {
    setError(null)
    try {
      setPreview(await api.previewEvent(toPayload(form)))
    } catch (err) {
      setError(err.message)
      setPreview([])
    }
  }

  async function save(e) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const payload = toPayload(form)
      // The endpoints return the saved row; re-listing would be another
      // round trip for data already in hand.
      if (form.id) {
        const saved = await api.updateEvent(form.id, payload)
        setRows((rs) => rs.map((r) => (r.id === saved.id ? saved : r)))
      } else {
        const saved = await api.createEvent(payload)
        setRows((rs) => [...rs, saved])
      }
      setForm(null)
      setPreview([])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(row) {
    if (!confirm(`Delete event "${row.name}"?`)) return
    setError(null)
    setPending((p) => ({ ...p, [row.id]: true }))
    try {
      await api.deleteEvent(row.id)
      setRows((rs) => rs.filter((r) => r.id !== row.id))
    } catch (err) {
      setError(err.message)
    } finally {
      setPending((p) => {
        const { [row.id]: _drop, ...rest } = p
        return rest
      })
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Event schedule</h2>
        <button className="btn primary" onClick={() => { setForm({ ...EMPTY }); setPreview([]) }}>
          New event
        </button>
      </div>

      <Banner tone="error" onDismiss={() => setError(null)}>{error}</Banner>
      {rows.length === 0 && !form && (
        <p className="muted">
          No events yet. Define recurring game events here, then attach an announcement to one.
        </p>
      )}

      <div className="cards">
        {rows.map((row) => (
          <div key={row.id} className={row.enabled ? 'card' : 'card disabled'}>
            <div className="card-head">
              <span className={`dot ${row.enabled ? 'ok' : 'off'}`} />
              <strong>{row.name}</strong>
              <span className="pill">{row.schedule_type}</span>
              <code className="muted">{row.key}</code>
            </div>
            {row.description && <p className="card-body">{row.description}</p>}
            <div className="card-meta">
              {row.schedule_type === 'weekly' && (
                <span>{(row.weekdays ?? []).map((d) => DAYS[d]).join(', ')}</span>
              )}
              {row.schedule_type === 'rotation' && <span>every {row.rotation_days} days</span>}
              <span>{row.start_time}</span>
              <span className="muted">{row.timezone}</span>
            </div>
            {row.upcoming?.length > 0 && (
              <div className="card-meta">
                <span>Next: {fmtWhen(row.upcoming[0])}</span>
                <span className="muted">{withServerTime(row.upcoming[0])}</span>
              </div>
            )}
            <div className="card-actions">
              <button className="btn" onClick={() => { setForm({ ...EMPTY, ...row, weekdays: row.weekdays ?? [] }); setPreview([]) }}>
                Edit
              </button>
              <button
                className="btn"
                onClick={() => setOpenDates(openDates === row.id ? null : row.id)}
              >
                {openDates === row.id ? 'Hide dates' : 'Manage dates'}
              </button>
              <button
                className="btn danger"
                onClick={() => remove(row)}
                disabled={Boolean(pending[row.id])}
              >
                {pending[row.id] ? 'Deleting…' : 'Delete'}
              </button>
            </div>

            {openDates === row.id && (
              <Occurrences eventId={row.id} onError={setError} />
            )}
          </div>
        ))}
      </div>

      {form && (
        <form className="panel" onSubmit={save}>
          <h3>{form.id ? `Edit "${form.name}"` : 'New event'}</h3>
          <div className="grid">
            <label>
              Key
              <input value={form.key} onChange={set('key')} required placeholder="alliance-duel" />
              <small className="muted">Lowercase, no spaces. Used by /events post.</small>
            </label>
            <label>
              Name
              <input value={form.name} onChange={set('name')} required />
            </label>
            <label className="wide">
              Description
              <textarea rows="2" value={form.description ?? ''} onChange={set('description')} />
            </label>

            <label>
              Repeats
              <select value={form.schedule_type} onChange={set('schedule_type')}>
                <option value="weekly">On set weekdays</option>
                <option value="rotation">Every N days</option>
                <option value="fixed">Specific dates</option>
              </select>
            </label>

            <label>
              Start time
              <input type="time" value={form.start_time ?? ''} onChange={set('start_time')} />
            </label>

            {form.schedule_type === 'weekly' && (
              <div className="wide">
                <span className="label">Days</span>
                <div className="row wrap">
                  {DAYS.map((day, i) => (
                    <button
                      type="button"
                      key={day}
                      className={form.weekdays.includes(i) ? 'chip on' : 'chip'}
                      onClick={() => toggleDay(i)}
                    >
                      {day}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {form.schedule_type === 'rotation' && (
              <>
                <label>
                  Every N days
                  <input type="number" min="1" value={form.rotation_days} onChange={set('rotation_days')} />
                </label>
                <label>
                  Counting from
                  <DateTimeField
                    mode="date"
                    value={(form.reference_date ?? '').slice(0, 10)}
                    onChange={(v) => setForm((f) => ({ ...f, reference_date: v }))}
                    placeholder="Pick a known event day…"
                  />
                  <small className="muted">A day the event is known to run.</small>
                </label>
              </>
            )}

            {form.schedule_type === 'fixed' && (
              <label className="wide">
                Dates
                <DateTimeField
                  mode="multi"
                  values={form.fixed_dates ?? []}
                  onChange={(v) => setForm((f) => ({ ...f, fixed_dates: v }))}
                  placeholder="Pick one or more days…"
                />
                {(form.fixed_dates ?? []).length > 0 && (
                  <div className="row wrap" style={{ marginTop: 6 }}>
                    {form.fixed_dates.map((d) => (
                      <button
                        type="button"
                        key={d}
                        className="chip on"
                        title="Remove"
                        onClick={() =>
                          setForm((f) => ({
                            ...f,
                            fixed_dates: f.fixed_dates.filter((x) => x !== d),
                          }))
                        }
                      >
                        {d} ×
                      </button>
                    ))}
                  </div>
                )}
              </label>
            )}

            <label>
              Duration (minutes)
              <input type="number" min="1" value={form.duration_minutes} onChange={set('duration_minutes')} />
            </label>
            <label>
              Timezone
              <input list="tz-options" value={form.timezone} onChange={set('timezone')} />
              <datalist id="tz-options">
                <option value="Asia/Seoul">Korea</option>
                <option value="Etc/GMT+2">Game server time (ST)</option>
                <option value="UTC">UTC</option>
              </datalist>
              <small className="muted">Etc/GMT+2 is server time — 00:00 ST is 11:00 KST.</small>
            </label>
            <label className="inline">
              <input type="checkbox" checked={form.signup_enabled} onChange={set('signup_enabled')} />
              Allow signups
            </label>
            <label className="inline">
              <input type="checkbox" checked={form.enabled} onChange={set('enabled')} />
              Enabled
            </label>
          </div>

          {preview.length > 0 && (
            <div className="banner ok">
              <strong>Next occurrences:</strong>
              <ul>
                {preview.slice(0, 6).map((iso) => (
                  <li key={iso}>
                    {fmtWhen(iso)}{' '}
                    <span className="muted">· {withServerTime(iso)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="card-actions">
            <button className="btn primary" type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button className="btn" type="button" onClick={runPreview}>Preview schedule</button>
            <button className="btn" type="button" onClick={() => { setForm(null); setPreview([]) }}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
