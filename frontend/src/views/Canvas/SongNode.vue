<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { storeToRefs } from 'pinia'
import { useLangStore } from '@/stores/lang'

defineProps<{
  data: {
    title: string
    mood: string
    bpm: number
    duration: number
    genre: string
    generateStatus?: string  // 'idle' | 'generating' | 'done' | 'failed'
    audioUrl?: string | null
  }
  selected?: boolean
}>()

const { lang } = storeToRefs(useLangStore())

function moodLabel(v?: string) {
  const s = (v || '').toLowerCase()
  if (lang.value !== 'zh') return v || ''
  if (s === 'energetic') return '活力'
  if (s === 'neutral') return '中性'
  if (s === 'melancholic') return '忧郁'
  if (s === 'romantic') return '浪漫'
  if (s === 'epic') return '史诗'
  if (s === 'peaceful') return '平静'
  return v || ''
}

function genreLabel(v?: string) {
  const s = (v || '').toLowerCase()
  if (lang.value !== 'zh') return v || ''
  if (s === 'electronic') return '电子'
  if (s === 'pop') return '流行'
  if (s === 'classical') return '古典'
  return v || ''
}

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}
</script>

<template>
  <div class="song-node" :class="{ selected }">
    <Handle type="target" :position="Position.Left" class="vf-handle in-handle" />
    <Handle type="source" :position="Position.Right" class="vf-handle music-handle" />

    <div class="sn-header">
      <div class="sn-icon-wrap">
        <span class="sn-icon">♪</span>
      </div>
      <div class="sn-meta">
        <span class="sn-type">{{ lang === 'zh' ? '音乐' : 'Music' }}</span>
        <div v-if="data.generateStatus === 'generating'" class="sn-status-dot gen" />
        <div v-else-if="data.generateStatus === 'done'" class="sn-status-dot done" />
        <div v-else-if="data.generateStatus === 'failed'" class="sn-status-dot fail" />
      </div>
    </div>
    <div class="sn-title">{{ data.title }}</div>
    <div class="sn-tags">
      <span class="sn-tag genre">{{ genreLabel(data.genre) }}</span>
      <span class="sn-tag bpm">{{ data.bpm }} BPM</span>
      <span class="sn-tag dur">{{ fmt(data.duration) }}</span>
      <span class="sn-tag mood">{{ moodLabel(data.mood) }}</span>
    </div>
    <div v-if="data.generateStatus === 'done'" class="sn-audio-badge">✓ AI 生成</div>
  </div>
</template>

<style scoped>
.song-node {
  width: 186px;
  border-radius: 12px;
  border: 1px solid rgba(141,92,255,.2);
  background: rgba(14,10,28,.88);
  backdrop-filter: blur(12px);
  padding: 11px 12px 10px;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, transform .1s ease;
  font-family: "Inter", system-ui, sans-serif;
}
.song-node:hover {
  border-color: rgba(141,92,255,.45);
  box-shadow: 0 4px 24px rgba(0,0,0,.55), inset 0 0 0 0.5px rgba(141,92,255,.12);
}
.song-node.selected {
  border-color: rgba(141,92,255,.65);
  box-shadow: 0 2px 20px rgba(0,0,0,.5), inset 0 0 0 0.5px rgba(141,92,255,.25);
}
.song-node:active { transform: scale(0.98); }

.sn-header { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }
.sn-icon-wrap {
  width: 26px; height: 26px; border-radius: 7px; flex-shrink: 0;
  background: rgba(141,92,255,.15);
  border: 0.5px solid rgba(141,92,255,.3);
  display: flex; align-items: center; justify-content: center;
}
.sn-icon { font-size: 12px; color: #c4b5fd; }
.sn-meta { display: flex; align-items: center; gap: 6px; flex: 1; }
.sn-type {
  font-size: 9px; font-weight: 700; letter-spacing: .08em;
  color: #a78bfa; text-transform: uppercase; flex: 1;
}
.sn-status-dot {
  width: 6px; height: 6px; border-radius: 50%;
}
.sn-status-dot.gen  { background: #fbbf24; animation: blink 1.2s ease infinite; }
.sn-status-dot.done { background: #34d399; }
.sn-status-dot.fail { background: #f87171; }
@keyframes blink { 0%,100% { opacity:1 } 50% { opacity:.2 } }

.sn-title {
  font-size: 13px; font-weight: 600; color: rgba(255,255,255,.88);
  margin-bottom: 8px; line-height: 1.3;
}
.sn-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.sn-tag {
  font-size: 9px; padding: 2px 6px; border-radius: 5px;
  background: rgba(255,255,255,.05); color: rgba(255,255,255,.4);
  border: 0.5px solid rgba(255,255,255,.06);
}
.sn-tag.mood  { color: #a78bfa; background: rgba(141,92,255,.12); border-color: rgba(141,92,255,.18); }
.sn-tag.bpm   { color: #c4b5fd; background: rgba(196,181,253,.07); border-color: rgba(196,181,253,.12); }
.sn-tag.genre { color: rgba(255,255,255,.42); }
.sn-audio-badge {
  margin-top: 8px;
  font-size: 9px; color: #34d399; font-weight: 600;
  background: rgba(52,211,153,.08);
  border: 0.5px solid rgba(52,211,153,.2);
  border-radius: 5px; padding: 2px 7px; display: inline-block;
}
.vf-handle.music-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(141,92,255,.7) !important;
  border: 1.5px solid rgba(14,10,28,.9) !important;
  border-radius: 50% !important;
}
.vf-handle.in-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(255,255,255,.2) !important;
  border: 1.5px solid rgba(14,10,28,.9) !important;
  border-radius: 50% !important;
}
</style>
