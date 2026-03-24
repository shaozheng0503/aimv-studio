<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import api from '@/api'
import { ElMessage } from 'element-plus'
import ComparePanel from '@/components/ComparePanel.vue'
import { useLangStore } from '@/stores/lang'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const langStore = useLangStore()
const { t } = storeToRefs(langStore)
const auth = useAuthStore()
const isGuest = computed(() => !auth.token)
const showLoginModal = ref(false)
const projectId = ref<number | null>(null)

// Chat state
const chatInput = ref('')
const chatLoading = ref(false)
const messages = ref<{ role: string; content: string }[]>([
  { role: 'assistant', content: '你好！我是你的 AI 导演。告诉我你想创作的 MV 风格、情绪、故事……' },
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

// Storyboard editing
const editingSegIdx = ref<number | null>(null)
const editingSegData = ref<any>(null)
const savingStoryboard = ref(false)

function startEditSeg(i: number) {
  editingSegIdx.value = i
  editingSegData.value = { ...storyboard.value[i] }
}

function cancelEditSeg() {
  editingSegIdx.value = null
  editingSegData.value = null
}

async function saveEditSeg() {
  if (editingSegIdx.value === null || !editingSegData.value || !projectId.value) return
  const updated = [...storyboard.value]
  updated[editingSegIdx.value] = { ...storyboard.value[editingSegIdx.value], ...editingSegData.value }
  savingStoryboard.value = true
  try {
    await api.put(`/projects/${projectId.value}`, { storyboard: updated })
    storyboard.value = updated
    editingSegIdx.value = null
    editingSegData.value = null
  } catch {
    ElMessage.error(t.value('saveError'))
  } finally {
    savingStoryboard.value = false
  }
}

// Progress state from WebSocket
const progress = ref<Record<string, any>>({
  image: 'pending',
  music: 'pending',
  video: 'pending',
  compose: 'pending',
})
const videoProgress = ref({ segment: 0, total: 0, pct: 0 })
let ws: WebSocket | null = null
let wsRetryCount = 0
const WS_MAX_RETRIES = 5

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
    const [projRes, mediaRes] = await Promise.all([
      api.get(`/projects/${projectId.value}`),
      api.get(`/projects/${projectId.value}/media`),
    ])
    const p = projRes.data
    visualStyle.value = p.visual_style || ''
    mood.value = p.mood || ''
    storyboard.value = p.storyboard || []
    if (p.model_preferences?.video) videoModel.value = p.model_preferences.video
    if (p.model_preferences?.music) musicModel.value = p.model_preferences.music
    if (p.chat_history?.length) {
      messages.value = p.chat_history
    }
    // Restore final video preview (survives page reload)
    const finalVideo = (mediaRes.data as any[]).find((m: any) => m.type === 'final_video')
    if (finalVideo?.file_url) {
      previewUrl.value = finalVideo.file_url
    }
  } catch { /* project may not exist yet */ }
}

function connectWebSocket() {
  if (!projectId.value) return
  const wsBase = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/^http/, 'ws')
  // Token sent as first message after connect (not in URL, to avoid logging)
  ws = new WebSocket(`${wsBase}/ws/projects/${projectId.value}/progress`)
  ws.onopen = () => {
    wsRetryCount = 0
    const token = localStorage.getItem('token') || ''
    if (token) ws?.send(JSON.stringify({ type: 'auth', token }))
  }
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      progress.value[data.type] = data.status

      if (data.type === 'video' && data.pct !== undefined) {
        videoProgress.value = { segment: data.segment || 0, total: data.total || 0, pct: data.pct }
      }

      if (data.type === 'pipeline' && data.status === 'completed') {
        generating.value = false
        videoProgress.value = { segment: 0, total: 0, pct: 100 }
        ElMessage.success(t.value('generationComplete'))
        loadProject()
      }

      if (data.file_url && data.type === 'compose' && data.status === 'completed') {
        previewUrl.value = data.file_url
      }
    } catch { /* malformed message */ }
  }
  ws.onerror = () => {
    ElMessage.warning(t.value('connectionLost'))
  }
  ws.onclose = () => {
    // Auto-reconnect with backoff, up to WS_MAX_RETRIES attempts
    if (generating.value && wsRetryCount < WS_MAX_RETRIES) {
      wsRetryCount++
      const delay = Math.min(3000 * wsRetryCount, 30000)
      setTimeout(() => connectWebSocket(), delay)
    } else if (wsRetryCount >= WS_MAX_RETRIES) {
      generating.value = false
      ElMessage.error(t.value('connectionLost'))
    }
  }
}

async function sendMessage() {
  if (!chatInput.value.trim() || chatLoading.value) return
  const text = chatInput.value.trim()
  chatInput.value = ''
  messages.value.push({ role: 'user', content: text })
  scrollChat()

  chatLoading.value = true
  try {
    // Guest mode: stateless LLM call, no project created
    if (isGuest.value) {
      const history = messages.value.slice(0, -1) // exclude the message we just added
      const res = await api.post('/chat/guest', { message: text, history })
      messages.value.push({ role: 'assistant', content: res.data.content })
      scrollChat()
      return
    }

    if (!projectId.value) {
      // Create project first, then update URL so reload works correctly
      const res = await api.post('/projects', { title: text.slice(0, 50) })
      projectId.value = res.data.id
      router.replace(`/create/${res.data.id}`)
    }

    const res = await api.post(`/projects/${projectId.value}/chat`, {
      message: text,
      stream: false,
    })
    messages.value.push({ role: 'assistant', content: res.data.content })
    if (res.data.plan?.storyboard) {
      storyboard.value = res.data.plan.storyboard
    }
    // Auto-apply extracted intent to sidebar selectors
    const intent = res.data.intent_extracted
    if (intent) {
      if (intent.visual_style) visualStyle.value = intent.visual_style
      if (intent.mood) mood.value = intent.mood
      if (intent.music_style) musicModel.value = intent.music_style
      if (intent.ready_to_plan) {
        ElMessage.info(t.value('readyToPlan'))
      }
    }
  } catch {
    messages.value.push({ role: 'assistant', content: t.value('chatError') })
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

async function generatePlan() {
  if (isGuest.value) { showLoginModal.value = true; return }
  if (!projectId.value) return
  chatLoading.value = true
  const lastUserMsg = [...messages.value].reverse().find(m => m.role === 'user')?.content || ''
  try {
    // Update project settings including model preferences
    await api.put(`/projects/${projectId.value}`, {
      visual_style: visualStyle.value,
      music_style: musicModel.value,
      mood: mood.value,
      model_preferences: {
        video: videoModel.value || undefined,
        music: musicModel.value || undefined,
      },
    })
    const res = await api.post(`/projects/${projectId.value}/chat`, {
      message: lastUserMsg || '根据我的偏好生成创作方案',
      generate_plan: true,
    })
    messages.value.push({ role: 'assistant', content: res.data.content })
    if (res.data.plan?.storyboard) {
      storyboard.value = res.data.plan.storyboard
    }
  } catch {
    ElMessage.error(t.value('generatePlanError'))
  } finally {
    chatLoading.value = false
    scrollChat()
  }
}

async function startGenerating() {
  if (isGuest.value) { showLoginModal.value = true; return }
  if (!projectId.value || !storyboard.value.length) {
    ElMessage.warning(t.value('planFirst'))
    return
  }
  generating.value = true
  progress.value = { image: 'pending', music: 'pending', video: 'pending', compose: 'pending' }
  try {
    await api.post(`/projects/${projectId.value}/pipeline/start`)
    ElMessage.info(t.value('startSuccess'))
    if (!ws || ws.readyState !== WebSocket.OPEN) connectWebSocket()
  } catch {
    ElMessage.error(t.value('startGenerateError'))
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

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: t.value('statusPending'),
    running: t.value('statusRunning'),
    completed: t.value('statusCompleted'),
    failed: t.value('statusFailed'),
    uploading: t.value('statusUploading'),
  }
  return map[status] || status
}

function taskTypeLabel(type: string): string {
  const map: Record<string, string> = {
    image: t.value('taskImage'),
    music: t.value('taskMusic'),
    video: t.value('taskVideo'),
    compose: t.value('taskCompose'),
  }
  return map[type] || type
}

function uploadAudio() {
  if (isGuest.value) { showLoginModal.value = true; return }
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
      ElMessage.success(`音频分析完成！BPM: ${res.data.analysis.bpm}`)
      messages.value.push({
        role: 'assistant',
        content: `音频上传并分析完成！\nBPM: ${res.data.analysis.bpm}\n时长: ${Math.round(res.data.analysis.duration)}秒\n检测到 ${res.data.analysis.sections.length} 个段落`,
      })
    } catch {
      ElMessage.error(t.value('uploadAudioError'))
    }
  }
  input.click()
}
</script>

<template>
  <div class="create-wrapper">
  <header class="create-topbar">
    <router-link to="/" class="topbar-logo">AIMV</router-link>
    <span class="topbar-project">{{ route.params.id ? `#${route.params.id}` : '' }}</span>
    <div class="topbar-right">
      <router-link v-if="!isGuest" to="/projects" class="btn-ghost btn-sm">{{ t('myProjects') }}</router-link>
      <button v-else class="btn-primary btn-sm" @click="showLoginModal = true">{{ t('loginBtn') }} / {{ t('registerBtn') }}</button>
    </div>
  </header>
  <div class="create-layout">
    <!-- Chat Panel -->
    <aside class="chat-panel">
      <div class="chat-header">
        <h3>{{ t('aiDirector') }}</h3>
        <div class="chat-header-right">
          <span v-if="isGuest" class="guest-badge">{{ t('guestHint') }}</span>
          <button class="btn-ghost btn-sm" @click="uploadAudio" :title="t('uploadAudio')">{{ t('uploadAudio') }}</button>
        </div>
      </div>
      <div class="chat-messages" ref="chatMessagesEl">
        <div v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <div class="msg-bubble">{{ msg.content }}</div>
        </div>
        <div v-if="chatLoading" class="msg assistant">
          <div class="msg-bubble typing">{{ t('thinking') }}</div>
        </div>
      </div>
      <div class="chat-input-area">
        <input
          v-model="chatInput"
          :placeholder="t('chatPlaceholder')"
          @keyup.enter="sendMessage"
          :disabled="chatLoading"
        />
        <button class="btn-primary send-btn" @click="sendMessage" :disabled="chatLoading">{{ t('send') }}</button>
      </div>
    </aside>

    <!-- Main: Preview + Timeline -->
    <main class="create-main">
      <div class="preview-area">
        <video v-if="previewUrl" :src="previewUrl" controls class="preview-video"></video>
        <div v-else class="preview-placeholder">
          <span class="preview-icon">{{ t('mvPreview') }}</span>
          <p>{{ t('previewPlaceholder') }}</p>
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
              <span class="seg-label">{{ seg.label === 'sing' ? t('labelSing') : t('labelStory') }}</span>
            </div>
          </div>
        </div>
        <div class="timeline-bar" v-else>
          <div class="timeline-track"></div>
        </div>
        <div class="timeline-controls">
          <button class="btn-ghost" @click="generatePlan" :disabled="chatLoading">
            {{ chatLoading ? t('generating') : t('generatePlan') }}
          </button>
          <button class="btn-primary" @click="startGenerating" :disabled="generating || !storyboard.length">
            {{ generating ? t('generatingMV') : t('startGenerating') }}
          </button>
          <button class="btn-ghost" @click="showCompare = true">{{ t('abCompare') }}</button>
          <button class="btn-ghost" @click="$router.push(`/editor/${projectId}`)">{{ t('export') }}</button>
        </div>
      </div>
    </main>

    <!-- Login prompt for guests -->
    <div v-if="showLoginModal" class="login-overlay" @click.self="showLoginModal = false">
      <div class="login-prompt card">
        <h3>{{ t('loginRequired') }}</h3>
        <p>{{ t('loginToGenerate') }}</p>
        <div class="login-prompt-actions">
          <button class="btn-ghost" @click="showLoginModal = false">{{ t('cancel') }}</button>
          <button class="btn-primary" @click="router.push({ name: 'login', query: { redirect: route.fullPath } })">
            {{ t('loginBtn') }} / {{ t('registerBtn') }}
          </button>
        </div>
      </div>
    </div>

    <!-- A/B Compare Modal -->
    <ComparePanel
      v-if="projectId"
      :project-id="projectId"
      :visible="showCompare"
      @close="showCompare = false"
      @picked="(id, model) => ElMessage.success(`已选择 ${model}`)"
    />

    <!-- Right: Properties Panel -->
    <aside class="props-panel">
      <h3>{{ t('properties') }}</h3>
      <div class="prop-group">
        <label>{{ t('visualStyle') }}</label>
        <el-select v-model="visualStyle" :placeholder="t('autoRouted')" style="width: 100%">
          <el-option :label="t('styleKpop')" value="韩娱" />
          <el-option :label="t('styleChinese')" value="国风" />
          <el-option :label="t('styleCyberpunk')" value="赛博朋克" />
          <el-option :label="t('styleRetro')" value="复古迪斯科" />
          <el-option :label="t('styleIndie')" value="独立电影" />
          <el-option :label="t('styleUrban')" value="都市甜酷" />
          <el-option :label="t('styleFantasy')" value="幻想童话" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>{{ t('videoModel') }}</label>
        <el-select v-model="videoModel" :placeholder="t('autoRouted')" style="width: 100%">
          <el-option :label="t('autoRouted')" value="" />
          <el-option label="Seedance 2.0" value="seedance" />
          <el-option label="Veo 3.1" value="veo" />
          <el-option label="Grok Video" value="grok" />
          <el-option label="Wan 2.2（本地）" value="wan2.2" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>{{ t('musicModel') }}</label>
        <el-select v-model="musicModel" :placeholder="t('autoRouted')" style="width: 100%">
          <el-option :label="t('autoRouted')" value="" />
          <el-option label="ACEStep 1.5（开源）" value="acestep" />
          <el-option label="Suno" value="suno" />
          <el-option label="Google Lyria" value="lyria" />
        </el-select>
      </div>
      <div class="prop-group">
        <label>{{ t('mood') }}</label>
        <el-select v-model="mood" :placeholder="t('autoRouted')" style="width: 100%">
          <el-option :label="t('moodEnergetic')" value="energetic" />
          <el-option :label="t('moodMelancholic')" value="melancholic" />
          <el-option :label="t('moodRomantic')" value="romantic" />
          <el-option :label="t('moodEpic')" value="epic" />
          <el-option :label="t('moodPeaceful')" value="peaceful" />
        </el-select>
      </div>

      <div class="generation-status">
        <h4>{{ t('generationStatus') }}</h4>
        <div class="status-item" v-for="type in ['image', 'music', 'video', 'compose']" :key="type">
          <span :class="['badge', statusBadge(progress[type])]">{{ statusLabel(progress[type]) }}</span>
          <span>{{ taskTypeLabel(type) }}</span>
          <span v-if="type === 'video' && videoProgress.total > 0" class="seg-counter">
            {{ videoProgress.segment }}/{{ videoProgress.total }}
          </span>
        </div>
        <div v-if="generating && videoProgress.total > 0" class="progress-bar-wrap">
          <div class="progress-bar" :style="{ width: videoProgress.pct + '%' }"></div>
          <span class="progress-label">{{ videoProgress.pct }}%</span>
        </div>
      </div>

      <div v-if="storyboard.length" class="storyboard-summary">
        <h4>{{ t('storyboard') }}（{{ storyboard.length }} 段）</h4>
        <div class="seg-list">
          <div v-for="(seg, i) in storyboard" :key="i">
            <!-- Edit mode -->
            <div v-if="editingSegIdx === i" class="seg-editor">
              <div class="seg-editor-row">
                <button
                  :class="['label-toggle', editingSegData.label === 'sing' ? 'active-sing' : 'active-story']"
                  @click="editingSegData.label = editingSegData.label === 'sing' ? 'story' : 'sing'"
                >{{ editingSegData.label === 'sing' ? t('labelSing') : t('labelStory') }}</button>
                <span class="seg-num">#{{ i + 1 }}</span>
              </div>
              <textarea
                v-model="editingSegData.description"
                class="seg-textarea"
                rows="3"
                placeholder="场景描述..."
              />
              <textarea
                v-if="editingSegData.video_prompt !== undefined"
                v-model="editingSegData.video_prompt"
                class="seg-textarea seg-textarea-sm"
                rows="2"
                placeholder="视频提示词（可选，留空使用描述）..."
              />
              <div class="seg-editor-actions">
                <button class="btn-ghost btn-xs" @click="cancelEditSeg">{{ t('cancel') }}</button>
                <button class="btn-primary btn-xs" @click="saveEditSeg" :disabled="savingStoryboard">
                  {{ savingStoryboard ? '...' : t('save') }}
                </button>
              </div>
            </div>
            <!-- View mode -->
            <div v-else class="seg-item seg-item-clickable" @click="startEditSeg(i)">
              <span class="seg-num">#{{ i + 1 }}</span>
              <span :class="['badge', seg.label === 'sing' ? 'badge-warning' : 'badge-info']">
                {{ seg.label === 'sing' ? t('labelSing') : t('labelStory') }}
              </span>
              <span class="seg-desc">{{ (seg.description || '').slice(0, 36) }}</span>
              <span class="seg-edit-hint">✎</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </div><!-- end .create-layout -->
  </div><!-- end .create-wrapper -->
</template>

<style scoped>
.create-wrapper { display: flex; flex-direction: column; height: 100vh; }

/* Top navigation bar */
.create-topbar {
  height: 44px; flex-shrink: 0;
  display: flex; align-items: center; padding: 0 16px; gap: 12px;
  background: var(--bg-soft); border-bottom: 1px solid var(--border);
}
.topbar-logo {
  font-size: 18px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  text-decoration: none;
}
.topbar-project { font-size: 12px; color: var(--text-muted); flex: 1; }
.topbar-right { display: flex; align-items: center; gap: 8px; }

.create-layout { flex: 1; display: flex; overflow: hidden; }

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
.chat-header-right { display: flex; align-items: center; gap: 8px; }
.guest-badge {
  font-size: 10px; color: var(--text-muted);
  background: var(--card); border: 1px solid var(--border);
  border-radius: 100px; padding: 2px 8px;
}

/* Login prompt overlay */
.login-overlay {
  position: fixed; inset: 0; z-index: 2000;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.login-prompt {
  width: 380px; padding: 32px; text-align: center;
}
.login-prompt h3 { font-size: 18px; margin-bottom: 10px; }
.login-prompt p { color: var(--text-muted); font-size: 14px; margin-bottom: 24px; line-height: 1.6; }
.login-prompt-actions { display: flex; gap: 12px; justify-content: center; }
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
.seg-desc { color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.seg-item-clickable { cursor: pointer; border-radius: var(--radius-sm); padding: 4px 2px; transition: background 0.15s; }
.seg-item-clickable:hover { background: var(--card); }
.seg-item-clickable:hover .seg-edit-hint { opacity: 1; }
.seg-edit-hint { font-size: 11px; color: var(--text-muted); opacity: 0; margin-left: auto; transition: opacity 0.15s; }

.seg-editor { background: var(--card); border-radius: var(--radius-sm); padding: 10px; margin-bottom: 4px; }
.seg-editor-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.label-toggle {
  font-size: 11px; padding: 3px 10px; border-radius: 100px; cursor: pointer; border: 1px solid;
  transition: all 0.15s;
}
.active-sing { background: rgba(251,191,36,0.15); border-color: rgba(251,191,36,0.5); color: #fbbf24; }
.active-story { background: rgba(141,92,255,0.15); border-color: rgba(141,92,255,0.5); color: var(--accent-strong); }
.seg-textarea {
  width: 100%; background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 6px 8px; color: var(--text);
  font-size: 12px; resize: vertical; outline: none; margin-bottom: 6px;
}
.seg-textarea:focus { border-color: var(--accent-strong); }
.seg-textarea-sm { font-size: 11px; color: var(--text-muted); }
.seg-editor-actions { display: flex; gap: 6px; justify-content: flex-end; }

/* Progress bar */
.seg-counter { margin-left: auto; font-size: 11px; color: var(--text-muted); }
.progress-bar-wrap {
  position: relative; height: 6px; background: var(--card);
  border-radius: 3px; overflow: hidden; margin-top: 8px;
}
.progress-bar {
  height: 100%; background: var(--accent-gradient);
  border-radius: 3px; transition: width 0.5s ease;
}
.progress-label {
  position: absolute; right: 0; top: -18px;
  font-size: 11px; color: var(--text-muted);
}
</style>
