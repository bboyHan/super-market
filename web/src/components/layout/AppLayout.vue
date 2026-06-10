<script setup lang="ts">
import { ref, provide } from 'vue'
import Sidebar from './Sidebar.vue'
import TopBar from './TopBar.vue'

const sidebarCollapsed = ref(false)
const sidebarMobileOpen = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function toggleMobileSidebar() {
  sidebarMobileOpen.value = !sidebarMobileOpen.value
}

provide('sidebarCollapsed', sidebarCollapsed)
provide('toggleSidebar', toggleSidebar)
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-[var(--color-bg)] transition-colors duration-300">
    <!-- Mobile sidebar overlay -->
    <div
      v-if="sidebarMobileOpen"
      class="fixed inset-0 z-40 bg-black/50 lg:hidden"
      @click="sidebarMobileOpen = false"
    />

    <!-- Sidebar -->
    <Sidebar
      :collapsed="sidebarCollapsed"
      :mobile-open="sidebarMobileOpen"
      @toggle="toggleSidebar"
      @close-mobile="sidebarMobileOpen = false"
    />

    <!-- Main content area -->
    <div class="flex flex-1 flex-col min-w-0">
      <!-- Top bar -->
      <TopBar @toggle-mobile-sidebar="toggleMobileSidebar" />

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
        <div class="mx-auto max-w-7xl animate-fade-in">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>
