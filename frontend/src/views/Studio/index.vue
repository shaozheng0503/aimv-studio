<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import api from '@/api'
import { useLangStore } from '@/stores/lang'
import ProgressPanel from './ProgressPanel.vue'

const route = useRoute()
const router = useRouter()
const { t } = storeToRefs(useLangStore())

// ─── state ────────────────────────────────────────────────────────────────────
type Phase = 'chat' | 'generating' | 'done'
const phase = ref<Phase>('chat')
const projectId = ref<number | null>(null)

// chat
const messages = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
const inputText = ref('')
const sending = ref(false)
const launching = ref(false)
const chatBox = ref<HTMLElement | null>(null)

// plan result
const storyboard = ref<any[]>([])
const characterBank = ref<Record<string, any>>({})
const musicPlan = ref<Record<string, any>>({})
const intentExtracted = ref<Record<string, any>>({})

// progress
interface ShotStatus {
  index: number; prompt: string; model: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  pct?: number; videoUrl?: string
}
const musicStatus = ref<'pending' | 'running' | 'completed' | 'failed'>('pending')
const shotStatuses = ref<ShotStatus[]>([])
const pipelineStatus = ref('')
const finalVideoUrl = ref('')

// websocket
let ws: WebSocket | null = null
let wsRetries = 0
const MAX_WS_RETRIES = 5

const overallPct = computed(() => {
  if (!shotStatuses.value.length) return 0
  const done = shotStatuses.value.filter(s => s.status === 'completed').length
  const running = shotStatuses.value.find(s => s.status === 'running')
  const runningPct = running?.pct ?? 0
  return Math.round(((done + runningPct / 100) / shotStatuses.value.length) * 100)
})

const canLaunch = computed(() => messages.value.some(m => m.role === 'user'))

// ─── init ─────────────────────────────────────────────────────────────────────
onMounted(async () => {
  const routeId = route.params.id as string
  if (routeId) {
    projectId.value = parseInt(routeId)
    // Restore state if project is already generating/done
    try {
      const { data: proj } = await api.get(`/projects/${projectId.value}`)
      if (proj.status === 'generating' || proj.status === 'composing') {
        storyboard.value = proj.storyboard || []
        buildShotStatusesFromStoryboard()
        phase.value = 'generating'
        connectWebSocket()
      } else if (proj.status === 'done') {
        storyboard.value = proj.storyboard || []
        buildShotStatusesFromStoryboard()
        phase.value = 'done'
        // try to fetch final video from media
        const { data: media } = await api.get(`/projects/${projectId.value}/media`).catch(() => ({ data: [] }))
        const composed = (media as any[]).find((m: any) => m.type === 'composed_video' || m.type === 'video')
        if (composed) finalVideoUrl.value = composed.file_url
      }
    } catch {
      // new project, stay in chat
    }
  }
  pushAssistantGreeting()
})

onUnmounted(() => { ws?.close() })

function pushAssistantGreeting() {
  if (messages.value.length === 0) {
    messages.value.push({
      role: 'assistant',
      content: '你好！我是 AIMV AI 导演 🎬\n\n告诉我你想创作的 MV 主题、风格、情感，我来帮你把整个 MV 规划好，然后一键生成。\n\n例如：「帮我做一个关于失恋的 MV，暗黑风格，节奏偏慢」',
    })
  }
}

// ─── chat ─────────────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  sending.value = true
  scrollChat()

  try {
    // Create project on first message
    if (!projectId.value) {
      const { data: proj } = await api.post('/projects', { title: text.slice(0, 40) })
      projectId.value = proj.id
      router.replace(`/studio/${proj.id}`)
    }

    const { data } = await api.post(`/projects/${projectId.value}/chat`, {
      message: text,
      generate_plan: false,
    })

    messages.value.push({ role: 'assistant', content: data.content })
    if (data.intent_extracted) {
      Object.assign(intentExtracted.value, data.intent_extracted)
    }
  } catch {
    ElMessage.error('发送失败，请重试')
  } finally {
    sending.value = false
    scrollChat()
  }
}

// ─── launch ───────────────────────────────────────────────────────────────────
async function launchStudio() {
  if (!canLaunch.value || launching.value) return
  launching.value = true

  const lastUserMsg = [...messages.value].reverse().find(m => m.role === 'user')?.content ?? ''

  try {
    // Step A: Create project if needed
    if (!projectId.value) {
      const { data: proj } = await api.post('/projects', { title: lastUserMsg.slice(0, 40) })
      projectId.value = proj.id
      router.replace(`/studio/${proj.id}`)
    }

    // Update intent-inferred settings
    if (intentExtracted.value.visual_style || intentExtracted.value.mood) {
      await api.put(`/projects/${projectId.value}`, {
        visual_style: intentExtracted.value.visual_style,
        mood: intentExtracted.value.mood,
        music_style: intentExtracted.value.music_style,
      })
    }

    // Step B: Generate plan
    messages.value.push({ role: 'assistant', content: t.value('studioPlanningMV') + ' ⏳' })
    scrollChat()

    const { data: chatResp } = await api.post(`/projects/${projectId.value}/chat`, {
      message: lastUserMsg,
      generate_plan: true,
    })

    const plan = chatResp.plan
    if (!plan?.storyboard?.length) throw new Error('规划失败，请重试')

    storyboard.value = plan.storyboard
    characterBank.value = plan.character_bank || {}
    musicPlan.value = plan.music_plan || {}

    // Replace planning message with summary
    messages.value[messages.value.length - 1] = { role: 'assistant', content: chatResp.content }
    scrollChat()

    // Step C: Build canvas nodes
    const { nodes, edges } = buildCanvasFromPlan(plan)

    // Step D: Save canvas
    await api.put(`/projects/${projectId.value}/canvas`, { nodes, edges, viewport: {} })

    // Step E: Start pipeline
    await api.post(`/projects/${projectId.value}/pipeline/start`)

    // Build shot statuses for display
    buildShotStatusesFromStoryboard()
    phase.value = 'generating'
    connectWebSocket()
  } catch (err: any) {
    if (err?.response?.status === 409) {
      // Already running — just switch to generating view
      buildShotStatusesFromStoryboard()
      phase.value = 'generating'
      connectWebSocket()
    } else {
      ElMessage.error(err?.message || '生成失败，请重试')
    }
  } finally {
    launching.value = false
  }
}

// ─── canvas builder ───────────────────────────────────────────────────────────
const GRADIENTS = [
  'linear-gradient(135deg,#1a1a2e,#4a1fa8)',
  'linear-gradient(135deg,#0f2027,#203a43)',
  'linear-gradient(135deg,#2d1b69,#11998e)',
  'linear-gradient(135deg,#360033,#0b8793)',
  'linear-gradient(135deg,#1f1c2c,#928dab)',
]

function buildCanvasFromPlan(plan: any) {
  const nodes: any[] = []
  const edges: any[] = []
  const { storyboard: sb, character_bank: charBank, music_plan: mp } = plan

  // Song node
  nodes.push({
    id: 'song1', type: 'song',
    position: { x: 60, y: 70 },
    data: {
      title: (mp?.music_prompt ?? '').slice(0, 20) || '生成中',
      mood: intentExtracted.value.mood || 'energetic',
      bpm: plan.music_analysis?.bpm || 120,
      duration: plan.music_analysis?.duration || 180,
      genre: intentExtracted.value.music_style || 'Electronic',
      description: mp?.music_prompt || '',
      lyrics: '',
      instrumental: true,
      generateStatus: 'idle',
      audioUrl: null,
    },
  })

  // Character nodes
  const chars = Object.entries(charBank || {})
  chars.forEach(([name, char]: [string, any], i) => {
    const cid = `char-${name}`
    nodes.push({
      id: cid, type: 'char',
      position: { x: 60, y: 280 + i * 180 },
      data: {
        name,
        description: char.description || char.appearance || '',
        loraId: char.lora_id || '',
        gender: char.gender || 'other',
      },
    })
  })

  // Shot nodes + edges
  sb.forEach((seg: any, i: number) => {
    const sid = `s${i + 1}`
    nodes.push({
      id: sid, type: 'shot',
      position: { x: 680 + (i % 3) * 290, y: 55 + Math.floor(i / 3) * 220 },
      data: {
        index: i + 1,
        prompt: seg.video_prompt || seg.description || '',
        model: seg.model_recommendation || 'Veo 3.1',
        duration: (seg.end_time ?? 0) - (seg.start_time ?? 0) || 5,
        status: 'pending',
        gradient: GRADIENTS[i % GRADIENTS.length],
        timeAnchor: seg.start_time ?? null,
        segment: seg.label === 'sing' ? '演唱' : '叙事',
        videoUrl: null,
      },
    })

    // Music → shot edge
    edges.push({
      id: `e-song1-${sid}`, source: 'song1', target: sid,
      type: 'smoothstep', animated: true,
      style: { stroke: 'rgba(141,92,255,0.4)', strokeWidth: 1.5 },
      data: { edgeType: 'music-ref' },
    })

    // Char → shot edges
    const segChars: string[] = seg.characters || []
    segChars.forEach((cName: string) => {
      const cid = `char-${cName}`
      if (chars.find(([n]) => n === cName)) {
        edges.push({
          id: `e-${cid}-${sid}`, source: cid, target: sid,
          type: 'smoothstep',
          style: { stroke: 'rgba(251,191,36,0.4)', strokeWidth: 1.5 },
          data: { edgeType: 'char-ref' },
        })
      }
    })

    // Sequence edges
    if (i > 0) {
      edges.push({
        id: `e-s${i}-${sid}`, source: `s${i}`, target: sid,
        type: 'smoothstep',
        style: { stroke: 'rgba(255,255,255,0.15)', strokeWidth: 1 },
        data: { edgeType: 'sequence' },
      })
    }
  })

  return { nodes, edges }
}

function buildShotStatusesFromStoryboard() {
  shotStatuses.value = storyboard.value.map((seg: any, i: number) => ({
    index: i + 1,
    prompt: seg.video_prompt || seg.description || '',
    model: seg.model_recommendation || 'Veo 3.1',
    status: 'pending' as const,
    pct: 0,
  }))
}

// ─── WebSocket ────────────────────────────────────────────────────────────────
function connectWebSocket() {
  if (!projectId.value) return
  const token = localStorage.getItem('token') || ''
  const wsUrl = `ws://localhost:8000/ws/projects/${projectId.value}/progress?token=${token}`
  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      handleProgressEvent(msg)
    } catch { /* ignore */ }
  }

  ws.onclose = () => {
    if (phase.value === 'generating' && wsRetries < MAX_WS_RETRIES) {
      wsRetries++
      setTimeout(connectWebSocket, 2000 * wsRetries)
    }
  }

  ws.onerror = () => { ws?.close() }
}

function handleProgressEvent(msg: any) {
  const { type, status, segment, pct, file_url } = msg

  if (type === 'pipeline') {
    pipelineStatus.value = status
    if (status === 'completed') {
      phase.value = 'done'
      ws?.close()
    }
  } else if (type === 'music') {
    if (status === 'running') musicStatus.value = 'running'
    else if (status === 'completed') musicStatus.value = 'completed'
    else if (status === 'failed') musicStatus.value = 'failed'
  } else if (type === 'video') {
    // segment is 1-based
    const idx = (segment ?? 1) - 1
    if (idx >= 0 && idx < shotStatuses.value.length) {
      const shot = shotStatuses.value[idx]
      if (status === 'running') {
        shot.status = 'running'
        shot.pct = pct ?? 0
      } else if (status === 'completed') {
        shot.status = 'completed'
        shot.pct = 100
        if (file_url) shot.videoUrl = file_url
      } else if (status === 'failed') {
        shot.status = 'failed'
      }
    }
  } else if (type === 'compose' && status === 'completed' && file_url) {
    finalVideoUrl.value = file_url
  }
}

// ─── helpers ──────────────────────────────────────────────────────────────────
function scrollChat() {
  nextTick(() => {
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  })
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="studio-page">
    <!-- Header -->
    <header class="studio-header">
      <router-link to="/" class="logo-text">AIMV</router-link>
      <span class="studio-title">{{ t('simpleStudio') }}</span>
      <router-link to="/projects" class="btn-ghost btn-sm">我的项目</router-link>
    </header>

    <!-- ── Phase: Chat ──────────────────────────────────────────────────────── -->
    <div v-if="phase === 'chat'" class="chat-phase">
      <div class="chat-wrap">
        <div class="chat-messages" ref="chatBox">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="msg-bubble"
            :class="msg.role"
          >
            <div class="msg-avatar">{{ msg.role === 'assistant' ? '🎬' : '👤' }}</div>
            <div class="msg-content" style="white-space: pre-wrap">{{ msg.content }}</div>
          </div>
          <div v-if="sending" class="msg-bubble assistant typing">
            <div class="msg-avatar">🎬</div>
            <div class="msg-content"><span class="dot-anim" /><span class="dot-anim" /><span class="dot-anim" /></div>
          </div>
        </div>

        <div class="chat-input-row">
          <textarea
            v-model="inputText"
            class="chat-input"
            rows="2"
            :placeholder="t('studioPlaceholder')"
            @keydown="handleKeydown"
          />
          <div class="chat-btns">
            <button class="btn-ghost btn-sm" :disabled="sending" @click="sendMessage">
              {{ t('studioSendMsg') }}
            </button>
            <button
              class="btn-primary btn-launch"
              :disabled="!canLaunch || launching"
              @click="launchStudio"
            >
              {{ launching ? t('studioLaunching') : t('studioLaunch') }}
            </button>
          </div>
        </div>

        <p class="studio-hint">{{ t('studioHint') }}</p>
      </div>
    </div>

    <!-- ── Phase: Generating ───────────────────────────────────────────────── -->
    <div v-else-if="phase === 'generating'" class="gen-phase">
      <div class="gen-left">
        <div class="gen-heading">
          <span class="gen-spinner" />
          {{ t('studioGenerating') }}
        </div>
        <div class="chat-log" ref="chatBox">
          <div v-for="(msg, i) in messages" :key="i" class="log-line" :class="msg.role">
            <span class="log-role">{{ msg.role === 'assistant' ? '🎬' : '👤' }}</span>
            <span style="white-space: pre-wrap">{{ msg.content }}</span>
          </div>
        </div>
      </div>
      <div class="gen-right">
        <ProgressPanel
          :music-status="musicStatus"
          :shots="shotStatuses"
          :overall-pct="overallPct"
          :pipeline-status="pipelineStatus"
        />
      </div>
    </div>

    <!-- ── Phase: Done ─────────────────────────────────────────────────────── -->
    <div v-else class="done-phase">
      <h1 class="done-title gradient-text">{{ t('studioMvReady') }}</h1>

      <div v-if="finalVideoUrl" class="video-wrap">
        <video :src="finalVideoUrl" controls class="final-video" />
      </div>
      <div v-else class="video-placeholder">
        <ProgressPanel
          :music-status="musicStatus"
          :shots="shotStatuses"
          :overall-pct="100"
          :pipeline-status="pipelineStatus"
        />
      </div>

      <div class="done-actions">
        <button class="btn-primary" @click="router.push(`/canvas/${projectId}`)">
          {{ t('studioEditCanvas') }}
        </button>
        <button class="btn-ghost" @click="router.push(`/editor/${projectId}`)">
          {{ t('studioExport') }}
        </button>
        <button class="btn-ghost" @click="phase = 'chat'">
          {{ t('studioRetry') }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio-page {
  min-height: 100vh; display: flex; flex-direction: column;
  background: var(--bg);
}

/* header */
.studio-header {
  display: flex; align-items: center; gap: 16px; padding: 14px 28px;
  border-bottom: 1px solid var(--border);
}
.logo-text {
  font-size: 20px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  text-decoration: none;
}
.studio-title {
  flex: 1; font-size: 14px; color: var(--text-muted);
}
.btn-sm { padding: 6px 14px; font-size: 13px; }

/* ── chat phase ── */
.chat-phase {
  flex: 1; display: flex; align-items: center; justify-content: center;
  padding: 32px 16px;
}
.chat-wrap { width: 100%; max-width: 680px; display: flex; flex-direction: column; gap: 16px; }

.chat-messages {
  background: var(--card); border: 1px solid var(--border); border-radius: 16px;
  padding: 20px; display: flex; flex-direction: column; gap: 16px;
  min-height: 300px; max-height: 55vh; overflow-y: auto;
}
.msg-bubble { display: flex; gap: 12px; align-items: flex-start; }
.msg-bubble.user { flex-direction: row-reverse; }
.msg-avatar { font-size: 18px; flex-shrink: 0; }
.msg-content {
  max-width: 80%; font-size: 14px; line-height: 1.6;
  padding: 10px 14px; border-radius: 12px;
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
}
.msg-bubble.user .msg-content {
  background: rgba(141,92,255,.15); border-color: rgba(141,92,255,.3); color: var(--text);
}
.typing .msg-content { display: flex; align-items: center; gap: 4px; padding: 14px; }

.dot-anim {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); animation: dotBounce 1.2s infinite;
}
.dot-anim:nth-child(2) { animation-delay: .2s; }
.dot-anim:nth-child(3) { animation-delay: .4s; }
@keyframes dotBounce { 0%,80%,100% { transform: scale(0.6); opacity:.4 } 40% { transform: scale(1); opacity:1 } }

.chat-input-row { display: flex; flex-direction: column; gap: 8px; }
.chat-input {
  width: 100%; padding: 12px 16px; resize: none;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; color: var(--text); font-size: 14px; outline: none;
}
.chat-input:focus { border-color: var(--accent-strong); }
.chat-btns { display: flex; gap: 10px; justify-content: flex-end; }
.btn-launch { padding: 10px 28px; font-size: 14px; }

.studio-hint { text-align: center; font-size: 12px; color: var(--text-muted); }

/* ── generating phase ── */
.gen-phase {
  flex: 1; display: grid; grid-template-columns: 1fr 1.4fr; gap: 0;
  overflow: hidden;
}
.gen-left {
  display: flex; flex-direction: column; gap: 16px;
  padding: 28px 20px 28px 28px; border-right: 1px solid var(--border);
  overflow: hidden;
}
.gen-heading {
  display: flex; align-items: center; gap: 10px;
  font-size: 16px; font-weight: 600; color: var(--accent);
}
.gen-spinner {
  width: 18px; height: 18px; border: 2px solid rgba(141,92,255,.25);
  border-top-color: #8d5cff; border-radius: 50%; animation: spin .8s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

.chat-log {
  flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px;
}
.log-line {
  display: flex; gap: 8px; font-size: 13px; line-height: 1.5; color: var(--text-muted);
}
.log-line.user { color: var(--text); }
.log-role { flex-shrink: 0; }

.gen-right { padding: 28px 28px 28px 20px; overflow: hidden; }

/* ── done phase ── */
.done-phase {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 28px; padding: 40px 24px;
}
.done-title { font-size: 32px; font-weight: 700; text-align: center; }
.gradient-text {
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.video-wrap { width: 100%; max-width: 900px; border-radius: 16px; overflow: hidden; }
.final-video { width: 100%; max-height: 55vh; background: #000; display: block; }
.video-placeholder { width: 100%; max-width: 680px; }
.done-actions { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }
</style>
