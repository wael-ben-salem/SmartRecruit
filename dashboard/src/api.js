async function call(path, options) {
  const r = await fetch(path, options)
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail || `${r.status} ${r.statusText}`)
  return body
}

export const api = {
  startRun: (formData) => call('/api/runs', { method: 'POST', body: formData }),
  listRuns: () => call('/api/runs'),
  status: (runId) => call(`/api/runs/${runId}/status`),
  result: (runId) => call(`/api/runs/${runId}/result`),
  deleteRun: (runId) => call(`/api/runs/${runId}`, { method: 'DELETE' }),
  decide: (runId, body) => call(`/api/runs/${runId}/decisions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
}
