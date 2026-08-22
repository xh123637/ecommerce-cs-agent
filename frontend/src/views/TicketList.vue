<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import client from '../api/client'

const router = useRouter()
const tickets = ref([])
const loading = ref(false)
const filters = ref({ status: '', category: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await client.get('/tickets', { params: filters.value })
    tickets.value = data
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="load">
        <el-option label="待处理" value="待处理" />
        <el-option label="处理中" value="处理中" />
        <el-option label="已解决" value="已解决" />
        <el-option label="待人工审核" value="待人工审核" />
      </el-select>
      <el-select v-model="filters.category" placeholder="分类" clearable style="width: 150px" @change="load">
        <el-option label="退换货" value="退换货" />
        <el-option label="技术咨询" value="技术咨询" />
        <el-option label="投诉" value="投诉" />
        <el-option label="物流" value="物流" />
        <el-option label="账户问题" value="账户问题" />
        <el-option label="其他" value="其他" />
      </el-select>
      <el-button type="primary" @click="router.push('/tickets/new')">新建工单</el-button>
    </div>
    <el-table v-loading="loading" :data="tickets" stripe>
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="title" label="标题" min-width="220" />
      <el-table-column prop="category" label="分类" width="110" />
      <el-table-column prop="priority" label="优先级" width="90" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="customer_name" label="客户" width="110" />
      <el-table-column label="创建人" width="140">
        <template #default="{ row }">
          <span>{{ row.created_by_name || '-' }}</span>
          <el-tag v-if="row.assisted" type="warning" size="small" style="margin-left: 4px">代录</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/tickets/${row.id}`)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
