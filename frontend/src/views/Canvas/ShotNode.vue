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

const emit = defineEmits<{ generate: [] }>()

function seekToFirstFrame(e: Event) {
  const v = e.target as HTMLVideoElement
  v.currentTime = 0.5
}

function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}

const MODEL_LABELS: Record<string, string> = {
  'veo':      'Veo',
  'veo-3.1':  'Veo 3.1',
  'veo-3.0':  'Veo 3.0',
  'veo-2.0':  'Veo 2.0',
  'seedance': 'Seedance',
  'grok':     'Grok',
  'wan2.2':   'Wan 2.2',
}

function modelLabel(model: string): string {
  return MODEL_LABELS[model.toLowerCase()] ?? model
}
</script>

<template>
  <div class="shot-node" :class="[`s-${data.status}`, { selected }]">
    <Handle type="target" :position="Position.Left" class="vf-handle" />

    <!-- thumbnail -->
    <div class="thumb" :style="data.videoUrl ? {} : { background: data.gradient }">
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

      <!-- subtle vignette overlay -->
      <div class="thumb-vignette" />

      <span class="idx">#{{ String(data.index).padStart(2,'0') }}</span>

      <!-- status overlays -->
      <div v-if="data.status === 'generating'" class="gen-overlay">
        <div class="gen-ring" />
      </div>
      <div v-else-if="data.status === 'pending'" class="pending-icon">＋</div>
      <div v-else-if="data.status === 'failed'" class="fail-icon">!</div>

      <span v-if="data.segment" class="seg-badge">{{ data.segment }}</span>
      <span class="pip" :class="data.status" />

      <button
        v-if="data.status !== 'generating'"
        class="quick-gen-btn"
        :title="data.status === 'failed' ? '重试生成' : '生成此镜头'"
        @click.stop="emit('generate')"
      >{{ data.status === 'failed' ? '↺' : '⚡' }}</button>
    </div>

    <!-- body -->
    <div class="body">
      <p class="prompt">{{ data.prompt }}</p>
      <div class="tags">
        <span class="tag model-tag">{{ modelLabel(data.model) }}</span>
        <span class="tag">{{ data.duration }}s</span>
        <span v-if="data.timeAnchor !== null" class="tag anchor">⏱ {{ fmt(data.timeAnchor!) }}</span>
      </div>
    </div>

    <Handle type="source" :position="Position.Right" class="vf-handle" />
  </div>
</template>

<style scoped>
.shot-node {
  width: 204px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,.1);
  background: rgba(14,14,22,.92);
  backdrop-filter: blur(12px);
  overflow: hidden;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, transform .1s ease;
  font-family: "Inter", system-ui, sans-serif;
}
.shot-node:hover {
  border-color: rgba(255,255,255,.22);
  box-shadow: 0 4px 24px rgba(0,0,0,.6), inset 0 0 0 0.5px rgba(255,255,255,.06);
}
.shot-node.selected {
  border-color: rgba(141,92,255,.6);
  box-shadow: 0 2px 20px rgba(0,0,0,.5), inset 0 0 0 0.5px rgba(141,92,255,.2);
}
.shot-node:active { transform: scale(0.98); }

/* generating: top border shimmer instead of glow */
.shot-node.s-generating {
  border-color: rgba(141,92,255,.4);
  animation: border-pulse 2.4s ease-in-out infinite;
}
.shot-node.s-failed { border-color: rgba(248,113,113,.35); }
@keyframes border-pulse {
  0%,100% { border-color: rgba(141,92,255,.25); }
  50%      { border-color: rgba(141,92,255,.55); }
}

/* thumbnail */
.thumb {
  height: 104px;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d0d18;
}
.thumb-video {
  position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover; opacity: .92;
}
/* subtle bottom vignette on thumbnail */
.thumb-vignette {
  position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(to bottom, transparent 50%, rgba(0,0,0,.45) 100%);
  z-index: 1;
}
.idx {
  position: absolute; top: 7px; left: 8px; z-index: 2;
  font-size: 10px; font-weight: 700; color: rgba(255,255,255,.5);
  font-family: "SF Mono", "Fira Code", monospace;
  background: rgba(0,0,0,.35); padding: 1px 5px; border-radius: 4px;
  backdrop-filter: blur(4px);
}
.seg-badge {
  position: absolute; top: 7px; right: 8px; z-index: 2;
  font-size: 9px; font-weight: 700; letter-spacing: .04em;
  padding: 2px 6px; border-radius: 6px;
  background: rgba(0,0,0,.4); color: rgba(255,255,255,.75);
  backdrop-filter: blur(6px);
  border: 0.5px solid rgba(255,255,255,.12);
}
.pip {
  position: absolute; bottom: 7px; right: 8px; z-index: 2;
  width: 7px; height: 7px; border-radius: 50%;
}
.pip.done { background: #4ade80; }
.pip.generating { background: #a78bfa; animation: pip-blink 1.2s ease infinite; }
.pip.pending { background: rgba(255,255,255,.2); }
.pip.failed { background: #f87171; }
@keyframes pip-blink { 0%,100%{opacity:1} 50%{opacity:.25} }

/* generating overlay */
.gen-overlay {
  position: absolute; inset: 0; z-index: 2;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,.15);
}
.gen-ring {
  width: 26px; height: 26px; border-radius: 50%;
  border: 2px solid rgba(255,255,255,.08);
  border-top-color: #a78bfa;
  border-right-color: rgba(141,92,255,.4);
  animation: spin .9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.pending-icon {
  position: absolute; z-index: 2;
  font-size: 26px; color: rgba(255,255,255,.15); font-weight: 200;
}
.fail-icon {
  position: absolute; z-index: 2;
  width: 26px; height: 26px; border-radius: 50%;
  background: rgba(248,113,113,.15);
  border: 1.5px solid rgba(248,113,113,.45);
  color: #fca5a5; font-size: 14px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

/* body */
.body {
  padding: 8px 10px 10px;
  border-top: 1px solid rgba(255,255,255,.05);
}
.prompt {
  font-size: 11px; color: rgba(255,255,255,.62); margin: 0 0 7px;
  line-height: 1.5; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag {
  font-size: 10px; padding: 2px 6px; border-radius: 5px;
  background: rgba(255,255,255,.06); color: rgba(255,255,255,.38);
  border: 0.5px solid rgba(255,255,255,.06);
}
.tag.model-tag { color: rgba(255,255,255,.45); }
.tag.anchor { color: #a78bfa; background: rgba(141,92,255,.12); border-color: rgba(141,92,255,.2); }

/* quick-generate hover button */
.quick-gen-btn {
  position: absolute; bottom: 7px; left: 8px; z-index: 2;
  width: 22px; height: 22px; border-radius: 6px; border: none;
  background: rgba(141,92,255,.8); color: white;
  font-size: 11px; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  opacity: 0;
  transition: opacity .15s, transform .1s;
  backdrop-filter: blur(4px);
}
.shot-node:hover .quick-gen-btn { opacity: 1; }
.quick-gen-btn:hover { transform: scale(1.1); }

/* handles */
.vf-handle {
  width: 9px !important; height: 9px !important;
  background: rgba(141,92,255,.7) !important;
  border: 1.5px solid rgba(14,14,22,.9) !important;
  border-radius: 50% !important;
  transition: background .15s !important;
}
.shot-node:hover .vf-handle { background: #a78bfa !important; }
</style>
