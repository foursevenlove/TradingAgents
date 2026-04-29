<template>
  <div class="max-w-5xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">持仓管理</h1>

    <!-- Add holding form with search -->
    <div class="bg-white rounded-xl border border-gray-200 p-4 mb-6">
      <div class="flex gap-3 items-end flex-wrap">
        <div class="flex-1 min-w-[200px] relative">
          <label class="block text-xs font-medium text-gray-500 mb-1">搜索股票（代码或名称）</label>
          <input
            v-model="searchQuery"
            @input="onSearchInput"
            @keyup.enter="selectFirstResult"
            placeholder="输入股票代码或名称搜索..."
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <div
            v-if="searchResults.length > 0"
            class="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
          >
            <div
              v-for="stock in searchResults"
              :key="stock.ticker"
              @click="selectStock(stock)"
              class="px-3 py-2 hover:bg-gray-50 cursor-pointer flex items-center gap-3"
            >
              <span class="font-mono text-sm text-gray-900">{{ stock.ticker }}</span>
              <span class="text-sm text-gray-600">{{ stock.name }}</span>
            </div>
          </div>
          <div v-if="searching" class="absolute right-3 top-9">
            <div class="w-4 h-4 border-2 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        </div>
        <div class="w-36">
          <label class="block text-xs font-medium text-gray-500 mb-1">已选股票</label>
          <div v-if="selectedStock" class="flex items-center gap-1 px-3 py-2 bg-gray-100 rounded-lg">
            <span class="font-mono text-sm text-gray-900 truncate">{{ selectedStock.ticker }}</span>
            <button @click="clearSelection" class="text-gray-400 hover:text-gray-600 flex-shrink-0">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
          <div v-else class="px-3 py-2 text-sm text-gray-400">请先搜索</div>
        </div>
        <div class="w-28">
          <label class="block text-xs font-medium text-gray-500 mb-1">持仓数量（股）</label>
          <input
            v-model.number="form.quantity"
            type="number"
            min="0"
            step="100"
            placeholder="0"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div class="w-28">
          <label class="block text-xs font-medium text-gray-500 mb-1">成本价（元）</label>
          <input
            v-model.number="form.costPrice"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div class="w-36">
          <label class="block text-xs font-medium text-gray-500 mb-1">备注</label>
          <input
            v-model="form.notes"
            placeholder="可选"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <button
          @click="addHolding"
          :disabled="!selectedStock || form.quantity <= 0 || form.costPrice <= 0"
          class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 text-sm font-medium"
        >
          添加
        </button>
      </div>
    </div>

    <!-- Holdings table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div v-if="store.holdings.length === 0" class="p-8 text-center text-gray-400">
        <p class="text-lg mb-2">暂无持仓记录</p>
        <p class="text-sm">添加持仓后，分析时将自动引入持仓上下文</p>
      </div>
      <table v-else class="w-full">
        <thead class="bg-gray-50 border-b border-gray-200">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">代码</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">持仓数量</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">成本价</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">备注</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">更新时间</th>
            <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in store.holdings" :key="h.id" class="border-b border-gray-100 hover:bg-gray-50">
            <td class="px-4 py-3 font-mono text-sm text-gray-900">{{ h.ticker }}</td>
            <td class="px-4 py-3 text-sm text-gray-600">{{ h.name || '-' }}</td>
            <!-- Quantity: inline edit -->
            <td class="px-4 py-3 text-right">
              <input
                v-if="editingId === h.id"
                v-model.number="editForm.quantity"
                type="number"
                min="0"
                step="100"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-sm text-right focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <span v-else class="text-sm text-gray-900">{{ h.quantity.toLocaleString() }}</span>
            </td>
            <!-- Cost price: inline edit -->
            <td class="px-4 py-3 text-right">
              <input
                v-if="editingId === h.id"
                v-model.number="editForm.costPrice"
                type="number"
                min="0"
                step="0.01"
                class="w-24 px-2 py-1 border border-gray-300 rounded text-sm text-right focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <span v-else class="text-sm text-gray-900">{{ h.cost_price.toFixed(2) }}</span>
            </td>
            <!-- Notes: inline edit -->
            <td class="px-4 py-3">
              <input
                v-if="editingId === h.id"
                v-model="editForm.notes"
                class="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <span v-else class="text-sm text-gray-500">{{ h.notes || '-' }}</span>
            </td>
            <td class="px-4 py-3 text-xs text-gray-400">{{ formatDate(h.updated_at) }}</td>
            <td class="px-4 py-3 text-right space-x-2">
              <template v-if="editingId === h.id">
                <button @click="saveEdit(h.id)" class="text-primary-600 hover:text-primary-800 text-sm">保存</button>
                <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600 text-sm">取消</button>
              </template>
              <template v-else>
                <button @click="startEdit(h)" class="text-primary-600 hover:text-primary-800 text-sm">编辑</button>
                <button @click="removeHolding(h.id)" class="text-red-500 hover:text-red-700 text-sm">删除</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { holdingsStore as store } from '../stores/holdingsStore.js'
import { api } from '../api.js'

const searchQuery = ref('')
const searchResults = ref([])
const selectedStock = ref(null)
const searching = ref(false)

const form = ref({ quantity: 0, costPrice: 0, notes: '' })

const editingId = ref(null)
const editForm = ref({ quantity: 0, costPrice: 0, notes: '' })

let searchTimeout = null

onMounted(() => { store.loadHoldings() })

function onSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (!searchQuery.value.trim()) { searchResults.value = []; return }
  searching.value = true
  searchTimeout = setTimeout(async () => {
    try {
      searchResults.value = await api.searchStocks(searchQuery.value.trim())
    } catch { searchResults.value = [] }
    finally { searching.value = false }
  }, 300)
}

function selectStock(stock) {
  selectedStock.value = stock
  searchQuery.value = ''
  searchResults.value = []
}

function selectFirstResult() {
  if (searchResults.value.length > 0) selectStock(searchResults.value[0])
}

function clearSelection() { selectedStock.value = null }

async function addHolding() {
  if (!selectedStock.value) return
  await store.addHolding(
    selectedStock.value.ticker,
    selectedStock.value.name,
    form.value.quantity,
    form.value.costPrice,
    form.value.notes,
  )
  clearSelection()
  form.value = { quantity: 0, costPrice: 0, notes: '' }
}

function startEdit(h) {
  editingId.value = h.id
  editForm.value = { quantity: h.quantity, costPrice: h.cost_price, notes: h.notes || '' }
}

function cancelEdit() { editingId.value = null }

async function saveEdit(id) {
  await store.updateHolding(id, editForm.value.quantity, editForm.value.costPrice, editForm.value.notes)
  editingId.value = null
}

async function removeHolding(id) { await store.removeHolding(id) }

function formatDate(s) {
  if (!s) return '-'
  try { return new Date(s).toLocaleString('zh-CN') } catch { return s }
}
</script>
