<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  data: {
    index: number
    prompt: string
    model: string
    duration: number
    status: 'pending' | 'generating' | 'done' | 'failed'
    gradient: string
    timeAnchor: number | null
    segment: string | null
    videoUrl?: string | null
  }
  selected?: boolean
}>()

function seekToFirstFrame(e: Event) {
  const v = e.target as HTMLVideoElement
  v.currentTime = 0.5
}

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}
</script>

<template>
  <div class="shot-node" :class="[`s-${data.status}`, { selected }]">
    <Handle type="target" :position="Position.Left" class="vf-handle" />

    <!-- thumbnail -->
    <div class="thumb" :style="data.videoUrl ? {} : { background: data.gradient }">
      <!-- actual video preview when done -->
      <video
        v-if="data.videoUrl && data.status === 'done'"
        :src="data.videoUrl"
        class="thumb-video"
        muted
        playsinline
        preload="metadata"
        @loadedmetadata="seekToFirstFrame"
        @mouseenter="($event.target as HTMLVideoElement).play()"
        @mouseleave="($event.target as HTMLVideoElement).pause()"
      />

      <span class="idx">#{{ String(data.index).padStart(2,'0') }}</span>

      <div v-if="data.status === 'generating'" class="spin-ring" />
      <div v-else-if="data.status === 'pending'" class="pending-plus">＋</div>
      <div v-else-if="data.status === 'failed'" class="fail-badge">!</div>

      <span v-if="data.segment" class="seg-badge">{{ data.segment }}</span>
      <span class="pip" :class="data.status" />
    </div>

    <!-- body -->
    <div class="body">
      <p class="prompt">{{ data.prompt }}</p>
      <div class="tags">
        <span class="tag">{{ data.model }}</span>
        <span class="tag">{{ data.duration }}s</span>
        <span v-if="data.timeAnchor !== null" class="tag anchor">⏱ {{ fmt(data.timeAnchor!) }}</span>
      </div>
    </div>

    <Handle type="source" :position="Position.Right" class="vf-handle" />
  </div>
</template>

<style scoped>
.shot-node {
  width: 200px; border-radius: 10px;
  border: 1.5px solid rgba(255,255,255,.1);
  background: #16161e; overflow: hidden; cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
  font-family: "Inter", system-ui, sans-serif;
}
.shot-node:hover, .shot-node.selected {
  border-color: #8d5cff;
  box-shadow: 0 0 18px rgba(141,92,255,.35);
}
.shot-node.s-generating { animation: glow 2s ease-in-out infinite; }
.shot-node.s-failed { border-color: rgba(248,113,113,.45); }
@keyframes glow {
  0%,100% { box-shadow: 0 0 8px rgba(141,92,255,.2); }
  50%      { box-shadow: 0 0 22px rgba(141,92,255,.55); }
}

/* thumbnail */
.thumb {
  height: 100px; position: relative; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background: #0d0d18;
}
.thumb-video {
  position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover; opacity: .9;
}
.idx {
  position: absolute; top: 6px; left: 8px;
  font-size: 10px; font-weight: 700; color: rgba(255,255,255,.6);
  font-family: monospace;
}
.seg-badge {
  position: absolute; top: 6px; right: 8px;
  font-size: 9px; font-weight: 700; letter-spacing: .05em;
  padding: 2px 6px; border-radius: 999px;
  background: rgba(0,0,0,.45); color: rgba(255,255,255,.8);
  backdrop-filter: blur(4px);
}
.pip {
  position: absolute; bottom: 6px; right: 8px;
  width: 8px; height: 8px; border-radius: 50%;
}
.pip.done { background: #4ade80; }
.pip.generating { background: #8d5cff; animation: blink 1s infinite; }
.pip.pending { background: rgba(255,255,255,.25); }
.pip.failed { background: #f87171; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }

.spin-ring {
  width: 30px; height: 30px; border-radius: 50%;
  border: 3px solid transparent;
  border-top-color: #8d5cff; border-right-color: #f3b2ff;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.pending-plus { font-size: 28px; color: rgba(255,255,255,.2); font-weight: 300; }
.fail-badge {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(248,113,113,.2); border: 2px solid #f87171;
  color: #f87171; font-size: 16px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

/* body */
.body { padding: 8px 10px 10px; }
.prompt {
  font-size: 11px; color: rgba(255,255,255,.7); margin: 0 0 6px;
  line-height: 1.45; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag {
  font-size: 10px; padding: 2px 6px; border-radius: 999px;
  background: rgba(255,255,255,.07); color: rgba(255,255,255,.45);
}
.tag.anchor { color: #a78bfa; background: rgba(141,92,255,.18); }

/* handle */
.vf-handle {
  width: 10px !important; height: 10px !important;
  background: #8d5cff !important;
  border: 2px solid #16161e !important;
  border-radius: 50% !important;
}
</style>
