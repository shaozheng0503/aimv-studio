import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/Home/index.vue'),
    },
    {
      path: '/create/:id?',
      redirect: (to) => {
        const id = to.params.id
        return id ? `/canvas/${id}` : '/projects'
      },
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('@/views/Project/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/editor/:id',
      name: 'editor',
      component: () => import('@/views/Editor/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/canvas/:id?',
      name: 'canvas',
      component: () => import('@/views/Canvas/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/gallery',
      name: 'gallery',
      component: () => import('@/views/Gallery/index.vue'),
    },
    {
      path: '/studio/:id?',
      name: 'studio',
      component: () => import('@/views/Studio/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/User/Login.vue'),
    },
  ],
})

const pageTitles: Record<string, string> = {
  home: 'AIMV Studio',
  create: 'Create — AIMV Studio',
  projects: 'My Projects — AIMV Studio',
  canvas: 'Canvas — AIMV Studio',
  editor: 'Editor — AIMV Studio',
  gallery: 'Gallery — AIMV Studio',
  login: 'Sign In — AIMV Studio',
  studio: 'Simple Studio — AIMV Studio',
}

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('token')) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

router.afterEach((to) => {
  document.title = pageTitles[to.name as string] ?? 'AIMV Studio'
})

export default router
