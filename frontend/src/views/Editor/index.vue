<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { useLangStore } from '@/stores/lang'

const route = useRoute()
const projectId = Number(route.params.id)
const project = ref<any>(null)
const mediaList = ref<any[]>([])
const previewUrl = ref('')
const exporting = ref(false)
const exportPlatform = ref('bilibili')
const addWatermark = ref(false)
const watermarkText = ref('Made with AIMV')
const addSubtitles = ref(false)
const showExportDialog = ref(false)
const videos = ref<any[]>([])
const audios = ref<any[]>([])
const images = ref<any[]>([])

// Export polling
let exportPollTimer: ReturnType<typeof setInterval> | null = null

function startExportPolling(taskId: number) {
  exportPollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/projects/${projectId}/tasks/${taskId}`)
      const task = res.data
      if (task.status === 'completed') {
        stopExportPolling()
        exporting.value = false
        const fileUrl = task.result?.file_url
        if (fileUrl) {
          ElMessage.success(t.value('exportReady'))
          window.open(fileUrl)
        }
      } else if (task.status === 'failed') {
        stopExportPolling()
        exporting.value = false
        ElMessage.error(task.error_message || t.value('exportFailed'))
      }
    } catch { /* ignore transient poll errors */ }
  }, 3000)
}

function stopExportPolling() {
  if (exportPollTimer) {
    clearInterval(exportPollTimer)
    exportPollTimer = null
  }
}

onUnmounted(() => stopExportPolling())

const langStore = useLangStore()
const { t } = storeToRefs(langStore)

const platforms = computed(() => [
  { value: 'douyin', label: t.value('platformDouyin'), icon: '📱' },
  { value: 'bilibili', label: t.value('platformBilibili'), icon: '📺' },
  { value: 'youtube', label: t.value('platformYoutube'), icon: '🎬' },
  { value: 'xiaohongshu', label: t.value('platformXhs'), icon: '📕' },
  { value: 'instagram', label: t.value('platformInstagram'), icon: '📷' },
  { value: 'original', label: t.value('platformOriginal'), icon: '💾' },
])

onMounted(async () => {
  let pRes, mRes
  try {
    ;[pRes, mRes] = await Promise.all([
      api.get(`/projects/${projectId}`),
      api.get(`/projects/${projectId}/media`),
    ])
  } catch {
    ElMessage.error(t.value('loadError'))
    return
  }
  project.value = pRes.data
  mediaList.value = mRes.data

  // Try to get canvas shot order so timeline matches canvas arrangement
  const canvasOrder: Record<number, number> = {}
  try {
    const cRes = await api.get(`/projects/${projectId}/canvas`)
    const shots: any[] = cRes.data.shots ?? []
    shots.forEach(s => {
      if (s.media_id != null) canvasOrder[s.media_id] = s.sort_order ?? 0
    })
  } catch { /* canvas may not exist for this project */ }

  const hasCanvasOrder = Object.keys(canvasOrder).length > 0

  videos.value = mediaList.value
    .filter((m: any) => m.type === 'video')
    .sort((a: any, b: any) =>
      hasCanvasOrder
        ? (canvasOrder[a.id] ?? 9999) - (canvasOrder[b.id] ?? 9999)
        : a.sort_order - b.sort_order
    )
  audios.value = mediaList.value.filter((m: any) => m.type === 'music' || m.type === 'audio')
  images.value = mediaList.value.filter((m: any) => m.type === 'image')

  const final = mediaList.value.find((m: any) => m.type === 'final_video')
  if (final) previewUrl.value = final.file_url
})

async function doExport() {
  exporting.value = true
  showExportDialog.value = false
  try {
    const res = await api.post(`/projects/${projectId}/export`, {
      platform: exportPlatform.value,
      add_watermark: addWatermark.value,
      watermark_text: watermarkText.value,
      add_subtitles: addSubtitles.value,
    })
    if (res.data.download_url) {
      // "original" platform — immediate download URL
      ElMessage.success(t.value('exportReady'))
      window.open(res.data.download_url)
      exporting.value = false
    } else if (res.data.task_id) {
      // Async re-encode — poll until done
      ElMessage.info(t.value('exportStarted'))
      startExportPolling(res.data.task_id)
    } else {
      exporting.value = false
    }
  } catch {
    ElMessage.error(t.value('exportFailed'))
    exporting.value = false
  }
}
</script>

<template>
  <div class="editor-page">
    <header class="editor-header">
      <h1>{{ project?.title || t('editorTitle') }}</h1>
      <div class="header-actions">
        <span v-if="exporting" class="export-status">
          <span class="export-spinner"></span>{{ t('exporting') }}
        </span>
        <router-link :to="`/canvas/${projectId}`" class="btn-ghost">{{ t('backToStudio') }}</router-link>
        <button class="btn-primary" @click="showExportDialog = true" :disabled="exporting">{{ t('export') }}</button>
      </div>
    </header>

    <div class="editor-layout">
      <!-- 预览区 -->
      <div class="editor-preview">
        <video v-if="previewUrl" :src="previewUrl" controls class="main-video" />
        <div v-else class="no-preview">{{ t('noFinalVideo') }}</div>
      </div>

      <!-- 媒体库 -->
      <aside class="media-library">
        <h3>{{ t('mediaLibrary') }}</h3>

        <div class="media-section" v-if="images.length">
          <h4>{{ t('images') }} ({{ images.length }})</h4>
          <div class="media-grid">
            <div v-for="m in images" :key="m.id" class="media-thumb">
              <img :src="m.file_url" :alt="`图片 ${m.id}`" />
            </div>
          </div>
        </div>

        <div class="media-section" v-if="videos.length">
          <h4>{{ t('videoClips') }} ({{ videos.length }})</h4>
          <div class="media-list">
            <div v-for="(m, i) in videos" :key="m.id" class="media-item" @click="previewUrl = m.file_url">
              <span class="item-num">#{{ i + 1 }}</span>
              <span class="item-dur">{{ m.duration ? `${m.duration.toFixed(1)}s` : '' }}</span>
              <span class="badge badge-success">{{ t('statusCompleted') }}</span>
            </div>
          </div>
        </div>

        <div class="media-section" v-if="audios.length">
          <h4>{{ t('audio') }} ({{ audios.length }})</h4>
          <div class="media-list">
            <div v-for="m in audios" :key="m.id" class="media-item">
              <audio :src="m.file_url" controls class="mini-audio" />
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 导出弹窗 -->
    <el-dialog v-model="showExportDialog" :title="t('exportMV')" width="480px">
      <div class="export-form">
        <div class="platform-grid">
          <div
            v-for="p in platforms"
            :key="p.value"
            :class="['platform-card', { active: exportPlatform === p.value }]"
            @click="exportPlatform = p.value"
          >
            <span class="platform-icon">{{ p.icon }}</span>
            <span class="platform-label">{{ p.label }}</span>
          </div>
        </div>
        <div class="export-option">
          <el-checkbox v-model="addSubtitles">{{ t('burnSubtitles') }}</el-checkbox>
        </div>
        <div class="export-option">
          <el-checkbox v-model="addWatermark">{{ t('addWatermark') }}</el-checkbox>
          <input v-if="addWatermark" v-model="watermarkText" :placeholder="t('watermarkText')" class="wm-input" />
        </div>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="showExportDialog = false">{{ t('cancel') }}</button>
        <button class="btn-primary" @click="doExport" :disabled="exporting">
          {{ exporting ? t('exporting') : t('exportBtn') }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.editor-page { min-height: 100vh; background: var(--bg); }
.editor-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px; border-bottom: 1px solid var(--border); background: var(--bg-soft);
}
.editor-header h1 { font-size: 18px; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.export-status { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); }
.export-spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid var(--border); border-top-color: var(--accent-strong);
  animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.editor-layout { display: flex; height: calc(100vh - 60px); }
.editor-preview { flex: 1; display: flex; align-items: center; justify-content: center; padding: 24px; }
.main-video { max-width: 100%; max-height: 100%; border-radius: var(--radius); }
.no-preview { color: var(--text-muted); }

.media-library {
  width: 300px; background: var(--bg-soft); border-left: 1px solid var(--border);
  padding: 20px; overflow-y: auto;
}
.media-library h3 { font-size: 15px; margin-bottom: 16px; }
.media-section { margin-bottom: 20px; }
.media-section h4 { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.media-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.media-thumb img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 4px; cursor: pointer; }
.media-list { display: flex; flex-direction: column; gap: 6px; }
.media-item {
  display: flex; align-items: center; gap: 8px; padding: 8px;
  background: var(--card); border-radius: var(--radius-sm); cursor: pointer; font-size: 12px;
}
.media-item:hover { background: var(--card-hover); }
.item-num { font-weight: 600; color: var(--accent-strong); }
.item-dur { color: var(--text-muted); }
.mini-audio { width: 100%; height: 32px; }

/* Export Dialog */
.export-form { padding: 8px 0; }
.platform-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 16px; }
.platform-card {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 12px 8px; background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); cursor: pointer; transition: all 0.2s;
}
.platform-card:hover { border-color: var(--accent-strong); }
.platform-card.active { border-color: var(--accent-strong); background: rgba(141, 92, 255, 0.1); }
.platform-icon { font-size: 24px; }
.platform-label { font-size: 11px; color: var(--text-muted); text-align: center; }
.export-option { margin-top: 12px; }
.wm-input {
  display: block; width: 100%; margin-top: 8px; padding: 8px 12px;
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text); font-size: 13px;
}
</style>
