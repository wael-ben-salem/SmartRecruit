import { Clock, FileText, CheckCircle2, AlertCircle } from 'lucide-react'

export default function History({ runs, current, onOpen }) {
  if (!runs.length) return <p className="hint">No analysis yet.</p>
  
  return (
    <nav className="history" aria-label="Previous analyses">
      <h3 style={{ marginBottom: '1rem', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '1px' }}>Recent History</h3>
      <ul className="history-list">
        {runs.map((r) => (
          <li key={r.run_id}>
            <button className={r.run_id === current ? 'hist active' : 'hist'} onClick={() => onOpen(r.run_id)}>
              <span className="t">{r.title || 'Untitled offer'}</span>
              <span className="m">
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <FileText size={12} /> {r.cvs} CV{r.cvs > 1 ? 's' : ''}
                </span>
                <span>·</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: r.status === 'done' ? 'var(--success)' : 'var(--warning)' }}>
                  {r.status === 'done' ? <CheckCircle2 size={12} /> : <Clock size={12} />} 
                  {r.status}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}