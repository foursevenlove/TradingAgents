import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import AnalyzeView from './views/AnalyzeView.vue'
import ReportView from './views/ReportView.vue'
import HistoryView from './views/HistoryView.vue'

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/analyze/:taskId', name: 'Analyze', component: AnalyzeView, props: true },
  { path: '/report/:taskId', name: 'Report', component: ReportView, props: true },
  { path: '/history', name: 'History', component: HistoryView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
