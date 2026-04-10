<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { storeToRefs } from 'pinia'
import { useLangStore } from '@/stores/lang'

defineProps<{
  data: {
    name: string
    description: string
    loraId: string
    gender: 'female' | 'male' | 'other'
  }
  selected?: boolean
}>()

const { lang } = storeToRefs(useLangStore())
</script>

<template>
  <div class="char-node" :class="{ selected }">
    <Handle type="target" :position="Position.Left" class="vf-handle in-handle" />
    <Handle type="source" :position="Position.Right" class="vf-handle char-handle" />

    <div class="cn-header">
      <div class="cn-avatar">{{ data.gender === 'female' ? '♀' : data.gender === 'male' ? '♂' : '◎' }}</div>
      <div class="cn-info">
        <div class="cn-type">{{ lang === 'zh' ? '角色' : 'Character' }}</div>
        <div class="cn-name">{{ data.name }}</div>
      </div>
    </div>
    <p class="cn-desc">{{ data.description }}</p>
    <div class="cn-lora">
      <span class="lora-label">{{ lang === 'zh' ? 'LoRA 模型' : 'LoRA' }}</span>
      <span class="lora-id">{{ data.loraId || '—' }}</span>
    </div>
  </div>
</template>

<style scoped>
.char-node {
  width: 176px;
  border-radius: 12px;
  border: 1px solid rgba(92,159,255,.18);
  background: rgba(10,14,30,.88);
  backdrop-filter: blur(12px);
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, transform .1s ease;
  font-family: "Inter", system-ui, sans-serif;
}
.char-node:hover {
  border-color: rgba(92,159,255,.4);
  box-shadow: 0 4px 24px rgba(0,0,0,.55), inset 0 0 0 0.5px rgba(92,159,255,.1);
}
.char-node.selected {
  border-color: rgba(92,159,255,.6);
  box-shadow: 0 2px 20px rgba(0,0,0,.5), inset 0 0 0 0.5px rgba(92,159,255,.22);
}
.char-node:active { transform: scale(0.98); }

.cn-header { display: flex; align-items: center; gap: 9px; margin-bottom: 7px; }
.cn-avatar {
  width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
  background: rgba(92,159,255,.1);
  border: 0.5px solid rgba(92,159,255,.25);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: #93c5fd;
}
.cn-info { flex: 1; min-width: 0; }
.cn-type { font-size: 9px; font-weight: 700; color: #7dd3fc; letter-spacing: .08em; text-transform: uppercase; }
.cn-name { font-size: 12px; font-weight: 600; color: rgba(255,255,255,.88); line-height: 1.3; margin-top: 1px; }
.cn-desc {
  font-size: 10px; color: rgba(255,255,255,.45); margin: 0 0 7px;
  line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.cn-lora {
  display: flex; align-items: center; gap: 5px;
  border-top: 0.5px solid rgba(255,255,255,.05); padding-top: 6px; margin-top: 2px;
}
.lora-label {
  font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 4px;
  background: rgba(92,159,255,.12);
  border: 0.5px solid rgba(92,159,255,.2);
  color: #93c5fd;
}
.lora-id { font-size: 9px; color: rgba(255,255,255,.35); font-family: "SF Mono","Fira Code",monospace; }
.vf-handle.char-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(92,159,255,.65) !important;
  border: 1.5px solid rgba(10,14,30,.9) !important;
  border-radius: 50% !important;
}
.vf-handle.in-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(255,255,255,.2) !important;
  border: 1.5px solid rgba(10,14,30,.9) !important;
  border-radius: 50% !important;
}
</style>
