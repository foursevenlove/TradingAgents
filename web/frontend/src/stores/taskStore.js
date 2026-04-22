import { reactive } from 'vue'

export const taskStore = reactive({
  currentTaskId: null,
  events: [],
  status: null,
  result: null,
  isConnected: false,

  reset() {
    this.currentTaskId = null
    this.events = []
    this.status = null
    this.result = null
    this.isConnected = false
  },

  addEvent(event) {
    this.events.push(event)
  },

  setTaskId(id) {
    this.currentTaskId = id
  },

  setStatus(status) {
    this.status = status
  },

  setResult(result) {
    this.result = result
  },
})
