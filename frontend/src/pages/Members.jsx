import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'

export default function Members() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [editing, setEditing] = useState(null)

  const refresh = () => api.listMembers().then(setRows).catch((e) => setError(e.message))
  useEffect(() => { refresh() }, [])

  async function sync() {
    setError(null)
    try {
      const result = await api.syncMembers()
      setNotice(`Imported ${result.added} new member(s) from ${result.guild_members} in the server.`)
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function save(row) {
    try {
      await api.updateMember(row.id, {
        game_name: row.game_name,
        rank: row.rank ? Number(row.rank) : null,
        power: row.power ? Number(row.power) : null,
        active: row.active,
      })
      setEditing(null)
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>Roster ({rows.length})</h2>
        <button className="btn primary" onClick={sync}>Import from Discord</button>
      </div>

      {error && <div className="banner error">{error}</div>}
      {notice && <div className="banner ok">{notice}</div>}

      <table className="table">
        <thead>
          <tr><th>In-game name</th><th>Discord</th><th>Rank</th><th>Power</th><th></th></tr>
        </thead>
        <tbody>
          {rows.map((row) =>
            editing?.id === row.id ? (
              <tr key={row.id}>
                <td><input value={editing.game_name ?? ''} onChange={(e) => setEditing({ ...editing, game_name: e.target.value })} /></td>
                <td className="muted">{row.discord_name}</td>
                <td><input type="number" min="1" max="5" value={editing.rank ?? ''} onChange={(e) => setEditing({ ...editing, rank: e.target.value })} /></td>
                <td><input type="number" min="0" value={editing.power ?? ''} onChange={(e) => setEditing({ ...editing, power: e.target.value })} /></td>
                <td className="row">
                  <button className="btn primary" onClick={() => save(editing)}>Save</button>
                  <button className="btn" onClick={() => setEditing(null)}>Cancel</button>
                </td>
              </tr>
            ) : (
              <tr key={row.id}>
                <td><strong>{row.game_name ?? '—'}</strong></td>
                <td className="muted">{row.discord_name}</td>
                <td>{row.rank ? `R${row.rank}` : '—'}</td>
                <td>{row.power ? row.power.toLocaleString() : '—'}</td>
                <td><button className="btn" onClick={() => setEditing(row)}>Edit</button></td>
              </tr>
            ),
          )}
        </tbody>
      </table>

      {rows.length === 0 && (
        <p className="muted">
          Nobody on the roster yet. Use “Import from Discord”, or ask members to run
          <code> /roster register</code>.
        </p>
      )}
    </div>
  )
}
