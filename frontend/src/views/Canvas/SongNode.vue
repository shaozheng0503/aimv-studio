<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    title: string
    mood: string
    bpm: number
    duration: number
    genre: string
  }
  selected?: boolean
}>()

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}
</script>

<template>
  <div class="song-node" :class="{ selected }">
    <Handle type="source" :position="Position.Right" class="vf-handle music-handle" />

    <div class="sn-header">
      <span class="sn-icon">&#x1F3B5;</span>
      <span class="sn-type">Music</span>
    </div>
    <div class="sn-title">{{ data.title }}</div>
    <div class="sn-tags">
      <span class="sn-tag genre">{{ data.genre }}</span>
      <span class="sn-tag bpm">{{ data.bpm }} BPM</span>
      <span class="sn-tag dur">{{ fmt(data.duration) }}</span>
      <span class="sn-tag mood">{{ data.mood }}</span>
    </div>
  </div>
</template>

<style scoped>
.song-node {
  width: 185px; border-radius: 10px;
  border: 1.5px solid rgba(141,92,255,.3);
  background: linear-gradient(135deg, rgba(141,92,255,.12), rgba(60,20,120,.15));
  padding: 12px 12px 10px;
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
  font-family: "Inter", system-ui, sans-serif;
}
.song-node:hover, .song-node.selected {
  border-color: #8d5cff;
  box-shadow: 0 0 18px rgba(141,92,255,.4);
}
.sn-header {
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
}
.sn-icon { font-size: 14px; }
.sn-type {
  font-size: 9px; font-weight: 700; letter-spacing: .08em;
  color: #a78bfa; text-transform: uppercase;
}
.sn-title {
  font-size: 13px; font-weight: 600; color: rgba(255,255,255,.9);
  margin-bottom: 8px;
}
.sn-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.sn-tag {
  font-size: 9px; padding: 2px 6px; border-radius: 999px;
  background: rgba(255,255,255,.06); color: rgba(255,255,255,.5);
}
.sn-tag.mood { color: #a78bfa; background: rgba(141,92,255,.18); }
.sn-tag.bpm  { color: #f3b2ff; background: rgba(243,178,255,.12); }
.sn-tag.genre { color: rgba(255,255,255,.45); }
.vf-handle.music-handle {
  width: 10px !important; height: 10px !important;
  background: #8d5cff !important;
  border: 2px solid #08080e !important;
  border-radius: 50% !important;
}
</style>
