/** API client with unified error handling and toast notifications. */

import { showError, showWarning, showInfo } from './stores/toastStore.js'

const API_BASE = import.meta.env.VITE_API_BASE || ''

// ── Error Parsing Utilities ────────────────────────────────────────────────────

/**
 * Parse error response from backend.
 * Backend returns: { error_code, message, detail }
 */
async function parseErrorResponse(res) {
  try {
    const text = await res.text()
    // Try to parse as JSON
    try {
      const data = JSON.parse(text)
      return {
        error_code: data.error_code || 'UNKNOWN',
        message: data.message || '请求失败',
        detail: data.detail || text,
        status_code: res.status,
      }
    } catch {
      // Not JSON, use raw text
      return {
        error_code: 'HTTP_ERROR',
        message: `请求失败 (${res.status})`,
        detail: text,
        status_code: res.status,
      }
    }
  } catch {
    return {
      error_code: 'NETWORK_ERROR',
      message: '网络连接失败',
      detail: '无法连接到服务器',
      status_code: 0,
    }
  }
}

/**
 * Get user-friendly message for common error codes.
 */
function getUserMessage(error) {
  const friendlyMessages = {
    'TASK_NOT_FOUND': '任务不存在，可能已被删除',
    'TASK_NOT_RUNNING': '任务不在运行状态',
    'LLM_ERROR': 'AI 模型服务暂时不可用',
    'LLM_TIMEOUT': 'AI 模型响应超时',
    'DATA_SOURCE_ERROR': '数据获取失败，请稍后重试',
    'DATA_SOURCE_TIMEOUT': '数据获取超时',
    'VALIDATION_ERROR': '请求参数无效',
    'EMPTY_WATCHLIST': '自选股列表为空',
    'STOCK_NOT_FOUND': '股票不存在',
    'INTERNAL_ERROR': '服务内部错误',
  }
  return friendlyMessages[error.error_code] || error.message || '操作失败'
}

// ── HTTP Methods with Error Handling ──────────────────────────────────────────

async function post(url, body) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const error = await parseErrorResponse(res)
    showError(getUserMessage(error))
    throw new Error(error.message)
  }

  return res.json()
}

async function get(url) {
  const res = await fetch(`${API_BASE}${url}`)

  if (!res.ok) {
    const error = await parseErrorResponse(res)
    showError(getUserMessage(error))
    throw new Error(error.message)
  }

  return res.json()
}

async function put(url, body) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const error = await parseErrorResponse(res)
    showError(getUserMessage(error))
    throw new Error(error.message)
  }

  return res.json()
}

async function del(url) {
  const res = await fetch(`${API_BASE}${url}`, { method: 'DELETE' })

  if (!res.ok) {
    const error = await parseErrorResponse(res)
    showError(getUserMessage(error))
    throw new Error(error.message)
  }

  return res.json()
}

// ── SSE Stream with Error Handling ─────────────────────────────────────────────

export const api = {
  startAnalysis: async (payload) => {
    try {
      const result = await post('/api/analyze/start', payload)
      showInfo(`分析任务已启动: ${payload.ticker}`)
      return result
    } catch (e) {
      throw e
    }
  },

  getStatus: (taskId) => get(`/api/analyze/${taskId}/status`),
  cancelAnalysis: async (taskId) => {
    try {
      const result = await post(`/api/analyze/${taskId}/cancel`, {})
      showInfo('分析任务已取消')
      return result
    } catch (e) {
      throw e
    }
  },
  getResult: (taskId) => get(`/api/analyze/${taskId}/result`),
  getHistory: (limit = 50, offset = 0) => get(`/api/history?limit=${limit}&offset=${offset}`),
  getHistoryDetail: (taskId) => get(`/api/history/${taskId}`),
  getConfig: () => get('/api/config'),

  streamEvents: (taskId, onEvent, onError, onComplete) => {
    const url = `${API_BASE}/api/analyze/${taskId}/events`
    const es = new EventSource(url)

    // SSE with named events: "event: agent_start\ndata: {...}\n\n"
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
        if (type === 'completed') {
          showInfo('分析完成')
          es.close()
          if (onComplete) onComplete()
        }
        if (type === 'failed') {
          const errorMsg = data.error || '分析失败'
          showError(errorMsg)
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

    // Connection error handling
    es.onerror = (err) => {
      console.error('SSE connection error', err)
      // Show warning for connection issues
      showWarning('分析连接中断，正在尝试恢复...', { duration: 3000 })
      if (onError) onError(err)
    }

    return () => es.close()
  },

  // ── Stock Search ─────────────────────────────────────────────────
  searchStocks: (query, limit = 20) => get(`/api/stocks/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  // ── Watchlist ────────────────────────────────────────────────
  getWatchlist: (enabledOnly = false) => get(`/api/watchlist?enabled_only=${enabledOnly}`),
  addStock: async (ticker, name = '') => {
    try {
      const result = await post('/api/watchlist', { ticker, name })
      showInfo(`已添加 ${ticker} 到自选股`)
      return result
    } catch (e) {
      throw e
    }
  },
  removeStock: async (id) => {
    try {
      const result = await del(`/api/watchlist/${id}`)
      showInfo('已移除自选股')
      return result
    } catch (e) {
      throw e
    }
  },
  updateStock: async (id, enabled) => {
    try {
      const result = await put(`/api/watchlist/${id}`, { enabled })
      return result
    } catch (e) {
      throw e
    }
  },

  // ── Schedule ─────────────────────────────────────────────────
  getSchedule: () => get('/api/schedule'),
  updateSchedule: async (body) => {
    try {
      const result = await put('/api/schedule', body)
      showInfo('定时配置已保存')
      return result
    } catch (e) {
      throw e
    }
  },
  getSchedulerStatus: () => get('/api/scheduler/status'),

  // ── Batch ────────────────────────────────────────────────────
  startBatch: async () => {
    try {
      const result = await post('/api/batch/start', {})
      showInfo(`批量分析已启动 (${result.total_stocks}只股票)`)
      return result
    } catch (e) {
      throw e
    }
  },
  getBatchRuns: (limit = 50, offset = 0) => get(`/api/batch/runs?limit=${limit}&offset=${offset}`),
  getBatchRun: (batchId) => get(`/api/batch/runs/${batchId}`),

  // ── Holdings (持仓) ──────────────────────────────────────────
  getHoldings: () => get('/api/holdings'),
  addHolding: async (ticker, name, quantity, costPrice, notes = '') => {
    try {
      const result = await post('/api/holdings', { ticker, name, quantity, cost_price: costPrice, notes })
      showInfo(`已添加 ${ticker} 持仓`)
      return result
    } catch (e) {
      throw e
    }
  },
  updateHolding: async (id, quantity, costPrice, notes = '') => {
    try {
      const result = await put(`/api/holdings/${id}`, { quantity, cost_price: costPrice, notes })
      showInfo('持仓已更新')
      return result
    } catch (e) {
      throw e
    }
  },
  removeHolding: async (id) => {
    try {
      const result = await del(`/api/holdings/${id}`)
      showInfo('持仓已删除')
      return result
    } catch (e) {
      throw e
    }
  },

  // ── Recommendations (股票推荐) ───────────────────────────────────
  getLatestRecommendations: () => get('/api/recommend/latest'),
  getLatestByMode: (mode) => get(`/api/recommend/latest/${mode}`),
  getRecommendHistory: (params) => get(`/api/recommend/history?${params}`),
  getDailyRecommend: (params) => get(`/api/recommend/daily?${params}`),
  getWeeklyRecommend: (params) => get(`/api/recommend/weekly?${params}`),
  getTopGainers: (params) => get(`/api/recommend/top?${params}`),
  getThemes: (params) => get(`/api/recommend/themes?${params}`),
}