import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import AnalyzeView from './views/AnalyzeView.vue'
import ReportView from './views/ReportView.vue'
import HistoryView from './views/HistoryView.vue'
import WatchlistView from './views/WatchlistView.vue'
import HoldingsView from './views/HoldingsView.vue'
import BatchRunsView from './views/BatchRunsView.vue'
import BatchRunDetail from './views/BatchRunDetail.vue'

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/analyze/:taskId', name: 'Analyze', component: AnalyzeView, props: true },
  { path: '/report/:taskId', name: 'Report', component: ReportView, props: true },
  { path: '/history', name: 'History', component: HistoryView },
  { path: '/watchlist', name: 'Watchlist', component: WatchlistView },
  { path: '/holdings', name: 'Holdings', component: HoldingsView },
  { path: '/batch', name: 'BatchRuns', component: BatchRunsView },
  { path: '/batch/:batchId', name: 'BatchRunDetail', component: BatchRunDetail, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
