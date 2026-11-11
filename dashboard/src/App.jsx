import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import NewRun from './components/NewRun'
import Progress from './components/Progress'
import Results from './components/Results'
import History from './components/History'
import { Sparkles, UserCircle } from 'lucide-react'

function runFromHash() {
  const m = window.location.hash.match(/run=([\w-]+)/)
  return m ? m[1] : null
}

export default function App() {
  const [runId, setRunId] = useState(runFromHash())
  const [status, setStatus] = useState(null)
  const [runs, setRuns] = useState([])

  const refreshRuns = useCallback(() => api.listRuns().then(setRuns).catch(() => {}), [])
  useEffect(() => { refreshRuns() }, [refreshRuns])

  useEffect(() => {
    const onHash = () => setRunId(runFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    if (!runId) { setStatus(null); return }
    let stop = false
    const tick = async () => {
      try {
        const s = await api.status(runId)
        if (stop) return
        setStatus(s)
        if (s.status === 'running' || (s.status === 'unknown' && !s.progress)) setTimeout(tick, 3000)
        else refreshRuns()
      } catch {
        if (!stop) setStatus({ status: 'error', error: 'Run not found' })
      }
    }
    tick()
    return () => { stop = true }
  }, [runId, refreshRuns])

  const open = (id) => { window.location.hash = id ? `run=${id}` : '' ; setRunId(id) }
  const finished = status && (status.status === 'done' || (status.status === 'unknown' && status.progress === 1))

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand" onClick={() => open(null)}>
          Smart<span>Recruit</span>
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <p className="tagline" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles size={16} color="var(--primary)" /> The AI recommends, the recruiter decides.
          </p>
          <UserCircle size={28} color="var(--text-muted)" style={{ cursor: 'pointer' }} />
        </div>
      </header>
      <div className="layout">
        <aside className="sidebar">
          <button className="btn btn-primary wide" onClick={() => open(null)} style={{ marginBottom: '1rem' }}>
            + New analysis
          </button>
          <History runs={runs} current={runId} onOpen={open} />
        </aside>
        <main className="content">
          {!runId && <NewRun onStarted={(id) => { open(id); refreshRuns() }} />}
          {runId && status && !finished && <Progress status={status} />}
          {runId && finished && <Results runId={runId} onDeleted={() => { open(null); refreshRuns() }} />}
        </main>
      </div>
    </div>
  )
}