<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { ElMessage } from 'element-plus'
import ComparePanel from '@/components/ComparePanel.vue'

const route = useRoute()
const projectId = ref<number | null>(null)

// Chat state
const chatInput = ref('')
const chatLoading = ref(false)
const messages = ref<{ role: string; content: string }[]>([
  { role: 'assistant', content: 'Hi! I\'m your AI director. Describe the music video you want to create — style, mood, story, anything!' },
])
const chatMessagesEl = ref<HTMLElement | null>(null)

// Project state
const visualStyle = ref('')
const musicModel = ref('')
const videoModel = ref('')
const mood = ref('')
const storyboard = ref<any[]>([])
const generating = ref(false)
const previewUrl = ref('')
const showCompare = ref(false)

// Progress state from WebSocket
const progress = ref<Record<string, string>>({
  image: 'pending',
  music: 'pending',
  video: 'pending',
  compose: 'pending',
})
let ws: WebSocket | null = null

onMounted(async () => {
  const id = route.params.id
  if (id) {
    projectId.value = Number(id)
    await loadProject()
    connectWebSocket()
  }
})

onUnmounted(() => {
  ws?.close()
})

async function loadProject() {
  if (!projectId.value) return
  try {
    const res = await api.get(`/projects/${projectId.value}`)
    const p = res.data
    visualStyle.value = p.visual_style || ''
    mood.value = p.mood || ''
    storyboard.value = p.storyboard || []
    if (p.chat_history?.length) {
      messages.value = p.chat_history
    }
  } catch { /* project may not exist yet */ }
}

function connectWebSocket() {
  if (!projectId.value) return
  ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId.value}/progress`)
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    progress.value[data.type] = data.status
    if (data.type === 'pipeline' && data.status === 'completed') {
      generating.value = false
      ElMessage.success('MV generation completed!')
      loadProject()
    }
    if (data.file_url && data.type === 'compose') {
      previewUrl.value = data.file_url
    }
  }
}

async function sendMessage() {
  if (!chatInput.value.trim() || chatLoading.value) return
  const text = chatInput.value.trim()
  chatInput.value = ''
  messages.value.push({ role: 'user', content: text })
  scrollChat()

  if (!projectId.value) {
    // Create project first
    const res = await api.post('/projects', { title: text.slice(0, 50) })
    projectId.value = res.data.id
  }

  chatLoading.value = true
  try {
    const res = await api.post(`/projects/${projectId.value}/chat`, {
      message: text,
      stream: false,
    })
    messages.value.push({ role: 'assistant', content: res.data.content })
    if (res.data.plan?.storyboard) {
      storyboard.value = res.data.plan.storyboard
    }
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: 'Sorry, something went wrong. Please try again.' })
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

async function generatePlan() {
  if (!projectId.value) return
  chatLoading.value = true
  const lastUserMsg = [...messages.value].reverse().find(m => m.role === 'user')?.content || ''
  try {
    // Update project settings
    await api.put(`/projects/${projectId.value}`, {
      visual_style: visualStyle.value,
      music_style: musicModel.value,
      mood: mood.value,
    })
    const res = await api.post(`/projects/${projectId.value}/chat`, {
      message: lastUserMsg || 'Generate a plan based on my preferences',
      generate_plan: true,
    })
    messages.value.push({ role: 'assistant', content: res.data.content })
    if (res.data.plan?.storyboard) {
      storyboard.value = res.data.plan.storyboard
    }
  } catch {
    ElMessage.error('Failed to generate plan')
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

async function startGenerating() {
  if (!projectId.value || !storyboard.value.length) {
    ElMessage.warning('Generate a plan first!')
    return
  }
  generating.value = true
  progress.value = { image: 'pending', music: 'pending', video: 'pending', compose: 'pending' }
  try {
    await api.post(`/projects/${projectId.value}/pipeline/start`)
    ElMessage.info('Generation started! Watch progress on the right panel.')
    if (!ws || ws.readyState !== WebSocket.OPEN) connectWebSocket()
  } catch {
    ElMessage.error('Failed to start generation')
    generating.value = false
  }
}

function scrollChat() {
  nextTick(() => {
    if (chatMessagesEl.value) {
      chatMessagesEl.value.scrollTop = chatMessagesEl.value.scrollHeight
    }
  })
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    pending: 'badge-info',
    running: 'badge-warning',
    completed: 'badge-success',
    failed: 'badge-error',
  }
  return map[status] || 'badge-info'
}

function uploadAudio() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.mp3,.wav,.flac,.m4a'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file || !projectId.value) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await api.post(`/projects/${projectId.value}/upload/audio`, formData)
      ElMessage.success(`Audio analyzed! BPM: ${res.data.analysis.bpm}`)
      messages.value.push({
        role: 'assistant',
        content: `Audio uploaded and analyzed!\nBPM: ${res.data.analysis.bpm}\nDuration: ${Math.round(res.data.analysis.duration)}s\nSections: ${res.data.analysis.sections.length} detected`,
      })
    } catch {
      ElMessage.error('Audio upload failed')
    }
  }
  input.click()
}
</script>

<template>
  <div class="create-layout">
    <!-- Chat Panel -->
    <aside class="chat-panel">
      <div class="chat-header">
        <h3>AI Director</h3>
        <button class="btn-ghost btn-sm" @click="uploadAudio" title="Upload audio">Upload Audio</button>
      </div>
      <div class="chat-messages" ref="chatMessagesEl">
        <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <div class="msg-bubble">{{ msg.content }}</div>
        </div>
        <div v-if="chatLoading" class="msg assistant">
          <div class="msg-bubble typing">Thinking...</div>
        </div>
      </div>
      <div class="chat-input-area">
        <input
          v-model="chatInput"
          placeholder="Describe your MV idea..."
          @keyup.enter="sendMessage"
          :disabled="chatLoading"
        />
        <button class="btn-primary send-btn" @click="sendMessage" :disabled="chatLoading">Send</button>
      </div>
    </aside>

    <!-- Main: Preview + Timeline -->
    <main class="create-main">
      <div class="preview-area">
        <video v-if="previewUrl" :src="previewUrl" controls class="preview-video"></video>
        <div v-else class="preview-placeholder">
          <span class="preview-icon">MV Preview</span>
          <p>Generated content will appear here</p>
        </div>
      </div>

      <!-- Storyboard Timeline -->
      <div class="timeline-area">
        <div class="timeline-bar" v-if="storyboard.length">
          <div class="timeline-segments">
            <div
              v-for="(seg, i) in storyboard"
              :key="i"
              class="timeline-segment"
              :class="seg.label"
              :title="`${seg.label}: ${seg.description?.slice(0, 60) || ''}...`"
            >
              <span class="seg-id">{{ i + 1 }}</span>
              <span class="seg-label">{{ seg.label === 'sing' ? 'Sing' : 'Story' }}</span>
            </div>
          </div>
        </div>
        <div class="timeline-bar" v-else>
          <div class="timeline-track"></div>
        </div>
        <div class="timeline-controls">
          <button class="btn-ghost" @click="generatePlan" :disabled="chatLoading">
            {{ chatLoading ? 'Planning...' : 'Generate Plan' }}
          </button>
          <button class="btn-primary" @click="startGenerating" :disabled="generating || !storyboard.length">
            {{ generating ? 'Generating...' : 'Start Generating' }}
          </button>
          <button class="btn-ghost" @click="showCompare = true">A/B Compare</button>
          <button class="btn-ghost">Export</button>
        </div>
      </div>
    </main>

    <!-- A/B Compare Modal -->
    <ComparePanel
      v-if="projectId"
      :project-id="projectId"
      :visible="showCompare"
      @close="showCompare = false"
      @picked="(id, model) => ElMessage.success(`Picked ${model}`)"
    />

    <!-- Properties Panel -->
    <aside class="props-panel">
      <h3>Properties</h3>
      <div class="prop-group">
        <label>Visual Style</label>
        <el-select v-model="visualStyle" placeholder="Select style" style="width: 100%">
          <el-option label="K-Pop" value="韩娱" />
          <el-option label="Chinese Classical" value="国风" />
          <el-option label="Cyberpunk" value="赛博朋克" />
          <el-option label="Retro Disco" value="复古迪斯科" />
          <el-option label="Indie Film" value="独立电影" />
          <el-option label="Urban Cool" value="都市甜酷" />
          <el-option label="Fantasy" value="幻想童话" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>Video Model</label>
        <el-select v-model="videoModel" placeholder="Auto" style="width: 100%">
          <el-option label="Auto (AI Routed)" value="" />
          <el-option label="Seedance 2.0" value="seedance" />
          <el-option label="Veo 3.1" value="veo" />
          <el-option label="Grok Video" value="grok" />
          <el-option label="Wan 2.2 (Local)" value="wan2.2" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>Music Model</label>
        <el-select v-model="musicModel" placeholder="Auto" style="width: 100%">
          <el-option label="Auto (AI Routed)" value="" />
          <el-option label="ACEStep 1.5" value="acestep" />
          <el-option label="Suno" value="suno" />
          <el-option label="Google Lyria" value="lyria" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>Mood</label>
        <el-select v-model="mood" placeholder="Select mood" style="width: 100%">
          <el-option label="Energetic" value="energetic" />
          <el-option label="Melancholic" value="melancholic" />
          <el-option label="Romantic" value="romantic" />
          <el-option label="Epic" value="epic" />
          <el-option label="Peaceful" value="peaceful" />
        </el-select>
      </div>

      <div class="generation-status">
        <h4>Generation Status</h4>
        <div class="status-item" v-for="type in ['image', 'music', 'video', 'compose']" :key="type">
          <span :class="['badge', statusBadge(progress[type])]">{{ progress[type] }}</span>
          <span>{{ type.charAt(0).toUpperCase() + type.slice(1) }}</span>
        </div>
      </div>

      <div v-if="storyboard.length" class="storyboard-summary">
        <h4>Storyboard</h4>
        <div class="seg-list">
          <div v-for="(seg, i) in storyboard" :key="i" class="seg-item">
            <span class="seg-num">#{{ i + 1 }}</span>
            <span :class="['badge', seg.label === 'sing' ? 'badge-warning' : 'badge-info']">{{ seg.label }}</span>
            <span class="seg-desc">{{ (seg.description || '').slice(0, 40) }}</span>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.create-layout { display: flex; height: 100vh; overflow: hidden; }

/* Chat */
.chat-panel {
  width: 320px; background: var(--bg-soft);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
}
.chat-header {
  padding: 12px 16px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.chat-header h3 {
  font-size: 15px; font-weight: 600;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.btn-sm { padding: 4px 12px; font-size: 11px; }
.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.msg.assistant .msg-bubble {
  background: var(--card); border-radius: 12px 12px 12px 4px;
  padding: 10px 14px; font-size: 13px; color: var(--text-muted); white-space: pre-wrap;
}
.msg.user .msg-bubble {
  background: var(--accent-strong); color: white;
  border-radius: 12px 12px 4px 12px; padding: 10px 14px; font-size: 13px;
}
.msg.user { display: flex; justify-content: flex-end; }
.typing { opacity: 0.6; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
.chat-input-area {
  padding: 12px; border-top: 1px solid var(--border); display: flex; gap: 8px;
}
.chat-input-area input {
  flex: 1; background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 10px 14px; color: var(--text); font-size: 13px; outline: none;
}
.chat-input-area input:focus { border-color: var(--accent-strong); }
.send-btn { padding: 10px 16px; font-size: 13px; }

/* Main */
.create-main { flex: 1; display: flex; flex-direction: column; }
.preview-area {
  flex: 1; display: flex; align-items: center; justify-content: center; background: var(--bg);
}
.preview-video { max-width: 100%; max-height: 100%; border-radius: var(--radius); }
.preview-placeholder { text-align: center; color: var(--text-muted); }
.preview-icon { display: block; font-size: 24px; font-weight: 600; color: var(--accent-strong); margin-bottom: 8px; }

/* Timeline */
.timeline-area { border-top: 1px solid var(--border); padding: 16px 24px; background: var(--bg-soft); }
.timeline-bar { margin-bottom: 12px; }
.timeline-track { height: 40px; background: var(--card); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.timeline-segments { display: flex; gap: 2px; height: 40px; }
.timeline-segment {
  flex: 1; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center;
  gap: 4px; font-size: 11px; font-weight: 500; cursor: pointer; transition: opacity 0.2s;
}
.timeline-segment.sing { background: rgba(251, 191, 36, 0.2); border: 1px solid rgba(251, 191, 36, 0.4); color: var(--warning); }
.timeline-segment.story { background: rgba(141, 92, 255, 0.2); border: 1px solid rgba(141, 92, 255, 0.4); color: var(--accent-strong); }
.timeline-segment:hover { opacity: 0.8; }
.seg-id { font-weight: 700; }
.timeline-controls { display: flex; gap: 12px; }

/* Props */
.props-panel {
  width: 280px; background: var(--bg-soft); border-left: 1px solid var(--border);
  padding: 20px; overflow-y: auto;
}
.props-panel h3 { font-size: 15px; margin-bottom: 20px; }
.prop-group { margin-bottom: 16px; }
.prop-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
.generation-status { margin-top: 24px; }
.generation-status h4, .storyboard-summary h4 { font-size: 13px; margin-bottom: 12px; }
.status-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; }
.storyboard-summary { margin-top: 24px; }
.seg-list { display: flex; flex-direction: column; gap: 6px; }
.seg-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.seg-num { color: var(--text-muted); font-weight: 600; min-width: 24px; }
.seg-desc { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
