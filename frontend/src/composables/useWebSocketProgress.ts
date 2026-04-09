/**
 * useWebSocketProgress
 *
 * Encapsulates the WebSocket connection to /ws/projects/{id}/progress.
 * Handles auth handshake, message dispatch, and exponential reconnect.
 *
 * Used by Create view and Canvas view so both share the same reliable logic.
 */

import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'

export interface ProgressState {
  image: string
  music: string
  video: string
  compose: string
  [key: string]: string
}

export interface VideoProgress {
  segment: number
  total: number
  pct: number
}

export interface WsProgressOptions {
  /** Called when pipeline completes. Receives the final video URL if provided. */
  onPipelineComplete?: (fileUrl?: string) => void
  /** i18n strings needed for toast messages. */
  messages: {
    generationComplete: string
    connectionLost: string
  }
}

const WS_MAX_RETRIES = 5
const WS_BASE_DELAY_MS = 3000
const WS_MAX_DELAY_MS = 30_000

export function useWebSocketProgress(
  projectId: Ref<number | null>,
  opts: WsProgressOptions,
) {
  const progress = ref<ProgressState>({
    image: 'pending',
    music: 'pending',
    video: 'pending',
    compose: 'pending',
  })
  const videoProgress = ref<VideoProgress>({ segment: 0, total: 0, pct: 0 })
  const generating = ref(false)

  let ws: WebSocket | null = null
  let retryCount = 0
  let destroyed = false

  function connect() {
    const id = projectId.value
    if (!id || destroyed) return

    const wsBase = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/^http/, 'ws')
    ws = new WebSocket(`${wsBase}/ws/projects/${id}/progress`)

    ws.onopen = () => {
      retryCount = 0
      const token = localStorage.getItem('token') || ''
      if (token) ws?.send(JSON.stringify({ type: 'auth', token }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const type: string = data.type || ''
        const status: string = data.status || ''

        // Update named stage status
        if (type in progress.value) {
          progress.value[type] = status
        }

        // Video segment progress
        if (type === 'video' && data.pct !== undefined) {
          videoProgress.value = {
            segment: data.segment ?? 0,
            total: data.total ?? 0,
            pct: data.pct,
          }
        }

        // Compose done → expose file URL
        if (type === 'compose' && status === 'completed' && data.file_url) {
          opts.onPipelineComplete?.(data.file_url)
        }

        // Full pipeline completion signal
        if (type === 'pipeline' && status === 'completed') {
          generating.value = false
          videoProgress.value = { segment: 0, total: 0, pct: 100 }
          ElMessage.success(opts.messages.generationComplete)
          opts.onPipelineComplete?.(data.file_url)
        }
      } catch {
        /* malformed message — ignore */
      }
    }

    ws.onclose = () => {
      if (destroyed) return
      // Only reconnect while a generation is in progress
      if (generating.value && retryCount < WS_MAX_RETRIES) {
        retryCount++
        const delay = Math.min(WS_BASE_DELAY_MS * retryCount, WS_MAX_DELAY_MS)
        setTimeout(() => connect(), delay)
      } else if (retryCount >= WS_MAX_RETRIES) {
        generating.value = false
        ElMessage.error(opts.messages.connectionLost)
      }
    }
  }

  /** Reconnect if the socket is not open. */
  function ensureConnected() {
    if (!ws || ws.readyState !== WebSocket.OPEN) connect()
  }

  /** Close the socket and stop any pending reconnects. */
  function disconnect() {
    destroyed = true
    ws?.close()
    ws = null
  }

  /** Reset progress to initial state (call before starting a new pipeline run). */
  function resetProgress() {
    progress.value = { image: 'pending', music: 'pending', video: 'pending', compose: 'pending' }
    videoProgress.value = { segment: 0, total: 0, pct: 0 }
  }

  return {
    progress,
    videoProgress,
    generating,
    connect,
    disconnect,
    ensureConnected,
    resetProgress,
  }
}
