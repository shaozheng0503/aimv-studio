<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="dark">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </div>
</template>

<style>
html {
  scroll-behavior: smooth;
}

html.dark {
  --el-bg-color: #15151f;
  --el-bg-color-overlay: #1c1c2a;
  --el-text-color-primary: #f7f7fb;
  --el-border-color: rgba(255, 255, 255, 0.08);
  --el-color-primary: #8d5cff;
  --el-color-primary-light-3: #a77dff;
  --el-color-primary-dark-2: #6b3fd9;
}

/* Page transitions */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Element Plus dark overrides */
.el-select-dropdown { background: var(--card) !important; border-color: var(--border) !important; }
.el-select-dropdown__item.hover, .el-select-dropdown__item:hover { background: rgba(141, 92, 255, 0.1) !important; }
.el-dialog { background: var(--bg-soft) !important; border: 1px solid var(--border) !important; }
.el-dialog__title { color: var(--text) !important; }
.el-checkbox__label { color: var(--text-muted) !important; }
</style>
