<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useNotificationsStore } from '../stores/notifications'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const notifications = useNotificationsStore()
const auth = useAuthStore()
const items = ref([])
const loading = ref(false)
const isCustomer = computed(() => auth.user?.role === 'customer')

async function load() {
  loading.value = true
  try {
    const { data } = await client.get('/notifications')
    items.value = data
  } finally {
    loading.value = false
  }
}

async function readAll() {
  loading.value = true
  try {
    await client.post('/notifications/read-all')
    await notifications.refresh()
    ElMessage.success('已全部标记为已读')
  } finally {
    loading.value = false
  }
  load()
}

async function read(item) {
  if (!item.is_read) {
    await client.post(`/notifications/${item.id}/read`)
    item.is_read = true
    notifications.refresh()
  }
  if (item.ticket_id) {
    router.push(`/tickets/${item.ticket_id}`)
  }
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <h3>{{ isCustomer ? '我的通知' : '站内通知' }}</h3>
      <el-button type="primary" plain @click="readAll">全部已读</el-button>
    </div>
    <el-empty
      v-if="!items.length && !loading"
      :description="isCustomer ? '暂无通知，有新进展我们会提醒您' : '暂无通知'"
    />
    <el-timeline v-else v-loading="loading">
      <el-timeline-item
        v-for="item in items"
        :key="item.id"
        :type="item.is_read ? 'info' : 'primary'"
        :hollow="item.is_read"
      >
        <div class="notice" @click="read(item)">
          <b>{{ item.title }}</b>
          <span>{{ item.content }}</span>
          <small>{{ item.created_at }}</small>
        </div>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.notice {
  display: grid;
  gap: 4px;
  cursor: pointer;
}
.notice small {
  color: #909399;
}
</style>
