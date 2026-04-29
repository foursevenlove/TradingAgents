/** Toast notification state management.
 *
 * Provides:
 * - showSuccess(), showError(), showWarning(), showInfo()
 * - Auto-dismiss after configurable duration
 * - Manual dismiss by ID
 */

import { reactive } from 'vue'

class ToastStore {
  constructor() {
    this.toasts = reactive([])
    this.nextId = 1
    this.defaultDuration = 3000 // 3 seconds
  }

  show(type, message, options = {}) {
    const id = this.nextId++
    const duration = options.duration ?? this.defaultDuration

    const toast = {
      id,
      type,
      message,
      title: options.title,
      duration,
    }

    this.toasts.push(toast)

    // Auto-dismiss after duration
    if (duration > 0) {
      setTimeout(() => {
        this.dismiss(id)
      }, duration)
    }

    return id
  }

  success(message, options = {}) {
    return this.show('success', message, options)
  }

  error(message, options = {}) {
    // Errors stay longer by default (5 seconds)
    return this.show('error', message, { ...options, duration: options.duration ?? 5000 })
  }

  warning(message, options = {}) {
    return this.show('warning', message, options)
  }

  info(message, options = {}) {
    return this.show('info', message, options)
  }

  dismiss(id) {
    const index = this.toasts.findIndex(t => t.id === id)
    if (index !== -1) {
      this.toasts.splice(index, 1)
    }
  }

  clear() {
    this.toasts.splice(0, this.toasts.length)
  }
}

// Global singleton
export const toastStore = new ToastStore()

// Convenience exports
export const showSuccess = toastStore.success.bind(toastStore)
export const showError = toastStore.error.bind(toastStore)
export const showWarning = toastStore.warning.bind(toastStore)
export const showInfo = toastStore.info.bind(toastStore)