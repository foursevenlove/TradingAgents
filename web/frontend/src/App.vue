<template>
  <div class="min-h-screen flex flex-col">
    <nav class="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center gap-6">
            <router-link to="/" class="flex items-center gap-2">
              <div class="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                <span class="text-white font-bold text-sm">TA</span>
              </div>
              <span class="font-bold text-lg text-gray-900">TradingAgents</span>
            </router-link>
            <div class="hidden sm:flex gap-4">
              <router-link to="/" class="text-gray-600 hover:text-gray-900 px-3 py-2 text-sm font-medium" active-class="text-primary-600">
                首页
              </router-link>
              <router-link to="/history" class="text-gray-600 hover:text-gray-900 px-3 py-2 text-sm font-medium" active-class="text-primary-600">
                历史记录
              </router-link>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xs text-gray-400 hidden sm:inline">v0.2.1</span>
          </div>
        </div>
      </div>
    </nav>

    <main class="flex-1">
      <router-view />
    </main>

    <footer class="bg-white border-t border-gray-200 py-4">
      <div class="max-w-7xl mx-auto px-4 text-center text-sm text-gray-400">
        TradingAgents - Multi-Agent LLM Financial Analysis Framework
      </div>
    </footer>
  </div>
</template>
