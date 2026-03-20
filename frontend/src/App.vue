<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { useLangStore } from '@/stores/lang'
import { storeToRefs } from 'pinia'

const langStore = useLangStore()
const { lang } = storeToRefs(langStore)
const route = useRoute()
</script>

<template>
  <div class="dark">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>

    <!-- 全局语言切换悬浮按钮（Home页已有自己的，不重复显示） -->
    <button
      v-if="route.name !== 'home'"
      class="global-lang-btn"
      @click="langStore.setLang(lang === 'zh' ? 'en' : 'zh')"
    >
      {{ lang === 'zh' ? 'EN' : '中' }}
    </button>
  </div>
</template>

<style>
html {
  scroll-behavior: smooth;
}

/* 全局语言切换悬浮按钮 */
.global-lang-btn {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--card, #1e1e2e);
  border: 1px solid var(--border, rgba(255,255,255,0.1));
  color: var(--text, #f7f7fb);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.global-lang-btn:hover {
  border-color: var(--accent-strong, #8d5cff);
  color: var(--accent, #8d5cff);
  transform: scale(1.1);
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
