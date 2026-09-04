import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import Banner from '../components/Banner.jsx'

/**
 * A four-column table cannot be read at 360px without sideways scrolling, so
 * below the breakpoint each member becomes a card instead. Both render the
 * same data and share the same edit form.
 */
function useIsNarrow(query = '(max-width: 640px)') {
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  )
  useEffect(() => {
    const mq = window.matchMedia(query)
    const on = (e) => setNarrow(e.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [query])
  return narrow
}

export default function Members() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(false)
  const narrow = useIsNarrow()

  const refresh = () => api.listMembers().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { refresh() }, [])

  async function sync() {
    setError(null)
    setBusy(true)
    try {
      const result = await api.syncMembers()
      setNotice(`Imported ${result.added} new member(s) from ${result.guild_members} in the server.`)
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function save(row) {
    setBusy(true)
    try {
      const saved = await api.updateMember(row.id, {
        game_name: row.game_name,
        rank: row.rank ? Number(row.rank) : null,
        power: row.power ? Number(row.power) : null,
        active: row.active,
      })
      setRows((rs) => rs.map((r) => (r.id === saved.id ? saved : r)))
      setEditing(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const editor = (row) => (
    <div className="grid" style={{ gap: 10 }}>
      <label>
        In-game name
        <input
          value={editing.game_name ?? ''}
          onChange={(e) => setEditing({ ...editing, game_name: e.target.value })}
        />
      </label>
      <label>
        Rank
        <input
          type="number" inputMode="numeric" min="1" max="5"
          value={editing.rank ?? ''}
          onChange={(e) => setEditing({ ...editing, rank: e.target.value })}
        />
      </label>
      <label>
        Power
        <input
          type="number" inputMode="numeric" min="0"
          value={editing.power ?? ''}
          onChange={(e) => setEditing({ ...editing, power: e.target.value })}
        />
      </label>
      <div className="row">
        <button className="btn primary" disabled={busy} onClick={() => save(editing)}>
          {busy ? 'Saving…' : 'Save'}
        </button>
        <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
      </div>
    </div>
  )

  return (
    <div className="page">
      <div className="page-head">
        <h2>Roster ({rows.length})</h2>
        <button className="btn primary" onClick={sync} disabled={busy}>
          {busy ? 'Working…' : 'Import from Discord'}
        </button>
      </div>

      <Banner tone="error" onDismiss={() => setError(null)}>{error}</Banner>
      <Banner tone="ok" onDismiss={() => setNotice(null)}>{notice}</Banner>

      {narrow ? (
        <div className="roster-cards">
          {rows.map((row) => (
            <div key={row.id} className="roster-card">
              {editing?.id === row.id ? editor(row) : (
                <>
                  <div className="top">
                    <span className="name">{row.game_name ?? '—'}</span>
                    <span className="pill">{row.rank ? `R${row.rank}` : 'no rank'}</span>
                  </div>
                  <div className="facts">
                    <span className="power">
                      {row.power ? row.power.toLocaleString() : <span className="muted">no power set</span>}
                    </span>
                    <button className="btn small" onClick={() => setEditing(row)}>Edit</button>
                  </div>
                  <div className="handle muted">{row.discord_name}</div>
                </>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr><th>In-game name</th><th>Discord</th><th>Rank</th><th>Power</th><th /></tr>
            </thead>
            <tbody>
              {rows.map((row) =>
                editing?.id === row.id ? (
                  <tr key={row.id}>
                    <td colSpan="5">{editor(row)}</td>
                  </tr>
                ) : (
                  <tr key={row.id}>
                    <td><strong>{row.game_name ?? '—'}</strong></td>
                    <td className="muted">{row.discord_name}</td>
                    <td>{row.rank ? `R${row.rank}` : '—'}</td>
                    <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {row.power ? row.power.toLocaleString() : '—'}
                    </td>
                    <td>
                      <button className="btn small" onClick={() => setEditing(row)}>Edit</button>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

      {rows.length === 0 && (
        <p className="muted">
          Nobody on the roster yet. Use “Import from Discord”, or ask members to run
          <code> /roster register</code>.
        </p>
      )}
    </div>
  )
}
