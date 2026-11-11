import { Loader2, CheckCircle2 } from 'lucide-react'

const STEPS = [
  ['read', 'Read PDF'],
  ['anonymize', 'Anonymize'],
  ['cv_agent', 'CV agent'],
  ['index', 'Index'],
  ['matching_agent', 'Matching'],
  ['audit_agent', 'Audit'],
]

export default function Progress({ status }) {
  if (status.status === 'error') {
    return (
      <div className="panel">
        <h1 style={{ color: 'var(--danger)' }}>Analysis failed</h1>
        <p className="error">{status.error}</p>
        <p className="muted" style={{ marginTop: '1rem' }}>Each step's output is kept in data/runs/{status.run_id}/.</p>
      </div>
    )
  }
  
  const jobDone = (status.events || []).some((e) => e.step === 'job_agent') || status.progress > 0.2
  
  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '3rem 2rem' }}>
      <Loader2 size={48} className="spin" style={{ color: 'var(--primary)', marginBottom: '1.5rem' }} />
      <h1>Analyzing Candidates…</h1>
      <p className="muted" style={{ marginBottom: '2rem', textAlign: 'center', maxWidth: '400px' }}>
        The agents are working their magic. This takes a few minutes per CV depending on the model.
      </p>
      
      <div style={{ width: '100%', maxWidth: '600px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          <span>Progress</span>
          <span>{Math.round(status.progress * 100)}%</span>
        </div>
        <div style={{ height: '8px', background: 'var(--bg-base)', borderRadius: '4px', overflow: 'hidden', marginBottom: '2rem' }}>
          <div style={{ height: '100%', background: 'var(--primary)', width: `${Math.max(4, status.progress * 100)}%`, transition: 'width 0.5s ease-out' }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.8rem 1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <span style={{ fontWeight: '600' }}>Job Offer Analysis</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: jobDone ? 'var(--success)' : 'var(--text-muted)', fontSize: '0.9rem' }}>
              {jobDone ? <><CheckCircle2 size={16} /> Done</> : <><Loader2 size={16} className="spin" /> In progress</>}
            </span>
          </div>
          
          {(status.candidates || []).map((c) => (
            <div key={c.candidate_id} style={{ padding: '1rem', background: 'var(--bg-base)', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: '600', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {c.file}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {STEPS.map(([id, label]) => {
                  const isDone = c.done.includes(id)
                  return (
                    <span key={id} style={{ 
                      display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.3rem 0.6rem', borderRadius: '20px', fontSize: '0.75rem', fontWeight: '500',
                      background: isDone ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-panel)', 
                      color: isDone ? 'var(--success)' : 'var(--text-muted)',
                      border: `1px solid ${isDone ? 'rgba(16, 185, 129, 0.3)' : 'var(--border)'}`
                    }}>
                      {isDone && <CheckCircle2 size={12} />} {label}
                    </span>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    </div>
  )
}