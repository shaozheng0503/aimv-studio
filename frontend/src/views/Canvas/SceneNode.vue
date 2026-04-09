<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    name: string
    style: string
    location: string
    lighting: string
  }
  selected?: boolean
}>()
</script>

<template>
  <div class="scene-node" :class="{ selected }">
    <Handle type="target" :position="Position.Left" class="vf-handle in-handle" />
    <Handle type="source" :position="Position.Right" class="vf-handle scene-handle" />

    <div class="scn-header">
      <div class="scn-icon-wrap">
        <span class="scn-icon">◈</span>
      </div>
      <div class="scn-meta">
        <span class="scn-type">Scene</span>
      </div>
    </div>
    <div class="scn-name">{{ data.name }}</div>
    <div class="scn-tags">
      <span class="scn-tag style">{{ data.style }}</span>
      <span class="scn-tag light">{{ data.lighting }}</span>
      <span class="scn-tag loc">{{ data.location }}</span>
    </div>
  </div>
</template>

<style scoped>
.scene-node {
  width: 176px;
  border-radius: 12px;
  border: 1px solid rgba(34,211,238,.18);
  background: rgba(8,16,22,.88);
  backdrop-filter: blur(12px);
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, transform .1s ease;
  font-family: "Inter", system-ui, sans-serif;
}
.scene-node:hover {
  border-color: rgba(34,211,238,.4);
  box-shadow: 0 4px 24px rgba(0,0,0,.55), inset 0 0 0 0.5px rgba(34,211,238,.08);
}
.scene-node.selected {
  border-color: rgba(34,211,238,.6);
  box-shadow: 0 2px 20px rgba(0,0,0,.5), inset 0 0 0 0.5px rgba(34,211,238,.2);
}
.scene-node:active { transform: scale(0.98); }

.scn-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.scn-icon-wrap {
  width: 26px; height: 26px; border-radius: 7px; flex-shrink: 0;
  background: rgba(34,211,238,.08);
  border: 0.5px solid rgba(34,211,238,.22);
  display: flex; align-items: center; justify-content: center;
}
.scn-icon { font-size: 12px; color: #67e8f9; }
.scn-meta { flex: 1; }
.scn-type { font-size: 9px; font-weight: 700; color: #67e8f9; letter-spacing: .08em; text-transform: uppercase; }
.scn-name { font-size: 12px; font-weight: 600; color: rgba(255,255,255,.88); margin-bottom: 7px; line-height: 1.3; }
.scn-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.scn-tag {
  font-size: 9px; padding: 2px 6px; border-radius: 5px;
  background: rgba(255,255,255,.05); color: rgba(255,255,255,.4);
  border: 0.5px solid rgba(255,255,255,.06);
}
.scn-tag.style { color: #67e8f9; background: rgba(34,211,238,.1); border-color: rgba(34,211,238,.15); }
.scn-tag.light { color: rgba(255,255,255,.38); }
.scn-tag.loc   { color: rgba(255,255,255,.3); }

.vf-handle.in-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(255,255,255,.2) !important;
  border: 1.5px solid rgba(8,16,22,.9) !important;
  border-radius: 50% !important;
}
.vf-handle.scene-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(34,211,238,.6) !important;
  border: 1.5px solid rgba(8,16,22,.9) !important;
  border-radius: 50% !important;
}
</style>
