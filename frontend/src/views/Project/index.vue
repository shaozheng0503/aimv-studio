<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import api from '@/api'
import { ElMessage } from 'element-plus'
import { useLangStore } from '@/stores/lang'

const router = useRouter()
const langStore = useLangStore()
const { t, lang } = storeToRefs(langStore)
const projects = ref<any[]>([])
const loading = ref(true)
const editingId = ref<number | null>(null)
const editingTitle = ref('')

const statusMap = computed<Record<string, string>>(() => ({
  draft: t.value('statusDraft'),
  planning: t.value('statusPlanning'),
  generating: t.value('statusGenerating'),
  composing: t.value('statusGenerating'),
  done: t.value('statusDone'),
  failed: t.value('statusFailed'),
}))

onMounted(async () => {
  try {
    const res = await api.get('/projects')
    projects.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

async function createProject() {
  const res = await api.post('/projects', { title: t.value('projectUntitled') })
  router.push(`/create/${res.data.id}`)
}

function startEdit(p: any, event: Event) {
  event.stopPropagation()
  editingId.value = p.id
  editingTitle.value = p.title
}

async function saveTitle(p: any) {
  const title = editingTitle.value.trim()
  if (!title || title === p.title) {
    editingId.value = null
    return
  }
  try {
    await api.put(`/projects/${p.id}`, { title })
    p.title = title
  } catch {
    ElMessage.error(t.value('renameError'))
  } finally {
    editingId.value = null
  }
}

async function deleteProject(p: any, event: Event) {
  event.stopPropagation()
  if (!confirm(t.value('confirmDeleteMsg'))) return
  try {
    await api.delete(`/projects/${p.id}`)
    projects.value = projects.value.filter(x => x.id !== p.id)
  } catch {
    ElMessage.error(t.value('deleteError'))
  }
}

function isPublished(p: any): boolean {
  return !!(p.style_config?.published)
}

async function togglePublish(p: any, event: Event) {
  event.stopPropagation()
  const published = isPublished(p)
  const endpoint = published ? `/projects/${p.id}/unpublish` : `/projects/${p.id}/publish`
  try {
    await api.post(endpoint)
    if (!p.style_config) p.style_config = {}
    p.style_config = { ...p.style_config, published: !published }
    ElMessage.success(t.value(published ? 'unpublishSuccess' : 'publishSuccess'))
  } catch {
    ElMessage.error(t.value('publishError'))
  }
}
</script>

<template>
  <div class="projects-page">
    <header class="page-header">
      <div class="header-logo">
        <router-link to="/" class="logo-text">AIMV</router-link>
      </div>
      <h1>{{ t('myProjects') }}</h1>
      <button class="btn-primary" @click="createProject">{{ t('newProject') }}</button>
    </header>

    <div v-if="loading" class="loading">{{ t('loading') }}</div>

    <div v-else-if="projects.length === 0" class="empty">
      <p>{{ t('noProjects') }}</p>
      <button class="btn-primary" style="margin-top:16px" @click="createProject">{{ t('newProject') }}</button>
    </div>

    <div v-else class="project-grid">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card project-card"
        @click="router.push(`/create/${p.id}`)"
      >
        <div class="project-thumb">
          <span class="thumb-status" :class="`status-${p.status}`">
            {{ statusMap[p.status] || p.status }}
          </span>
        </div>
        <div class="project-info">
          <!-- 标题：双击进入编辑模式 -->
          <div class="project-title-row">
            <input
              v-if="editingId === p.id"
              class="title-input"
              v-model="editingTitle"
              @blur="saveTitle(p)"
              @keyup.enter="saveTitle(p)"
              @keyup.esc="editingId = null"
              @click.stop
              autofocus
            />
            <h3 v-else @dblclick.stop="startEdit(p, $event)">{{ p.title }}</h3>
          </div>
          <div class="project-meta">
            <span :class="['badge', p.status === 'done' ? 'badge-success' : p.status === 'failed' ? 'badge-error' : 'badge-info']">
              {{ statusMap[p.status] || p.status }}
            </span>
            <span class="meta-date">{{ new Date(p.created_at).toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US') }}</span>
          </div>
          <div class="project-actions">
            <button class="btn-ghost btn-xs" @click.stop="router.push(`/create/${p.id}`)">{{ t('enterCreate') }}</button>
            <button v-if="p.status === 'done'" class="btn-ghost btn-xs" @click.stop="router.push(`/editor/${p.id}`)">{{ t('export') }}</button>
            <button
              v-if="p.status === 'done'"
              class="btn-ghost btn-xs"
              :class="isPublished(p) ? 'btn-published' : 'btn-publish'"
              @click.stop="togglePublish(p, $event)"
            >{{ isPublished(p) ? t('unpublishProject') : t('publishProject') }}</button>
            <button class="btn-ghost btn-xs btn-danger" @click="deleteProject(p, $event)">{{ t('delete') }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.projects-page { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
.page-header {
  display: flex; align-items: center; gap: 16px; margin-bottom: 32px;
}
.page-header h1 { flex: 1; font-size: 20px; }
.header-logo .logo-text {
  font-size: 22px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.project-card { cursor: pointer; padding: 0; overflow: hidden; transition: transform 0.2s; }
.project-card:hover { transform: translateY(-3px); }
.project-thumb {
  height: 160px;
  background: linear-gradient(135deg, #1a1a2e, #2d1b69);
  display: flex; align-items: flex-end; padding: 12px;
}
.thumb-status {
  font-size: 11px; font-weight: 600; padding: 3px 8px;
  border-radius: 100px; background: rgba(0,0,0,0.5); color: white;
}
.status-done { background: rgba(52, 211, 153, 0.3); color: #34d399; }
.status-generating, .status-composing { background: rgba(251,191,36,0.3); color: #fbbf24; }
.status-failed { background: rgba(248,113,113,0.3); color: #f87171; }
.project-info { padding: 14px 16px; }
.project-title-row { margin-bottom: 8px; }
.project-info h3 { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: text; }
.project-info h3:hover { color: var(--accent); }
.title-input {
  width: 100%; padding: 2px 6px; font-size: 14px; font-weight: 600;
  background: var(--bg); border: 1px solid var(--accent-strong);
  border-radius: 4px; color: var(--text); outline: none;
}
.project-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.meta-date { font-size: 11px; color: var(--text-muted); }
.project-actions { display: flex; gap: 8px; }
.btn-xs { padding: 4px 10px; font-size: 11px; }
.btn-danger { color: var(--error, #f87171) !important; }
.btn-publish { color: var(--accent, #a78bfa) !important; }
.btn-published { color: #34d399 !important; }
.empty, .loading { text-align: center; padding: 80px; color: var(--text-muted); }
</style>
