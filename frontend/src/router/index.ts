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
      name: 'create',
      component: () => import('@/views/Create/index.vue'),
      meta: { requiresAuth: true },
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
      path: '/gallery',
      name: 'gallery',
      component: () => import('@/views/Gallery/index.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/User/Login.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('token')) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

export default router
