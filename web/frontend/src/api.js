const API_BASE = import.meta.env.VITE_API_BASE || ''

async function post(url, body) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function get(url) {
  const res = await fetch(`${API_BASE}${url}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  startAnalysis: (payload) => post('/api/analyze/start', payload),
  getStatus: (taskId) => get(`/api/analyze/${taskId}/status`),
  cancelAnalysis: (taskId) => fetch(`${API_BASE}/api/analyze/${taskId}/cancel`, { method: 'POST' }).then(r => r.json()),
  getResult: (taskId) => get(`/api/analyze/${taskId}/result`),
  getHistory: (limit = 50, offset = 0) => get(`/api/history?limit=${limit}&offset=${offset}`),
  getHistoryDetail: (taskId) => get(`/api/history/${taskId}`),
  getConfig: () => get('/api/config'),
  streamEvents: (taskId, onEvent, onError, onComplete) => {
    const url = `${API_BASE}/api/analyze/${taskId}/events`
    const es = new EventSource(url)

    // SSE with named events: "event: agent_start\ndata: {...}\n\n"
    // These arrive as custom events, not the default 'message' event
    const EVENT_TYPES = [
      'started','agent_start','agent_output','agent_end',
      'tool_call','tool_result','debate_speech','debate_judge',
      'trader_plan','final_decision','report_complete','stats',
      'completed','failed',
    ]

    function handleEvent(type, e) {
      try {
        const data = JSON.parse(e.data)
        onEvent({ type, data })
        if (type === 'completed' || type === 'failed') {
          es.close()
          if (onComplete) onComplete()
        }
      } catch (err) {
        console.error('SSE parse error', err)
      }
    }

    // Register listener for each named event type
    EVENT_TYPES.forEach(type => {
      es.addEventListener(type, (e) => handleEvent(type, e))
    })

    // Fallback for unnamed messages
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const type = data.type || 'unknown'
        onEvent({ type, data })
      } catch (err) {
        console.error('SSE parse error', err)
      }
    }

    es.onerror = (err) => {
      if (onError) onError(err)
    }
    return () => es.close()
  },

  // ── Stock Search ─────────────────────────────────────────────────
  searchStocks: (query, limit = 20) => get(`/api/stocks/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  // ── Watchlist ────────────────────────────────────────────────
  getWatchlist: (enabledOnly = false) => get(`/api/watchlist?enabled_only=${enabledOnly}`),
  addStock: (ticker, name = '') => post('/api/watchlist', { ticker, name }),
  removeStock: (id) => fetch(`${API_BASE}/api/watchlist/${id}`, { method: 'DELETE' }).then(r => r.json()),
  updateStock: (id, enabled) => fetch(`${API_BASE}/api/watchlist/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  }).then(r => r.json()),

  // ── Schedule ─────────────────────────────────────────────────
  getSchedule: () => get('/api/schedule'),
  updateSchedule: (body) => fetch(`${API_BASE}/api/schedule`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json()),
  getSchedulerStatus: () => get('/api/scheduler/status'),

  // ── Batch ────────────────────────────────────────────────────
  startBatch: () => post('/api/batch/start', {}),
  getBatchRuns: (limit = 50, offset = 0) => get(`/api/batch/runs?limit=${limit}&offset=${offset}`),
  getBatchRun: (batchId) => get(`/api/batch/runs/${batchId}`),
}
