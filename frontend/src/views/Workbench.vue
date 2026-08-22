<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'
import { isSupervisor } from '../utils/permissions'

const router = useRouter()
const auth = useAuthStore()
const canAssign = isSupervisor(auth.user?.role)

const active = ref('mine')
const summary = ref({ my_open: 0, unassigned: 0, human_review: 0, total_open: 0 })
const tickets = ref([])
const loading = ref(false)
const staff = ref([])

async function loadSummary() {
  const { data } = await client.get('/tickets/queue/summary')
  summary.value = data
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await client.get('/tickets/queue', { params: { scope: active.value } })
    tickets.value = data
  } finally {
    loading.value = false
  }
}

async function loadStaff() {
  if (!canAssign) return
  const { data } = await client.get('/staff')
  staff.value = data
}

function onTab(name) {
  active.value = name
  loadList()
}

async function claim(row) {
  await client.post(`/tickets/${row.id}/assign`, null, {
    params: { assignee_id: auth.user.id },
  })
  ElMessage.success('已领取到我的队列')
  loadSummary()
  loadList()
}

async function assign(row, id) {
  if (!id) return
  await client.post(`/tickets/${row.id}/assign`, null, {
    params: { assignee_id: id },
  })
  ElMessage.success('已分配')
  loadSummary()
  loadList()
}

function open(row) {
  router.push(`/tickets/${row.id}`)
}

onMounted(() => {
  loadSummary()
  loadList()
  loadStaff()
})
</script>

<template>
  <div class="wb-wrap">
    <div class="stat-grid">
      <div class="stat">
        <div class="stat-num">{{ summary.my_open }}</div>
        <div class="stat-label">我的工单</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ summary.unassigned }}</div>
        <div class="stat-label">待分配</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ summary.human_review }}</div>
        <div class="stat-label">待人工审核</div>
      </div>
      <div class="stat">
        <div class="stat-num">{{ summary.total_open }}</div>
        <div class="stat-label">全部进行中</div>
      </div>
    </div>

    <el-tabs v-model="active" class="queue-tabs" @tab-change="onTab">
      <el-tab-pane :label="`我的工单 (${summary.my_open})`" name="mine" />
      <el-tab-pane :label="`待分配 (${summary.unassigned})`" name="unassigned" />
      <el-tab-pane :label="`待人工审核 (${summary.human_review})`" name="review" />
      <el-tab-pane :label="`全部进行中 (${summary.total_open})`" name="all" />
    </el-tabs>

    <el-table v-loading="loading" :data="tickets" stripe>
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="customer_name" label="客户" width="100" />
      <el-table-column prop="assigned_name" label="处理人" width="100">
        <template #default="{ row }">{{ row.assigned_name || '未分配' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="165" />
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">查看</el-button>
          <el-button v-if="!row.assigned_to" link type="success" @click="claim(row)">领取</el-button>
          <el-select
            v-if="canAssign"
            :model-value="row.assigned_to"
            placeholder="分配"
            size="small"
            style="width: 90px"
            @change="(id) => assign(row, id)"
          >
            <el-option
              v-for="s in staff"
              :key="s.id"
              :label="s.display_name"
              :value="s.id"
            />
          </el-select>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.wb-wrap {
  display: grid;
  gap: 16px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.stat {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 14px 16px;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
}
.stat-label {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
</style>
