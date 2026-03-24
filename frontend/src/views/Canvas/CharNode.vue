<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    name: string
    description: string
    loraId: string
    gender: 'female' | 'male' | 'other'
  }
  selected?: boolean
}>()
</script>

<template>
  <div class="char-node" :class="{ selected }">
    <Handle type="source" :position="Position.Right" class="vf-handle char-handle" />

    <div class="cn-header">
      <div class="cn-avatar">{{ data.gender === 'female' ? '\u2640' : data.gender === 'male' ? '\u2642' : '\u25CE' }}</div>
      <div>
        <div class="cn-type">Character</div>
        <div class="cn-name">{{ data.name }}</div>
      </div>
    </div>
    <p class="cn-desc">{{ data.description }}</p>
    <div class="cn-lora">
      <span class="lora-label">LoRA</span>
      <span class="lora-id">{{ data.loraId }}</span>
    </div>
  </div>
</template>

<style scoped>
.char-node {
  width: 175px; border-radius: 10px;
  border: 1.5px solid rgba(92,159,255,.3);
  background: linear-gradient(135deg, rgba(92,159,255,.1), rgba(20,40,100,.15));
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
  font-family: "Inter", system-ui, sans-serif;
}
.char-node:hover, .char-node.selected {
  border-color: #5c9fff;
  box-shadow: 0 0 18px rgba(92,159,255,.4);
}
.cn-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.cn-avatar {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  background: rgba(92,159,255,.2); border: 1px solid rgba(92,159,255,.4);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: #93c5fd;
}
.cn-type { font-size: 9px; font-weight: 700; color: #93c5fd; letter-spacing: .08em; text-transform: uppercase; }
.cn-name { font-size: 12px; font-weight: 600; color: rgba(255,255,255,.9); }
.cn-desc {
  font-size: 10px; color: rgba(255,255,255,.5); margin: 0 0 6px;
  line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden;
}
.cn-lora { display: flex; align-items: center; gap: 5px; }
.lora-label {
  font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 4px;
  background: rgba(92,159,255,.2); color: #93c5fd;
}
.lora-id { font-size: 9px; color: rgba(255,255,255,.4); font-family: monospace; }
.vf-handle.char-handle {
  width: 10px !important; height: 10px !important;
  background: #5c9fff !important;
  border: 2px solid #08080e !important;
  border-radius: 50% !important;
}
</style>
