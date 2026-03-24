<script setup lang="ts">
import { ref, computed, markRaw, watch, onMounted, onUnmounted } from 'vue'
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
      width:'100%', height:'100%', borderRadius:'18px', boxSizing:'border-box',
      border:'1.5px dashed ' + data.color + '38',
      background: data.color + '09',
      position:'relative', pointerEvents:'none',
    }">
      <div :style="{ position:'absolute', top:'14px', left:'18px' }">
        <div :style="{ fontSize:'13px', fontWeight:'700', color:data.color+'bb', letterSpacing:'.03em' }">{{ data.label }}</div>
        <div :style="{ fontSize:'9px', color:data.color+'55', letterSpacing:'.1em', textTransform:'uppercase', marginTop:'2px' }">{{ data.sublabel }}</div>
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
      index: 2, status: 'done', duration: 6, model: 'Veo 3.1', timeAnchor: null,
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
      index: 4, status: 'pending', duration: 7, model: 'Kling 2.0', timeAnchor: null,
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
const loading      = ref(false)
const saving       = ref(false)
const canSave      = ref(false)
const projectTitle = ref('')
let saveTimer: ReturnType<typeof setTimeout> | null = null
const pollingIntervals: Record<string, ReturnType<typeof setInterval>> = {}

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
  nodes.value = nodes.value.map(n =>
    n.id === nodeId
      ? { ...n, data: { ...n.data, status, ...(videoUrl ? { videoUrl } : {}) } }
      : n
  )
}

function startPolling(nodeId: string) {
  if (pollingIntervals[nodeId] || !projectId) return
  pollingIntervals[nodeId] = setInterval(async () => {
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
  if (pollingIntervals[nodeId]) {
    clearInterval(pollingIntervals[nodeId])
    delete pollingIntervals[nodeId]
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
    if (savedNodes.length > 0) {
      // Rebuild: keep zone nodes from default, apply saved non-zone nodes
      const zoneNodes = initialNodes.filter((n: any) => n.type === 'zone')
      const contentNodes = savedNodes.filter((n: any) => n.type !== 'zone')

      // Patch shot statuses from API shots
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

      // Resume polling for any shots still generating
      nodes.value.filter((n: any) => n.type === 'shot' && n.data.status === 'generating')
        .forEach((n: any) => startPolling(n.id))
    }
  } catch { /* network error — keep default mock canvas */ }
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

  _patchNodeStatus(nodeId, 'generating')
  try {
    await api.post(`/projects/${projectId}/canvas/shots/${nodeId}/generate`, {
      prompt: node.data.prompt ?? '',
      model_name: String(node.data.model ?? 'veo').toLowerCase().replace(/\s/g, '_'),
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

const VIDEO_MODELS = ['Veo 3.1', 'Seedance 2.0', 'Kling 2.0', 'Wan2.2', 'Hailuo 2.0']

function addNode(type: 'shot' | 'song' | 'char' | 'scene') {
  const id = `${type}-${Date.now()}`
  const shotCount = nodes.value.filter(n => n.type === 'shot').length

  const defaultData: Record<string, any> = {
    shot:  { index: shotCount + 1, prompt: '', model: 'Veo 3.1', duration: 5, status: 'pending',
             gradient: 'linear-gradient(135deg,#1a1a2e,#16213e)', segment: null, timeAnchor: null },
    song:  { title: '新音乐', mood: 'neutral', bpm: 120, duration: 180, genre: 'Electronic' },
    char:  { name: '新角色', description: '', loraId: '', gender: 'other' },
    scene: { name: '新场景', style: '', location: '', lighting: '' },
  }[type]

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

  // Prevent duplicate edges
  const dup = edges.value.some(e => e.source === connection.source && e.target === connection.target)
  if (dup) return

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
  edges.value = edges.value.filter(e => e.id !== id)
  selectedEdgeId.value = null
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Delete' && e.key !== 'Backspace') return
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement).tagName)) return
  if (selectedNodeId.value) deleteSelectedNode()
  else if (selectedEdgeId.value) deleteSelectedEdge()
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
      nodes.value = nodes.value.map((n: any) =>
        n.type === 'shot' && n.data.status === 'pending'
          ? { ...n, data: { ...n.data, status: 'generating' } }
          : n
      )
      nodes.value.filter((n: any) => n.type === 'shot' && n.data.status === 'generating')
        .forEach((n: any) => startPolling(n.id))
    }
  } catch { /* ignore */ }
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
        stopPolling(nodeId)
        _patchNodeStatus(nodeId, 'done', msg.file_url)
      } else if (msg.status === 'failed') {
        stopPolling(nodeId)
        _patchNodeStatus(nodeId, 'failed')
      }
    } catch { /* ignore parse errors */ }
  }

  ws.onclose = () => {
    if (!wsDestroyed) setTimeout(connectWS, 5000)
  }
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
  Object.keys(pollingIntervals).forEach(stopPolling)
  ws?.close()
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="canvas-page">

    <!-- ── Top Bar ─────────────────────────────────────────────────────────── -->
    <header class="topbar">
      <button class="back-btn" @click="router.back()">&#x2190; &#x8FD4;&#x56DE;</button>
      <span class="project-name">{{ projectTitle || 'AIMV Canvas' }}</span>
      <div class="topbar-center">
        <span class="canvas-badge">&#x2728; 自由画布</span>
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
        <button class="btn-import" @click="importFromStoryboard()" title="从分镜脚本导入镜头节点">&#x21E9; 导入分镜</button>
        <button class="btn-gen-all" @click="generateAll()">&#x26A1; &#x751F;&#x6210;&#x7A7A;&#x767D;&#x955C;&#x5934;</button>
        <button class="btn-export" @click="router.push(`/editor/${projectId}`)">&#x5BFC;&#x51FA;&#x65F6;&#x95F4;&#x7EBF; &#x2192;</button>
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
          <Background pattern-color="rgba(255,255,255,0.04)" :gap="28" :size="1" />
          <Controls position="top-left" />
          <MiniMap :node-color="minimapNodeColor" mask-color="rgba(0,0,0,0.7)" position="bottom-right" />

          <!-- slot overrides to pass programmatic selection state -->
          <template #node-shot="np">
            <component :is="nodeTypes.shot"  v-bind="np"
              :selected="np.id === selectedNodeId || np.id === highlightedNodeId" />
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
            <label>Prompt</label>
            <textarea
              class="panel-input"
              rows="4"
              :value="(selectedNode.data.prompt as string)"
              placeholder="描述这个镜头的画面..."
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
                <option v-for="m in VIDEO_MODELS" :key="m">{{ m }}</option>
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
            <label>&#x63CF;&#x8FF0;</label>
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
.canvas-badge {
  font-size: .78rem; font-weight: 600; letter-spacing: .04em;
  padding: 4px 12px; border-radius: 20px;
  background: rgba(141,92,255,.15); border: 1px solid rgba(141,92,255,.35);
  color: #c4b5fd;
}
.mode-btn {
  padding: 5px 16px; border-radius: 8px; border: none;
  font-size: .82rem; cursor: pointer; background: transparent; color: rgba(255,255,255,.5);
  transition: all .2s;
}
.mode-btn.active { background: #8d5cff; color: white; font-weight: 600; }
.topbar-right { display: flex; align-items: center; gap: 14px; }

.legend { display: flex; align-items: center; gap: 10px; }
.leg-item {
  display: flex; align-items: center; gap: 5px;
  font-size: .72rem; color: rgba(255,255,255,.4); white-space: nowrap;
}
.leg-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}

.btn-gen-all {
  padding: 6px 14px; border-radius: 8px; border: 1px solid rgba(141,92,255,.4);
  background: rgba(141,92,255,.15); color: #a78bfa; font-size: .82rem; cursor: pointer;
  white-space: nowrap;
}
.btn-gen-all:hover { background: rgba(141,92,255,.3); }
.saving-hint { font-size: .72rem; color: rgba(255,255,255,.3); white-space: nowrap; }
.loading-overlay {
  position: absolute; inset: 0; z-index: 100;
  background: rgba(8,8,14,.85); backdrop-filter: blur(6px);
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px;
  color: rgba(255,255,255,.5); font-size: .9rem;
}
.loading-ring {
  width: 36px; height: 36px; border-radius: 50%;
  border: 3px solid rgba(141,92,255,.2); border-top-color: #8d5cff;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.btn-export {
  padding: 6px 14px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#8d5cff,#f3b2ff); color: #000;
  font-size: .82rem; font-weight: 700; cursor: pointer; white-space: nowrap;
}

/* ── Main ──────────────────────────────────────────────────────────────── */
.main-area { flex: 1; display: flex; overflow: hidden; }
.flow-wrap { flex: 1; position: relative; }
.vf { background: #08080e !important; }

/* ── Panel ─────────────────────────────────────────────────────────────── */
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
.panel-status.done       { background: rgba(74,222,128,.15);  color: #4ade80; }
.panel-status.generating { background: rgba(141,92,255,.2);   color: #a78bfa; animation: blink 1.2s infinite; }
.panel-status.pending    { background: rgba(255,255,255,.08); color: rgba(255,255,255,.4); }
.panel-status.failed     { background: rgba(248,113,113,.15); color: #f87171; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }

.panel-section { padding: 8px 16px; border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0; }
.panel-row {
  display: flex; gap: 8px; padding: 8px 16px;
  border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0;
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
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  color: rgba(255,255,255,.8); font-size: .82rem; border-radius: 8px; padding: 8px;
  resize: none; line-height: 1.5; font-family: inherit;
}
.field-val {
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px; padding: 6px 10px; font-size: .85rem; color: rgba(255,255,255,.8);
}

/* context blocks */
.context-block { border-radius: 8px; padding: 10px 12px; font-size: .8rem; }
.music-block  { background: rgba(141,92,255,.06); border: 1px solid rgba(141,92,255,.2); }
.char-block   { background: rgba(92,159,255,.06); border: 1px solid rgba(92,159,255,.2); }
.scene-block  { background: rgba(34,211,238,.05); border: 1px solid rgba(34,211,238,.18); }
.canvas-block { background: rgba(141,92,255,.04); border: 1px solid rgba(141,92,255,.15); }

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
  background: rgba(0,0,0,.4); border: 1px solid rgba(255,255,255,.08);
  border-radius: 8px; padding: 10px; font-size: .7rem; color: #a78bfa;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all;
  max-height: 200px; overflow-y: auto; font-family: monospace; line-height: 1.5;
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
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  color: rgba(255,255,255,.8); font-size: .82rem; border-radius: 8px; padding: 6px 8px;
  font-family: inherit; cursor: pointer;
}
.panel-input-sm {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  color: rgba(255,255,255,.8); font-size: .82rem; border-radius: 8px; padding: 6px 8px;
  font-family: inherit;
}
.panel-input-line {
  width: 100%; box-sizing: border-box;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.1);
  color: rgba(255,255,255,.8); font-size: .85rem; border-radius: 8px; padding: 6px 10px;
  font-family: inherit;
}
.panel-select:focus, .panel-input-sm:focus, .panel-input-line:focus, .panel-input:focus {
  outline: none; border-color: rgba(141,92,255,.5);
}

/* floating add toolbar */
.add-toolbar {
  position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%);
  z-index: 20; display: flex; align-items: center; gap: 6px;
  background: rgba(13,13,24,.92); border: 1px solid rgba(255,255,255,.1);
  border-radius: 12px; padding: 6px 10px; backdrop-filter: blur(12px);
}
.add-label { font-size: .72rem; color: rgba(255,255,255,.3); margin-right: 2px; }
.add-btn {
  padding: 5px 12px; border-radius: 8px; border: 1px solid transparent;
  font-size: .78rem; cursor: pointer; background: rgba(255,255,255,.06);
  color: rgba(255,255,255,.6); transition: all .18s;
}
.add-btn:hover { color: white; }
.add-btn.shot  { border-color: rgba(255,255,255,.15); }
.add-btn.shot:hover  { background: rgba(255,255,255,.12); }
.add-btn.song  { border-color: rgba(141,92,255,.3); }
.add-btn.song:hover  { background: rgba(141,92,255,.2); color: #a78bfa; }
.add-btn.char  { border-color: rgba(92,159,255,.3); }
.add-btn.char:hover  { background: rgba(92,159,255,.2); color: #93c5fd; }
.add-btn.scene { border-color: rgba(34,211,238,.25); }
.add-btn.scene:hover { background: rgba(34,211,238,.15); color: #67e8f9; }

.panel-actions {
  display: flex; gap: 6px; padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,.06); flex-shrink: 0;
}
.btn-regen {
  flex: 1; padding: 9px; border-radius: 8px; border: none;
  background: linear-gradient(135deg,#8d5cff,#f3b2ff);
  color: #000; font-weight: 700; font-size: .85rem; cursor: pointer;
}
.btn-regen:disabled { opacity: .5; cursor: not-allowed; }
.btn-copy {
  padding: 9px 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,.15);
  background: transparent; color: rgba(255,255,255,.6); font-size: .85rem; cursor: pointer;
}
.btn-delete {
  padding: 9px 10px; border-radius: 8px; border: 1px solid rgba(248,113,113,.25);
  background: rgba(248,113,113,.08); color: #f87171; font-size: .85rem; cursor: pointer;
}
.btn-delete:hover { background: rgba(248,113,113,.2); }
.btn-delete-sm {
  padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(248,113,113,.2);
  background: transparent; color: rgba(248,113,113,.6); font-size: .8rem; cursor: pointer;
}
.btn-delete-sm:hover { background: rgba(248,113,113,.15); color: #f87171; }

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
.tl-hint { font-size: .68rem; color: rgba(255,255,255,.2); white-space: nowrap; }

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
.pin-label { font-size: 8px; color: rgba(255,255,255,.4); margin-top: 2px; white-space: nowrap; }
.tl-anchor-pin.active .pin-label { color: #a78bfa; }
.tl-playhead {
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: rgba(255,255,255,.9); border-radius: 1px;
  box-shadow: 0 0 8px rgba(255,255,255,.4);
  pointer-events: none; z-index: 10;
}

/* status counter */
.status-counter {
  display: flex; align-items: center; gap: 6px;
  font-size: .75rem; background: rgba(255,255,255,.06);
  padding: 4px 10px; border-radius: 8px;
}
.sc-done { color: rgba(255,255,255,.55); font-family: monospace; }
.sc-gen  { color: #fbbf24; font-size: .68rem; }
.sc-fail { color: #f87171; font-size: .68rem; }

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

/* import from storyboard button */
.btn-import {
  background: transparent; border: 1px solid rgba(255,255,255,.18);
  color: rgba(255,255,255,.55); font-size: .75rem; padding: 5px 12px;
  border-radius: 8px; cursor: pointer; white-space: nowrap;
}
.btn-import:hover { border-color: rgba(255,255,255,.4); color: white; }
</style>
