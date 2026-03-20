<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useLangStore } from '@/stores/lang'

const router = useRouter()
const auth = useAuthStore()
const { t } = useLangStore()
const isRegister = ref(false)
const form = ref({ username: '', email: '', password: '' })
const error = ref('')

async function submit() {
  error.value = ''
  try {
    if (isRegister.value) {
      await auth.register(form.value.username, form.value.email, form.value.password)
    } else {
      await auth.login(form.value.username, form.value.password)
    }
    router.push('/projects')
  } catch (e: any) {
    error.value = e.response?.data?.detail || t('loginError')
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <h2 class="gradient-text">{{ isRegister ? t('registerTitle') : t('loginTitle') }}</h2>
      <p class="login-subtitle">{{ isRegister ? t('registerSubtitle') : t('loginSubtitle') }}</p>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <div class="form-group">
        <input v-model="form.username" :placeholder="t('username')" />
      </div>
      <div v-if="isRegister" class="form-group">
        <input v-model="form.email" type="email" :placeholder="t('email')" />
      </div>
      <div class="form-group">
        <input v-model="form.password" type="password" :placeholder="t('password')" @keyup.enter="submit" />
      </div>

      <button class="btn-primary full-width" @click="submit">
        {{ isRegister ? t('registerBtn') : t('loginBtn') }}
      </button>

      <p class="toggle-text">
        {{ isRegister ? t('toLogin') : t('toRegister') }}
        <a href="#" @click.prevent="isRegister = !isRegister">
          {{ isRegister ? t('loginBtn') : t('registerBtn') }}
        </a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: radial-gradient(ellipse at 50% 30%, rgba(141, 92, 255, 0.1) 0%, transparent 50%);
}
.login-card { width: 400px; padding: 40px; text-align: center; }
.login-card h2 {
  font-size: 28px; margin-bottom: 8px;
  background: var(--accent-gradient); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.login-subtitle { color: var(--text-muted); margin-bottom: 32px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
.form-group input {
  width: 100%; padding: 12px 16px;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text);
  font-size: 14px; outline: none;
}
.form-group input:focus { border-color: var(--accent-strong); }
.full-width { width: 100%; padding: 12px; font-size: 15px; margin-bottom: 16px; }
.toggle-text { font-size: 13px; color: var(--text-muted); }
.error-msg {
  background: rgba(248, 113, 113, 0.1); color: var(--error);
  padding: 10px; border-radius: var(--radius-sm); margin-bottom: 16px; font-size: 13px;
}
</style>
