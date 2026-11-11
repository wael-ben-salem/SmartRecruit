import { useEffect, useState } from 'react'
import { api } from '../api'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'
import { FileText, CheckCircle2, XCircle, AlertTriangle, ShieldCheck, Download, Trash2, ArrowRight } from 'lucide-react'

const STATUS = {
  met: { label: 'Met', cls: 'met' },
  partial: { label: 'Partial', cls: 'partial' },
  missing: { label: 'Not evidenced', cls: 'missing' },
  unverified: { label: 'Unverified claim', cls: 'unverified' },
}

function ScoreRing({ value, size = 88 }) {
  const r = size / 2 - 7
  const c = 2 * Math.PI * r
  let color = 'var(--primary)'
  if (value >= 70) color = 'var(--success)'
  else if (value < 40) color = 'var(--warning)'

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Score ${value} out of 100`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--bg-base)" strokeWidth="8" fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="8" fill="none"
        strokeDasharray={`${(c * value) / 100} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} strokeLinecap="round" style={{ transition: 'stroke-dasharray 1s ease-out' }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" style={{ fontSize: '1.5rem', fontWeight: '700', fill: 'var(--text-main)' }}>{Math.round(value)}</text>
    </svg>
  )
}

function Badge({ status }) {
  const s = STATUS[status] || { label: status, cls: '' }
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

const DECISIONS = [
  ['interview', 'Invite to interview'],
  ['undecided', 'Undecided'],
  ['not_retained', 'Not retained'],
]

function DecisionBox({ runId, candidateId, current, onSaved }) {
  const [note, setNote] = useState(current?.note || '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  
  useEffect(() => { setNote(current?.note || '') }, [candidateId, current])
  
  const save = async (decision) => {
    setBusy(true); setErr('')
    try { onSaved(candidateId, await api.decide(runId, { candidate_id: candidateId, decision, note })) }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }
  
  return (
    <div style={{ background: 'var(--bg-base)', padding: '1.5rem', borderRadius: 'var(--radius)', marginTop: '2rem', border: '1px solid var(--border)' }}>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}><ShieldCheck size={20} color="var(--primary)"/> Recruiter Decision</h3>
      <textarea className="input" rows={2} placeholder="Add a note (why, what to ask in the interview…)" value={note} onChange={(e) => setNote(e.target.value)} style={{ marginBottom: '1rem' }} />
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        {DECISIONS.map(([id, label]) => (
          <button key={id} type="button" disabled={busy} className={current?.decision === id ? 'btn btn-primary' : 'btn'} onClick={() => save(id)}>{label}</button>
        ))}
        {current && <span className="muted small">Recorded {new Date(current.at).toLocaleString()}</span>}
      </div>
      {err && <p className="error" style={{ marginTop: '1rem' }}>{err}</p>}
    </div>
  )
}

export default function Results({ runId, onDeleted }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [decisions, setDecisions] = useState({})

  const remove = async () => {
    if (!window.confirm('Delete this analysis, its CVs, texts and vectors? This cannot be undone.')) return
    try { await api.deleteRun(runId); onDeleted() } catch (e) { setError(e.message) }
  }

  useEffect(() => {
    setData(null)
    api.result(runId).then((d) => { setData(d); setDecisions(d.decisions || {}); setSelected(d.candidates[0]?.candidate_id) }).catch((e) => setError(e.message))
  }, [runId])

  if (error) return <div className="panel"><p className="error">{error}</p></div>
  if (!data) return <div className="panel"><p className="muted">Loading the results…</p></div>

  const reqs = Object.fromEntries(data.job.requirements.map((r) => [r.id, r]))
  const cand = data.candidates.find((c) => c.candidate_id === selected)

  // Préparation des données pour le Radar Chart
  const chartData = cand ? cand.assessments.map(a => {
    const r = reqs[a.requirement_id] || {}
    let score = 0
    if (a.status === 'met') score = 100
    else if (a.status === 'partial') score = 50
    return {
      subject: r.text.length > 25 ? r.text.substring(0, 25) + '...' : r.text,
      score: score,
      fullMark: 100,
      type: r.type
    }
  }) : []

  return (
    <div className="results">
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <p className="muted" style={{ textTransform: 'uppercase', letterSpacing: '1px', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Job Offer</p>
            <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{data.job.title}</h1>
            <p className="muted">{data.job.requirements.filter((r) => r.type === 'must').length} must-have and {data.job.requirements.filter((r) => r.type !== 'must').length} nice-to-have requirements</p>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <a className="btn" href={data.report_url} target="_blank" rel="noreferrer" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Download size={16} /> Full HTML report
            </a>
            <button className="btn danger" onClick={remove} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Trash2 size={16} /> Delete
            </button>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
          <span className="muted small" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><Badge status="met" /> CV proves it</span>
          <span className="muted small" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><Badge status="partial" /> Weaker evidence</span>
          <span className="muted small" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><Badge status="missing" /> Not in CV (ask in interview)</span>
          <span className="muted small" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}><Badge status="unverified" /> Audit rejected</span>
        </div>
      </div>

      <div className="cards">
        {data.candidates.map((c, i) => (
          <button key={c.candidate_id} className={c.candidate_id === selected ? 'card active' : 'card'} onClick={() => setSelected(c.candidate_id)}>
            <span className="rank">#{i + 1}</span>
            <ScoreRing value={c.score} />
            <div style={{ flex: 1, width: '100%' }}>
              <strong title={c.file} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}><FileText size={14} /> {c.file}</strong>
              <span className="muted small" style={{ display: 'block', marginTop: '0.5rem' }}>Must-have met: {c.must_have_met}</span>
              {c.unverified_claims > 0 && <span style={{ display: 'inline-block', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--danger)', background: 'rgba(239, 68, 68, 0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>{c.unverified_claims} unverified</span>}
              {decisions[c.candidate_id] && <span className="badge must" style={{ display: 'inline-block', marginTop: '0.5rem' }}>{DECISIONS.find(([id]) => id === decisions[c.candidate_id].decision)?.[1]}</span>}
            </div>
          </button>
        ))}
      </div>

      {cand && (
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><FileText size={24} color="var(--primary)"/> {cand.file}</h2>
            <span className="muted small">{cand.pages.map((p) => `p.${p.page} ${p.method}`).join(' · ')} · Audit: {cand.audit_rounds.map((r) => r.issues).join(' → ')} issues</span>
          </div>

          {cand.reading_quality?.status === 'check' && (
            <div style={{ background: 'rgba(245, 158, 11, 0.1)', borderLeft: '4px solid var(--warning)', padding: '1rem', borderRadius: '4px', marginBottom: '1.5rem' }}>
              <p style={{ color: 'var(--warning)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={16} /> <strong>Reading quality to check:</strong> {cand.reading_quality.reasons.join('; ')}
              </p>
            </div>
          )}
          
          {cand.must_have_not_evidenced?.length > 0 && (
            <div style={{ background: 'rgba(239, 68, 68, 0.05)', borderLeft: '4px solid var(--danger)', padding: '1rem', borderRadius: '4px', marginBottom: '1.5rem' }}>
              <p style={{ color: 'var(--danger)', fontSize: '0.9rem' }}>
                <strong>Must-haves not evidenced:</strong> {cand.must_have_not_evidenced.map((id) => reqs[id]?.text || id).join(' · ')}
              </p>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '2rem' }}>
            {/* Colonne Gauche : Texte */}
            <div>
              <p style={{ fontSize: '1rem', lineHeight: '1.7', color: 'var(--text-main)', marginBottom: '2rem' }}>{cand.summary}</p>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                <div style={{ background: 'rgba(16, 185, 129, 0.05)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                  <h3 style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}><CheckCircle2 size={18}/> Strengths</h3>
                  <ul style={{ paddingLeft: '1.5rem', fontSize: '0.9rem', lineHeight: '1.6' }}>{cand.strengths.map((s, i) => <li key={i} style={{ marginBottom: '0.5rem' }}>{s}</li>)}</ul>
                </div>
                <div style={{ background: 'rgba(239, 68, 68, 0.05)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  <h3 style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}><XCircle size={18}/> Gaps</h3>
                  <ul style={{ paddingLeft: '1.5rem', fontSize: '0.9rem', lineHeight: '1.6' }}>{cand.gaps.map((s, i) => <li key={i} style={{ marginBottom: '0.5rem' }}>{s}</li>)}</ul>
                </div>
              </div>
            </div>

            {/* Colonne Droite : Radar Chart */}
            <div>
              <h3 style={{ marginBottom: '1rem', textAlign: 'center' }}>Competency Radar</h3>
              <div style={{ height: '300px', background: 'var(--bg-base)', borderRadius: 'var(--radius)', padding: '1rem', border: '1px solid var(--border)' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar name="Score" dataKey="score" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.4} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <DecisionBox runId={runId} candidateId={cand.candidate_id} current={decisions[cand.candidate_id]}
            onSaved={(id, d) => setDecisions({ ...decisions, [id]: d })} />

          <h3 style={{ marginTop: '2rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Detailed Requirement Breakdown</h3>
          <div className="reqs">
            {cand.assessments.map((a) => {
              const r = reqs[a.requirement_id] || {}
              const quotes = (a.evidence || []).filter((e) => e.found !== false)
              return (
                <div className="req" key={a.requirement_id}>
                  <div className="req-head">
                    <Badge status={a.status} />
                    <span style={{ fontSize: '0.75rem', fontWeight: '600', textTransform: 'uppercase', color: r.type === 'must' ? 'var(--primary)' : 'var(--text-muted)', background: r.type === 'must' ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-panel)', padding: '0.2rem 0.6rem', borderRadius: '12px' }}>
                      {r.type === 'must' ? 'Must-have' : 'Nice-to-have'}
                    </span>
                    <strong style={{ flex: 1 }}>{r.text}</strong>
                  </div>
                  {a.reasoning && <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>{a.reasoning}</p>}
                  {quotes.map((e, i) => (
                    <blockquote key={i}>“{e.quote}” <span className="pg">page {e.page ?? '?'}</span></blockquote>
                  ))}
                  {a.audit && a.audit !== 'verified' && a.audit !== 'n/a' && (
                    <p style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <AlertTriangle size={14} /> Audit: {a.audit}{a.original_status ? ` (was ${a.original_status})` : ''} {a.audit_comment}
                    </p>
                  )}
                  {a.audit === 'verified' && <p className="ok" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={14} /> Evidence verified in the CV</p>}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {data.candidates.length > 1 && (
        <div className="panel">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}><ArrowRight size={20} color="var(--primary)"/> Side-by-side comparison</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                  <th style={{ padding: '1rem', fontWeight: '600', color: 'var(--text-muted)' }}>Requirement</th>
                  {data.candidates.map((c) => (
                    <th key={c.candidate_id} style={{ padding: '1rem', fontWeight: '600', textAlign: 'center' }} title={c.file}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                        <FileText size={16} color="var(--primary)" />
                        <span>{c.file.length > 15 ? c.file.substring(0,15)+'...' : c.file}</span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{c.score} / 100</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.job.requirements.map((r) => (
                  <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: '700', textTransform: 'uppercase', color: r.type === 'must' ? 'var(--primary)' : 'var(--text-muted)' }}>{r.type === 'must' ? 'Must-have' : 'Nice-to-have'}</span>
                      <span>{r.text}</span>
                    </td>
                    {data.candidates.map((c) => {
                      const a = c.assessments.find((x) => x.requirement_id === r.id)
                      return <td key={c.candidate_id} style={{ padding: '1rem', textAlign: 'center' }}>{a ? <Badge status={a.status} /> : '–'}</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="hint" style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.75rem' }}>Models used {data.meta.models.join(', ')} · chunking {data.meta.chunking} · top-k {data.meta.top_k} · prompts {Object.entries(data.meta.prompts).map(([a, v]) => `${a} ${v}`).join(', ')} · run {data.run_id}</p>
    </div>
  )
}