import { useState } from 'react'
import { api } from '../api'
import { UploadCloud, Link as LinkIcon, FileText, Type, X } from 'lucide-react'

const SOURCES = [
  { id: 'url', label: 'Job link', icon: <LinkIcon size={16} /> },
  { id: 'text', label: 'Paste text', icon: <Type size={16} /> },
  { id: 'file', label: 'File', icon: <FileText size={16} /> },
]

export default function NewRun({ onStarted }) {
  const [source, setSource] = useState('url')
  const [jobUrl, setJobUrl] = useState('')
  const [jobText, setJobText] = useState('')
  const [jobFile, setJobFile] = useState(null)
  const [cvs, setCvs] = useState([])
  const [mode, setMode] = useState('n8n')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)

  const addFiles = (list) => {
    const pdfs = [...list].filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setCvs((prev) => [...prev, ...pdfs.filter((f) => !prev.some((p) => p.name === f.name))])
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!cvs.length) return setError('Add at least one CV (PDF).')
    const fd = new FormData()
    if (source === 'url') fd.append('job_url', jobUrl)
    if (source === 'text') fd.append('job_text', jobText)
    if (source === 'file' && jobFile) fd.append('job_file', jobFile)
    cvs.forEach((f) => fd.append('cvs', f))
    fd.append('mode', mode)
    setBusy(true)
    try {
      const { run_id } = await api.startRun(fd)
      onStarted(run_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h1>New Analysis</h1>
      <p className="muted" style={{ marginBottom: '2rem' }}>Give the job offer, add CVs, and get explainable results.</p>

      <section className="field">
        <h3>1. Job Offer</h3>
        <div className="tabs" role="tablist">
          {SOURCES.map((s) => (
            <button type="button" key={s.id} role="tab" aria-selected={source === s.id}
              className={source === s.id ? 'tab active' : 'tab'} onClick={() => setSource(s.id)}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {s.icon} {s.label}
            </button>
          ))}
        </div>
        {source === 'url' && (
          <>
            <input className="input" type="url" placeholder="https://… (job board or company career page)"
              value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} required />
            <p className="hint" style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Works with public pages. If the page requires login, paste the text instead.</p>
          </>
        )}
        {source === 'text' && (
          <textarea className="input" rows={8} placeholder="Paste the full job description here"
            value={jobText} onChange={(e) => setJobText(e.target.value)} required />
        )}
        {source === 'file' && (
          <input className="input" type="file" accept=".pdf,.txt" onChange={(e) => setJobFile(e.target.files[0])} required style={{ padding: '0.5rem' }} />
        )}
      </section>

      <section className="field">
        <h3>2. Candidate CVs</h3>
        <label className={dragging ? 'drop dragging' : 'drop'}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}>
          <input type="file" accept=".pdf" multiple hidden onChange={(e) => addFiles(e.target.files)} />
          <UploadCloud size={48} color="var(--primary)" style={{ marginBottom: '1rem' }} />
          <strong>Drop CV PDFs here</strong> or click to browse
          <span className="hint" style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Any layout. Scanned or two-column CVs are read by the vision model.</span>
        </label>
        {cvs.length > 0 && (
          <ul style={{ marginTop: '1rem', listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {cvs.map((f) => (
              <li key={f.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-panel)', padding: '0.5rem 1rem', borderRadius: '8px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}><FileText size={16} color="var(--primary)" /> {f.name}</span>
                <button type="button" style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }} onClick={() => setCvs(cvs.filter((x) => x !== f))}><X size={18} /></button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="field row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
        <label className="check" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
          <input type="checkbox" checked={mode === 'n8n'} onChange={(e) => setMode(e.target.checked ? 'n8n' : 'direct')} style={{ width: '1rem', height: '1rem' }} />
          Run through n8n workflow
        </label>
        <button className="btn btn-primary" disabled={busy} style={{ padding: '0.8rem 2rem', fontSize: '1rem' }}>
          {busy ? 'Starting…' : 'Analyse Candidates'}
        </button>
      </section>
      {error && <p className="error" role="alert" style={{ marginTop: '1rem' }}>{error}</p>}
    </form>
  )
}