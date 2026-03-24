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
      <span class="scn-icon">&#x1F3D9;</span>
      <span class="scn-type">Scene</span>
    </div>
    <div class="scn-name">{{ data.name }}</div>
    <div class="scn-tags">
      <span class="scn-tag style">{{ data.style }}</span>
      <span class="scn-tag">{{ data.lighting }}</span>
      <span class="scn-tag loc">{{ data.location }}</span>
    </div>
  </div>
</template>

<style scoped>
.scene-node {
  width: 175px; border-radius: 10px;
  border: 1.5px solid rgba(34,211,238,.25);
  background: linear-gradient(135deg, rgba(34,211,238,.08), rgba(10,60,80,.15));
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
  font-family: "Inter", system-ui, sans-serif;
}
.scene-node:hover, .scene-node.selected {
  border-color: #22d3ee;
  box-shadow: 0 0 18px rgba(34,211,238,.35);
}
.scn-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.scn-icon { font-size: 14px; }
.scn-type { font-size: 9px; font-weight: 700; color: #67e8f9; letter-spacing: .08em; text-transform: uppercase; }
.scn-name { font-size: 12px; font-weight: 600; color: rgba(255,255,255,.9); margin-bottom: 6px; }
.scn-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.scn-tag {
  font-size: 9px; padding: 2px 6px; border-radius: 999px;
  background: rgba(255,255,255,.06); color: rgba(255,255,255,.5);
}
.scn-tag.style { color: #67e8f9; background: rgba(34,211,238,.15); }
.scn-tag.loc   { color: rgba(255,255,255,.35); }
.vf-handle.in-handle {
  width: 10px !important; height: 10px !important;
  background: rgba(255,255,255,.25) !important;
  border: 2px solid #08080e !important;
  border-radius: 50% !important;
}
.vf-handle.scene-handle {
  width: 10px !important; height: 10px !important;
  background: #22d3ee !important;
  border: 2px solid #08080e !important;
  border-radius: 50% !important;
}
</style>
