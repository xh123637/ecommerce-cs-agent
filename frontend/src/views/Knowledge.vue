<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'

const docs = ref([])
const loading = ref(false)
const form = ref({ category: '退换货', title: '', content: '', tags: '' })
const dialogVisible = ref(false)
const editing = ref({ id: '', category: '', title: '', content: '', tags: '' })

async function load() {
  loading.value = true
  try {
    const { data } = await client.get('/knowledge')
    docs.value = data
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!form.value.title || !form.value.content) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  await client.post('/knowledge', form.value)
  ElMessage.success('已添加')
  form.value = { category: '退换货', title: '', content: '', tags: '' }
  load()
}

function openEdit(row) {
  editing.value = { ...row }
  dialogVisible.value = true
}

async function saveEdit() {
  const payload = {}
  if (editing.value.category) payload.category = editing.value.category
  if (editing.value.title) payload.title = editing.value.title
  if (editing.value.content) payload.content = editing.value.content
  if (editing.value.tags) payload.tags = editing.value.tags
  await client.patch(`/knowledge/${editing.value.id}`, payload)
  dialogVisible.value = false
  ElMessage.success('已更新')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除 ${row.id} 吗？`, '确认', { type: 'warning' })
  await client.delete(`/knowledge/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<template>
  <div class="page-card">
    <el-form label-width="70px" class="form">
      <el-form-item label="分类">
        <el-select v-model="form.category">
          <el-option label="退换货" value="退换货" />
          <el-option label="技术咨询" value="技术咨询" />
          <el-option label="投诉" value="投诉" />
          <el-option label="账户问题" value="账户问题" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔" /></el-form-item>
      <el-form-item><el-button type="primary" @click="submit">添加</el-button></el-form-item>
    </el-form>
    <el-table v-loading="loading" :data="docs">
      <el-table-column prop="id" label="ID" width="120" />
      <el-table-column prop="category" label="分类" width="110" />
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="tags" label="标签" min-width="140" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="编辑知识库文档" width="560px">
      <el-form label-width="60px">
        <el-form-item label="分类">
          <el-select v-model="editing.category">
            <el-option label="退换货" value="退换货" />
            <el-option label="技术咨询" value="技术咨询" />
            <el-option label="投诉" value="投诉" />
            <el-option label="账户问题" value="账户问题" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题"><el-input v-model="editing.title" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="editing.content" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="editing.tags" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form {
  max-width: 720px;
  margin-bottom: 20px;
}
</style>
