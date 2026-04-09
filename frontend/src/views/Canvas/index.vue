<script setup lang="ts">
import { ref, computed, markRaw, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/minimap/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import ShotNode  from './ShotNode.vue'
import SongNode  from './SongNode.vue'
import CharNode  from './CharNode.vue'
import SceneNode from './SceneNode.vue'

const route  = useRoute()
const router = useRouter()
const projectId = route.params.id as string

// ─── mock music analysis (attached to song1 node) ──────────────────────────
const DURATION = 180
const BPM = 128
const segments = [
  { label: '前奏', start: 0,   end: 22,  color: '#8d5cff', energy: 0.35 },
  { label: 'A段',  start: 22,  end: 74,  color: '#5cf3ff', energy: 0.65 },
  { label: '高潮', start: 74,  end: 144, color: '#f3b2ff', energy: 0.95 },
  { label: 'C段',  start: 144, end: 168, color: '#5cf3ff', energy: 0.60 },
  { label: '尾奏', start: 168, end: 180, color: '#8d5cff', energy: 0.25 },
]

function getSegmentAt(sec: number) {
  return segments.find(s => sec >= s.start && sec < s.end) ?? null
}
function fmt(s: number) {
  const m = Math.floor(s / 60)
  const sec = String(Math.floor(s % 60)).padStart(2, '0')
  return `${m}:${sec}`
}

// ─── zone background nodes (visual areas, not interactive) ────────────────
const ZoneNode = markRaw({
  props: ['data'],
  template: `
    <div :style="{
      width:'100%', height:'100%', borderRadius:'16px', boxSizing:'border-box',
      border:'1px dashed ' + data.color + '28',
      background: 'radial-gradient(ellipse at 20% 20%, ' + data.color + '07 0%, transparent 70%)',
      position:'relative', pointerEvents:'none',
    }">
      <div :style="{ position:'absolute', top:'14px', left:'16px', display:'flex', alignItems:'center', gap:'7px' }">
        <div :style="{ width:'3px', height:'16px', borderRadius:'2px', background: data.color + '55', flexShrink:0 }"></div>
        <div>
          <div :style="{ fontSize:'12px', fontWeight:'700', color:data.color+'aa', letterSpacing:'.04em', lineHeight:'1.2' }">{{ data.label }}</div>
          <div :style="{ fontSize:'9px', color:data.color+'44', letterSpacing:'.1em', textTransform:'uppercase', marginTop:'2px' }">{{ data.sublabel }}</div>
        </div>
      </div>
    </div>
  `,
})

// ─── nodes: music / chars / scenes / shots — all equal, no forced order ────
const initialNodes = [
  // ── Zone backgrounds (rendered first = behind all other nodes) ──────────
  {
    id: 'zone-material', type: 'zone',
    position: { x: 18, y: 28 }, zIndex: -1, draggable: false, selectable: false,
    style: { width: '324px', height: '568px' },
    data: { label: '素材库', sublabel: 'Music / Character', color: '#8d5cff' },
  },
  {
    id: 'zone-scene', type: 'zone',
    position: { x: 352, y: 104 }, zIndex: -1, draggable: false, selectable: false,
    style: { width: '250px', height: '416px' },
    data: { label: '场景', sublabel: 'Scene', color: '#22d3ee' },
  },
  {
    id: 'zone-mv', type: 'zone',
    position: { x: 646, y: 18 }, zIndex: -1, draggable: false, selectable: false,
    style: { width: '860px', height: '548px' },
    data: { label: 'MV 制作', sublabel: 'Shot Sequence', color: '#f3b2ff' },
  },

  // Music
  {
    id: 'song1', type: 'song', position: { x: 60, y: 70 },
    data: { title: '夏日霓虹', mood: 'energetic', bpm: 128, duration: 180, genre: 'Electronic' },
  },
  // Characters
  {
    id: 'char1', type: 'char', position: { x: 60, y: 280 },
    data: { name: '霓虹少女', description: '青春活力的女主角，赛博朋克风格造型', loraId: 'neon_girl_v2', gender: 'female' },
  },
  {
    id: 'char2', type: 'char', position: { x: 60, y: 460 },
    data: { name: '机械武士', description: '冷酷沉默的科幻男配角', loraId: 'mech_warrior_v1', gender: 'male' },
  },
  // Scenes
  {
    id: 'scene1', type: 'scene', position: { x: 380, y: 140 },
    data: { name: '赛博街道', style: '赛博朋克', location: '新东京', lighting: '霓虹夜景' },
  },
  {
    id: 'scene2', type: 'scene', position: { x: 380, y: 360 },
    data: { name: '星空舞台', style: '极简主义', location: '荒野高原', lighting: '追光灯' },
  },
  // Shots — no zone, freely placed
  {
    id: 's1', type: 'shot', position: { x: 680, y: 55 },
    data: {
      index: 1, status: 'done', duration: 5, model: 'Wan2.2', timeAnchor: 4,
      gradient: 'linear-gradient(135deg,#1a1a2e,#16213e)', segment: null,
      prompt: '城市夜景，霓虹倒影，镜头从地面缓慢上扬',
    },
  },
  {
    id: 's2', type: 'shot', position: { x: 680, y: 240 },
    data: {
      index: 2, status: 'done', duration: 6, model: 'veo', timeAnchor: null,
      gradient: 'linear-gradient(135deg,#2d1b69,#4a1942)', segment: null,
      prompt: '女孩独自站在窗边，灯光从侧面打过来',
    },
  },
  {
    id: 's3', type: 'shot', position: { x: 970, y: 140 },
    data: {
      index: 3, status: 'generating', duration: 5, model: 'Seedance 2.0', timeAnchor: 82,
      gradient: 'linear-gradient(135deg,#f5af19,#f12711)', segment: null,
      prompt: '高潮舞蹈爆发，舞台爆破特效，全身跟拍',
    },
  },
  {
    id: 's4', type: 'shot', position: { x: 970, y: 345 },
    data: {
      index: 4, status: 'pending', duration: 7, model: 'veo', timeAnchor: null,
      gradient: 'linear-gradient(135deg,#0f3460,#533483)', segment: null,
      prompt: '双人近景对视，情感高峰，虚化背景',
    },
  },
  {
    id: 's5', type: 'shot', position: { x: 1260, y: 225 },
    data: {
      index: 5, status: 'failed', duration: 6, model: 'Wan2.2', timeAnchor: null,
      gradient: 'linear-gradient(135deg,#314755,#26a0da)', segment: null,
      prompt: '尾奏，女孩独自走向远处，背影渐渐模糊消失',
    },
  },
]

// edge style presets per context type
const EM = { stroke: '#8d5cff', strokeWidth: 1.5, strokeDasharray: '5,4' } // music-ref
const EC = { stroke: '#5c9fff', strokeWidth: 1.5, strokeDasharray: '5,4' } // char-ref
const ES = { stroke: '#22d3ee', strokeWidth: 1.5, strokeDasharray: '5,4' } // scene-ref
const EQ = { stroke: 'rgba(255,255,255,.28)', strokeWidth: 1.5 }            // sequence

const initialEdges = [
  // music-ref: song → shot (animated — music is always "flowing")
  { id: 'em-s1',   source: 'song1',  target: 's1', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
  { id: 'em-s3',   source: 'song1',  target: 's3', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
  // scene-ref
  { id: 'esc1-s1', source: 'scene1', target: 's1', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
  { id: 'esc1-s2', source: 'scene1', target: 's2', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
  { id: 'esc2-s3', source: 'scene2', target: 's3', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
  { id: 'esc2-s5', source: 'scene2', target: 's5', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
  // char-ref
  { id: 'ec1-s2',  source: 'char1',  target: 's2', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
  { id: 'ec1-s3',  source: 'char1',  target: 's3', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
  { id: 'ec1-s4',  source: 'char1',  target: 's4', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
  { id: 'ec2-s4',  source: 'char2',  target: 's4', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
  // shot sequence
  { id: 'es1-2',   source: 's1',     target: 's2', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
  { id: 'es2-3',   source: 's2',     target: 's3', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
  { id: 'es3-4',   source: 's3',     target: 's4', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
  { id: 'es4-5',   source: 's4',     target: 's5', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
]

// ─── vue flow setup ────────────────────────────────────────────────────────
const nodes = ref<any[]>(initialNodes)
const edges = ref<any[]>(initialEdges)

// ─── API state ─────────────────────────────────────────────────────────────
const loading       = ref(false)
const saving        = ref(false)
const canSave       = ref(false)
const projectTitle  = ref('')
const showGuide     = ref(false)
const editingTitle  = ref(false)
const editedTitle   = ref('')

async function startEditTitle() {
  editedTitle.value = projectTitle.value
  editingTitle.value = true
  await nextTick()
  ;(document.getElementById('title-edit-input') as HTMLInputElement | null)?.focus()
}

async function saveProjectTitle() {
  editingTitle.value = false
  const t = editedTitle.value.trim()
  if (!t || t === projectTitle.value || !projectId) return
  const prev = projectTitle.value
  projectTitle.value = t
  document.title = `${t} — Canvas`
  try {
    await api.put(`/projects/${projectId}`, { title: t })
  } catch {
    projectTitle.value = prev
    document.title = `${prev} — Canvas`
  }
}
let saveTimer: ReturnType<typeof setTimeout> | null = null
// Single timer registry for all polling, keyed as "shot:<nodeId>" or "music:<nodeId>"
const _pollingTimers: Record<string, ReturnType<typeof setInterval>> = {}

// ─── undo / redo ───────────────────────────────────────────────────────────
const MAX_HISTORY = 30
const undoStack = ref<Array<{ nodes: any[]; edges: any[] }>>([])
const redoStack = ref<Array<{ nodes: any[]; edges: any[] }>>([])

function _snapshot() {
  return {
    nodes: JSON.parse(JSON.stringify(nodes.value.filter((n: any) => n.type !== 'zone'))),
    edges: JSON.parse(JSON.stringify(edges.value)),
  }
}

function pushHistory() {
  undoStack.value.push(_snapshot())
  if (undoStack.value.length > MAX_HISTORY) undoStack.value.shift()
  redoStack.value = []
}

function undo() {
  if (!undoStack.value.length) return
  redoStack.value.push(_snapshot())
  const prev = undoStack.value.pop()!
  const zoneNodes = initialNodes.filter((n: any) => n.type === 'zone')
  nodes.value = [...zoneNodes, ...prev.nodes]
  edges.value = prev.edges
}

function redo() {
  if (!redoStack.value.length) return
  undoStack.value.push(_snapshot())
  const next = redoStack.value.pop()!
  const zoneNodes = initialNodes.filter((n: any) => n.type === 'zone')
  nodes.value = [...zoneNodes, ...next.nodes]
  edges.value = next.edges
}

// ─── generation status summary ────────────────────────────────────────────
const shotStats = computed(() => {
  const shots = nodes.value.filter(n => n.type === 'shot')
  return {
    total:      shots.length,
    done:       shots.filter(n => n.data.status === 'done').length,
    generating: shots.filter(n => n.data.status === 'generating').length,
    failed:     shots.filter(n => n.data.status === 'failed').length,
  }
})

// Sync shot node status from polling result
function _patchNodeStatus(nodeId: string, status: string, videoUrl?: string | null) {
  let shotIndex: number | null = null
  nodes.value = nodes.value.map(n => {
    if (n.id === nodeId) {
      shotIndex = n.data.index ?? null
      return { ...n, data: { ...n.data, status, ...(videoUrl ? { videoUrl } : {}) } }
    }
    return n
  })
  const idxStr = shotIndex !== null ? ` #${String(shotIndex).padStart(2, '0')}` : ''
  if (status === 'done')   ElMessage.success({ message: `Shot${idxStr} 生成完成 ✓`, duration: 3500 })
  if (status === 'failed') ElMessage.error({ message: `Shot${idxStr} 生成失败`, duration: 4000 })
}

function startPolling(nodeId: string) {
  const key = `shot:${nodeId}`
  if (_pollingTimers[key] || !projectId) return
  _pollingTimers[key] = setInterval(async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}/canvas/shots/${nodeId}`)
      if (data.status === 'done' || data.status === 'failed') {
        stopPolling(nodeId)
        _patchNodeStatus(nodeId, data.status, data.video_url)
      }
    } catch { stopPolling(nodeId) }
  }, 3000)
}

function stopPolling(nodeId: string) {
  const key = `shot:${nodeId}`
  if (_pollingTimers[key]) {
    clearInterval(_pollingTimers[key])
    delete _pollingTimers[key]
  }
}

async function loadCanvas() {
  if (!projectId) return
  loading.value = true
  let savedViewport: { x: number; y: number; zoom: number } | null = null
  try {
    const [canvasRes, projectRes] = await Promise.all([
      api.get(`/projects/${projectId}/canvas`),
      api.get(`/projects/${projectId}`),
    ])
    const data = canvasRes.data
    projectTitle.value = projectRes.data.title ?? ''
    document.title = `${projectTitle.value} — Canvas`
    const savedNodes: any[] = data.nodes ?? []
    const zoneNodes = initialNodes.filter((n: any) => n.type === 'zone')

    if (savedNodes.length > 0) {
      // Existing project — restore saved canvas
      const contentNodes = savedNodes.filter((n: any) => n.type !== 'zone')

      const shotMap: Record<string, { status: string; video_url: string | null }> = {}
      for (const s of (data.shots ?? [])) shotMap[s.node_id] = s

      nodes.value = [
        ...zoneNodes,
        ...contentNodes.map((n: any) => {
          if (n.type === 'shot' && shotMap[n.id]) {
            const s = shotMap[n.id]
            return {
              ...n,
              data: {
                ...n.data,
                status: s.status === 'done' ? 'done' : s.status,
                ...(s.video_url ? { videoUrl: s.video_url } : {}),
              },
            }
          }
          return n
        }),
      ]
      edges.value = data.edges ?? []
      if (data.viewport?.zoom) savedViewport = data.viewport

      nodes.value.filter((n: any) => n.type === 'shot' && n.data.status === 'generating')
        .forEach((n: any) => startPolling(n.id))
    } else {
      // New project — start with empty canvas + show guide
      nodes.value = zoneNodes
      edges.value = []
      showGuide.value = true
    }
  } catch { /* network error — keep zone-only canvas */ }
  finally {
    loading.value = false
    canSave.value = true
    setTimeout(() => {
      if (savedViewport) setViewport(savedViewport)
      else fitView({ padding: 0.12 })
    }, 150)
  }
}

function scheduleSave() {
  if (!canSave.value || !projectId) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    saving.value = true
    try {
      await api.put(`/projects/${projectId}/canvas`, {
        nodes: nodes.value.filter((n: any) => n.type !== 'zone'),
        edges: edges.value,
        viewport: getViewport(),
      })
    } finally { saving.value = false }
  }, 1500)
}

async function generateShot(nodeId: string) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node || !projectId) return
  const payload = generationPayload.value

  updateNodeData(nodeId, { status: 'generating' })
  try {
    await api.post(`/projects/${projectId}/canvas/shots/${nodeId}/generate`, {
      prompt: node.data.prompt ?? '',
      model_name: String(node.data.model ?? 'veo').toLowerCase(),
      duration: node.data.duration ?? 5,
      time_anchor: node.data.timeAnchor ?? null,
      canvas_context: payload?.canvas_context ?? {},
    })
    startPolling(nodeId)
  } catch {
    _patchNodeStatus(nodeId, 'failed')
  }
}

function copyPrompt(text: string) {
  navigator.clipboard?.writeText(text)
}

// ─── node CRUD ─────────────────────────────────────────────────────────────

function updateNodeData(nodeId: string, updates: Record<string, any>) {
  nodes.value = nodes.value.map(n =>
    n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n
  )
}

// Only list models that have a backend adapter implemented.
const VIDEO_MODELS = ['veo', 'seedance', 'grok', 'wan2.2']
const VIDEO_MODEL_LABELS: Record<string, string> = {
  'veo': 'Veo 3.0 (Google)',
  'seedance': 'Seedance 2.0',
  'grok': 'Grok Video',
  'wan2.2': 'Wan 2.2 (本地)',
}

function addNode(type: 'shot' | 'song' | 'char' | 'scene') {
  const id = `${type}-${Date.now()}`
  const shotCount = nodes.value.filter(n => n.type === 'shot').length

  const defaultData: Record<string, any> = {
    shot:  { index: shotCount + 1, prompt: '', model: 'Veo 3.1', duration: 5, status: 'pending',
             gradient: 'linear-gradient(135deg,#1a1a2e,#16213e)', segment: null, timeAnchor: null },
    song:  { title: '新音乐', mood: 'neutral', bpm: 120, duration: 180, genre: 'Electronic',
             description: '', lyrics: '', vocalLanguage: 'unknown', instrumental: false,
             generateStatus: 'idle', audioUrl: null },
    char:  { name: '新角色', description: '', loraId: '', gender: 'other' },
    scene: { name: '新场景', style: '', location: '', lighting: '' },
  }[type]

  pushHistory()
  nodes.value = [...nodes.value, {
    id, type,
    position: { x: 500 + Math.random() * 260 - 130, y: 250 + Math.random() * 200 - 100 },
    data: defaultData,
  }]
  selectedNodeId.value = id
}

function duplicateShot() {
  const node = selectedNode.value
  if (!node || node.type !== 'shot') return
  pushHistory()
  const id = `shot-${Date.now()}`
  const shotCount = nodes.value.filter(n => n.type === 'shot').length
  nodes.value = [...nodes.value, {
    id,
    type: 'shot',
    position: { x: node.position.x + 30, y: node.position.y + 220 },
    selected: false,
    data: { ...node.data, index: shotCount + 1, status: 'pending', videoUrl: null },
  }]
  selectedNodeId.value = id
}

function reindexShots() {
  let idx = 1
  nodes.value = nodes.value.map(n =>
    n.type === 'shot' ? { ...n, data: { ...n.data, index: idx++ } } : n
  )
}

function deleteSelectedNode() {
  const id = selectedNodeId.value
  if (!id) return
  const node = nodes.value.find(n => n.id === id)
  if (!node || node.type === 'zone') return
  pushHistory()
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  selectedNodeId.value = null
  if (node.type === 'shot') reindexShots()
}

// ─── connect handler — infers edge type from source node type ──────────────

function handleConnect(connection: any) {
  const src = nodes.value.find(n => n.id === connection.source)
  const tgt = nodes.value.find(n => n.id === connection.target)
  if (!src || !tgt || src.type === 'zone' || tgt.type === 'zone') return

  const dup = edges.value.some(e => e.source === connection.source && e.target === connection.target)
  if (dup) return

  pushHistory()

  let edgeType = 'sequence'
  let style = EQ
  let animated = false
  if (src.type === 'song')  { edgeType = 'music-ref'; style = EM; animated = true  }
  if (src.type === 'char')  { edgeType = 'char-ref';  style = EC }
  if (src.type === 'scene') { edgeType = 'scene-ref'; style = ES }

  edges.value = [...edges.value, {
    id: `e-${connection.source}-${connection.target}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    type: 'smoothstep',
    animated,
    style,
    data: { edgeType },
  }]
}

// ─── keyboard shortcuts ────────────────────────────────────────────────────

function deleteSelectedEdge() {
  const id = selectedEdgeId.value
  if (!id) return
  pushHistory()
  edges.value = edges.value.filter(e => e.id !== id)
  selectedEdgeId.value = null
}

function onKeydown(e: KeyboardEvent) {
  const inInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)
  // Undo / Redo
  if ((e.metaKey || e.ctrlKey) && !inInput) {
    if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return }
    if (e.key === 'z' &&  e.shiftKey) { e.preventDefault(); redo(); return }
    if (e.key === 'y')                { e.preventDefault(); redo(); return }
  }
  if (e.key !== 'Delete' && e.key !== 'Backspace') return
  if (inInput) return
  if (selectedNodeId.value) deleteSelectedNode()
  else if (selectedEdgeId.value) deleteSelectedEdge()
}

// ─── Music generation (ACE-Step V1.5) ────────────────────────────────────

function startMusicPolling(nodeId: string) {
  const key = `music:${nodeId}`
  if (_pollingTimers[key] || !projectId) return
  _pollingTimers[key] = setInterval(async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}/canvas/music/${nodeId}`)
      if (data.status === 'completed') {
        stopMusicPolling(nodeId)
        updateNodeData(nodeId, { generateStatus: 'done', audioUrl: data.audio_url })
        ElMessage.success('音乐生成完成 ✓')
      } else if (data.status === 'failed') {
        stopMusicPolling(nodeId)
        updateNodeData(nodeId, { generateStatus: 'failed' })
        ElMessage.error('音乐生成失败')
      }
    } catch { stopMusicPolling(nodeId) }
  }, 4000)
}

function stopMusicPolling(nodeId: string) {
  const key = `music:${nodeId}`
  if (_pollingTimers[key]) {
    clearInterval(_pollingTimers[key])
    delete _pollingTimers[key]
  }
}

async function generateMusic(nodeId: string) {
  const node = nodes.value.find(n => n.id === nodeId)
  if (!node || node.type !== 'song' || !projectId) return
  updateNodeData(nodeId, { generateStatus: 'generating' })
  try {
    await api.post(`/projects/${projectId}/canvas/music/generate`, {
      node_id: nodeId,
      description: node.data.description ?? node.data.title ?? '',
      lyrics: node.data.lyrics ?? '',
      bpm: node.data.bpm ?? 0,
      duration: node.data.duration ?? -1,
      vocal_language: node.data.vocalLanguage ?? 'unknown',
      instrumental: node.data.instrumental ?? false,
    })
    startMusicPolling(nodeId)
  } catch {
    updateNodeData(nodeId, { generateStatus: 'failed' })
    ElMessage.error('音乐生成请求失败')
  }
}

// ─── AI prompt suggest & optimize ────────────────────────────────────────
const suggestingPrompt = ref(false)
const optimizingField = ref<string | null>(null)

async function optimizePrompt(
  fieldKey: string,
  type: string,
  currentValue: string,
  updateKey: string,
) {
  if (!selectedNodeId.value || !projectId || !currentValue.trim()) return
  optimizingField.value = fieldKey
  try {
    const { data } = await api.post(`/projects/${projectId}/canvas/optimize-prompt`, {
      prompt: currentValue,
      type,
    })
    updateNodeData(selectedNodeId.value, { [updateKey]: data.prompt })
  } catch {
    ElMessage.error('提示词优化失败，请稍后重试')
  } finally {
    optimizingField.value = null
  }
}

async function suggestPrompt() {
  if (!selectedNodeId.value || !projectId) return
  const node = selectedNode.value
  if (!node || node.type !== 'shot') return
  suggestingPrompt.value = true
  try {
    const { data } = await api.post(`/projects/${projectId}/canvas/prompt-suggest`, {
      shot_index: node.data.index ?? 1,
      canvas_context: generationPayload.value?.canvas_context ?? {},
      existing_prompt: node.data.prompt ?? '',
    })
    updateNodeData(selectedNodeId.value, { prompt: data.prompt })
  } catch {
    ElMessage.error('AI 生成失败，请稍后重试')
  } finally {
    suggestingPrompt.value = false
  }
}

// ─── storyboard → canvas import ───────────────────────────────────────────
async function importFromStoryboard() {
  if (!projectId) return
  try {
    const { data: project } = await api.get(`/projects/${projectId}`)
    const storyboard: any[] = project.storyboard ?? []
    if (!storyboard.length) {
      ElMessage.info('该项目暂无分镜脚本，请先在线性向导中完成规划。')
      return
    }

    const gradients = [
      'linear-gradient(135deg,#1a1a2e,#2d1b69)',
      'linear-gradient(135deg,#0d0d18,#1a2a4a)',
      'linear-gradient(135deg,#14213d,#0d1b2a)',
      'linear-gradient(135deg,#1b1b2f,#162447)',
      'linear-gradient(135deg,#251b37,#1a1a2e)',
    ]

    // Place shot nodes to the right of existing nodes or at a default position
    const existingShots = nodes.value.filter(n => n.type === 'shot').length
    const startX = 720
    const startY = 120

    const newShotNodes = storyboard.map((seg: any, i: number) => ({
      id: `shot-sb-${Date.now()}-${i}`,
      type: 'shot',
      position: {
        x: startX + (i % 4) * 240,
        y: startY + Math.floor(i / 4) * 180,
      },
      data: {
        index: existingShots + i + 1,
        prompt: seg.description ?? seg.image_prompt ?? '',
        model: 'Veo 3.1',
        duration: seg.duration ?? 5,
        status: 'pending',
        gradient: gradients[i % gradients.length],
        segment: seg.label ?? null,
        timeAnchor: null,
      },
    }))

    // Add sequence edges between imported shots
    const newEdges = newShotNodes.slice(1).map((n: any, i: number) => ({
      id: `es-sb-${i}-${Date.now()}`,
      source: newShotNodes[i].id,
      target: n.id,
      type: 'smoothstep',
      animated: false,
      style: EQ,
      data: { edgeType: 'sequence' },
    }))

    nodes.value = [...nodes.value, ...newShotNodes]
    edges.value = [...edges.value, ...newEdges]
    reindexShots()
    ElMessage.success(`已导入 ${newShotNodes.length} 个分镜节点`)
  } catch {
    ElMessage.error('导入失败，请检查项目数据')
  }
}

async function generateAll() {
  if (!projectId) return
  try {
    const { data } = await api.post(`/projects/${projectId}/canvas/generate-all`)
    if (data.dispatched > 0) {
      const dispatchedIds: Set<string> = new Set(data.node_ids ?? [])
      nodes.value = nodes.value.map((n: any) =>
        n.type === 'shot' && dispatchedIds.has(n.id)
          ? { ...n, data: { ...n.data, status: 'generating' } }
          : n
      )
      dispatchedIds.forEach(id => startPolling(id))
    }
  } catch { /* ignore */ }
}

// ─── auto-layout ──────────────────────────────────────────────────────────
function autoLayout() {
  const songs  = nodes.value.filter(n => n.type === 'song')
  const chars  = nodes.value.filter(n => n.type === 'char')
  const scenes = nodes.value.filter(n => n.type === 'scene')
  const shots  = nodes.value.filter(n => n.type === 'shot')
  const zones  = nodes.value.filter(n => n.type === 'zone')

  pushHistory()

  const COL_MAT  = 80    // songs + chars
  const COL_SCN  = 400   // scenes
  const COL_SHOT = 700   // shots (2 sub-columns)
  const ROW_GAP  = 190

  const laid: any[] = [...zones]
  songs.forEach((n, i) => laid.push({ ...n, position: { x: COL_MAT, y: 80 + i * ROW_GAP } }))
  chars.forEach((n, i) => laid.push({ ...n, position: { x: COL_MAT, y: 80 + (songs.length + i) * ROW_GAP } }))
  scenes.forEach((n, i) => laid.push({ ...n, position: { x: COL_SCN, y: 100 + i * ROW_GAP } }))
  shots.forEach((n, i) => {
    const col = Math.floor(i / 4)
    const row = i % 4
    laid.push({ ...n, position: { x: COL_SHOT + col * 260, y: 50 + row * ROW_GAP } })
  })

  nodes.value = laid
  setTimeout(() => fitView({ padding: 0.1 }), 120)
}

function minimapNodeColor(node: any): string {
  const map: Record<string, string> = {
    shot:  '#8d5cff',
    song:  '#a855f7',
    char:  '#3b82f6',
    scene: '#06b6d4',
    zone:  'rgba(0,0,0,0)',
  }
  return map[node.type] ?? '#8d5cff'
}

const nodeTypes: Record<string, any> = {
  shot:  markRaw(ShotNode),
  song:  markRaw(SongNode),
  char:  markRaw(CharNode),
  scene: markRaw(SceneNode),
  zone:  ZoneNode,
}

const { onNodeClick, onEdgeClick, fitView, getViewport, setViewport } = useVueFlow()
const selectedNodeId  = ref<string | null>(null)
const selectedEdgeId  = ref<string | null>(null)

onNodeClick(({ node }) => {
  if (node.type === 'zone') return
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
})

onEdgeClick(({ edge }) => {
  selectedEdgeId.value = edge.id
  selectedNodeId.value = null
})

// ─── context: traverse edges to collect upstream context ──────────────────
const selectedNode = computed(() =>
  nodes.value.find(n => n.id === selectedNodeId.value) ?? null
)

const canvasContext = computed(() => {
  const id = selectedNodeId.value
  if (!id) return null
  const node = nodes.value.find(n => n.id === id)
  if (!node) return null

  const inEdges  = edges.value.filter(e => e.target === id)
  const outEdges = edges.value.filter(e => e.source === id)

  if (node.type === 'shot') {
    const byType = (t: string) =>
      inEdges.filter(e => e.data?.edgeType === t)
        .map(e => nodes.value.find(n => n.id === e.source)).filter(Boolean)

    const musicNodes = byType('music-ref')
    const charNodes  = byType('char-ref')
    const sceneNodes = byType('scene-ref')
    const prevShots  = byType('sequence')
    const nextShots  = outEdges.filter(e => e.data?.edgeType === 'sequence')
      .map(e => nodes.value.find(n => n.id === e.target)).filter(Boolean)

    return { nodeType: 'shot', musicNodes, charNodes, sceneNodes, prevShots, nextShots }
  }

  // For music/char/scene nodes: show which shots reference them
  const connectedShots = outEdges
    .map(e => nodes.value.find(n => n.id === e.target))
    .filter(n => n?.type === 'shot')
  return { nodeType: node.type, connectedShots }
})

// Generation payload: assembles only what's actually connected
const generationPayload = computed(() => {
  const ctx = canvasContext.value as any
  if (!ctx || ctx.nodeType !== 'shot') return null
  const nd = selectedNode.value!.data as any
  return {
    prompt: nd.prompt,
    model_name: String(nd.model ?? '').toLowerCase().replace(/\s/g, '_'),
    canvas_context: {
      music: ctx.musicNodes.length
        ? ctx.musicNodes.map((n: any) => ({
            song_id: n.id, title: n.data.title,
            bpm: n.data.bpm, mood: n.data.mood, time_anchor: nd.timeAnchor,
          }))
        : null,
      characters: ctx.charNodes.length
        ? ctx.charNodes.map((n: any) => ({ char_id: n.id, name: n.data.name, lora_id: n.data.loraId }))
        : null,
      scene: ctx.sceneNodes.length
        ? ctx.sceneNodes.map((n: any) => ({ scene_id: n.id, name: n.data.name, style: n.data.style }))
        : null,
      prev_frames: ctx.prevShots
        .filter((n: any) => n.data.status === 'done' && n.data.videoUrl)
        .map((n: any) => ({ shot_id: n.id, last_frame_url: n.data.videoUrl })),
    },
  }
})

// ─── music playhead ────────────────────────────────────────────────────────
const playheadTime = ref(82)
const isPlaying    = ref(false)
let playRAF: number | null = null
let playStart: number | null = null
let playOrigin = 82

const playheadPct    = computed(() => (playheadTime.value / DURATION) * 100)
const currentSegment = computed(() => getSegmentAt(playheadTime.value))

const highlightedNodeId = computed(() => {
  const t = playheadTime.value
  return nodes.value
    .filter(n => n.type === 'shot')
    .find(n => {
      const a = n.data.timeAnchor as number | null
      return a !== null && Math.abs(a - t) < 8
    })?.id ?? null
})

function togglePlay() {
  if (isPlaying.value) {
    isPlaying.value = false
    if (playRAF) cancelAnimationFrame(playRAF)
  } else {
    isPlaying.value = true
    playOrigin = playheadTime.value
    playStart  = Date.now()
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
  const rect  = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const t     = ratio * DURATION
  playheadTime.value = t
  playOrigin = t
  if (isPlaying.value) playStart = Date.now()

  // When a shot is selected: shift+click clears anchor, plain click sets it
  const selId = selectedNodeId.value
  if (selId) {
    const node = nodes.value.find(n => n.id === selId)
    if (node?.type === 'shot') {
      if (e.shiftKey) {
        updateNodeData(selId, { timeAnchor: null, segment: null })
      } else {
        const anchor = Math.round(t)
        updateNodeData(selId, {
          timeAnchor: anchor,
          segment: getSegmentAt(anchor)?.label ?? null,
        })
      }
    }
  }
}

// Auto-save on any canvas change
watch([nodes, edges], scheduleSave, { deep: true })

// ─── WebSocket: live generation updates ────────────────────────────────────
let ws: WebSocket | null = null
let wsDestroyed = false

function connectWS() {
  if (!projectId || wsDestroyed) return
  const wsBase = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/^http/, 'ws')
  ws = new WebSocket(`${wsBase}/ws/projects/${projectId}/progress`)

  ws.onopen = () => {
    const token = localStorage.getItem('token')
    ws!.send(JSON.stringify({ type: 'auth', token }))
  }

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      const nodeId: string | undefined = msg.node_id
      if (!nodeId) return
      if (msg.status === 'completed') {
        if (msg.type === 'music') {
          stopMusicPolling(nodeId)
          updateNodeData(nodeId, { generateStatus: 'done', audioUrl: msg.file_url })
          ElMessage.success('音乐生成完成 ✓')
        } else {
          stopPolling(nodeId)
          _patchNodeStatus(nodeId, 'done', msg.file_url)
        }
      } else if (msg.status === 'failed') {
        if (msg.type === 'music') {
          stopMusicPolling(nodeId)
          updateNodeData(nodeId, { generateStatus: 'failed' })
          ElMessage.error('音乐生成失败')
        } else {
          stopPolling(nodeId)
          _patchNodeStatus(nodeId, 'failed')
        }
      }
    } catch { /* ignore parse errors */ }
  }

  ws.onclose = (ev) => {
    // 4001 = bad/missing token, 4003 = project not owned — no point retrying
    const terminal = ev.code === 4001 || ev.code === 4003
    if (!wsDestroyed && !terminal) setTimeout(connectWS, 5000)
  }
}

// ─── canvas templates ─────────────────────────────────────────────────────
const showTemplates = ref(false)

const TEMPLATES = [
  {
    id: 'lyrical',
    name: '抒情情歌',
    desc: '慢节奏抒情 — 音乐 + 角色 + 3 个情感镜头',
    icon: '💿',
    nodes: [
      { id: 'tpl-song1', type: 'song', position: { x: 80, y: 80 },
        data: { title: '思念', mood: 'melancholic', bpm: 76, duration: 240, genre: 'Pop' } },
      { id: 'tpl-char1', type: 'char', position: { x: 80, y: 300 },
        data: { name: '女主角', description: '情感丰富的女性角色', loraId: '', gender: 'female' } },
      { id: 'tpl-scene1', type: 'scene', position: { x: 400, y: 80 },
        data: { name: '海边黄昏', style: '写实主义', location: '海边', lighting: '暖色夕阳' } },
      { id: 'tpl-s1', type: 'shot', position: { x: 690, y: 50 },
        data: { index: 1, status: 'pending', duration: 6, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#1a1a2e,#2d1b69)',
          prompt: '海边，女孩站在浪旁，长焦背影拍摄，暖色夕阳余晖' } },
      { id: 'tpl-s2', type: 'shot', position: { x: 690, y: 240 },
        data: { index: 2, status: 'pending', duration: 5, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#14213d,#0d1b2a)',
          prompt: '特写，女孩泪眼模糊，慢动作，浅景深背景虚化，柔光' } },
      { id: 'tpl-s3', type: 'shot', position: { x: 690, y: 430 },
        data: { index: 3, status: 'pending', duration: 7, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#1b1b2f,#162447)',
          prompt: '俯拍，女孩独自沿海边走向远方，画面渐渐暗淡' } },
    ],
    edges: [
      { id: 'te-m1', source: 'tpl-song1', target: 'tpl-s1', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-m2', source: 'tpl-song1', target: 'tpl-s2', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-c1', source: 'tpl-char1', target: 'tpl-s1', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-c2', source: 'tpl-char1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-c3', source: 'tpl-char1', target: 'tpl-s3', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-sc1', source: 'tpl-scene1', target: 'tpl-s1', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc2', source: 'tpl-scene1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-q1', source: 'tpl-s1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q2', source: 'tpl-s2', target: 'tpl-s3', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
    ],
  },
  {
    id: 'rhythm',
    name: '节拍律动',
    desc: '电子音乐卡点快剪 — 4 个节奏镜头锁定音乐节拍',
    icon: '🎧',
    nodes: [
      { id: 'tpl-song1', type: 'song', position: { x: 80, y: 80 },
        data: { title: '霓虹节拍', mood: 'energetic', bpm: 130, duration: 180, genre: 'Electronic' } },
      { id: 'tpl-scene1', type: 'scene', position: { x: 80, y: 300 },
        data: { name: '都市街道夜景', style: '赛博朋克', location: '城市', lighting: '霓虹灯光' } },
      { id: 'tpl-s1', type: 'shot', position: { x: 420, y: 50 },
        data: { index: 1, status: 'pending', duration: 3, model: 'Seedance 2.0', timeAnchor: 0, segment: '前奏',
          gradient: 'linear-gradient(135deg,#0d0d18,#1a2a4a)',
          prompt: '城市全景夜景，霓虹闪烁，镜头快速推进' } },
      { id: 'tpl-s2', type: 'shot', position: { x: 420, y: 220 },
        data: { index: 2, status: 'pending', duration: 3, model: 'Seedance 2.0', timeAnchor: 28, segment: 'A段',
          gradient: 'linear-gradient(135deg,#1a1a2e,#4a1942)',
          prompt: '街头舞者卡点动作爆发，霓虹背景，仰拍' } },
      { id: 'tpl-s3', type: 'shot', position: { x: 700, y: 50 },
        data: { index: 3, status: 'pending', duration: 3, model: 'Seedance 2.0', timeAnchor: 56, segment: '高潮',
          gradient: 'linear-gradient(135deg,#251b37,#533483)',
          prompt: '特效爆破，舞台干冰喷发，快速剪辑卡点' } },
      { id: 'tpl-s4', type: 'shot', position: { x: 700, y: 220 },
        data: { index: 4, status: 'pending', duration: 3, model: 'Seedance 2.0', timeAnchor: 84, segment: 'C段',
          gradient: 'linear-gradient(135deg,#314755,#26a0da)',
          prompt: '慢动作收尾，城市灯光倒影，镜头缓缓拉远' } },
    ],
    edges: [
      { id: 'te-m1', source: 'tpl-song1', target: 'tpl-s1', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-m2', source: 'tpl-song1', target: 'tpl-s2', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-m3', source: 'tpl-song1', target: 'tpl-s3', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-m4', source: 'tpl-song1', target: 'tpl-s4', type: 'smoothstep', animated: true,  style: EM, data: { edgeType: 'music-ref' } },
      { id: 'te-sc1', source: 'tpl-scene1', target: 'tpl-s1', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc2', source: 'tpl-scene1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc3', source: 'tpl-scene1', target: 'tpl-s3', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc4', source: 'tpl-scene1', target: 'tpl-s4', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-q1', source: 'tpl-s1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q2', source: 'tpl-s2', target: 'tpl-s3', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q3', source: 'tpl-s3', target: 'tpl-s4', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
    ],
  },
  {
    id: 'cinematic',
    name: '电影叙事',
    desc: '无音乐参考，纯场景叙事，5 个宽画幅镜头',
    icon: '🎬',
    nodes: [
      { id: 'tpl-char1', type: 'char', position: { x: 80, y: 80 },
        data: { name: '孤独旅人', description: '沉默寡言、内心复杂的主角', loraId: '', gender: 'male' } },
      { id: 'tpl-scene1', type: 'scene', position: { x: 80, y: 300 },
        data: { name: '荒野公路', style: '极简主义', location: '荒野', lighting: '黄金时段自然光' } },
      { id: 'tpl-s1', type: 'shot', position: { x: 420, y: 50 },
        data: { index: 1, status: 'pending', duration: 7, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#1a1a2e,#16213e)',
          prompt: '宽画幅，主角站在荒野公路尽头，仰角，黄金时段逆光剪影' } },
      { id: 'tpl-s2', type: 'shot', position: { x: 420, y: 240 },
        data: { index: 2, status: 'pending', duration: 6, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#14213d,#0d1b2a)',
          prompt: '中景跟拍，主角缓缓行走，沙尘在脚边飞舞，镜头平移' } },
      { id: 'tpl-s3', type: 'shot', position: { x: 420, y: 430 },
        data: { index: 3, status: 'pending', duration: 5, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#251b37,#1a1a2e)',
          prompt: '微距特写，主角手指捡起一枚硬币，岩石粗糙纹理清晰可见' } },
      { id: 'tpl-s4', type: 'shot', position: { x: 720, y: 130 },
        data: { index: 4, status: 'pending', duration: 6, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#1b1b2f,#162447)',
          prompt: '主观视角，地平线上一座城市轮廓，热浪虚影，广角镜头' } },
      { id: 'tpl-s5', type: 'shot', position: { x: 720, y: 330 },
        data: { index: 5, status: 'pending', duration: 8, model: 'Veo 3.1', timeAnchor: null, segment: null,
          gradient: 'linear-gradient(135deg,#314755,#26a0da)',
          prompt: '大远景航拍，主角渺小身影走向城市地平线，画面渐暗' } },
    ],
    edges: [
      { id: 'te-c1', source: 'tpl-char1', target: 'tpl-s1', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-c2', source: 'tpl-char1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-c3', source: 'tpl-char1', target: 'tpl-s3', type: 'smoothstep', animated: false, style: EC, data: { edgeType: 'char-ref' } },
      { id: 'te-sc1', source: 'tpl-scene1', target: 'tpl-s1', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc2', source: 'tpl-scene1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc4', source: 'tpl-scene1', target: 'tpl-s4', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-sc5', source: 'tpl-scene1', target: 'tpl-s5', type: 'smoothstep', animated: false, style: ES, data: { edgeType: 'scene-ref' } },
      { id: 'te-q1', source: 'tpl-s1', target: 'tpl-s2', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q2', source: 'tpl-s2', target: 'tpl-s3', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q3', source: 'tpl-s3', target: 'tpl-s4', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
      { id: 'te-q4', source: 'tpl-s4', target: 'tpl-s5', type: 'smoothstep', animated: false, style: EQ, data: { edgeType: 'sequence' } },
    ],
  },
] as const

function applyTemplate(tpl: typeof TEMPLATES[number]) {
  pushHistory()
  const zoneNodes = initialNodes.filter((n: any) => n.type === 'zone')
  nodes.value = [...zoneNodes, ...tpl.nodes.map(n => ({ ...n }))]
  edges.value = [...tpl.edges.map(e => ({ ...e }))]
  showGuide.value = false
  showTemplates.value = false
  setTimeout(() => fitView({ padding: 0.14 }), 160)
}

onMounted(() => {
  loadCanvas()
  connectWS()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  wsDestroyed = true
  if (playRAF) cancelAnimationFrame(playRAF)
  if (saveTimer) clearTimeout(saveTimer)
  Object.values(_pollingTimers).forEach(clearInterval)
  ws?.close()
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="canvas-page">

    <!-- ── Top Bar ─────────────────────────────────────────────────────────── -->
    <header class="topbar">
      <button class="back-btn" @click="router.back()">&#x2190; &#x8FD4;&#x56DE;</button>
      <input
        v-if="editingTitle"
        id="title-edit-input"
        class="title-edit-input"
        v-model="editedTitle"
        @blur="saveProjectTitle"
        @keyup.enter="saveProjectTitle"
        @keyup.esc="editingTitle = false"
      />
      <span v-else class="project-name" @dblclick="startEditTitle" title="双击重命名">{{ projectTitle || 'AIMV Canvas' }}</span>
      <div class="topbar-center">
        <span class="canvas-badge">&#x2728; 自由画布</span>
        <div class="undo-redo">
          <button class="ur-btn" :disabled="!undoStack.length" @click="undo()" title="撤销 (Ctrl+Z)">&#x21B6;</button>
          <button class="ur-btn" :disabled="!redoStack.length" @click="redo()" title="重做 (Ctrl+Y)">&#x21B7;</button>
        </div>
      </div>
      <div class="topbar-right">
        <!-- Edge legend -->
        <div class="legend">
          <span class="leg-item"><span class="leg-dot" style="background:#8d5cff"></span> &#x97F3;&#x4E50;</span>
          <span class="leg-item"><span class="leg-dot" style="background:#5c9fff"></span> &#x89D2;&#x8272;</span>
          <span class="leg-item"><span class="leg-dot" style="background:#22d3ee"></span> &#x573A;&#x666F;</span>
          <span class="leg-item"><span class="leg-dot" style="background:rgba(255,255,255,.3)"></span> &#x955C;&#x5934;&#x5E8F;&#x5217;</span>
        </div>
        <div v-if="shotStats.total > 0" class="status-counter">
          <span class="sc-done">{{ shotStats.done }}/{{ shotStats.total }}</span>
          <span v-if="shotStats.generating > 0" class="sc-gen">&#x25CF; {{ shotStats.generating }}</span>
          <span v-if="shotStats.failed > 0" class="sc-fail">&#x25CF; {{ shotStats.failed }}</span>
        </div>
        <span v-if="saving" class="saving-hint">&#x1F4BE; &#x4FDD;&#x5B58;&#x4E2D;&#x2026;</span>
        <button class="btn-layout" @click="autoLayout()" title="自动整理节点布局">&#x25A6; 自动布局</button>
        <button class="btn-import" @click="importFromStoryboard()" title="从分镜脚本导入镜头节点">&#x21E9; 导入分镜</button>
        <button class="btn-gen-all" @click="generateAll()">&#x26A1; &#x751F;&#x6210;&#x7A7A;&#x767D;&#x955C;&#x5934;</button>
        <button class="btn-export" @click="router.push(`/editor/${projectId}`)">&#x5BFC;&#x51FA;&#x65F6;&#x95F4;&#x7EBF; &#x2192;</button>
        <button class="topbar-help" @click="showGuide = true" title="使用指南">?</button>
      </div>
    </header>

    <!-- ── Loading overlay ──────────────────────────────────────────────── -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-ring"></div>
      <span>&#x52A0;&#x8F7D;&#x753B;&#x5E03;&#x2026;</span>
    </div>

    <!-- ── Main: Canvas + Panel ───────────────────────────────────────────── -->
    <div class="main-area">

      <div class="flow-wrap">
        <!-- Floating add-node toolbar -->
        <div class="add-toolbar">
          <span class="add-label">+ 添加</span>
          <button class="add-btn shot"  @click="addNode('shot')">&#x1F3AC; 镜头</button>
          <button class="add-btn song"  @click="addNode('song')">&#x1F3B5; 音乐</button>
          <button class="add-btn char"  @click="addNode('char')">&#x1F464; 角色</button>
          <button class="add-btn scene" @click="addNode('scene')">&#x1F3D9; 场景</button>
        </div>

        <VueFlow
          :nodes="nodes"
          :edges="edges"
          :node-types="nodeTypes"
          :default-viewport="{ zoom: 0.72 }"
          :min-zoom="0.15"
          :max-zoom="2.5"
          class="vf"
          @pane-click="selectedNodeId = null; selectedEdgeId = null"
          @connect="handleConnect"
        >
          <Background pattern-color="rgba(255,255,255,0.035)" :gap="24" :size="1" />
          <Controls position="top-left" />
          <MiniMap :node-color="minimapNodeColor" mask-color="rgba(0,0,0,0.7)" position="bottom-right" />

          <!-- slot overrides to pass programmatic selection state -->
          <template #node-shot="np">
            <component :is="nodeTypes.shot"  v-bind="np"
              :selected="np.id === selectedNodeId || np.id === highlightedNodeId"
              @generate="generateShot(np.id)" />
          </template>
          <template #node-song="np">
            <component :is="nodeTypes.song"  v-bind="np" :selected="np.id === selectedNodeId" />
          </template>
          <template #node-char="np">
            <component :is="nodeTypes.char"  v-bind="np" :selected="np.id === selectedNodeId" />
          </template>
          <template #node-scene="np">
            <component :is="nodeTypes.scene" v-bind="np" :selected="np.id === selectedNodeId" />
          </template>
        </VueFlow>
      </div>

      <!-- ── Right Panel ──────────────────────────────────────────────────── -->
      <aside class="panel" :class="{ open: !!selectedNode || !!selectedEdgeId }">

        <!-- Shot panel -->
        <template v-if="selectedNode?.type === 'shot'">
          <div class="panel-header">
            <span class="panel-title">Shot #{{ String(selectedNode.data.index).padStart(2,'0') }}</span>
            <span class="panel-status" :class="(selectedNode.data.status as string)">{{ selectedNode.data.status }}</span>
          </div>

          <div class="panel-section">
            <div class="prompt-label-row">
              <label>Prompt</label>
              <button
                class="btn-ai-suggest"
                :disabled="suggestingPrompt"
                @click="suggestPrompt()"
                title="根据上下文 AI 生成 Prompt"
              >
                <span v-if="suggestingPrompt">生成中…</span>
                <span v-else>✨ AI 生成</span>
              </button>
              <button
                class="btn-optimize"
                :disabled="optimizingField === 'shot_prompt'"
                @click="optimizePrompt('shot_prompt', 'video', (selectedNode.data.prompt as string) ?? '', 'prompt')"
                title="优化 Prompt"
              >
                <span v-if="optimizingField === 'shot_prompt'">优化中…</span>
                <span v-else>✦ 优化</span>
              </button>
            </div>
            <textarea
              class="panel-input"
              rows="4"
              :value="(selectedNode.data.prompt as string)"
              placeholder="描述这个镜头的画面，或点击「✨ AI 生成」自动填写…"
              @input="updateNodeData(selectedNodeId!, { prompt: ($event.target as HTMLTextAreaElement).value })"
            />
          </div>
          <div class="panel-row">
            <div class="panel-field">
              <label>&#x6A21;&#x578B;</label>
              <select
                class="panel-select"
                :value="(selectedNode.data.model as string)"
                @change="updateNodeData(selectedNodeId!, { model: ($event.target as HTMLSelectElement).value })"
              >
                <option v-for="m in VIDEO_MODELS" :key="m" :value="m">{{ VIDEO_MODEL_LABELS[m] ?? m }}</option>
              </select>
            </div>
            <div class="panel-field">
              <label>&#x65F6;&#x957F; (s)</label>
              <input
                type="number"
                class="panel-input-sm"
                :value="(selectedNode.data.duration as number)"
                min="3" max="30" step="1"
                @change="updateNodeData(selectedNodeId!, { duration: Number(($event.target as HTMLInputElement).value) })"
              />
            </div>
          </div>

          <!-- Time anchor -->
          <div class="anchor-row">
            <span class="anchor-label">&#x23F1; 音乐锁点</span>
            <span v-if="selectedNode.data.timeAnchor !== null" class="anchor-val">
              {{ fmt(selectedNode.data.timeAnchor as number) }}
              <button class="anchor-clear" @click="updateNodeData(selectedNodeId!, { timeAnchor: null, segment: null })" title="清除锁点">&#x2715;</button>
            </span>
            <span v-else class="anchor-empty">未设置 — 点击时间轴</span>
          </div>

          <!-- Music context -->
          <div v-if="(canvasContext as any)?.musicNodes?.length" class="panel-section">
            <label class="layer-label music-label">&#x1F3B5; Music</label>
            <div class="context-block music-block">
              <div v-for="n in (canvasContext as any).musicNodes" :key="n.id" class="ctx-row">
                <span class="ctx-name">{{ n.data.title }}</span>
                <span class="ctx-tag">{{ n.data.bpm }} BPM</span>
                <span class="ctx-tag mood-tag">{{ n.data.mood }}</span>
              </div>
              <div v-if="selectedNode.data.timeAnchor !== null" class="cb-row" style="margin-top:5px">
                <span class="cb-k">&#x65F6;&#x95F4;&#x9501;&#x70B9;</span>
                <span class="cb-v">&#x23F1; {{ fmt(selectedNode.data.timeAnchor as number) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="panel-section no-ctx">
            <span class="ctx-hint">&#x1F3B5; &#x672A;&#x8FDE;&#x63A5;&#x97F3;&#x4E50;&#x8282;&#x70B9;</span>
          </div>

          <!-- Character context -->
          <div v-if="(canvasContext as any)?.charNodes?.length" class="panel-section">
            <label class="layer-label char-label">&#x1F464; Characters ({{ (canvasContext as any).charNodes.length }})</label>
            <div class="context-block char-block">
              <div v-for="n in (canvasContext as any).charNodes" :key="n.id" class="ctx-row">
                <span class="ctx-name">{{ n.data.name }}</span>
                <span class="ctx-tag lora-tag">{{ n.data.loraId }}</span>
              </div>
            </div>
          </div>
          <div v-else class="panel-section no-ctx">
            <span class="ctx-hint">&#x1F464; &#x672A;&#x8FDE;&#x63A5;&#x89D2;&#x8272;&#x8282;&#x70B9;</span>
          </div>

          <!-- Scene context -->
          <div v-if="(canvasContext as any)?.sceneNodes?.length" class="panel-section">
            <label class="layer-label scene-label">&#x1F3D9; Scene</label>
            <div class="context-block scene-block">
              <div v-for="n in (canvasContext as any).sceneNodes" :key="n.id" class="ctx-row">
                <span class="ctx-name">{{ n.data.name }}</span>
                <span class="ctx-tag">{{ n.data.style }}</span>
                <span class="ctx-tag">{{ n.data.lighting }}</span>
              </div>
            </div>
          </div>
          <div v-else class="panel-section no-ctx">
            <span class="ctx-hint">&#x1F3D9; &#x672A;&#x8FDE;&#x63A5;&#x573A;&#x666F;&#x8282;&#x70B9;</span>
          </div>

          <!-- Frame chaining -->
          <div class="panel-section">
            <label class="layer-label canvas-label">&#x25C8; Frame Chaining</label>
            <div class="context-block canvas-block">
              <template v-if="(canvasContext as any)?.prevShots?.length">
                <div class="cb-label">&#x2190; &#x524D;&#x9A71;</div>
                <div v-for="n in (canvasContext as any).prevShots" :key="(n as any).id" class="ctx-node">
                  <span class="ctx-dot done" />
                  <span class="ctx-text">{{ String((n as any).data.prompt ?? '').slice(0,30) }}&#x2026;</span>
                </div>
              </template>
              <template v-if="(canvasContext as any)?.nextShots?.length">
                <div class="cb-label" style="margin-top:6px">&#x2192; &#x540E;&#x7EE7;</div>
                <div v-for="n in (canvasContext as any).nextShots" :key="(n as any).id" class="ctx-node">
                  <span class="ctx-dot pending" />
                  <span class="ctx-text">{{ String((n as any).data.prompt ?? '').slice(0,30) }}&#x2026;</span>
                </div>
              </template>
              <div v-if="!(canvasContext as any)?.prevShots?.length && !(canvasContext as any)?.nextShots?.length" class="cb-empty">
                &#x65E0;&#x524D;&#x9A71;/&#x540E;&#x7EE7;&#x955C;&#x5934;
              </div>
            </div>
          </div>

          <!-- Video preview when done -->
          <div v-if="selectedNode.data.status === 'done' && selectedNode.data.videoUrl" class="panel-section">
            <label class="layer-label">&#x1F3AC; 预览</label>
            <video
              :src="(selectedNode.data.videoUrl as string)"
              controls
              loop
              class="panel-video"
              :key="(selectedNode.data.videoUrl as string)"
            />
          </div>

          <!-- Generation payload -->
          <div class="panel-section">
            <label class="layer-label ai-label">&#x1F916; Generation Payload</label>
            <pre class="payload-pre">{{ JSON.stringify(generationPayload?.canvas_context, null, 2) }}</pre>
          </div>

          <div class="panel-actions">
            <button
              class="btn-regen"
              :class="{ 'btn-retry': selectedNode.data.status === 'failed' }"
              :disabled="selectedNode.data.status === 'generating'"
              @click="generateShot(selectedNodeId!)"
            >
              <span v-if="selectedNode.data.status === 'generating'">&#x751F;&#x6210;&#x4E2D;&#x2026;</span>
              <span v-else-if="selectedNode.data.status === 'failed'">&#x21BA; &#x91CD;&#x8BD5;</span>
              <span v-else>&#x26A1; &#x751F;&#x6210;</span>
            </button>
            <button class="btn-copy" @click="copyPrompt(selectedNode.data.prompt as string)" title="复制 Prompt">&#x590D;&#x5236;</button>
            <button class="btn-copy" @click="duplicateShot()" title="复制节点">&#x2398;</button>
            <button class="btn-delete" @click="deleteSelectedNode()" title="&#x5220;&#x9664;&#x8282;&#x70B9; (Del)">&#x1F5D1;</button>
          </div>
        </template>

        <!-- Song panel -->
        <template v-else-if="selectedNode?.type === 'song'">
          <div class="panel-header">
            <span class="panel-title">&#x1F3B5; Music</span>
            <button class="btn-delete-sm" @click="deleteSelectedNode()" title="&#x5220;&#x9664;">&#x1F5D1;</button>
          </div>
          <div class="panel-section">
            <label>&#x6807;&#x9898;</label>
            <input class="panel-input-line" :value="(selectedNode.data.title as string)"
              @input="updateNodeData(selectedNodeId!, { title: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="panel-row">
            <div class="panel-field">
              <label>&#x98CE;&#x683C;</label>
              <input class="panel-input-line" :value="(selectedNode.data.genre as string)"
                @input="updateNodeData(selectedNodeId!, { genre: ($event.target as HTMLInputElement).value })" />
            </div>
            <div class="panel-field">
              <label>BPM</label>
              <input type="number" class="panel-input-sm" :value="(selectedNode.data.bpm as number)" min="60" max="200"
                @change="updateNodeData(selectedNodeId!, { bpm: Number(($event.target as HTMLInputElement).value) })" />
            </div>
          </div>
          <div class="np-tags" style="padding: 0 16px 8px">
            <span class="np-tag purple">{{ selectedNode.data.mood }}</span>
            <span class="np-tag purple">{{ fmt(selectedNode.data.duration as number) }}</span>
          </div>
          <div class="panel-section">
            <label>&#x6BB5;&#x843D;&#x5206;&#x6790;</label>
            <div class="seg-list">
              <div v-for="seg in segments" :key="seg.label" class="seg-row">
                <span class="seg-lbl" :style="{ color: seg.color }">{{ seg.label }}</span>
                <span class="seg-time">{{ fmt(seg.start) }}&#x2014;{{ fmt(seg.end) }}</span>
                <div class="seg-bar">
                  <div class="seg-fill" :style="{ width: (seg.energy*100)+'%', background: seg.color }" />
                </div>
              </div>
            </div>
          </div>
          <div class="panel-section">
            <label>&#x5DF2;&#x8FDE;&#x63A5;&#x955C;&#x5934;</label>
            <div class="ctx-badge-list">
              <span v-for="n in (canvasContext as any)?.connectedShots" :key="(n as any).id" class="ctx-shot-badge">
                #{{ String((n as any).data.index).padStart(2,'0') }}
              </span>
              <span v-if="!(canvasContext as any)?.connectedShots?.length" class="cb-empty">&#x6682;&#x65E0;&#x8FDE;&#x63A5;</span>
            </div>
          </div>

          <!-- ── ACE-Step V1.5 Music Generation ───────────────────── -->
          <div class="music-gen-section">
            <div class="music-gen-header">
              <span>&#x1F3B6; ACE-Step &#x97F3;&#x4E50;&#x751F;&#x6210;</span>
            </div>
            <div class="panel-section" style="padding:0;margin-top:8px">
              <div class="prompt-label-row">
                <label>&#x97F3;&#x4E50;&#x63CF;&#x8FF0;</label>
                <button
                  class="btn-optimize"
                  :disabled="optimizingField === 'song_desc'"
                  @click="optimizePrompt('song_desc', 'music_desc', (selectedNode.data.description as string) ?? '', 'description')"
                  title="优化音乐描述"
                >
                  <span v-if="optimizingField === 'song_desc'">优化中…</span>
                  <span v-else>✦ 优化</span>
                </button>
              </div>
              <textarea
                class="panel-input"
                rows="3"
                :value="(selectedNode.data.description as string ?? '')"
                placeholder="描述想生成的音乐，例如：'暗黑戏剧古风，高潮激昂，弦乐+打击乐'"
                @input="updateNodeData(selectedNodeId!, { description: ($event.target as HTMLTextAreaElement).value })"
              />
            </div>
            <div class="panel-section" style="padding:0;margin-top:8px">
              <div class="prompt-label-row">
                <label>&#x6B4C;&#x8BCD; (&#x53EF;&#x9009;)</label>
                <button
                  class="btn-optimize"
                  :disabled="optimizingField === 'song_lyrics'"
                  @click="optimizePrompt('song_lyrics', 'music_lyrics', (selectedNode.data.lyrics as string) ?? '', 'lyrics')"
                  title="优化歌词"
                >
                  <span v-if="optimizingField === 'song_lyrics'">优化中…</span>
                  <span v-else>✦ 优化</span>
                </button>
              </div>
              <textarea
                class="panel-input"
                rows="4"
                :value="(selectedNode.data.lyrics as string ?? '')"
                placeholder="[第一段]\n在星空下..."
                @input="updateNodeData(selectedNodeId!, { lyrics: ($event.target as HTMLTextAreaElement).value })"
              />
            </div>
            <div class="panel-row" style="margin-top:8px">
              <div class="panel-field">
                <label>&#x4EBA;&#x58F0;&#x8BED;&#x8A00;</label>
                <select
                  class="panel-select"
                  :value="(selectedNode.data.vocalLanguage as string ?? 'unknown')"
                  @change="updateNodeData(selectedNodeId!, { vocalLanguage: ($event.target as HTMLSelectElement).value })"
                >
                  <option value="unknown">&#x81EA;&#x52A8;</option>
                  <option value="zh">&#x4E2D;&#x6587;</option>
                  <option value="en">English</option>
                  <option value="ja">&#x65E5;&#x672C;&#x8BED;</option>
                  <option value="ko">&#x97E9;&#x8BED;</option>
                </select>
              </div>
              <div class="panel-field" style="justify-content:flex-end;align-items:center">
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:11px;color:rgba(255,255,255,.6)">
                  <input
                    type="checkbox"
                    :checked="!!(selectedNode.data.instrumental)"
                    @change="updateNodeData(selectedNodeId!, { instrumental: ($event.target as HTMLInputElement).checked })"
                    style="accent-color:#8d5cff"
                  />
                  &#x7EAF;&#x97F3;&#x4E50;
                </label>
              </div>
            </div>
            <div class="panel-actions" style="margin-top:12px">
              <button
                class="btn-gen-music"
                :class="{ 'btn-gen-music--fail': selectedNode.data.generateStatus === 'failed' }"
                :disabled="selectedNode.data.generateStatus === 'generating'"
                @click="generateMusic(selectedNodeId!)"
              >
                <span v-if="selectedNode.data.generateStatus === 'generating'">&#x1F3B5; &#x751F;&#x6210;&#x4E2D;&#x2026;</span>
                <span v-else-if="selectedNode.data.generateStatus === 'done'">&#x21BA; &#x91CD;&#x65B0;&#x751F;&#x6210;</span>
                <span v-else-if="selectedNode.data.generateStatus === 'failed'">&#x21BA; &#x91CD;&#x8BD5;</span>
                <span v-else>&#x26A1; AI &#x751F;&#x6210;&#x97F3;&#x4E50;</span>
              </button>
            </div>
            <div v-if="selectedNode.data.generateStatus === 'done' && selectedNode.data.audioUrl" class="panel-section" style="padding:0;margin-top:12px">
              <label class="layer-label">&#x1F50A; &#x9884;&#x89C8;</label>
              <audio
                :src="(selectedNode.data.audioUrl as string)"
                controls
                class="panel-audio"
                :key="(selectedNode.data.audioUrl as string)"
              />
            </div>
          </div>
        </template>

        <!-- Char panel -->
        <template v-else-if="selectedNode?.type === 'char'">
          <div class="panel-header">
            <span class="panel-title">&#x1F464; Character</span>
            <button class="btn-delete-sm" @click="deleteSelectedNode()" title="&#x5220;&#x9664;">&#x1F5D1;</button>
          </div>
          <div class="panel-section">
            <label>&#x540D;&#x79F0;</label>
            <input class="panel-input-line" :value="(selectedNode.data.name as string)"
              @input="updateNodeData(selectedNodeId!, { name: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="panel-section">
            <div class="prompt-label-row">
              <label>&#x63CF;&#x8FF0;</label>
              <button
                class="btn-optimize"
                :disabled="optimizingField === 'char_desc'"
                @click="optimizePrompt('char_desc', 'character', (selectedNode.data.description as string) ?? '', 'description')"
                title="优化角色描述"
              >
                <span v-if="optimizingField === 'char_desc'">优化中…</span>
                <span v-else>✦ 优化</span>
              </button>
            </div>
            <textarea class="panel-input" rows="2" :value="(selectedNode.data.description as string)"
              @input="updateNodeData(selectedNodeId!, { description: ($event.target as HTMLTextAreaElement).value })" />
          </div>
          <div class="panel-section">
            <label>LoRA &#x6A21;&#x578B; ID</label>
            <input class="panel-input-line" style="font-family:monospace" :value="(selectedNode.data.loraId as string)"
              placeholder="e.g. neon_girl_v2"
              @input="updateNodeData(selectedNodeId!, { loraId: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="panel-section">
            <label>&#x51FA;&#x73B0;&#x7684;&#x955C;&#x5934;</label>
            <div class="ctx-badge-list">
              <span v-for="n in (canvasContext as any)?.connectedShots" :key="(n as any).id" class="ctx-shot-badge blue">
                #{{ String((n as any).data.index).padStart(2,'0') }}
              </span>
              <span v-if="!(canvasContext as any)?.connectedShots?.length" class="cb-empty">&#x6682;&#x65E0;&#x8FDE;&#x63A5;</span>
            </div>
          </div>
        </template>

        <!-- Scene panel -->
        <template v-else-if="selectedNode?.type === 'scene'">
          <div class="panel-header">
            <span class="panel-title">&#x1F3D9; Scene</span>
            <button class="btn-delete-sm" @click="deleteSelectedNode()" title="&#x5220;&#x9664;">&#x1F5D1;</button>
          </div>
          <div class="panel-section">
            <label>&#x540D;&#x79F0;</label>
            <input class="panel-input-line" :value="(selectedNode.data.name as string)"
              @input="updateNodeData(selectedNodeId!, { name: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="panel-row">
            <div class="panel-field">
              <label>&#x98CE;&#x683C;</label>
              <input class="panel-input-line" :value="(selectedNode.data.style as string)"
                @input="updateNodeData(selectedNodeId!, { style: ($event.target as HTMLInputElement).value })" />
            </div>
            <div class="panel-field">
              <label>&#x706F;&#x5149;</label>
              <input class="panel-input-line" :value="(selectedNode.data.lighting as string)"
                @input="updateNodeData(selectedNodeId!, { lighting: ($event.target as HTMLInputElement).value })" />
            </div>
          </div>
          <div class="panel-section">
            <label>&#x5730;&#x70B9;</label>
            <input class="panel-input-line" :value="(selectedNode.data.location as string)"
              @input="updateNodeData(selectedNodeId!, { location: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="panel-section">
            <label>&#x4F7F;&#x7528;&#x6B64;&#x573A;&#x666F;&#x7684;&#x955C;&#x5934;</label>
            <div class="ctx-badge-list">
              <span v-for="n in (canvasContext as any)?.connectedShots" :key="(n as any).id" class="ctx-shot-badge teal">
                #{{ String((n as any).data.index).padStart(2,'0') }}
              </span>
              <span v-if="!(canvasContext as any)?.connectedShots?.length" class="cb-empty">&#x6682;&#x65E0;&#x8FDE;&#x63A5;</span>
            </div>
          </div>
        </template>

        <!-- Edge selected -->
        <template v-else-if="selectedEdgeId">
          <div class="panel-header">
            <span class="panel-title">连接线</span>
          </div>
          <div class="panel-empty" style="padding-top:12px">
            <p class="pe-hint">选中了一条连接</p>
            <button class="btn-delete" style="margin-top:16px" @click="deleteSelectedEdge()">删除连接线 (Del)</button>
          </div>
        </template>

        <!-- Empty state -->
        <div v-else class="panel-empty">
          <div class="panel-empty-icon">&#x25C8;</div>
          <p>&#x70B9;&#x51FB;&#x4EFB;&#x610F;&#x8282;&#x70B9;&#x67E5;&#x770B;&#x8BE6;&#x60C5;</p>
          <p class="pe-hint">&#x1F3B5; &#x97F3;&#x4E50; &nbsp;&#x1F464; &#x89D2;&#x8272; &nbsp;&#x1F3D9; &#x573A;&#x666F; &nbsp;&#x1F3AC; &#x955C;&#x5934;</p>
          <p class="pe-hint">&#x5747;&#x53EF;&#x4F5C;&#x4E3A;&#x751F;&#x6210;&#x4E0A;&#x4E0B;&#x6587;&#xFF0C;&#x81EA;&#x7531;&#x7EC4;&#x5408;</p>
        </div>
      </aside>
    </div>

    <!-- ── Music Timeline ─────────────────────────────────────────────────── -->
    <div class="timeline">
      <div class="tl-controls">
        <button class="tl-play" @click="togglePlay">{{ isPlaying ? '&#x23F8;' : '&#x25B6;' }}</button>
        <span class="tl-time">{{ fmt(playheadTime) }} / {{ fmt(DURATION) }}</span>
        <span class="tl-bpm">{{ BPM }} BPM</span>
        <span v-if="currentSegment" class="tl-seg" :style="{ color: currentSegment.color }">
          {{ currentSegment.label }}
        </span>
        <span v-if="selectedNode?.type === 'shot'" class="tl-hint tl-hint-active">
          &#x21E7; &#x70B9;&#x51FB;&#x8BBE;&#x7F6E;&#x9501;&#x70B9; &nbsp;Shift+&#x70B9;&#x51FB;&#x6E05;&#x9664;
        </span>
        <span v-else class="tl-hint">&#x2014; &#x9009;&#x4E2D;&#x955C;&#x5934;&#x8282;&#x70B9;&#x540E;&#x70B9;&#x51FB;&#x65F6;&#x95F4;&#x8F74;&#x8BBE;&#x7F6E;&#x9501;&#x70B9;</span>
      </div>
      <div class="tl-track" @click="seekTimeline">
        <div
          v-for="seg in segments" :key="seg.label"
          class="tl-seg-block"
          :style="{
            left:  (seg.start / DURATION * 100) + '%',
            width: ((seg.end - seg.start) / DURATION * 100) + '%',
            background: seg.color + '22',
            borderLeft: '1px solid ' + seg.color + '55',
          }"
        >
          <span class="tl-seg-label" :style="{ color: seg.color }">{{ seg.label }}</span>
        </div>

        <div
          v-for="b in Math.floor(DURATION * BPM / 60 / 8)" :key="b"
          class="tl-beat"
          :style="{ left: (b * 8 / (DURATION * BPM / 60) * 100) + '%' }"
        />

        <!-- Only shots with timeAnchor (those connected to a SongNode) show pins -->
        <div
          v-for="n in nodes.filter(n => n.type === 'shot' && n.data.timeAnchor !== null)"
          :key="n.id"
          class="tl-anchor-pin"
          :class="{ active: n.id === selectedNodeId || n.id === highlightedNodeId }"
          :style="{ left: ((n.data.timeAnchor as number) / DURATION * 100) + '%' }"
          :title="'Shot #' + n.data.index + ' \u2014 ' + String(n.data.prompt ?? '').slice(0,30)"
          @click.stop="selectedNodeId = n.id"
        >
          <span class="pin-label">#{{ n.data.index }}</span>
        </div>

        <div class="tl-playhead" :style="{ left: playheadPct + '%' }" />
      </div>
    </div>

    <!-- ── 引导 Overlay ─────────────────────────────────────────────────── -->
    <Transition name="guide-fade">
      <div v-if="showGuide" class="guide-overlay" @click.self="showGuide = false">
        <div class="guide-card">
          <div class="guide-header">
            <div class="guide-logo">✦ AIMV 自由画布</div>
            <p class="guide-sub">像剪辑师一样可视化创作你的 MV — 按以下步骤上手</p>
          </div>

          <div class="guide-steps">
            <div class="guide-step">
              <div class="gs-num">1</div>
              <div class="gs-icon">🎵</div>
              <div class="gs-body">
                <div class="gs-title">添加音乐节点</div>
                <div class="gs-desc">点击底部工具栏「+ 音乐」，填入曲名、BPM 和情绪标签，作为所有镜头的参考背景。</div>
                <button class="gs-btn music" @click="showGuide = false; addNode('song')">+ 添加音乐</button>
              </div>
            </div>

            <div class="guide-step">
              <div class="gs-num">2</div>
              <div class="gs-icon">👤</div>
              <div class="gs-body">
                <div class="gs-title">定义角色 &amp; 场景</div>
                <div class="gs-desc">添加「角色」节点绑定 LoRA 模型，添加「场景」节点定义拍摄环境，连线到镜头后自动注入生成上下文。</div>
                <div class="gs-btn-row">
                  <button class="gs-btn char" @click="showGuide = false; addNode('char')">+ 角色</button>
                  <button class="gs-btn scene" @click="showGuide = false; addNode('scene')">+ 场景</button>
                </div>
              </div>
            </div>

            <div class="guide-step">
              <div class="gs-num">3</div>
              <div class="gs-icon">🎬</div>
              <div class="gs-body">
                <div class="gs-title">规划镜头序列</div>
                <div class="gs-desc">添加多个「镜头」节点，写入画面提示词，用连线串联顺序（前驱帧自动传递），或从已有分镜脚本一键导入。</div>
                <div class="gs-btn-row">
                  <button class="gs-btn shot" @click="showGuide = false; addNode('shot')">+ 镜头</button>
                  <button class="gs-btn import" @click="showGuide = false; importFromStoryboard()">⇩ 导入分镜</button>
                </div>
              </div>
            </div>

            <div class="guide-step">
              <div class="gs-num">4</div>
              <div class="gs-icon">⚡</div>
              <div class="gs-body">
                <div class="gs-title">生成 &amp; 导出</div>
                <div class="gs-desc">选中镜头点击「生成」单独生成，或点击顶栏「⚡ 生成空白镜头」批量生成，完成后「导出时间线」合成完整 MV。</div>
              </div>
            </div>
          </div>

          <!-- Template picker -->
          <div class="guide-tpl-section">
            <div class="guide-tpl-title">或从模板快速开始</div>
            <div class="guide-tpl-grid">
              <div
                v-for="tpl in TEMPLATES"
                :key="tpl.id"
                class="guide-tpl-card"
                @click="applyTemplate(tpl)"
              >
                <div class="gtc-icon">{{ tpl.icon }}</div>
                <div class="gtc-name">{{ tpl.name }}</div>
                <div class="gtc-desc">{{ tpl.desc }}</div>
                <div class="gtc-use">使用此模板 →</div>
              </div>
            </div>
          </div>

          <div class="guide-footer">
            <div class="guide-tip">💡 点击节点查看详情，拖拽连线传递上下文，时间轴锁点对齐音乐节拍</div>
            <button class="guide-start" @click="showGuide = false">我知道了，从空白开始 →</button>
          </div>
        </div>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
.canvas-page {
  display: flex; flex-direction: column; height: 100vh;
  background: #07070d; color: white;
  font-family: "Inter", system-ui, sans-serif;
  overflow: hidden;
}

/* ── Top Bar ──────────────────────────────────────────────────────────── */
.topbar {
  height: 50px; min-height: 50px;
  display: flex; align-items: center; gap: 14px; padding: 0 18px;
  background: rgba(7,7,13,.96);
  border-bottom: 1px solid rgba(255,255,255,.07);
  backdrop-filter: blur(20px);
  z-index: 10;
}
.back-btn {
  background: transparent; border: 1px solid rgba(255,255,255,.12);
  color: rgba(255,255,255,.5); font-size: .8rem; padding: 4px 11px;
  border-radius: 7px; cursor: pointer; white-space: nowrap;
  transition: border-color .2s, color .2s;
}
.back-btn:hover { color: rgba(255,255,255,.85); border-color: rgba(255,255,255,.3); }
.project-name { font-size: .83rem; color: rgba(255,255,255,.45); white-space: nowrap; cursor: default; }
.project-name:hover { color: rgba(255,255,255,.7); }
.topbar-center { flex: 1; display: flex; justify-content: center; align-items: center; }
.canvas-badge {
  font-size: .75rem; font-weight: 600; letter-spacing: .05em;
  padding: 3px 11px; border-radius: 20px;
  background: rgba(141,92,255,.1); border: 0.5px solid rgba(141,92,255,.28);
  color: #c4b5fd;
}
.mode-btn {
  padding: 4px 14px; border-radius: 7px; border: none;
  font-size: .8rem; cursor: pointer; background: transparent; color: rgba(255,255,255,.45);
  transition: all .2s;
}
.mode-btn.active { background: rgba(141,92,255,.25); color: #c4b5fd; font-weight: 600; border: 0.5px solid rgba(141,92,255,.4); }
.topbar-right { display: flex; align-items: center; gap: 12px; }

.legend { display: flex; align-items: center; gap: 10px; }
.leg-item {
  display: flex; align-items: center; gap: 5px;
  font-size: .7rem; color: rgba(255,255,255,.35); white-space: nowrap;
}
.leg-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}

.btn-gen-all {
  padding: 5px 13px; border-radius: 8px;
  border: 0.5px solid rgba(141,92,255,.35);
  background: rgba(141,92,255,.1); color: #a78bfa; font-size: .78rem; cursor: pointer;
  white-space: nowrap; transition: background .15s, border-color .15s;
}
.btn-gen-all:hover { background: rgba(141,92,255,.22); border-color: rgba(141,92,255,.55); }
.saving-hint { font-size: .7rem; color: rgba(255,255,255,.28); white-space: nowrap; }
.loading-overlay {
  position: absolute; inset: 0; z-index: 100;
  background: rgba(7,7,13,.88); backdrop-filter: blur(8px);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;
  color: rgba(255,255,255,.45); font-size: .88rem;
}
.loading-ring {
  width: 32px; height: 32px; border-radius: 50%;
  border: 2px solid rgba(141,92,255,.15); border-top-color: #a78bfa;
  animation: spin .9s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.btn-export {
  padding: 5px 14px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#7c4dff,#d580ff); color: #fff;
  font-size: .78rem; font-weight: 700; cursor: pointer; white-space: nowrap;
  transition: opacity .15s, transform .1s;
}
.btn-export:hover { opacity: .88; }
.btn-export:active { transform: scale(0.97); }

/* ── Main ──────────────────────────────────────────────────────────────── */
.main-area { flex: 1; display: flex; overflow: hidden; }
.flow-wrap { flex: 1; position: relative; }
.vf { background: #07070d !important; }

/* ── Panel ─────────────────────────────────────────────────────────────── */
.panel {
  width: 0; min-width: 0; overflow: hidden;
  background: rgba(10,10,18,.97);
  backdrop-filter: blur(20px);
  border-left: 1px solid rgba(255,255,255,.07);
  transition: width .25s ease, min-width .25s ease;
  display: flex; flex-direction: column;
}
.panel.open { width: 300px; min-width: 300px; overflow-y: auto; }

.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 8px; flex-shrink: 0;
  border-bottom: 1px solid rgba(255,255,255,.05);
}
.panel-title { font-size: .95rem; font-weight: 700; color: rgba(255,255,255,.92); }
.panel-status {
  font-size: .68rem; font-weight: 700; padding: 2px 8px; border-radius: 999px;
  text-transform: uppercase; letter-spacing: .06em;
}
.panel-status.done       { background: rgba(74,222,128,.1);   color: #4ade80; border: 0.5px solid rgba(74,222,128,.2); }
.panel-status.generating { background: rgba(141,92,255,.12);  color: #a78bfa; border: 0.5px solid rgba(141,92,255,.3); animation: blink 1.4s ease infinite; }
.panel-status.pending    { background: rgba(255,255,255,.06); color: rgba(255,255,255,.35); border: 0.5px solid rgba(255,255,255,.1); }
.panel-status.failed     { background: rgba(248,113,113,.1);  color: #fca5a5; border: 0.5px solid rgba(248,113,113,.2); }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.35} }

.panel-section { padding: 8px 16px; border-top: 1px solid rgba(255,255,255,.05); flex-shrink: 0; }
.panel-row {
  display: flex; gap: 8px; padding: 8px 16px;
  border-top: 1px solid rgba(255,255,255,.05); flex-shrink: 0;
}
.panel-field { flex: 1; }
label {
  display: block; font-size: .72rem; color: rgba(255,255,255,.4);
  text-transform: uppercase; letter-spacing: .06em; margin-bottom: 5px;
}
.layer-label { display: block; font-size: .72rem; font-weight: 700; letter-spacing: .04em; margin-bottom: 6px; }
.canvas-label { color: #a78bfa; }
.music-label  { color: #8d5cff; }
.char-label   { color: #5c9fff; }
.scene-label  { color: #22d3ee; }
.ai-label     { color: #f3b2ff; }

.panel-input {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.03); border: 0.5px solid rgba(255,255,255,.09);
  color: rgba(255,255,255,.78); font-size: .82rem; border-radius: 8px; padding: 8px;
  resize: none; line-height: 1.5; font-family: inherit;
  transition: border-color .15s;
}
.panel-input:focus { outline: none; border-color: rgba(141,92,255,.4); background: rgba(255,255,255,.04); }
.field-val {
  background: rgba(255,255,255,.03); border: 0.5px solid rgba(255,255,255,.07);
  border-radius: 8px; padding: 6px 10px; font-size: .85rem; color: rgba(255,255,255,.75);
}

/* context blocks */
.context-block { border-radius: 8px; padding: 9px 11px; font-size: .8rem; }
.music-block  { background: rgba(141,92,255,.05); border: 0.5px solid rgba(141,92,255,.18); }
.char-block   { background: rgba(92,159,255,.05); border: 0.5px solid rgba(92,159,255,.18); }
.scene-block  { background: rgba(34,211,238,.04); border: 0.5px solid rgba(34,211,238,.15); }
.canvas-block { background: rgba(141,92,255,.03); border: 0.5px solid rgba(141,92,255,.13); }

.ctx-row { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; flex-wrap: wrap; }
.ctx-row:last-child { margin-bottom: 0; }
.ctx-name { font-size: .82rem; color: rgba(255,255,255,.85); font-weight: 600; }
.ctx-tag {
  font-size: .7rem; padding: 1px 6px; border-radius: 999px;
  background: rgba(255,255,255,.07); color: rgba(255,255,255,.45);
}
.ctx-tag.mood-tag { color: #a78bfa; background: rgba(141,92,255,.18); }
.ctx-tag.lora-tag { color: #93c5fd; background: rgba(92,159,255,.18); font-family: monospace; }

.no-ctx { padding: 6px 16px !important; }
.ctx-hint { font-size: .75rem; color: rgba(255,255,255,.2); font-style: italic; }

.cb-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.cb-k   { font-size: .75rem; color: rgba(255,255,255,.4); min-width: 52px; }
.cb-v   { font-size: .8rem;  color: rgba(255,255,255,.8); font-weight: 600; }
.cb-label { font-size: .72rem; color: rgba(255,255,255,.35); margin-bottom: 4px; }
.cb-empty { font-size: .78rem; color: rgba(255,255,255,.25); font-style: italic; }

.ctx-node { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.ctx-dot  { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ctx-dot.done    { background: #4ade80; }
.ctx-dot.pending { background: rgba(255,255,255,.3); }
.ctx-text { font-size: .77rem; color: rgba(255,255,255,.55); }

.payload-pre {
  background: rgba(0,0,0,.3); border: 0.5px solid rgba(255,255,255,.06);
  border-radius: 8px; padding: 10px; font-size: .68rem; color: rgba(167,139,250,.7);
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
  max-height: 180px; overflow-y: auto; font-family: "SF Mono","Fira Code",monospace; line-height: 1.5;
}

/* non-shot node panels */
.np-title {
  font-size: 1.1rem; font-weight: 700; color: rgba(255,255,255,.92);
  padding: 4px 16px 8px;
}
.np-desc {
  font-size: .82rem; color: rgba(255,255,255,.5); padding: 0 16px 8px; margin: 0;
  line-height: 1.5;
}
.np-tags { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 16px 10px; }
.np-tag {
  font-size: .78rem; padding: 3px 9px; border-radius: 999px;
  background: rgba(255,255,255,.07); color: rgba(255,255,255,.5);
}
.np-tag.purple { color: #a78bfa; background: rgba(141,92,255,.18); }
.np-tag.blue   { color: #93c5fd; background: rgba(92,159,255,.18); }
.np-tag.teal   { color: #67e8f9; background: rgba(34,211,238,.15); }

.seg-list { display: flex; flex-direction: column; gap: 6px; }
.seg-row  { display: flex; align-items: center; gap: 8px; }
.seg-lbl  { font-size: .75rem; font-weight: 700; min-width: 28px; }
.seg-time { font-size: .7rem; color: rgba(255,255,255,.35); min-width: 72px; font-family: monospace; }
.seg-bar  { flex: 1; height: 4px; background: rgba(255,255,255,.08); border-radius: 999px; overflow: hidden; }
.seg-fill { height: 100%; border-radius: 999px; }

.lora-badge {
  font-size: .82rem; font-family: monospace; color: #93c5fd;
  background: rgba(92,159,255,.1); border: 1px solid rgba(92,159,255,.2);
  border-radius: 8px; padding: 6px 10px;
}

.ctx-badge-list { display: flex; gap: 6px; flex-wrap: wrap; }
.ctx-shot-badge {
  font-size: .78rem; font-weight: 700; padding: 3px 9px; border-radius: 999px;
  background: rgba(141,92,255,.18); color: #a78bfa; font-family: monospace;
}
.ctx-shot-badge.blue { background: rgba(92,159,255,.18); color: #93c5fd; }
.ctx-shot-badge.teal { background: rgba(34,211,238,.15); color: #67e8f9; }

/* editable fields */
.panel-select {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.03); border: 0.5px solid rgba(255,255,255,.09);
  color: rgba(255,255,255,.78); font-size: .82rem; border-radius: 8px; padding: 6px 8px;
  font-family: inherit; cursor: pointer;
  transition: border-color .15s;
}
.panel-input-sm {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.03); border: 0.5px solid rgba(255,255,255,.09);
  color: rgba(255,255,255,.78); font-size: .82rem; border-radius: 8px; padding: 6px 8px;
  font-family: inherit;
  transition: border-color .15s;
}
.panel-input-line {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.03); border: 0.5px solid rgba(255,255,255,.09);
  color: rgba(255,255,255,.78); font-size: .85rem; border-radius: 8px; padding: 6px 10px;
  font-family: inherit;
  transition: border-color .15s;
}
.panel-select:focus, .panel-input-sm:focus, .panel-input-line:focus, .panel-input:focus {
  outline: none; border-color: rgba(141,92,255,.4);
}

/* floating add toolbar */
.add-toolbar {
  position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%);
  z-index: 20; display: flex; align-items: center; gap: 5px;
  background: rgba(10,10,18,.94);
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 14px; padding: 6px 10px;
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04);
}
.add-label {
  font-size: .68rem; color: rgba(255,255,255,.25); margin-right: 4px;
  letter-spacing: .06em; text-transform: uppercase; white-space: nowrap;
}
.add-btn {
  padding: 5px 12px; border-radius: 8px; border: 0.5px solid transparent;
  font-size: .76rem; cursor: pointer; background: rgba(255,255,255,.05);
  color: rgba(255,255,255,.55); transition: all .15s; white-space: nowrap;
}
.add-btn:hover { color: rgba(255,255,255,.9); transform: translateY(-1px); }
.add-btn:active { transform: translateY(0) scale(0.97); }
.add-btn.shot  { border-color: rgba(255,255,255,.1); }
.add-btn.shot:hover  { background: rgba(255,255,255,.1); border-color: rgba(255,255,255,.22); }
.add-btn.song  { border-color: rgba(141,92,255,.22); }
.add-btn.song:hover  { background: rgba(141,92,255,.15); border-color: rgba(141,92,255,.45); color: #c4b5fd; }
.add-btn.char  { border-color: rgba(92,159,255,.22); }
.add-btn.char:hover  { background: rgba(92,159,255,.15); border-color: rgba(92,159,255,.45); color: #93c5fd; }
.add-btn.scene { border-color: rgba(34,211,238,.18); }
.add-btn.scene:hover { background: rgba(34,211,238,.12); border-color: rgba(34,211,238,.4); color: #67e8f9; }

.panel-actions {
  display: flex; gap: 6px; padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,.05); flex-shrink: 0;
}
.btn-regen {
  flex: 1; padding: 9px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#7c4dff,#c480ff);
  color: rgba(255,255,255,.95); font-weight: 700; font-size: .82rem; cursor: pointer;
  transition: opacity .15s, transform .1s;
}
.btn-regen:not(:disabled):hover { opacity: .88; }
.btn-regen:not(:disabled):active { transform: scale(0.98); }
.btn-regen:disabled { opacity: .4; cursor: not-allowed; }
.btn-copy {
  padding: 9px 12px; border-radius: 8px;
  border: 0.5px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.04); color: rgba(255,255,255,.55); font-size: .82rem; cursor: pointer;
  transition: border-color .15s, color .15s;
}
.btn-copy:hover { border-color: rgba(255,255,255,.28); color: rgba(255,255,255,.8); }
.btn-delete {
  padding: 9px 10px; border-radius: 8px;
  border: 0.5px solid rgba(248,113,113,.2);
  background: rgba(248,113,113,.05); color: #fca5a5; font-size: .82rem; cursor: pointer;
  transition: background .15s;
}
.btn-delete:hover { background: rgba(248,113,113,.18); }
.btn-delete-sm {
  padding: 3px 8px; border-radius: 6px;
  border: 0.5px solid rgba(248,113,113,.18);
  background: transparent; color: rgba(248,113,113,.5); font-size: .78rem; cursor: pointer;
  transition: background .15s, color .15s;
}
.btn-delete-sm:hover { background: rgba(248,113,113,.12); color: #fca5a5; }

.panel-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 10px;
  color: rgba(255,255,255,.2); font-size: .85rem; text-align: center; padding: 24px;
}
.panel-empty-icon { font-size: 2.5rem; opacity: .3; }
.panel-empty p { margin: 0; }
.pe-hint { font-size: .78rem; color: rgba(255,255,255,.15); line-height: 1.6; }

/* ── Music Timeline ─────────────────────────────────────────────────────── */
.timeline {
  height: 68px; min-height: 68px;
  background: rgba(7,7,13,.98);
  border-top: 1px solid rgba(255,255,255,.06);
  backdrop-filter: blur(12px);
  display: flex; align-items: center; gap: 14px; padding: 0 18px;
  flex-shrink: 0;
}
.tl-controls { display: flex; align-items: center; gap: 11px; flex-shrink: 0; }
.tl-play {
  width: 30px; height: 30px; border-radius: 50%;
  border: 0.5px solid rgba(255,255,255,.18);
  background: rgba(255,255,255,.04); color: rgba(255,255,255,.75); font-size: .9rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s, border-color .15s;
}
.tl-play:hover { background: rgba(141,92,255,.2); border-color: rgba(141,92,255,.4); color: #c4b5fd; }
.tl-time { font-size: .75rem; color: rgba(255,255,255,.45); font-family: "SF Mono","Fira Code",monospace; white-space: nowrap; }
.tl-bpm  { font-size: .7rem; color: rgba(141,92,255,.65); font-weight: 700; }
.tl-seg  { font-size: .7rem; font-weight: 700; }
.tl-hint { font-size: .66rem; color: rgba(255,255,255,.18); white-space: nowrap; }

.tl-track {
  flex: 1; height: 42px; position: relative;
  background: rgba(255,255,255,.025); border-radius: 8px;
  border: 0.5px solid rgba(255,255,255,.07); cursor: crosshair; overflow: hidden;
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
.pin-label { font-size: 8px; color: rgba(255,255,255,.4); margin-top: 2px; white-space: nowrap; }
.tl-anchor-pin.active .pin-label { color: #a78bfa; }
.tl-playhead {
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: rgba(255,255,255,.9); border-radius: 1px;
  box-shadow: 0 0 8px rgba(255,255,255,.4);
  pointer-events: none; z-index: 10;
}

/* ── topbar help button ───────────────────────────────────────────────── */
.topbar-help {
  width: 26px; height: 26px; border-radius: 50%;
  border: 0.5px solid rgba(255,255,255,.15); background: rgba(255,255,255,.04);
  color: rgba(255,255,255,.4); font-size: .8rem; font-weight: 600;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: border-color .15s, color .15s;
}
.topbar-help:hover { border-color: rgba(141,92,255,.5); color: #c4b5fd; }

/* ── guide overlay ───────────────────────────────────────────────────── */
.guide-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,.7); backdrop-filter: blur(10px);
  display: flex; align-items: center; justify-content: center;
}
.guide-card {
  width: 680px; max-width: 96vw; max-height: 90vh; overflow-y: auto;
  background: rgba(12,12,22,.97);
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 20px; padding: 36px 40px;
  box-shadow: 0 24px 80px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.05);
  backdrop-filter: blur(20px);
}
.guide-header { text-align: center; margin-bottom: 32px; }
.guide-logo {
  font-size: 1.4rem; font-weight: 800; letter-spacing: .02em;
  background: linear-gradient(135deg,#a78bfa,#f3b2ff);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin-bottom: 8px;
}
.guide-sub { font-size: .88rem; color: rgba(255,255,255,.4); }

.guide-steps { display: flex; flex-direction: column; gap: 20px; }
.guide-step {
  display: flex; gap: 16px; align-items: flex-start;
  padding: 16px 18px; border-radius: 12px;
  background: rgba(255,255,255,.025); border: 0.5px solid rgba(255,255,255,.07);
  transition: border-color .2s, background .2s;
}
.guide-step:hover { border-color: rgba(141,92,255,.3); background: rgba(141,92,255,.04); }
.gs-num {
  width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
  background: rgba(141,92,255,.2); border: 0.5px solid rgba(141,92,255,.5);
  color: #c4b5fd; font-size: .7rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center; margin-top: 2px;
}
.gs-icon { font-size: 1.6rem; flex-shrink: 0; }
.gs-body { flex: 1; }
.gs-title { font-size: .95rem; font-weight: 700; margin-bottom: 5px; color: #e2e8f0; }
.gs-desc { font-size: .8rem; color: rgba(255,255,255,.45); line-height: 1.55; margin-bottom: 10px; }
.gs-btn-row { display: flex; gap: 8px; flex-wrap: wrap; }
.gs-btn {
  padding: 5px 14px; font-size: .78rem; border-radius: 8px; cursor: pointer;
  border: 1px solid; font-weight: 600; transition: all .15s;
}
.gs-btn.music  { border-color: #8d5cff; color: #c4b5fd; background: rgba(141,92,255,.12); }
.gs-btn.char   { border-color: #3b82f6; color: #93c5fd; background: rgba(59,130,246,.12); }
.gs-btn.scene  { border-color: #06b6d4; color: #67e8f9; background: rgba(6,182,212,.12); }
.gs-btn.shot   { border-color: #a855f7; color: #d8b4fe; background: rgba(168,85,247,.12); }
.gs-btn.import { border-color: rgba(255,255,255,.2); color: rgba(255,255,255,.6); background: transparent; }
.gs-btn:hover  { filter: brightness(1.25); }

.guide-footer { margin-top: 28px; text-align: center; }
.guide-tip {
  font-size: .78rem; color: rgba(255,255,255,.3);
  margin-bottom: 16px; line-height: 1.6;
}
.guide-start {
  padding: 11px 30px; font-size: .9rem; font-weight: 700;
  background: linear-gradient(135deg,#7c4dff,#c480ff);
  border: none; border-radius: 10px; color: rgba(255,255,255,.95); cursor: pointer;
  transition: opacity .18s, transform .1s;
}
.guide-start:hover { opacity: .88; }
.guide-start:active { transform: scale(0.98); }

.guide-fade-enter-active, .guide-fade-leave-active { transition: opacity .25s; }
.guide-fade-enter-from, .guide-fade-leave-to { opacity: 0; }

/* status counter */
.status-counter {
  display: flex; align-items: center; gap: 6px;
  font-size: .72rem;
  background: rgba(255,255,255,.05); border: 0.5px solid rgba(255,255,255,.08);
  padding: 3px 9px; border-radius: 7px;
}
.sc-done { color: rgba(255,255,255,.5); font-family: "SF Mono","Fira Code",monospace; }
.sc-gen  { color: #fbbf24; font-size: .65rem; }
.sc-fail { color: #f87171; font-size: .65rem; }

/* retry button state */
.btn-retry { border-color: rgba(248,113,113,.6) !important; color: #f87171 !important; }
.btn-retry:hover { background: rgba(248,113,113,.15) !important; }

/* timeline hint when shot selected */
.tl-hint-active { color: rgba(141,92,255,.8) !important; font-weight: 600; }

/* time anchor row in shot panel */
.anchor-row {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; margin: 0 16px 10px;
  background: rgba(141,92,255,.08); border-radius: 6px;
}
.anchor-label { font-size: 11px; color: rgba(255,255,255,.45); }
.anchor-val { font-size: 12px; font-family: monospace; color: #a78bfa; display: flex; align-items: center; gap: 6px; }
.anchor-empty { font-size: 11px; color: rgba(255,255,255,.25); }
.anchor-clear {
  background: transparent; border: none; color: rgba(255,255,255,.3);
  cursor: pointer; font-size: 11px; padding: 0 2px; line-height: 1;
}
.anchor-clear:hover { color: #f87171; }

/* panel video preview */
.panel-video {
  width: 100%; border-radius: 8px;
  background: #000; display: block;
  max-height: 160px; object-fit: contain;
}

/* music gen section */
.music-gen-section {
  border-top: 1px solid rgba(141,92,255,.15);
  padding: 14px 16px 16px;
  background: rgba(141,92,255,.025);
}
.music-gen-header {
  font-size: 10px; font-weight: 700; letter-spacing: .07em;
  color: #a78bfa; text-transform: uppercase; margin-bottom: 2px;
}
.btn-gen-music {
  flex: 1; padding: 9px; border-radius: 8px; border: none;
  background: linear-gradient(135deg, #7c4dff, #4a90e2);
  color: rgba(255,255,255,.95); font-weight: 700; font-size: .82rem; cursor: pointer;
  width: 100%; transition: opacity .15s, transform .1s;
}
.btn-gen-music:disabled { opacity: .4; cursor: not-allowed; }
.btn-gen-music:not(:disabled):hover { opacity: .88; }
.btn-gen-music:not(:disabled):active { transform: scale(0.98); }
.btn-gen-music--fail { background: linear-gradient(135deg,#ef4444,#f472b6) !important; }
.panel-audio {
  width: 100%; border-radius: 8px; display: block;
  background: rgba(0,0,0,.3);
}

/* import from storyboard button */
.btn-import {
  background: transparent; border: 0.5px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.48); font-size: .75rem; padding: 4px 11px;
  border-radius: 7px; cursor: pointer; white-space: nowrap;
  transition: border-color .15s, color .15s;
}
.btn-import:hover { border-color: rgba(255,255,255,.35); color: rgba(255,255,255,.8); }

/* editable project title */
.title-edit-input {
  background: rgba(255,255,255,.07); border: 1px solid rgba(141,92,255,.5);
  color: white; font-size: .85rem; border-radius: 8px;
  padding: 3px 10px; outline: none; max-width: 220px;
}
.project-name { cursor: default; }
.project-name:hover { color: rgba(255,255,255,.75); }

/* auto-layout button */
.btn-layout {
  background: transparent; border: 0.5px solid rgba(255,255,255,.12);
  color: rgba(255,255,255,.4); font-size: .73rem; padding: 4px 10px;
  border-radius: 7px; cursor: pointer; white-space: nowrap;
  transition: border-color .15s, color .15s;
}
.btn-layout:hover { border-color: rgba(255,255,255,.3); color: rgba(255,255,255,.72); }

/* undo / redo buttons */
.undo-redo { display: flex; gap: 3px; margin-left: 8px; }
.ur-btn {
  width: 27px; height: 27px; border-radius: 7px;
  border: 0.5px solid rgba(255,255,255,.12); background: rgba(255,255,255,.03);
  color: rgba(255,255,255,.4); font-size: .95rem; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s;
}
.ur-btn:disabled { opacity: .18; cursor: not-allowed; }
.ur-btn:not(:disabled):hover { border-color: rgba(141,92,255,.4); color: #c4b5fd; background: rgba(141,92,255,.08); }

/* prompt label row (label + AI suggest button) */
.prompt-label-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 5px;
}
.prompt-label-row label { margin-bottom: 0; }
.btn-ai-suggest {
  padding: 2px 10px; font-size: .72rem; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(243,178,255,.3); color: #f3b2ff;
  background: rgba(243,178,255,.08); font-weight: 600; white-space: nowrap;
  transition: all .15s;
}
.btn-ai-suggest:disabled { opacity: .4; cursor: not-allowed; }
.btn-ai-suggest:not(:disabled):hover { background: rgba(243,178,255,.2); border-color: rgba(243,178,255,.6); }
.btn-optimize {
  padding: 2px 10px; font-size: .72rem; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(141,92,255,.35); color: #a78bfa;
  background: rgba(141,92,255,.08); font-weight: 600; white-space: nowrap;
  transition: all .15s;
}
.btn-optimize:disabled { opacity: .4; cursor: not-allowed; }
.btn-optimize:not(:disabled):hover { background: rgba(141,92,255,.2); border-color: rgba(141,92,255,.6); }

/* canvas template section in guide */
.guide-tpl-section {
  margin-top: 28px; padding-top: 24px;
  border-top: 1px solid rgba(255,255,255,.08);
}
.guide-tpl-title {
  font-size: .8rem; color: rgba(255,255,255,.35);
  text-align: center; margin-bottom: 14px; letter-spacing: .04em;
}
.guide-tpl-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
}
.guide-tpl-card {
  background: rgba(255,255,255,.025); border: 0.5px solid rgba(255,255,255,.08);
  border-radius: 12px; padding: 15px 13px; cursor: pointer; transition: all .2s;
  display: flex; flex-direction: column; gap: 5px;
}
.guide-tpl-card:hover {
  border-color: rgba(141,92,255,.4); background: rgba(141,92,255,.06);
  transform: translateY(-1px);
}
.gtc-icon { font-size: 1.5rem; margin-bottom: 2px; }
.gtc-name { font-size: .88rem; font-weight: 700; color: rgba(255,255,255,.9); }
.gtc-desc { font-size: .72rem; color: rgba(255,255,255,.4); line-height: 1.45; }
.gtc-use  { font-size: .72rem; color: #a78bfa; margin-top: 4px; font-weight: 600; opacity: 0; transition: opacity .2s; }
.guide-tpl-card:hover .gtc-use { opacity: 1; }
</style>
