<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import api from '@/api'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  projectId: number
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'picked', taskId: number, model: string): void
}>()

const prompt = ref('')
const compareType = ref('video')
const selectedModels = ref<string[]>([])
const loading = ref(false)
const results = ref<any[]>([])
const groupId = ref('')
let _stopPolling = false

onUnmounted(() => { _stopPolling = true })

const modelOptions: Record<string, { label: string; value: string }[]> = {
  video: [
    { label: 'Seedance 2.0', value: 'seedance' },
    { label: 'Veo 3.1', value: 'veo' },
    { label: 'Grok Video', value: 'grok' },
    { label: 'Wan 2.2', value: 'wan2.2' },
  ],
  music: [
    { label: 'ACEStep 1.5', value: 'acestep' },
    { label: 'Suno', value: 'suno' },
    { label: 'Google Lyria', value: 'lyria' },
  ],
  image: [
    { label: 'Qwen Image', value: 'qwen-image' },
  ],
}

const currentModels = computed(() => modelOptions[compareType.value] || [])

async function startCompare() {
  if (selectedModels.value.length < 2) {
    ElMessage.warning('Select at least 2 models')
    return
  }
  if (!prompt.value.trim()) {
    ElMessage.warning('Enter a prompt')
    return
  }

  loading.value = true
  results.value = []
  try {
    const res = await api.post(`/projects/${props.projectId}/compare`, {
      prompt: prompt.value,
      type: compareType.value,
      models: selectedModels.value,
    })
    groupId.value = res.data.compare_group_id
    results.value = res.data.tasks.map((t: any) => ({
      ...t,
      status: 'pending',
    }))
    pollResults()
  } catch {
    ElMessage.error('Failed to start comparison')
    loading.value = false
  }
}

async function pollResults() {
  _stopPolling = false
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 3000))
    if (_stopPolling) break
    try {
      const res = await api.get(`/projects/${props.projectId}/compare/${groupId.value}`)
      results.value = res.data.tasks
      const allDone = res.data.tasks.every((t: any) => t.status === 'completed' || t.status === 'failed')
      if (allDone) break
    } catch { break }
  }
  if (!_stopPolling) loading.value = false
}

async function pickWinner(taskId: number, model: string) {
  try {
    await api.post(`/projects/${props.projectId}/compare/${groupId.value}/pick/${taskId}`)
    ElMessage.success(`Selected ${model} version!`)
    emit('picked', taskId, model)
  } catch {
    ElMessage.error('Failed to save selection')
  }
}
</script>

<template>
  <div v-if="visible" class="compare-overlay" @click.self="emit('close')">
    <div class="compare-modal">
      <div class="compare-header">
        <h2>A/B Compare</h2>
        <button class="btn-ghost btn-sm" @click="emit('close')">Close</button>
      </div>

      <!-- Setup -->
      <div class="compare-setup" v-if="!results.length">
        <div class="setup-row">
          <label>Type</label>
          <el-select v-model="compareType" style="width: 160px" @change="selectedModels = []">
            <el-option label="Video" value="video" />
            <el-option label="Music" value="music" />
            <el-option label="Image" value="image" />
          </el-select>
        </div>
        <div class="setup-row">
          <label>Models</label>
          <el-checkbox-group v-model="selectedModels">
            <el-checkbox v-for="m in currentModels" :key="m.value" :value="m.value" :label="m.value">
              {{ m.label }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
        <div class="setup-row">
          <label>Prompt</label>
          <textarea v-model="prompt" rows="3" placeholder="Describe what you want to generate..." />
        </div>
        <button class="btn-primary" @click="startCompare" :disabled="loading">
          {{ loading ? 'Generating...' : 'Start Comparison' }}
        </button>
      </div>

      <!-- Results -->
      <div class="compare-results" v-else>
        <div class="compare-grid" :style="{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }">
          <div v-for="r in results" :key="r.id" class="compare-card card">
            <div class="card-header">
              <span class="model-name">{{ r.model_name }}</span>
              <span :class="['badge', r.status === 'completed' ? 'badge-success' : r.status === 'failed' ? 'badge-error' : 'badge-warning']">
                {{ r.status }}
              </span>
            </div>
            <div class="card-preview">
              <div v-if="r.status === 'completed' && r.result?.file_url" class="preview-content">
                <video v-if="compareType === 'video'" :src="r.result.file_url" controls class="result-media" />
                <audio v-else-if="compareType === 'music'" :src="r.result.file_url" controls class="result-audio" />
                <img v-else-if="compareType === 'image'" :src="r.result.file_url" class="result-media" />
              </div>
              <div v-else-if="r.status === 'failed'" class="preview-error">Generation failed</div>
              <div v-else class="preview-loading">
                <div class="spinner"></div>
                Generating...
              </div>
            </div>
            <div class="card-score" v-if="r.quality_score">
              Quality: {{ r.quality_score.toFixed(1) }}/5
            </div>
            <button
              v-if="r.status === 'completed'"
              class="btn-primary pick-btn"
              @click="pickWinner(r.id, r.model_name)"
            >
              Pick This
            </button>
          </div>
        </div>

        <div class="compare-actions">
          <button class="btn-ghost" @click="results = []; groupId = ''">
            New Comparison
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compare-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.compare-modal {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-radius: var(--radius); width: min(900px, 92vw); max-height: 85vh;
  overflow-y: auto; padding: 24px;
}
.compare-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;
}
.compare-header h2 {
  font-size: 20px;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.btn-sm { padding: 6px 14px; font-size: 12px; }

.setup-row { margin-bottom: 16px; }
.setup-row label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
.setup-row textarea {
  width: 100%; background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 10px; color: var(--text);
  font-size: 13px; resize: vertical; outline: none;
}
.setup-row textarea:focus { border-color: var(--accent-strong); }

.compare-grid { display: grid; gap: 16px; }
.compare-card { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.model-name { font-weight: 600; font-size: 14px; }
.card-preview { min-height: 200px; display: flex; align-items: center; justify-content: center; margin-bottom: 12px; }
.result-media { width: 100%; border-radius: var(--radius-sm); }
.result-audio { width: 100%; }
.preview-loading { text-align: center; color: var(--text-muted); font-size: 13px; }
.preview-error { color: var(--error); font-size: 13px; }
.spinner {
  width: 24px; height: 24px; border: 2px solid var(--border);
  border-top-color: var(--accent-strong); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 8px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.card-score { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.pick-btn { width: 100%; padding: 8px; font-size: 13px; }
.compare-actions { margin-top: 16px; text-align: center; }
</style>
