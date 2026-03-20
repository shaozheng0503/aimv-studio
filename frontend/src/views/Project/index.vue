<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()
const projects = ref<any[]>([])
const loading = ref(true)

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
  const res = await api.post('/projects', { title: 'Untitled MV' })
  router.push(`/create/${res.data.id}`)
}
</script>

<template>
  <div class="projects-page">
    <header class="page-header">
      <h1>My Projects</h1>
      <button class="btn-primary" @click="createProject">+ New Project</button>
    </header>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="projects.length === 0" class="empty">
      <p>No projects yet. Create your first MV!</p>
    </div>

    <div v-else class="project-grid">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card project-card"
        @click="router.push(`/create/${p.id}`)"
      >
        <div class="project-thumb"></div>
        <div class="project-info">
          <h3>{{ p.title }}</h3>
          <div class="project-meta">
            <span class="badge badge-info">{{ p.status }}</span>
            <span class="meta-date">{{ new Date(p.created_at).toLocaleDateString() }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.projects-page { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
.project-card { cursor: pointer; padding: 0; overflow: hidden; }
.project-thumb { height: 160px; background: linear-gradient(135deg, #1a1a2e, #2d1b69); }
.project-info { padding: 16px; }
.project-info h3 { font-size: 15px; margin-bottom: 8px; }
.project-meta { display: flex; align-items: center; gap: 8px; }
.meta-date { font-size: 12px; color: var(--text-muted); }
.empty, .loading { text-align: center; padding: 80px; color: var(--text-muted); }
</style>
