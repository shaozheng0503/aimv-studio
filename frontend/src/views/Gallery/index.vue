<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

interface GalleryItem {
  id: number
  title: string
  visual_style: string | null
  mood: string | null
  thumbnail_url: string | null
  video_url: string | null
  likes: number
  created_at: string
}

const items = ref<GalleryItem[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)
const filterStyle = ref('')
const previewItem = ref<GalleryItem | null>(null)

const styles = ['', '韩娱', '国风', '赛博朋克', '复古迪斯科', '独立电影', '都市甜酷', '幻想童话']
const styleLabels: Record<string, string> = {
  '': 'All', '韩娱': 'K-Pop', '国风': 'Classical', '赛博朋克': 'Cyberpunk',
  '复古迪斯科': 'Disco', '独立电影': 'Indie', '都市甜酷': 'Urban', '幻想童话': 'Fantasy',
}

onMounted(() => fetchGallery())

async function fetchGallery() {
  loading.value = true
  try {
    const res = await api.get('/gallery', { params: { page: page.value, style: filterStyle.value } })
    items.value = res.data.items
    total.value = res.data.total
  } catch { /* */ }
  loading.value = false
}

async function like(item: GalleryItem) {
  try {
    const res = await api.post(`/gallery/${item.id}/like`)
    item.likes = res.data.likes
  } catch { /* */ }
}

function changeStyle(s: string) {
  filterStyle.value = s
  page.value = 1
  fetchGallery()
}
</script>

<template>
  <div class="gallery-page">
    <header class="gallery-header">
      <div class="header-inner">
        <router-link to="/" class="logo-link">
          <span class="logo-text">AIMV</span>
        </router-link>
        <h1>Gallery</h1>
        <nav class="header-nav">
          <router-link to="/projects">My Projects</router-link>
          <router-link to="/create">Create</router-link>
        </nav>
      </div>
    </header>

    <!-- Style Filters -->
    <div class="filters">
      <button
        v-for="s in styles"
        :key="s"
        :class="['filter-chip', { active: filterStyle === s }]"
        @click="changeStyle(s)"
      >
        {{ styleLabels[s] }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">Loading...</div>

    <!-- Empty -->
    <div v-else-if="!items.length" class="empty-state">
      No published works yet. Be the first to share!
    </div>

    <!-- Grid -->
    <div v-else class="gallery-grid">
      <div
        v-for="item in items"
        :key="item.id"
        class="gallery-card card"
        @click="previewItem = item"
      >
        <div class="card-thumb">
          <img v-if="item.thumbnail_url" :src="item.thumbnail_url" :alt="item.title" />
          <div v-else class="thumb-placeholder" />
          <span v-if="item.visual_style" class="style-tag badge badge-info">
            {{ styleLabels[item.visual_style] || item.visual_style }}
          </span>
        </div>
        <div class="card-body">
          <h3>{{ item.title }}</h3>
          <div class="card-meta">
            <button class="like-btn" @click.stop="like(item)">
              <span class="heart">&#9829;</span> {{ item.likes }}
            </button>
            <span class="date">{{ new Date(item.created_at).toLocaleDateString() }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > 12" class="pagination">
      <button class="btn-ghost" :disabled="page <= 1" @click="page--; fetchGallery()">Prev</button>
      <span class="page-info">{{ page }} / {{ Math.ceil(total / 12) }}</span>
      <button class="btn-ghost" :disabled="page * 12 >= total" @click="page++; fetchGallery()">Next</button>
    </div>

    <!-- Preview Modal -->
    <div v-if="previewItem" class="preview-overlay" @click.self="previewItem = null">
      <div class="preview-modal">
        <div class="preview-close" @click="previewItem = null">&times;</div>
        <video v-if="previewItem.video_url" :src="previewItem.video_url" controls autoplay class="preview-video" />
        <div class="preview-info">
          <h2>{{ previewItem.title }}</h2>
          <div class="preview-meta">
            <span v-if="previewItem.visual_style" class="badge badge-info">{{ previewItem.visual_style }}</span>
            <span v-if="previewItem.mood" class="badge badge-warning">{{ previewItem.mood }}</span>
            <button class="like-btn" @click="like(previewItem!)">
              <span class="heart">&#9829;</span> {{ previewItem.likes }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gallery-page { min-height: 100vh; }

.gallery-header {
  position: sticky; top: 0; z-index: 100;
  background: rgba(5, 5, 7, 0.9); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1200px; margin: 0 auto; padding: 0 24px; height: 64px;
  display: flex; align-items: center; gap: 24px;
}
.logo-text {
  font-size: 22px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.gallery-header h1 { font-size: 18px; flex: 1; }
.header-nav { display: flex; gap: 20px; }
.header-nav a { color: var(--text-muted); font-size: 14px; }
.header-nav a:hover { color: var(--text); }

.filters {
  max-width: 1200px; margin: 24px auto 0; padding: 0 24px;
  display: flex; gap: 8px; flex-wrap: wrap;
}
.filter-chip {
  padding: 6px 16px; border-radius: 100px; font-size: 13px;
  background: var(--card); border: 1px solid var(--border); color: var(--text-muted);
  cursor: pointer; transition: all 0.2s;
}
.filter-chip:hover { border-color: var(--accent-strong); color: var(--text); }
.filter-chip.active { background: rgba(141, 92, 255, 0.15); border-color: var(--accent-strong); color: var(--accent); }

.loading-state, .empty-state { text-align: center; padding: 80px; color: var(--text-muted); }

.gallery-grid {
  max-width: 1200px; margin: 24px auto; padding: 0 24px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px;
}
.gallery-card { padding: 0; overflow: hidden; cursor: pointer; transition: transform 0.2s; }
.gallery-card:hover { transform: translateY(-4px); }
.card-thumb { position: relative; aspect-ratio: 16/9; overflow: hidden; }
.card-thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb-placeholder { width: 100%; height: 100%; background: linear-gradient(135deg, #1a1a2e, #2d1b69); }
.style-tag { position: absolute; top: 8px; right: 8px; }
.card-body { padding: 14px 16px; }
.card-body h3 { font-size: 14px; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-meta { display: flex; justify-content: space-between; align-items: center; }
.like-btn {
  background: none; border: none; color: var(--text-muted); cursor: pointer;
  font-size: 13px; display: flex; align-items: center; gap: 4px; transition: color 0.2s;
}
.like-btn:hover { color: #f87171; }
.heart { color: #f87171; }
.date { font-size: 11px; color: var(--text-muted); }

.pagination {
  max-width: 1200px; margin: 24px auto; padding: 0 24px;
  display: flex; justify-content: center; align-items: center; gap: 16px;
}
.page-info { font-size: 13px; color: var(--text-muted); }

/* Preview Modal */
.preview-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}
.preview-modal { max-width: 900px; width: 92vw; }
.preview-close {
  position: absolute; top: 16px; right: 16px; font-size: 32px;
  color: var(--text-muted); cursor: pointer; z-index: 10;
}
.preview-video { width: 100%; border-radius: var(--radius); }
.preview-info { padding: 16px 0; }
.preview-info h2 { font-size: 20px; margin-bottom: 8px; }
.preview-meta { display: flex; gap: 8px; align-items: center; }
</style>
