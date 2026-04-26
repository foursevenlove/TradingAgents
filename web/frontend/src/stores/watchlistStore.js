import { reactive } from 'vue'
import { api } from '../api.js'

export const watchlistStore = reactive({
  stocks: [],
  schedule: {
    enabled: false,
    cron_expression: '0 9 * * 1-5',
    max_concurrency: 2,
    config: {},
    next_run_at: null,
    last_run_at: null,
  },
  schedulerStatus: { running: false, enabled: false },

  async loadStocks() {
    this.stocks = await api.getWatchlist()
  },

  async loadSchedule() {
    this.schedule = await api.getSchedule()
  },

  async loadSchedulerStatus() {
    this.schedulerStatus = await api.getSchedulerStatus()
  },

  async addStock(ticker, name = '') {
    await api.addStock(ticker, name)
    await this.loadStocks()
  },

  async removeStock(id) {
    await api.removeStock(id)
    await this.loadStocks()
  },

  async toggleStock(id, enabled) {
    await api.updateStock(id, enabled)
    await this.loadStocks()
  },

  async updateSchedule(body) {
    this.schedule = await api.updateSchedule(body)
    await this.loadSchedulerStatus()
  },
})
