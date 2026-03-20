<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function startCreating() {
  const token = localStorage.getItem('token')
  if (!token) {
    router.push('/login')
  } else {
    router.push('/create')
  }
}
</script>

<template>
  <div class="home">
    <!-- Header -->
    <header class="home-header">
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">AIMV</span>
        </div>
        <nav class="header-nav">
          <router-link to="/gallery">Gallery</router-link>
          <router-link to="/projects">My Projects</router-link>
          <router-link to="/login">Sign In</router-link>
        </nav>
      </div>
    </header>

    <!-- Hero -->
    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <h1>AI Music Video <span class="gradient-text">Creation Platform</span></h1>
        <p class="hero-subtitle">
          Transform your creative vision into professional music videos with AI.
          From concept to final cut — powered by multi-modal AI orchestration.
        </p>
        <div class="hero-actions">
          <button class="btn-primary hero-cta" @click="startCreating">
            Start Creating
          </button>
          <button class="btn-ghost">Watch Demo</button>
        </div>
        <div class="hero-stats">
          <div class="stat">
            <span class="stat-value">8+</span>
            <span class="stat-label">AI Models</span>
          </div>
          <div class="stat">
            <span class="stat-value">7</span>
            <span class="stat-label">Visual Styles</span>
          </div>
          <div class="stat">
            <span class="stat-value">3</span>
            <span class="stat-label">Music Engines</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Features -->
    <section class="features">
      <div class="container">
        <h2>How It Works</h2>
        <div class="feature-grid">
          <div class="card feature-card">
            <div class="feature-icon">01</div>
            <h3>Describe Your Vision</h3>
            <p>Chat with our AI director. Describe the mood, style, and story you want.</p>
          </div>
          <div class="card feature-card">
            <div class="feature-icon">02</div>
            <h3>AI Generates Everything</h3>
            <p>Images, video clips, and music are generated in parallel by the best AI models.</p>
          </div>
          <div class="card feature-card">
            <div class="feature-icon">03</div>
            <h3>Review & Refine</h3>
            <p>Preview, compare A/B versions, adjust any part, and export your final MV.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Styles -->
    <section class="styles-section">
      <div class="container">
        <h2>Supported Styles</h2>
        <div class="style-grid">
          <div class="style-card" v-for="style in styles" :key="style.name">
            <div class="style-preview" :style="{ background: style.color }"></div>
            <span>{{ style.name }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      styles: [
        { name: 'K-Pop', color: 'linear-gradient(135deg, #ff6b9d, #c051e0)' },
        { name: 'Chinese Classical', color: 'linear-gradient(135deg, #2d5016, #8b6914)' },
        { name: 'Cyberpunk', color: 'linear-gradient(135deg, #0ff, #f0f)' },
        { name: 'Retro Disco', color: 'linear-gradient(135deg, #ff8c00, #ff1493)' },
        { name: 'Indie Film', color: 'linear-gradient(135deg, #3a3a3a, #8b7355)' },
        { name: 'Urban Cool', color: 'linear-gradient(135deg, #667eea, #764ba2)' },
        { name: 'Fantasy', color: 'linear-gradient(135deg, #a18cd1, #fbc2eb)' },
      ],
    }
  },
}
</script>

<style scoped>
.home { min-height: 100vh; }

.home-header {
  position: fixed; top: 0; left: 0; width: 100%;
  background: rgba(5, 5, 7, 0.85); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border); z-index: 100;
}
.header-inner {
  max-width: 1200px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 64px;
}
.logo-icon {
  font-size: 24px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-nav { display: flex; gap: 24px; }
.header-nav a { color: var(--text-muted); font-size: 14px; }
.header-nav a:hover { color: var(--text); }

.hero {
  position: relative; min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  text-align: center; padding: 120px 24px 80px;
}
.hero-bg {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at 50% 0%, rgba(141, 92, 255, 0.15) 0%, transparent 60%);
}
.hero-content { position: relative; max-width: 800px; }
.hero h1 { font-size: 56px; font-weight: 700; line-height: 1.1; margin-bottom: 20px; }
.gradient-text {
  background: var(--accent-gradient); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero-subtitle { font-size: 18px; color: var(--text-muted); margin-bottom: 40px; max-width: 600px; margin-left: auto; margin-right: auto; }
.hero-actions { display: flex; gap: 16px; justify-content: center; margin-bottom: 60px; }
.hero-cta { padding: 14px 36px; font-size: 16px; border-radius: 12px; }
.hero-stats { display: flex; gap: 48px; justify-content: center; }
.stat { text-align: center; }
.stat-value { display: block; font-size: 32px; font-weight: 700; color: var(--accent-strong); }
.stat-label { font-size: 13px; color: var(--text-muted); }

.features, .styles-section { padding: 80px 24px; }
.container { max-width: 1200px; margin: 0 auto; }
h2 { font-size: 32px; margin-bottom: 40px; text-align: center; }
.feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.feature-card { text-align: center; padding: 32px; }
.feature-icon {
  font-size: 28px; font-weight: 800; color: var(--accent-strong);
  margin-bottom: 16px;
}
.feature-card h3 { margin-bottom: 12px; }
.feature-card p { color: var(--text-muted); font-size: 14px; }

.style-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px; }
.style-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
  text-align: center; cursor: pointer; transition: transform 0.2s;
}
.style-card:hover { transform: translateY(-4px); }
.style-preview { height: 100px; }
.style-card span { display: block; padding: 12px; font-size: 13px; font-weight: 500; }

@media (max-width: 768px) {
  .hero h1 { font-size: 32px; }
  .feature-grid { grid-template-columns: 1fr; }
  .hero-stats { gap: 24px; }
}
</style>
