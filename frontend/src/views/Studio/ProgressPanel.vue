<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useLangStore } from '@/stores/lang'

const { t } = storeToRefs(useLangStore())

interface ShotStatus {
  index: number
  prompt: string
  model: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  pct?: number
  videoUrl?: string
}

const props = defineProps<{
  musicStatus: 'pending' | 'running' | 'completed' | 'failed'
  shots: ShotStatus[]
  overallPct: number
  pipelineStatus: string
}>()

const completedShots = computed(() => props.shots.filter(s => s.status === 'completed').length)
</script>

<template>
  <div class="progress-panel">
    <!-- Overall bar -->
    <div class="overall-row">
      <span class="overall-label">{{ t('studioOverallProgress') }}</span>
      <div class="bar-track">
        <div class="bar-fill" :style="{ width: overallPct + '%' }" />
      </div>
      <span class="overall-pct">{{ overallPct }}%</span>
    </div>

    <!-- Music row -->
    <div class="node-row" :class="musicStatus">
      <span class="node-icon">🎵</span>
      <span class="node-label">{{ t('studioMusicGen') }}</span>
      <span class="node-model">ACEStep</span>
      <span class="status-dot">
        <span v-if="musicStatus === 'running'" class="spinner" />
        <span v-else-if="musicStatus === 'completed'" class="dot-done">✓</span>
        <span v-else-if="musicStatus === 'failed'" class="dot-fail">✗</span>
        <span v-else class="dot-pending" />
      </span>
    </div>

    <!-- Shots -->
    <div class="shots-header">{{ t('studioShotSeq') }} ({{ completedShots }}/{{ shots.length }})</div>
    <div class="shot-list">
      <div v-for="s in shots" :key="s.index" class="shot-row" :class="s.status">
        <!-- Thumbnail / spinner -->
        <div class="shot-thumb">
          <video
            v-if="s.videoUrl"
            :src="s.videoUrl"
            class="thumb-video"
            muted
            preload="metadata"
            @loadedmetadata="(e: Event) => { (e.target as HTMLVideoElement).currentTime = 0.5 }"
            @mouseenter="(e: Event) => (e.target as HTMLVideoElement).play()"
            @mouseleave="(e: Event) => (e.target as HTMLVideoElement).pause()"
          />
          <span v-else-if="s.status === 'running'" class="thumb-spinner" />
          <span v-else class="thumb-idx">#{{ String(s.index).padStart(2, '0') }}</span>
        </div>

        <div class="shot-info">
          <div class="shot-prompt">{{ s.prompt.slice(0, 40) }}{{ s.prompt.length > 40 ? '…' : '' }}</div>
          <div class="shot-sub">
            <span class="model-badge">{{ s.model }}</span>
            <div v-if="s.status === 'running' && s.pct !== undefined" class="mini-bar-track">
              <div class="mini-bar-fill" :style="{ width: s.pct + '%' }" />
            </div>
          </div>
        </div>

        <span class="status-dot">
          <span v-if="s.status === 'running'" class="spinner" />
          <span v-else-if="s.status === 'completed'" class="dot-done">✓</span>
          <span v-else-if="s.status === 'failed'" class="dot-fail">✗</span>
          <span v-else class="dot-pending" />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px; display: flex; flex-direction: column; gap: 10px;
  max-height: calc(100vh - 140px); overflow-y: auto;
}

/* overall */
.overall-row { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.overall-label { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.bar-track { flex: 1; height: 6px; background: rgba(255,255,255,.08); border-radius: 100px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent-gradient); border-radius: 100px; transition: width .4s ease; }
.overall-pct { font-size: 12px; color: var(--accent); font-weight: 600; min-width: 34px; text-align: right; }

/* music row */
.node-row {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border-radius: 10px; background: rgba(255,255,255,.03); border: 1px solid var(--border);
}
.node-row.running { border-color: rgba(141,92,255,.4); background: rgba(141,92,255,.06); }
.node-row.completed { border-color: rgba(52,211,153,.3); }
.node-row.failed { border-color: rgba(248,113,113,.3); }
.node-icon { font-size: 16px; }
.node-label { flex: 1; font-size: 13px; }
.node-model { font-size: 11px; color: var(--text-muted); }

/* shots */
.shots-header { font-size: 11px; color: var(--text-muted); padding: 4px 0 2px; letter-spacing: .04em; }
.shot-list { display: flex; flex-direction: column; gap: 6px; }
.shot-row {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border-radius: 10px; background: rgba(255,255,255,.02); border: 1px solid var(--border);
}
.shot-row.running { border-color: rgba(141,92,255,.4); background: rgba(141,92,255,.05); }
.shot-row.completed { border-color: rgba(52,211,153,.25); }
.shot-row.failed { border-color: rgba(248,113,113,.25); }

.shot-thumb {
  width: 44px; height: 32px; border-radius: 6px;
  background: rgba(255,255,255,.06); overflow: hidden; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.thumb-video { width: 100%; height: 100%; object-fit: cover; }
.thumb-spinner { width: 14px; height: 14px; border: 2px solid rgba(141,92,255,.3); border-top-color: #8d5cff; border-radius: 50%; animation: spin .8s linear infinite; }
.thumb-idx { font-size: 10px; color: var(--text-muted); }

.shot-info { flex: 1; min-width: 0; }
.shot-prompt { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.shot-sub { display: flex; align-items: center; gap: 8px; margin-top: 3px; }
.model-badge { font-size: 10px; padding: 1px 6px; border-radius: 100px; background: rgba(141,92,255,.15); color: #a78bfa; }
.mini-bar-track { flex: 1; height: 3px; background: rgba(255,255,255,.08); border-radius: 100px; overflow: hidden; }
.mini-bar-fill { height: 100%; background: #8d5cff; border-radius: 100px; transition: width .3s ease; }

/* status dots */
.status-dot { width: 20px; text-align: center; flex-shrink: 0; }
.spinner { display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(141,92,255,.3); border-top-color: #8d5cff; border-radius: 50%; animation: spin .8s linear infinite; }
.dot-done { color: #34d399; font-size: 13px; font-weight: 700; }
.dot-fail { color: #f87171; font-size: 13px; }
.dot-pending { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,.2); }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
