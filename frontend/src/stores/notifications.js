import { ref } from 'vue'
import { defineStore } from 'pinia'
import client from '../api/client'

export const useNotificationsStore = defineStore('notifications', () => {
  const unread = ref(0)

  async function refresh() {
    try {
      const { data } = await client.get('/notifications/unread-count')
      unread.value = data.count
    } catch {
      unread.value = 0
    }
  }

  return { unread, refresh }
})
