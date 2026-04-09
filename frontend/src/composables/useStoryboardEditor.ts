/**
 * useStoryboardEditor
 *
 * Manages the storyboard list and inline-editing of individual segments.
 * Extracted from Create/index.vue to keep the view slim and make the
 * editing logic independently testable/reusable.
 */

import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

export interface StoryboardSegment {
  label: 'sing' | 'story'
  description: string
  video_prompt?: string
  [key: string]: unknown
}

export function useStoryboardEditor(
  projectId: Ref<number | null>,
  saveErrorMsg: string,
) {
  const storyboard = ref<StoryboardSegment[]>([])
  const editingSegIdx = ref<number | null>(null)
  const editingSegData = ref<StoryboardSegment | null>(null)
  const savingStoryboard = ref(false)

  function startEditSeg(i: number) {
    editingSegIdx.value = i
    // Shallow clone so edits don't mutate the source array until saved
    editingSegData.value = { ...storyboard.value[i] }
  }

  function cancelEditSeg() {
    editingSegIdx.value = null
    editingSegData.value = null
  }

  async function saveEditSeg() {
    if (editingSegIdx.value === null || !editingSegData.value || !projectId.value) return

    const updated = [...storyboard.value]
    updated[editingSegIdx.value] = {
      ...storyboard.value[editingSegIdx.value],
      ...editingSegData.value,
    }

    savingStoryboard.value = true
    try {
      await api.put(`/projects/${projectId.value}`, { storyboard: updated })
      storyboard.value = updated
      editingSegIdx.value = null
      editingSegData.value = null
    } catch {
      ElMessage.error(saveErrorMsg)
    } finally {
      savingStoryboard.value = false
    }
  }

  return {
    storyboard,
    editingSegIdx,
    editingSegData,
    savingStoryboard,
    startEditSeg,
    cancelEditSeg,
    saveEditSeg,
  }
}
