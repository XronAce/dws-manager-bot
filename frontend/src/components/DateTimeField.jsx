import { useEffect, useRef, useState } from 'react'

/**
 * A calendar field with no external dependency.
 *
 * Three shapes, one implementation:
 *   mode="datetime" — one day plus a time, for a one-shot announcement
 *   mode="date"     — one day, for a rotation's reference date
 *   mode="multi"    — several days, for an event's fixed dates
 *
 * Everything is handled in local time. Building strings by hand rather than
 * going through toISOString() matters: that converts to UTC, which shifts the
 * calendar day for anyone east or west of Greenwich — in Asia/Seoul it would
 * land a 09:00 pick on the previous day.
 */

/**
 * Month and weekday names in the viewer's own language, rather than hardcoded
 * English. The card timestamps already follow the browser locale, so a Korean
 * officer was reading Korean dates above an English calendar.
 *
 * The week still starts on Monday everywhere. That is not a locale question
 * here: the backend stores weekdays as 0 = Monday, and the Events form's day
 * chips write those same indices.
 */
const WEEKDAYS = (() => {
  const f = new Intl.DateTimeFormat(undefined, { weekday: 'short' })
  // 1 Jan 2024 was a Monday, so seven days from there covers the week in order.
  return Array.from({ length: 7 }, (_, i) => f.format(new Date(2024, 0, 1 + i)))
})()

/**
 * The month header. Formatted whole rather than as month + " " + year: Korean
 * and Japanese lead with the year ("2026년 9월"), so concatenating in English
 * word order reads backwards.
 */
const fmtMonthYear = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'long',
})

/** The trigger's own label, e.g. "5 Sep 2026" or "2026년 9월 5일". */
const fmtDay = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'short', day: 'numeric',
})

const pad = (n) => String(n).padStart(2, '0')

export const toDateStr = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
export const toDateTimeStr = (d) => `${toDateStr(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`

/** Now, rounded up to the next 5-minute mark. */
export function nextRoundedNow(minutesAhead = 5) {
  const d = new Date()
  d.setSeconds(0, 0)
  d.setMinutes(d.getMinutes() + minutesAhead)
  d.setMinutes(Math.ceil(d.getMinutes() / 5) * 5)
  return d
}

function parseValue(value, mode) {
  if (!value) return null
  if (mode === 'multi') return null
  const d = new Date(value.length === 10 ? `${value}T00:00` : value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Days of the grid: leading blanks so the 1st lands under its weekday. */
function monthGrid(year, month) {
  const first = new Date(year, month, 1)
  const lead = (first.getDay() + 6) % 7          // 0 = Monday
  const days = new Date(year, month + 1, 0).getDate()
  const cells = Array.from({ length: lead }, () => null)
  for (let d = 1; d <= days; d += 1) cells.push(new Date(year, month, d))
  return cells
}

export default function DateTimeField({
  value,
  onChange,
  mode = 'datetime',
  values = [],        // mode="multi"
  minToday = false,
  placeholder = 'Select…',
}) {
  const selected = parseValue(value, mode)
  const [open, setOpen] = useState(false)
  const [cursor, setCursor] = useState(() => selected ?? new Date())
  const wrap = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (wrap.current && !wrap.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const pickDay = (day) => {
    if (mode === 'multi') {
      const key = toDateStr(day)
      onChange(values.includes(key) ? values.filter((v) => v !== key) : [...values, key].sort())
      return
    }
    if (mode === 'date') {
      onChange(toDateStr(day))
      setOpen(false)
      return
    }
    // Keep whatever time was already chosen; only the day moves.
    const base = selected ?? nextRoundedNow()
    const next = new Date(day)
    next.setHours(base.getHours(), base.getMinutes(), 0, 0)
    onChange(toDateTimeStr(next))
  }

  const setTime = (hhmm) => {
    const [h, m] = hhmm.split(':').map(Number)
    const next = new Date(selected ?? new Date())
    next.setHours(h || 0, m || 0, 0, 0)
    onChange(toDateTimeStr(next))
  }

  const label = (() => {
    if (mode === 'multi') {
      return values.length ? `${values.length} date${values.length > 1 ? 's' : ''} selected` : placeholder
    }
    if (!selected) return placeholder
    const day = fmtDay.format(selected)
    return mode === 'date' ? day : `${day}, ${pad(selected.getHours())}:${pad(selected.getMinutes())}`
  })()

  const cells = monthGrid(cursor.getFullYear(), cursor.getMonth())
  const selectedKey = selected ? toDateStr(selected) : null

  return (
    <div className="dtf" ref={wrap}>
      <button
        type="button"
        className={open ? 'dtf-trigger open' : 'dtf-trigger'}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={selected || values.length ? '' : 'muted'}>{label}</span>
        <span className="dtf-icon" aria-hidden="true">▾</span>
      </button>

      {open && (
        <div className="dtf-pop" role="dialog" aria-label="Choose a date">
          <div className="dtf-head">
            <button type="button" className="dtf-nav" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} aria-label="Previous month">‹</button>
            <strong>{fmtMonthYear.format(cursor)}</strong>
            <button type="button" className="dtf-nav" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} aria-label="Next month">›</button>
          </div>

          <div className="dtf-grid dtf-dow">
            {WEEKDAYS.map((d) => <span key={d}>{d}</span>)}
          </div>

          <div className="dtf-grid">
            {cells.map((day, i) => {
              if (!day) return <span key={`b${i}`} />
              const key = toDateStr(day)
              const isToday = key === toDateStr(today)
              const isSel = mode === 'multi' ? values.includes(key) : key === selectedKey
              const disabled = minToday && day < today
              return (
                <button
                  type="button"
                  key={key}
                  className={[
                    'dtf-day',
                    isSel ? 'sel' : '',
                    isToday ? 'today' : '',
                  ].filter(Boolean).join(' ')}
                  disabled={disabled}
                  onClick={() => pickDay(day)}
                >
                  {day.getDate()}
                </button>
              )
            })}
          </div>

          {mode === 'datetime' && (
            <div className="dtf-foot">
              <label className="dtf-time">
                Time
                <input
                  type="time"
                  value={selected ? `${pad(selected.getHours())}:${pad(selected.getMinutes())}` : ''}
                  onChange={(e) => setTime(e.target.value)}
                />
              </label>
              <button type="button" className="btn" onClick={() => { onChange(toDateTimeStr(nextRoundedNow())); }}>
                Now
              </button>
              <button type="button" className="btn" onClick={() => setOpen(false)}>Done</button>
            </div>
          )}

          {mode !== 'datetime' && (
            <div className="dtf-foot">
              {mode === 'multi' && values.length > 0 && (
                <button type="button" className="btn" onClick={() => onChange([])}>Clear</button>
              )}
              <button type="button" className="btn" onClick={() => setOpen(false)}>Done</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
