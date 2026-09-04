/**
 * Dark War Survival server time.
 *
 * The game announces everything against one clock, two hours behind UTC.
 * The alliance's anchor is 00:00 ST = 11:00 KST, which says the same thing:
 * KST is UTC+9, so ST is UTC+9-11 = UTC-2.
 *
 * The Etc zones invert the sign, so "Etc/GMT+2" is UTC-02:00. It has no
 * daylight saving, matching the game.
 */

export const SERVER_TZ = 'Etc/GMT+2'

const opts = (extra) => ({ timeZone: SERVER_TZ, ...extra })

/** "13:30 ST" — no date, for pairing beside a local time on the same line. */
export const fmtServerTime = (iso) =>
  `${new Intl.DateTimeFormat(undefined, opts({ hour: '2-digit', minute: '2-digit', hour12: false })).format(new Date(iso))} ST`

/** "Sat 5 Sep, 13:30 ST" — when the ST date can differ from the local one. */
export const fmtServerFull = (iso) =>
  `${new Intl.DateTimeFormat(undefined, opts({
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: false,
  })).format(new Date(iso))} ST`

/**
 * True when a moment falls on a different calendar day in server time than
 * locally. A KST evening is the same ST afternoon, but anything after 11:00
 * KST has already rolled over — so the date has to be shown, not just the
 * time, or "13:30 ST" beside "Sun 00:30" looks like a mistake.
 */
export function crossesServerDay(iso) {
  const d = new Date(iso)
  const local = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit' })
  const server = new Intl.DateTimeFormat('en-CA', opts({ year: 'numeric', month: '2-digit', day: '2-digit' }))
  return local.format(d) !== server.format(d)
}

/** The pairing used throughout the UI: local time, with ST alongside. */
export const withServerTime = (iso) =>
  crossesServerDay(iso) ? fmtServerFull(iso) : fmtServerTime(iso)
