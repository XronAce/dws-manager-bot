import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import Banner from '../components/Banner.jsx'
import DateTimeField, { nextRoundedNow, toDateTimeStr } from '../components/DateTimeField.jsx'

const CRON_PRESETS = [
  { label: 'Every day at 09:00', value: '0 9 * * *' },
  { label: 'Every day at 20:00', value: '0 20 * * *' },
  { label: 'Weekdays at 09:00', value: '0 9 * * 1-5' },
  { label: 'Mondays at 19:00', value: '0 19 * * 1' },
  { label: 'Saturdays at 20:00', value: '0 20 * * 6' },
  { label: 'Every 6 hours', value: '0 */6 * * *' },
]

function blankForm() {
  return { ...EMPTY, run_at: toDateTimeStr(nextRoundedNow()) }
}

const EMPTY = {
  name: '',
  enabled: true,
  channel_id: '',
  kind: 'cron',
  cron_expr: '0 9 * * *',
  interval_minutes: 60,
  run_at: '',   // filled by blankForm() with the next 5-minute mark
  timezone: 'Asia/Seoul',
  title: '',
  body: '',
  use_embed: true,
  embed_color: '#5865F2',
  mention: '',
  event_id: null,
  lead_minutes: 0,
}

/**
 * A datetime-local input needs "YYYY-MM-DDTHH:mm" in local time, but the API
 * returns an ISO string with an offset. Without this, editing a one-shot
 * showed an empty date field and silently cleared it on save.
 */
function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
         `T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toPayload(form) {
  return {
    ...form,
    // Left as a string on purpose. A Discord snowflake exceeds
    // Number.MAX_SAFE_INTEGER, so Number() silently rounds it into a channel
    // that does not exist. The API accepts and returns these as strings.
    channel_id: form.channel_id,
    interval_minutes: form.kind === 'interval' ? Number(form.interval_minutes) : null,
    run_at: form.kind === 'once' && form.run_at ? new Date(form.run_at).toISOString() : null,
    cron_expr: form.kind === 'cron' ? form.cron_expr : null,
    event_id: form.kind === 'event' ? Number(form.event_id) : null,   // DB serial, not a snowflake
    lead_minutes: Number(form.lead_minutes) || 0,
    title: form.title || null,
    mention: form.mention || null,
  }
}

export default function Announcements() {
  const [rows, setRows] = useState([])
  const [channels, setChannels] = useState([])
  const [events, setEvents] = useState([])
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)
  // Per-row in-flight state, so a slow link still gives immediate feedback.
  const [pending, setPending] = useState({})

  const refresh = () =>
    api
      .listAnnouncements()
      .then(setRows)
      .catch((e) => setError(e.message))

  useEffect(() => {
    refresh()
    api.channels().then(setChannels).catch(() => setChannels([]))
    api.listEvents().then(setEvents).catch(() => setEvents([]))
  }, [])

  const set = (field) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const payload = toPayload(form)
      // Both endpoints return the saved row, so re-listing the collection
      // would be a second round trip for data we already hold.
      if (form.id) {
        const saved = await api.updateAnnouncement(form.id, payload)
        setRows((rs) => rs.map((r) => (r.id === saved.id ? saved : r)))
      } else {
        const saved = await api.createAnnouncement(payload)
        setRows((rs) => [...rs, saved])
      }
      setForm(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function sendTest(row) {
    setError(null)
    setNotice(null)
    setPending((p) => ({ ...p, [row.id]: 'sending' }))
    try {
      await api.testAnnouncement(row.id)
      setNotice(`Sent "${row.name}" to Discord.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setPending((p) => {
        const { [row.id]: _drop, ...rest } = p
        return rest
      })
    }
  }

  async function remove(row) {
    if (!confirm(`Delete "${row.name}"? This cannot be undone.`)) return
    setError(null)
    setPending((p) => ({ ...p, [row.id]: 'deleting' }))
    try {
      await api.deleteAnnouncement(row.id)
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

  // Both sides are strings now; === on mixed types would never match.
  const channelName = (id) =>
    channels.find((c) => String(c.id) === String(id))?.name ?? id

  return (
    <div className="page">
      <div className="page-head">
        <h2>Scheduled announcements</h2>
        <button className="btn primary" onClick={() => setForm(blankForm())}>
          New announcement
        </button>
      </div>

      <Banner tone="error" onDismiss={() => setError(null)}>{error}</Banner>
      <Banner tone="ok" onDismiss={() => setNotice(null)}>{notice}</Banner>

      {rows.length === 0 && !form && (
        <p className="muted">Nothing scheduled yet. Create one to get started.</p>
      )}

      <div className="cards">
        {rows.map((row) => (
          <div key={row.id} className={row.enabled ? 'card' : 'card disabled'}>
            <div className="card-head">
              <span className={`dot ${row.enabled ? 'ok' : 'off'}`} />
              <strong>{row.name}</strong>
              <span className="pill">{row.kind}</span>
            </div>
            <div className="card-meta">
              <span>#{channelName(row.channel_id)}</span>
              {row.kind === 'cron' && <code>{row.cron_expr}</code>}
              {row.kind === 'interval' && <code>every {row.interval_minutes}m</code>}
              <span className="muted">{row.timezone}</span>
            </div>
            <p className="card-body">{row.body.slice(0, 160)}</p>
            <div className="card-meta">
              {row.next_run_at ? (
                <span>Next: {new Date(row.next_run_at).toLocaleString()}</span>
              ) : (
                <span className="muted">Not scheduled</span>
              )}
              {row.last_fired_at && (
                <span className="muted">
                  Last: {new Date(row.last_fired_at).toLocaleString()} ({row.fire_count}×)
                </span>
              )}
            </div>
            {row.last_error && <div className="banner error small"><div className="banner-body">{row.last_error}</div></div>}
            <div className="card-actions">
              <button
                className="btn"
                onClick={() =>
                  setForm({
                    ...EMPTY,
                    ...row,
                    channel_id: String(row.channel_id),
                    run_at: toLocalInput(row.run_at),
                  })
                }
              >
                Edit
              </button>
              <button
                className="btn"
                onClick={() => sendTest(row)}
                disabled={Boolean(pending[row.id])}
              >
                {pending[row.id] === 'sending' ? 'Sending…' : 'Send test'}
              </button>
              <button
                className="btn danger"
                onClick={() => remove(row)}
                disabled={Boolean(pending[row.id])}
              >
                {pending[row.id] === 'deleting' ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {form && (
        <form className="panel" onSubmit={save}>
          <h3>{form.id ? `Edit "${form.name}"` : 'New announcement'}</h3>

          <div className="grid">
            <label>
              Name
              <input value={form.name} onChange={set('name')} required />
            </label>

            <label>
              Channel
              <select value={form.channel_id} onChange={set('channel_id')} required>
                <option value="">Select a channel…</option>
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    #{c.name}
                    {c.category ? ` (${c.category})` : ''}
                  </option>
                ))}
              </select>
              {channels.length === 0 && (
                <small className="muted">
                  No channels loaded — the bot may not be connected yet.
                </small>
              )}
            </label>

            <label>
              Schedule type
              <select value={form.kind} onChange={set('kind')}>
                <option value="cron">Recurring (cron)</option>
                <option value="interval">Every N minutes</option>
                <option value="once">One time</option>
                <option value="event">Before an event</option>
              </select>
            </label>

            <label>
              Timezone
              <input value={form.timezone} onChange={set('timezone')} />
            </label>

            {form.kind === 'cron' && (
              <label className="wide">
                Cron expression
                <div className="row">
                  <input value={form.cron_expr} onChange={set('cron_expr')} required />
                  <select
                    value=""
                    onChange={(e) =>
                      e.target.value && setForm((f) => ({ ...f, cron_expr: e.target.value }))
                    }
                  >
                    <option value="">Presets…</option>
                    {CRON_PRESETS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
                <small className="muted">minute hour day-of-month month day-of-week</small>
              </label>
            )}

            {form.kind === 'interval' && (
              <label>
                Every (minutes)
                <input
                  type="number"
                  min="1"
                  value={form.interval_minutes}
                  onChange={set('interval_minutes')}
                />
              </label>
            )}

            {form.kind === 'once' && (
              <label>
                Run at
                <DateTimeField
                  mode="datetime"
                  value={form.run_at}
                  onChange={(v) => setForm((f) => ({ ...f, run_at: v }))}
                  minToday
                  placeholder="Pick a date and time…"
                />
                <small className="muted">Must be in the future.</small>
              </label>
            )}

            {form.kind === 'event' && (
              <>
                <label>
                  Event
                  <select value={form.event_id ?? ''} onChange={set('event_id')} required>
                    <option value="">Select an event…</option>
                    {events.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Minutes before start
                  <input
                    type="number"
                    min="0"
                    value={form.lead_minutes}
                    onChange={set('lead_minutes')}
                  />
                </label>
              </>
            )}

            <label>
              Title
              <input value={form.title ?? ''} onChange={set('title')} />
            </label>

            <label>
              Mention
              <select value={form.mention ?? ''} onChange={set('mention')}>
                <option value="">No ping</option>
                <option value="@everyone">@everyone</option>
                <option value="@here">@here</option>
              </select>
            </label>

            <label className="wide">
              Message
              <textarea rows="6" value={form.body} onChange={set('body')} required />
              <small className="muted">Discord markdown works: **bold**, *italic*, `code`.</small>
            </label>

            <label className="inline">
              <input type="checkbox" checked={form.use_embed} onChange={set('use_embed')} />
              Send as embed
            </label>

            {form.use_embed && (
              <label>
                Embed colour
                <input type="color" value={form.embed_color ?? '#5865F2'} onChange={set('embed_color')} />
              </label>
            )}

            <label className="inline">
              <input type="checkbox" checked={form.enabled} onChange={set('enabled')} />
              Enabled
            </label>
          </div>

          <div className="card-actions">
            <button className="btn primary" type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button className="btn" type="button" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
