<template>
  <div class="skeleton-card">
    <div class="skeleton-thumb shimmer" />
    <div class="skeleton-body">
      <div class="skeleton-line shimmer" style="width: 70%" />
      <div class="skeleton-line shimmer short" style="width: 40%" />
    </div>
  </div>
</template>

<style scoped>
.skeleton-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
}
.skeleton-thumb { aspect-ratio: 16/9; background: var(--bg-soft); }
.skeleton-body { padding: 14px 16px; }
.skeleton-line { height: 14px; border-radius: 4px; background: var(--bg-soft); margin-bottom: 8px; }
.skeleton-line.short { height: 10px; }
.shimmer {
  background: linear-gradient(90deg, var(--bg-soft) 25%, rgba(255,255,255,0.04) 50%, var(--bg-soft) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
</style>
