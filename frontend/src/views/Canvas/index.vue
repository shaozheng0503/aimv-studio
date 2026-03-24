<script setup lang="ts">
import { ref, computed, markRaw, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VueFlow, useVueFlow, Position } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import ShotNode from './ShotNode.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.id as string

// ─── music segments (from MusicAnalysis) ─────────────────────────────────────
const DURATION = 180 // 3 min total
const segments = [
  { label: '前奏',  start: 0,   end: 22,  color: '#8d5cff', energy: 0.35 },
  { label: 'A段',   start: 22,  end: 74,  color: '#5cf3ff', energy: 0.65 },
  { label: '高潮',  start: 74,  end: 144, color: '#f3b2ff', energy: 0.95 },
  { label: 'C段',   start: 144, end: 168, color: '#5cf3ff', energy: 0.60 },
  { label: '尾奏',  start: 168, end: 180, color: '#8d5cff', energy: 0.25 },
]
const BPM = 128

function getSegmentAt(sec: number) {
  return segments.find(s => sec >= s.start && sec < s.end) ?? null
}
function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}

// ─── mock nodes ───────────────────────────────────────────────────────────────
const initialNodes = [
  // ── Scene Group: 前奏段 ──────────────────────────────────────────────────
  {
    id: 'g-intro', type: 'group', position: { x: 50, y: 40 },
    data: { label: '前奏段', color: '#8d5cff' },
    style: { width: '580px', height: '270px' },
  },
  // ── Scene Group: 高潮段 ──────────────────────────────────────────────────
  {
    id: 'g-climax', type: 'group', position: { x: 900, y: 40 },
    data: { label: '高潮段', color: '#f3b2ff' },
    style: { width: '360px', height: '270px' },
  },

  // ── Shot nodes ──────────────────────────────────────────────────────────
  {
    id: 's1', type: 'shot', position: { x: 80, y: 110 },
    data: {
      index: 1, status: 'done', duration: 5, model: 'Wan2.2', timeAnchor: 4,
      gradient: 'linear-gradient(135deg,#1a1a2e,#16213e)',
      segment: getSegmentAt(4)?.label ?? null,
      prompt: '城市夜景，霓虹倒影，镜头从地面缓慢上扬',
    },
  },
  {
    id: 's2', type: 'shot', position: { x: 340, y: 70 },
    data: {
      index: 2, status: 'done', duration: 6, model: 'Veo 3.1', timeAnchor: 11,
      gradient: 'linear-gradient(135deg,#2d1b69,#4a1942)',
      segment: getSegmentAt(11)?.label ?? null,
      prompt: '女孩独自站在窗边，灯光从侧面打过来',
    },
  },
  {
    id: 's3', type: 'shot', position: { x: 340, y: 195 },
    data: {
      index: 3, status: 'generating', duration: 5, model: 'Seedance 2.0', timeAnchor: 16,
      gradient: 'linear-gradient(135deg,#0f3460,#533483)',
      segment: getSegmentAt(16)?.label ?? null,
      prompt: '雨中路灯的光圈特写，景深虚化',
    },
  },
  {
    id: 's4', type: 'shot', position: { x: 720, y: 165 },
    data: {
      index: 4, status: 'done', duration: 7, model: 'Seedance 2.0', timeAnchor: 30,
      gradient: 'linear-gradient(135deg,#c94b4b,#4b134f)',
      segment: getSegmentAt(30)?.label ?? null,
      prompt: '两人在咖啡馆相遇，对视一瞬，慢镜',
    },
  },
  {
    id: 's5', type: 'shot', position: { x: 940, y: 80 },
    data: {
      index: 5, status: 'done', duration: 6, model: 'Kling 2.0', timeAnchor: 82,
      gradient: 'linear-gradient(135deg,#f5af19,#f12711)',
      segment: getSegmentAt(82)?.label ?? null,
      prompt: '高潮舞蹈爆发，舞台爆破特效，全身跟拍',
    },
  },
  {
    id: 's6', type: 'shot', position: { x: 940, y: 200 },
    data: {
      index: 6, status: 'pending', duration: 5, model: 'Veo 3.1', timeAnchor: 98,
      gradient: 'linear-gradient(135deg,#7b2d8b,#b2238e)',
      segment: getSegmentAt(98)?.label ?? null,
      prompt: '【A/B 分支】同场景另一风格：极简线条光效版',
    },
  },
  {
    id: 's7', type: 'shot', position: { x: 1360, y: 165 },
    data: {
      index: 7, status: 'failed', duration: 6, model: 'Wan2.2', timeAnchor: 120,
      gradient: 'linear-gradient(135deg,#314755,#26a0da)',
      segment: getSegmentAt(120)?.label ?? null,
      prompt: '回忆闪回，蒙太奇剪辑，胶片颗粒感处理',
    },
  },
  {
    id: 's8', type: 'shot', position: { x: 1620, y: 165 },
    data: {
      index: 8, status: 'done', duration: 8, model: 'Veo 3.1', timeAnchor: 162,
      gradient: 'linear-gradient(135deg,#360033,#0b8793)',
      segment: getSegmentAt(162)?.label ?? null,
      prompt: '尾奏，女孩独自走向远处，背影渐渐模糊消失',
    },
  },
]

const initialEdges = [
  // sequence
  { id: 'e1-2', source: 's1', target: 's2', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e1-3', source: 's1', target: 's3', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e2-4', source: 's2', target: 's4', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e3-4', source: 's3', target: 's4', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e4-5', source: 's4', target: 's5', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  // branch (A/B)
  { id: 'e4-6', source: 's4', target: 's6', type: 'smoothstep', animated: true,
    label: 'A/B 分支', labelStyle: { fill: '#f59e0b', fontSize: 10 },
    style: { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '5,4' } },
  // merge back
  { id: 'e5-7', source: 's5', target: 's7', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e6-7', source: 's6', target: 's7', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
  { id: 'e7-8', source: 's7', target: 's8', type: 'smoothstep', animated: false,
    style: { stroke: 'rgba(255,255,255,.35)', strokeWidth: 1.5 } },
]

// ─── vue flow setup ───────────────────────────────────────────────────────────
const nodes = ref(initialNodes)
const edges = ref(initialEdges)

// Custom node types
const GroupNode = markRaw({
  props: ['data', 'selected'],
  template: `
    <div :style="{
      width:'100%', height:'100%', borderRadius:'14px',
      border:'1.5px dashed ' + data.color + '55',
      background: data.color + '0a',
      position:'relative'
    }">
      <span :style="{
        position:'absolute', top:'10px', left:'14px',
        fontSize:'11px', fontWeight:'700', letterSpacing:'.06em',
        color: data.color + 'cc',
        textTransform:'uppercase'
      }">{{ data.label }}</span>
    </div>
  `,
})

const nodeTypes: Record<string, any> = {
  shot: markRaw(ShotNode),
  group: GroupNode,
}

const { onNodeClick, fitView } = useVueFlow()

const selectedNodeId = ref<string | null>(null)

onNodeClick(({ node }) => {
  if (node.type === 'group') return
  selectedNodeId.value = node.id
})

// ─── canvas context (三层联动核心) ────────────────────────────────────────────
const selectedNode = computed(() =>
  nodes.value.find(n => n.id === selectedNodeId.value) ?? null
)

const canvasContext = computed(() => {
  if (!selectedNodeId.value) return null
  const id = selectedNodeId.value

  // 从 edges 找前驱 / 后继（三层联动：Canvas → AI）
  const inEdges  = edges.value.filter(e => e.target === id)
  const outEdges = edges.value.filter(e => e.source === id)
  const prevNodes = inEdges.map(e => nodes.value.find(n => n.id === e.source)).filter(Boolean)
  const nextNodes = outEdges.map(e => nodes.value.find(n => n.id === e.target)).filter(Boolean)

  // 从 time_anchor 找音乐段落（三层联动：Music → Canvas）
  const anchor = selectedNode.value?.data.timeAnchor ?? null
  const musicSeg = anchor !== null ? getSegmentAt(anchor) : null

  return { prevNodes, nextNodes, anchor, musicSeg }
})

// 生成时实际传给后端的 payload（断点1修复后应有的结构）
const generationPayload = computed(() => {
  if (!selectedNode.value || selectedNode.value.type === 'group') return null
  const nd = selectedNode.value.data
  const ctx = canvasContext.value
  return {
    prompt: nd.prompt,
    model_name: String(nd.model ?? '').toLowerCase().replace(/\s/g, '_'),
    canvas_context: {
      prev_nodes: ctx?.prevNodes.map((n: any) => ({
        id: n!.id, prompt: n!.data.prompt,
        last_frame_url: `mock://frames/${n!.id}/last.jpg`,
      })),
      next_nodes: ctx?.nextNodes.map((n: any) => ({
        id: n!.id, prompt: n!.data.prompt,
      })),
      music_segment: ctx?.musicSeg ? {
        label: ctx.musicSeg.label,
        bpm: BPM,
        energy: ctx.musicSeg.energy,
        time_range: [ctx.musicSeg.start, ctx.musicSeg.end],
      } : null,
      time_anchor: ctx?.anchor,
    },
  }
})

// ─── music playhead ───────────────────────────────────────────────────────────
const playheadTime = ref(82) // 默认停在高潮段，与 s5 对应
const isPlaying = ref(false)
let playRAF: number | null = null
let playStart: number | null = null
let playOrigin = 82

const playheadPct = computed(() => (playheadTime.value / DURATION) * 100)
const currentSegment = computed(() => getSegmentAt(playheadTime.value))

// 播放头对应的节点高亮（三层联动：Music → Canvas）
const highlightedNodeId = computed(() => {
  const t = playheadTime.value
  const match = nodes.value
    .filter(n => n.type === 'shot')
    .find(n => {
      const anchor = n.data.timeAnchor as number | null
      return anchor !== null && Math.abs(anchor - t) < 8
    })
  return match?.id ?? null
})

function togglePlay() {
  if (isPlaying.value) {
    isPlaying.value = false
    if (playRAF) cancelAnimationFrame(playRAF)
  } else {
    isPlaying.value = true
    playOrigin = playheadTime.value
    playStart = Date.now()
    const tick = () => {
      const elapsed = (Date.now() - playStart!) / 1000
      playheadTime.value = Math.min(DURATION, playOrigin + elapsed)
      if (playheadTime.value >= DURATION) { isPlaying.value = false; return }
      playRAF = requestAnimationFrame(tick)
    }
    playRAF = requestAnimationFrame(tick)
  }
}

function seekTimeline(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  playheadTime.value = ratio * DURATION
  playOrigin = playheadTime.value
  if (isPlaying.value) { playStart = Date.now() }
}

onUnmounted(() => {
  if (playRAF) cancelAnimationFrame(playRAF)
})

onMounted(() => {
  setTimeout(() => fitView({ padding: 0.1 }), 100)
})
</script>

<template>
  <div class="canvas-page">

    <!-- ── Top Bar ─────────────────────────────────────────────────────── -->
    <header class="topbar">
      <button class="back-btn" @click="router.back()">← 返回</button>
      <span class="project-name">AIMV Canvas · 项目 #{{ projectId || 'demo' }}</span>
      <div class="topbar-center">
        <div class="mode-switch">
          <button class="mode-btn">线性向导</button>
          <button class="mode-btn active">自由画布</button>
        </div>
      </div>
      <div class="topbar-right">
        <div class="layer-status">
          <span class="layer-dot canvas">Canvas</span>
          <span class="layer-arrow">→</span>
          <span class="layer-dot music">Music</span>
          <span class="layer-arrow">→</span>
          <span class="layer-dot ai">AI</span>
        </div>
        <button class="btn-gen-all">⚡ 生成所有空白镜头</button>
        <button class="btn-export" @click="router.push(`/editor/${projectId}`)">导出时间线 →</button>
      </div>
    </header>

    <!-- ── Main: Canvas + Panel ───────────────────────────────────────── -->
    <div class="main-area">

      <!-- Vue Flow Canvas -->
      <div class="flow-wrap">
        <VueFlow
          :nodes="nodes"
          :edges="edges"
          :node-types="nodeTypes"
          :default-viewport="{ zoom: 0.75 }"
          :min-zoom="0.2"
          :max-zoom="2"
          class="vf"
          @pane-click="selectedNodeId = null"
        >
          <Background pattern-color="rgba(255,255,255,0.04)" :gap="28" :size="1" />
          <Controls position="top-left" />
          <MiniMap
            node-color="#8d5cff"
            mask-color="rgba(0,0,0,0.7)"
            position="bottom-right"
          />

          <!-- Playhead-highlighted node overlay -->
          <template #node-shot="nodeProps">
            <component
              :is="nodeTypes.shot"
              v-bind="nodeProps"
              :selected="nodeProps.id === selectedNodeId || nodeProps.id === highlightedNodeId"
            />
          </template>
        </VueFlow>
      </div>

      <!-- ── Right Panel ──────────────────────────────────────────────── -->
      <aside class="panel" :class="{ open: !!selectedNode && selectedNode.type === 'shot' }">
        <template v-if="selectedNode && selectedNode.type === 'shot'">
          <div class="panel-header">
            <span class="panel-title">Shot #{{ String(selectedNode.data.index).padStart(2,'0') }}</span>
            <span class="panel-status" :class="selectedNode.data.status">{{ selectedNode.data.status }}</span>
          </div>

          <!-- Prompt -->
          <div class="panel-section">
            <label>Prompt</label>
            <textarea class="panel-input" rows="3" :value="selectedNode.data.prompt" readonly />
          </div>

          <!-- Model / Duration -->
          <div class="panel-row">
            <div class="panel-field">
              <label>模型</label>
              <div class="field-val">{{ selectedNode.data.model }}</div>
            </div>
            <div class="panel-field">
              <label>时长</label>
              <div class="field-val">{{ selectedNode.data.duration }}s</div>
            </div>
          </div>

          <!-- Music Layer connection -->
          <div class="panel-section" v-if="canvasContext?.anchor !== null">
            <label class="layer-label music-label">⏱ Music Layer — 时间锚点</label>
            <div class="context-block music-block">
              <div class="cb-row">
                <span class="cb-k">时间位置</span>
                <span class="cb-v">{{ fmt(canvasContext!.anchor!) }}</span>
              </div>
              <div class="cb-row" v-if="canvasContext?.musicSeg">
                <span class="cb-k">段落</span>
                <span class="cb-v" :style="{ color: canvasContext.musicSeg.color }">
                  {{ canvasContext.musicSeg.label }}
                </span>
              </div>
              <div class="cb-row" v-if="canvasContext?.musicSeg">
                <span class="cb-k">能量</span>
                <div class="energy-bar">
                  <div class="energy-fill" :style="{
                    width: (canvasContext.musicSeg.energy * 100) + '%',
                    background: canvasContext.musicSeg.color
                  }" />
                </div>
              </div>
              <div class="cb-row">
                <span class="cb-k">BPM</span>
                <span class="cb-v">{{ BPM }}</span>
              </div>
            </div>
          </div>

          <!-- Canvas Layer connection -->
          <div class="panel-section">
            <label class="layer-label canvas-label">◈ Canvas Layer — 上下文</label>
            <div class="context-block canvas-block">
              <div v-if="canvasContext?.prevNodes.length">
                <div class="cb-label">前驱节点（Frame Chaining 来源）</div>
                <div v-for="n in canvasContext.prevNodes" :key="(n as any).id" class="ctx-node">
                  <span class="ctx-dot done" />
                  <span class="ctx-text">{{ (n as any).data.prompt.slice(0, 32) }}…</span>
                </div>
              </div>
              <div v-if="canvasContext?.nextNodes.length" style="margin-top:8px">
                <div class="cb-label">后继节点（叙事约束）</div>
                <div v-for="n in canvasContext.nextNodes" :key="(n as any).id" class="ctx-node">
                  <span class="ctx-dot pending" />
                  <span class="ctx-text">{{ (n as any).data.prompt.slice(0, 32) }}…</span>
                </div>
              </div>
              <div v-if="!canvasContext?.prevNodes.length && !canvasContext?.nextNodes.length" class="cb-empty">
                无前驱/后继节点
              </div>
            </div>
          </div>

          <!-- AI Layer payload preview -->
          <div class="panel-section">
            <label class="layer-label ai-label">🤖 AI Layer — 生成 Payload 预览</label>
            <pre class="payload-pre">{{ JSON.stringify(generationPayload, null, 2) }}</pre>
          </div>

          <!-- Actions -->
          <div class="panel-actions">
            <button class="btn-regen" :disabled="selectedNode.data.status === 'generating'">
              {{ selectedNode.data.status === 'generating' ? '生成中…' : '重新生成' }}
            </button>
            <button class="btn-copy">复制 Prompt</button>
          </div>
        </template>

        <!-- empty state -->
        <div v-else class="panel-empty">
          <div class="panel-empty-icon">◈</div>
          <p>点击画布中的镜头节点</p>
          <p>查看三层联动上下文</p>
        </div>
      </aside>
    </div>

    <!-- ── Music Timeline ─────────────────────────────────────────────── -->
    <div class="timeline">
      <div class="tl-controls">
        <button class="tl-play" @click="togglePlay">{{ isPlaying ? '⏸' : '▶' }}</button>
        <span class="tl-time">{{ fmt(playheadTime) }} / {{ fmt(DURATION) }}</span>
        <span class="tl-bpm">{{ BPM }} BPM</span>
        <span v-if="currentSegment" class="tl-seg" :style="{ color: currentSegment.color }">
          {{ currentSegment.label }}
        </span>
      </div>
      <div class="tl-track" @click="seekTimeline">
        <!-- Segments -->
        <div
          v-for="seg in segments" :key="seg.label"
          class="tl-seg-block"
          :style="{
            left: (seg.start / DURATION * 100) + '%',
            width: ((seg.end - seg.start) / DURATION * 100) + '%',
            background: seg.color + '22',
            borderLeft: '1px solid ' + seg.color + '55',
          }"
        >
          <span class="tl-seg-label" :style="{ color: seg.color }">{{ seg.label }}</span>
        </div>

        <!-- Beat marks (每8拍一个) -->
        <div
          v-for="b in Math.floor(DURATION * BPM / 60 / 8)" :key="b"
          class="tl-beat"
          :style="{ left: (b * 8 / (DURATION * BPM / 60) * 100) + '%' }"
        />

        <!-- Node anchor pins -->
        <div
          v-for="n in nodes.filter(n => n.type === 'shot' && n.data.timeAnchor !== null)"
          :key="n.id"
          class="tl-anchor-pin"
          :class="{ active: n.id === selectedNodeId || n.id === highlightedNodeId }"
          :style="{ left: ((n.data.timeAnchor as number) / DURATION * 100) + '%' }"
          :title="'Shot #' + n.data.index + ' — ' + String(n.data.prompt ?? '').slice(0, 30)"
          @click.stop="selectedNodeId = n.id"
        >
          <span class="pin-label">#{{ n.data.index }}</span>
        </div>

        <!-- Playhead -->
        <div class="tl-playhead" :style="{ left: playheadPct + '%' }" />
      </div>
    </div>

  </div>
</template>

<style scoped>
.canvas-page {
  display: flex; flex-direction: column; height: 100vh;
  background: #08080e; color: white;
  font-family: "Inter", system-ui, sans-serif;
  overflow: hidden;
}

/* ── Top Bar ──────────────────────────────────────────────────────────── */
.topbar {
  height: 52px; min-height: 52px;
  display: flex; align-items: center; gap: 16px; padding: 0 20px;
  background: rgba(10,10,18,.95); border-bottom: 1px solid rgba(255,255,255,.08);
  z-index: 10;
}
.back-btn {
  background: transparent; border: 1px solid rgba(255,255,255,.15);
  color: rgba(255,255,255,.6); font-size: .82rem; padding: 5px 12px;
  border-radius: 8px; cursor: pointer; white-space: nowrap;
}
.back-btn:hover { color: white; border-color: rgba(255,255,255,.4); }
.project-name { font-size: .85rem; color: rgba(255,255,255,.5); white-space: nowrap; }
.topbar-center { flex: 1; display: flex; justify-content: center; }
.mode-switch { display: flex; gap: 2px; background: rgba(255,255,255,.06); border-radius: 10px; padding: 3px; }
.mode-btn {
  padding: 5px 16px; border-radius: 8px; border: none;
  font-size: .82rem; cursor: pointer; background: transparent; color: rgba(255,255,255,.5);
  transition: all .2s;
}
.mode-btn.active { background: #8d5cff; color: white; font-weight: 600; }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.layer-status { display: flex; align-items: center; gap: 6px; }
.layer-dot {
  font-size: .72rem; font-weight: 700; padding: 3px 8px; border-radius: 999px;
  letter-spacing: .04em;
}
.layer-dot.canvas { background: rgba(141,92,255,.2); color: #a78bfa; border: 1px solid rgba(141,92,255,.4); }
.layer-dot.music  { background: rgba(92,243,255,.15); color: #5cf3ff; border: 1px solid rgba(92,243,255,.3); }
.layer-dot.ai     { background: rgba(243,178,255,.15); color: #f3b2ff; border: 1px solid rgba(243,178,255,.3); }
.layer-arrow { font-size: .75rem; color: rgba(255,255,255,.3); }
.btn-gen-all {
  padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(141,92,255,.4);
  background: rgba(141,92,255,.15); color: #a78bfa; font-size: .82rem; cursor: pointer;
  white-space: nowrap;
}
.btn-gen-all:hover { background: rgba(141,92,255,.3); }
.btn-export {
  padding: 6px 14px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#8d5cff,#f3b2ff); color: #000;
  font-size: .82rem; font-weight: 700; cursor: pointer; white-space: nowrap;
}

/* ── Main ──────────────────────────────────────────────────────────────── */
.main-area { flex: 1; display: flex; overflow: hidden; }
.flow-wrap { flex: 1; position: relative; }
.vf { background: #08080e !important; }

/* ── Panel ──────────────────────────────────────────────────────────────  */
.panel {
  width: 0; min-width: 0; overflow: hidden;
  background: #0d0d18; border-left: 1px solid rgba(255,255,255,.08);
  transition: width .25s ease, min-width .25s ease;
  display: flex; flex-direction: column;
}
.panel.open { width: 300px; min-width: 300px; overflow-y: auto; }

.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 16px 8px; flex-shrink: 0;
}
.panel-title { font-size: 1rem; font-weight: 700; }
.panel-status {
  font-size: .72rem; font-weight: 700; padding: 3px 8px; border-radius: 999px;
  text-transform: uppercase; letter-spacing: .05em;
}
.panel-status.done { background: rgba(74,222,128,.15); color: #4ade80; }
.panel-status.generating { background: rgba(141,92,255,.2); color: #a78bfa; animation: blink 1.2s infinite; }
.panel-status.pending { background: rgba(255,255,255,.08); color: rgba(255,255,255,.4); }
.panel-status.failed { background: rgba(248,113,113,.15); color: #f87171; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }

.panel-section { padding: 8px 16px; border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0; }
.panel-row {
  display: flex; gap: 8px; padding: 8px 16px;
  border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0;
}
.panel-field { flex: 1; }
label { display: block; font-size: .72rem; color: rgba(255,255,255,.4);
  text-transform: uppercase; letter-spacing: .06em; margin-bottom: 5px; }
.layer-label { display: block; font-size: .72rem; font-weight: 700;
  letter-spacing: .04em; margin-bottom: 6px; }
.canvas-label { color: #a78bfa; }
.music-label  { color: #5cf3ff; }
.ai-label     { color: #f3b2ff; }

.panel-input {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  color: rgba(255,255,255,.8); font-size: .82rem; border-radius: 8px; padding: 8px;
  resize: none; line-height: 1.5; font-family: inherit;
}
.field-val {
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px; padding: 6px 10px; font-size: .85rem;
  color: rgba(255,255,255,.8);
}

/* context blocks */
.context-block {
  border-radius: 8px; padding: 10px 12px;
  font-size: .8rem;
}
.music-block  { background: rgba(92,243,255,.05); border: 1px solid rgba(92,243,255,.15); }
.canvas-block { background: rgba(141,92,255,.05); border: 1px solid rgba(141,92,255,.15); }

.cb-row { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.cb-row:last-child { margin-bottom: 0; }
.cb-k { font-size: .75rem; color: rgba(255,255,255,.4); min-width: 56px; }
.cb-v { font-size: .8rem; color: rgba(255,255,255,.8); font-weight: 600; }
.cb-label { font-size: .72rem; color: rgba(255,255,255,.35); margin-bottom: 5px; }
.cb-empty { font-size: .78rem; color: rgba(255,255,255,.25); font-style: italic; }

.energy-bar {
  flex: 1; height: 5px; background: rgba(255,255,255,.1); border-radius: 999px; overflow: hidden;
}
.energy-fill { height: 100%; border-radius: 999px; transition: width .3s; }

.ctx-node { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.ctx-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ctx-dot.done { background: #4ade80; }
.ctx-dot.pending { background: rgba(255,255,255,.3); }
.ctx-text { font-size: .77rem; color: rgba(255,255,255,.55); }

.payload-pre {
  background: rgba(0,0,0,.4); border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px; padding: 10px; font-size: .7rem; color: #a78bfa;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
  max-height: 220px; overflow-y: auto; font-family: monospace; line-height: 1.5;
}

.panel-actions {
  display: flex; gap: 8px; padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0;
}
.btn-regen {
  flex: 1; padding: 9px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#8d5cff,#f3b2ff);
  color: #000; font-weight: 700; font-size: .85rem; cursor: pointer;
}
.btn-regen:disabled { opacity: .5; cursor: not-allowed; }
.btn-copy {
  padding: 9px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,.15);
  background: transparent; color: rgba(255,255,255,.6); font-size: .85rem; cursor: pointer;
}

.panel-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
  color: rgba(255,255,255,.2); font-size: .85rem; text-align: center; padding: 24px;
}
.panel-empty-icon { font-size: 2.5rem; opacity: .3; }
.panel-empty p { margin: 0; }

/* ── Music Timeline ─────────────────────────────────────────────────── */
.timeline {
  height: 72px; min-height: 72px;
  background: rgba(8,8,16,.98); border-top: 1px solid rgba(255,255,255,.08);
  display: flex; align-items: center; gap: 16px; padding: 0 20px;
  flex-shrink: 0;
}
.tl-controls { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.tl-play {
  width: 32px; height: 32px; border-radius: 50%; border: 1px solid rgba(255,255,255,.2);
  background: transparent; color: white; font-size: 1rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.tl-play:hover { background: rgba(141,92,255,.3); }
.tl-time { font-size: .78rem; color: rgba(255,255,255,.5); font-family: monospace; white-space: nowrap; }
.tl-bpm  { font-size: .72rem; color: rgba(141,92,255,.7); font-weight: 700; }
.tl-seg  { font-size: .72rem; font-weight: 700; }

.tl-track {
  flex: 1; height: 44px; position: relative;
  background: rgba(255,255,255,.03); border-radius: 6px;
  border: 1px solid rgba(255,255,255,.08); cursor: crosshair; overflow: hidden;
}
.tl-seg-block {
  position: absolute; top: 0; bottom: 0;
  display: flex; align-items: flex-end; padding-bottom: 4px;
}
.tl-seg-label {
  font-size: 9px; font-weight: 700; letter-spacing: .05em; padding-left: 4px;
  text-transform: uppercase; opacity: .8;
}
.tl-beat {
  position: absolute; top: 0; bottom: 0; width: 1px;
  background: rgba(255,255,255,.05);
}
.tl-anchor-pin {
  position: absolute; top: 4px; transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center;
  cursor: pointer; z-index: 5;
}
.tl-anchor-pin::before {
  content: ''; width: 8px; height: 8px; border-radius: 50%;
  background: rgba(141,92,255,.6); border: 1.5px solid #8d5cff;
  transition: transform .2s;
}
.tl-anchor-pin.active::before {
  background: #8d5cff; transform: scale(1.5);
  box-shadow: 0 0 8px rgba(141,92,255,.8);
}
.pin-label {
  font-size: 8px; color: rgba(255,255,255,.4); margin-top: 2px; white-space: nowrap;
}
.tl-anchor-pin.active .pin-label { color: #a78bfa; }
.tl-playhead {
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: rgba(255,255,255,.9); border-radius: 1px;
  box-shadow: 0 0 8px rgba(255,255,255,.4);
  pointer-events: none; z-index: 10;
}
</style>
