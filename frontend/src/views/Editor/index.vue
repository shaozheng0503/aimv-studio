<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const projectId = Number(route.params.id)
const project = ref<any>(null)
const mediaList = ref<any[]>([])
const previewUrl = ref('')
const exporting = ref(false)
const exportPlatform = ref('bilibili')
const addWatermark = ref(false)
const watermarkText = ref('Made with AIMV')
const showExportDialog = ref(false)

const platforms = [
  { value: 'douyin', label: 'Douyin (9:16)', icon: '📱' },
  { value: 'bilibili', label: 'Bilibili (16:9)', icon: '📺' },
  { value: 'youtube', label: 'YouTube (16:9 HQ)', icon: '🎬' },
  { value: 'xiaohongshu', label: 'Xiaohongshu (3:4)', icon: '📕' },
  { value: 'instagram', label: 'Instagram Reels', icon: '📷' },
  { value: 'original', label: 'Original', icon: '💾' },
]

onMounted(async () => {
  const [pRes, mRes] = await Promise.all([
    api.get(`/projects/${projectId}`),
    api.get(`/projects/${projectId}/media`),
  ])
  project.value = pRes.data
  mediaList.value = mRes.data
  const final = mediaList.value.find((m: any) => m.type === 'final_video')
  if (final) previewUrl.value = final.file_url
})

async function doExport() {
  exporting.value = true
  try {
    const res = await api.post(`/projects/${projectId}/export`, {
      platform: exportPlatform.value,
      add_watermark: addWatermark.value,
      watermark_text: watermarkText.value,
    })
    if (res.data.download_url) {
      ElMessage.success('Export ready!')
      window.open(res.data.download_url)
    } else {
      ElMessage.info('Export started. You will be notified when ready.')
    }
    showExportDialog.value = false
  } catch {
    ElMessage.error('Export failed')
  } finally {
    exporting.value = false
  }
}

const videos = ref<any[]>([])
const audios = ref<any[]>([])
const images = ref<any[]>([])

onMounted(() => {
  setTimeout(() => {
    videos.value = mediaList.value.filter((m: any) => m.type === 'video')
    audios.value = mediaList.value.filter((m: any) => m.type === 'music' || m.type === 'audio')
    images.value = mediaList.value.filter((m: any) => m.type === 'image')
  }, 500)
})
</script>

<template>
  <div class="editor-page">
    <header class="editor-header">
      <h1>{{ project?.title || 'Editor' }}</h1>
      <div class="header-actions">
        <router-link :to="`/create/${projectId}`" class="btn-ghost">Back to Studio</router-link>
        <button class="btn-primary" @click="showExportDialog = true">Export</button>
      </div>
    </header>

    <div class="editor-layout">
      <!-- Preview -->
      <div class="editor-preview">
        <video v-if="previewUrl" :src="previewUrl" controls class="main-video" />
        <div v-else class="no-preview">No final video yet</div>
      </div>

      <!-- Media Library -->
      <aside class="media-library">
        <h3>Media Library</h3>

        <div class="media-section" v-if="images.length">
          <h4>Images ({{ images.length }})</h4>
          <div class="media-grid">
            <div v-for="m in images" :key="m.id" class="media-thumb">
              <img :src="m.file_url" :alt="`Image ${m.id}`" />
            </div>
          </div>
        </div>

        <div class="media-section" v-if="videos.length">
          <h4>Video Clips ({{ videos.length }})</h4>
          <div class="media-list">
            <div v-for="(m, i) in videos" :key="m.id" class="media-item" @click="previewUrl = m.file_url">
              <span class="item-num">#{{ i + 1 }}</span>
              <span class="item-dur">{{ m.duration ? `${m.duration.toFixed(1)}s` : '' }}</span>
              <span class="badge badge-success">ready</span>
            </div>
          </div>
        </div>

        <div class="media-section" v-if="audios.length">
          <h4>Audio ({{ audios.length }})</h4>
          <div class="media-list">
            <div v-for="m in audios" :key="m.id" class="media-item">
              <audio :src="m.file_url" controls class="mini-audio" />
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- Export Dialog -->
    <el-dialog v-model="showExportDialog" title="Export MV" width="480px">
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
          <el-checkbox v-model="addWatermark">Add watermark</el-checkbox>
          <input v-if="addWatermark" v-model="watermarkText" placeholder="Watermark text" class="wm-input" />
        </div>
      </div>
      <template #footer>
        <button class="btn-ghost" @click="showExportDialog = false">Cancel</button>
        <button class="btn-primary" @click="doExport" :disabled="exporting">
          {{ exporting ? 'Exporting...' : 'Export' }}
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
.header-actions { display: flex; gap: 12px; }

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
