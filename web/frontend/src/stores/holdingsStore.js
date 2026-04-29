import { reactive } from 'vue'
import { api } from '../api.js'

export const holdingsStore = reactive({
  holdings: [],

  async loadHoldings() {
    this.holdings = await api.getHoldings()
  },

  async addHolding(ticker, name, quantity, costPrice, notes = '') {
    await api.addHolding(ticker, name, quantity, costPrice, notes)
    await this.loadHoldings()
  },

  async updateHolding(id, quantity, costPrice, notes = '') {
    await api.updateHolding(id, quantity, costPrice, notes)
    await this.loadHoldings()
  },

  async removeHolding(id) {
    await api.removeHolding(id)
    await this.loadHoldings()
  },
})
