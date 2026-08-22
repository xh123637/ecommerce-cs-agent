<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'
import { isAgent, isSupervisor } from '../utils/permissions'

const route = useRoute()
const auth = useAuthStore()
const ticket = ref(null)
const logs = ref([])
const processing = ref(false)
const reply = ref('')
const needsHuman = ref(false)
const isWorker = computed(() => isAgent(auth.user?.role))
const canAssign = computed(() => isSupervisor(auth.user?.role))
const canViewConversation = computed(() => {
  if (!ticket.value) return false
  if (!isWorker.value) return true
  if (isSupervisor(auth.user?.role)) return true
  return ticket.value.status === '待人工审核' || ticket.value.assigned_to === auth.user.id
})
const isLogisticsTicket = computed(() =>
  Boolean(
    ticket.value &&
      (ticket.value.category === '物流' ||
        ticket.value.shipper_code ||
        ticket.value.tracking_no)
  )
)
const feedbacks = ref([])
const feedbackForm = ref({ rating: 5, comment: '' })
const updateForm = ref({ status: '待处理', resolution: '' })
const rlhfRecords = ref([])
const rlhfForm = ref({ label: 'good', rating: 5, human_reply: '', comment: '' })
const related = ref([])
const attachments = ref([])
const staffOptions = ref([])
const conversation = ref(null)
const messages = ref([])
const chatInput = ref('')
const sending = ref(false)
const chatLoading = ref(false)
const logistics = ref(null)
const trackingLoading = ref(false)

async function loadStaff() {
  if (!canAssign.value) return
  const { data } = await client.get('/staff')
  staffOptions.value = data
}

async function assignTo(id) {
  await client.post(`/tickets/${route.params.id}/assign`, null, {
    params: { assignee_id: id },
  })
  ElMessage.success('已分配')
  await load()
  await loadConversation()
}

async function claim() {
  await assignTo(auth.user.id)
  ElMessage.success('已领取')
}

async function load() {
  const { data } = await client.get(`/tickets/${route.params.id}`)
  ticket.value = data
}

async function loadLogs() {
  const { data } = await client.get(`/tickets/${route.params.id}/logs`)
  logs.value = data
}

async function loadFeedback() {
  const { data } = await client.get(`/tickets/${route.params.id}/feedback`)
  feedbacks.value = data
}

async function loadRlhf() {
  const { data } = await client.get('/rlhf', { params: { ticket_id: route.params.id } })
  rlhfRecords.value = data
}

async function loadRelated() {
  const { data } = await client.get(`/tickets/${route.params.id}/related`)
  related.value = data
}

async function loadAttachments() {
  const { data } = await client.get(`/tickets/${route.params.id}/attachments`)
  attachments.value = data
}

async function loadConversation() {
  if (!canViewConversation.value) return
  chatLoading.value = true
  try {
    const { data } = await client.get(`/agent/tickets/${route.params.id}/conversation`)
    conversation.value = data.conversation
    messages.value = data.messages
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '加载对话失败')
  } finally {
    chatLoading.value = false
  }
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || sending.value) return
  sending.value = true
  try {
    const { data } = await client.post(`/agent/tickets/${route.params.id}/conversation/chat`, {
      question: text,
    })
    chatInput.value = ''
    messages.value = data.messages
    if (data.compactions > 0) {
      ElMessage.info(`上下文已自动压缩 ${data.compactions} 次`)
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '发送失败')
  } finally {
    sending.value = false
  }
}

async function trackExpress() {
  trackingLoading.value = true
  try {
    const { data } = await client.post('/logistics/track', {
      ticket_id: route.params.id,
    })
    logistics.value = data
  } catch (err) {
    logistics.value = { error: err.response?.data?.detail || '查询失败' }
  } finally {
    trackingLoading.value = false
  }
}

async function uploadAttachment(options) {
  const form = new FormData()
  form.append('file', options.file)
  await client.post(`/tickets/${route.params.id}/attachments`, form)
  ElMessage.success('上传成功')
  loadAttachments()
}

async function submitFeedback() {
  await client.post(`/tickets/${route.params.id}/feedback`, feedbackForm.value)
  ElMessage.success('感谢您的评价')
  feedbackForm.value = { rating: 5, comment: '' }
  loadFeedback()
}

async function updateTicket() {
  const payload = {}
  if (updateForm.value.status) payload.status = updateForm.value.status
  if (updateForm.value.resolution) payload.resolution = updateForm.value.resolution
  const { data } = await client.patch(`/tickets/${route.params.id}`, payload)
  ticket.value = data
  ElMessage.success('工单已更新')
}

async function submitRlhf() {
  await client.post('/rlhf', {
    ticket_id: route.params.id,
    ai_reply: reply.value || ticket.value.resolution || '',
    human_reply: rlhfForm.value.human_reply,
    label: rlhfForm.value.label,
    rating: rlhfForm.value.rating,
    comment: rlhfForm.value.comment,
  })
  ElMessage.success('RLHF 反馈已保存')
  rlhfForm.value = { label: 'good', rating: 5, human_reply: '', comment: '' }
  loadRlhf()
}

async function process() {
  processing.value = true
  try {
    const { data } = await client.post(`/tickets/${route.params.id}/process`)
    ticket.value = data.ticket
    reply.value = data.reply
    needsHuman.value = data.needs_human
    logs.value = data.logs
    ElMessage.success('AI 处理完成')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '处理失败')
  } finally {
    processing.value = false
  }
}

async function confirmResolution(solved) {
  await client.post(`/tickets/${route.params.id}/resolution`, { solved })
  ElMessage.success(solved ? '已确认解决' : '已反馈，客服将继续跟进')
  load()
}

async function transferHuman() {
  await client.post(`/agent/tickets/${route.params.id}/human`)
  ElMessage.success('已转人工，请稍候')
  await load()
  await loadConversation()
}

onMounted(async () => {
  loadLogs()
  loadFeedback()
  loadRlhf()
  loadRelated()
  loadAttachments()
  loadStaff()
  await load()
  loadConversation()
})
</script>

<template>
  <div v-if="ticket" class="detail-wrap">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span>{{ ticket.id }} · {{ ticket.title }}</span>
          <el-tag :type="ticket.status === '已解决' ? 'success' : ticket.status === '待人工审核' || ticket.status === '待客户确认' ? 'warning' : 'info'">
            {{ ticket.status }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="分类">{{ ticket.category }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ ticket.priority }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ ticket.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ ticket.created_at }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ ticket.assigned_name || '未分配' }}</el-descriptions-item>
        <el-descriptions-item v-if="isLogisticsTicket" label="快递公司">{{ ticket.shipper_code || '未填写' }}</el-descriptions-item>
        <el-descriptions-item v-if="isLogisticsTicket" label="快递单号">{{ ticket.tracking_no || '未填写' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ ticket.source }}</el-descriptions-item>
        <el-descriptions-item label="语言">{{ ticket.language }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ ticket.description }}</el-descriptions-item>
        <el-descriptions-item v-if="ticket.resolution" label="解决方案" :span="2">{{ ticket.resolution }}</el-descriptions-item>
      </el-descriptions>
      <el-button v-if="isWorker" class="process-btn" type="primary" :loading="processing" @click="process">
        AI 处理工单
      </el-button>
    </el-card>

    <el-card v-if="isWorker" class="page-card">
      <template #header>工单指派</template>
      <div class="assign-row">
        <span v-if="ticket.assigned_to">
          当前处理人：{{ ticket.assigned_name }}
        </span>
        <span v-else>尚未指派</span>
        <el-button v-if="ticket.assigned_to !== auth.user.id" type="primary" plain @click="claim">
          领取到我的队列
        </el-button>
        <el-select
          v-if="canAssign"
          :model-value="ticket.assigned_to"
          placeholder="分配给客服"
          style="width: 160px"
          @change="assignTo"
        >
          <el-option v-for="s in staffOptions" :key="s.id" :label="s.display_name" :value="s.id" />
        </el-select>
      </div>
    </el-card>

    <el-card v-if="reply || needsHuman" class="page-card">
      <template #header>AI 处理结果</template>
      <el-alert
        :title="needsHuman ? '需要人工介入' : '自动回复已生成'"
        :type="needsHuman ? 'warning' : 'success'"
        :closable="false"
      />
      <p class="reply-text">{{ reply }}</p>
    </el-card>

    <el-card v-if="related.length" class="page-card">
      <template #header>相似工单 / 知识库</template>
      <el-table :data="related" size="small">
        <el-table-column prop="id" label="ID" width="120" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="score" label="相关度" width="90" />
        <el-table-column prop="resolution" label="解决方案" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!isWorker && ticket.status === '待客户确认' && ticket.resolution" class="page-card">
      <template #header>确认处理结果</template>
      <p class="confirm-text">AI 已为您生成处理方案，请确认是否已解决您的问题。</p>
      <div class="confirm-row">
        <el-button type="success" @click="confirmResolution(true)">已解决</el-button>
        <el-button type="warning" @click="confirmResolution(false)">还没解决</el-button>
      </div>
    </el-card>

    <el-card v-if="canViewConversation" class="page-card">
      <template #header>工单对话</template>
      <div v-loading="chatLoading" class="chat-box">
        <div v-if="!messages.length" class="chat-empty">
         暂无消息，输入内容开始与客服对话。
        {{ isWorker ? '暂无消息，已和客户建立对话通道。' : '暂无消息，输入内容开始与客服对话。' }}
        </div>
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-msg"
          :class="msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-assistant'"
        >
          <div class="chat-bubble">
            <div class="chat-bubble-head">
        <b>{{ msg.role === 'user' ? (isWorker ? '客户' : '我') : msg.role === 'human' ? (isWorker ? '我' : '客服') : '客服助手' }}</b>
              <span class="chat-time">{{ msg.created_at }}</span>
            </div>
            <div class="chat-bubble-text">{{ msg.content }}</div>
            <div v-if="msg.tools_called && msg.tools_called.length" class="chat-tools">
              调用了工具：{{ msg.tools_called.join('、') }}
            </div>
          </div>
        </div>
      </div>
      <div class="chat-input-row">
        <el-input
          v-model="chatInput"
          type="textarea"
          :rows="2"
          :placeholder="isWorker ? '输入内容回复客户...' : '输入消息...'"
          @keydown.enter.exact.prevent="sendChat"
        />
        <el-button type="primary" :loading="sending" @click="sendChat">发送</el-button>
        <el-button
          v-if="!isWorker && ticket.status !== '待人工审核'"
          type="warning"
          plain
          @click="transferHuman"
        >
          转人工
        </el-button>
      </div>
    </el-card>

    <el-card v-if="isLogisticsTicket" class="page-card">
      <template #header>物流轨迹</template>
      <div class="logi-row">
        <el-button type="primary" :loading="trackingLoading" @click="trackExpress">
          查询物流
        </el-button>
        <span class="logi-hint">从工单描述中识别快递单号</span>
      </div>
      <el-alert
        v-if="logistics?.error"
        type="info"
        :title="logistics.error"
        :closable="false"
      />
      <el-timeline v-else-if="logistics?.Traces?.length">
        <el-timeline-item
          v-for="(item, idx) in logistics.Traces"
          :key="idx"
          :timestamp="item.AcceptTime"
        >
          {{ item.AcceptStation }}
        </el-timeline-item>
      </el-timeline>
      <el-alert
        v-else-if="logistics"
        type="info"
        :title="logistics.message || logistics.status || '暂无轨迹'"
        :closable="false"
      />
    </el-card>

    <el-card class="page-card">
      <template #header>附件</template>
      <el-upload :http-request="uploadAttachment" :show-file-list="false">
        <el-button type="primary" plain>上传附件</el-button>
      </el-upload>
      <el-table v-if="attachments.length" :data="attachments" size="small" class="attachment-table">
        <el-table-column prop="filename" label="文件名" min-width="180" />
        <el-table-column prop="size" label="大小" width="120" />
        <el-table-column prop="created_at" label="上传时间" width="170" />
      </el-table>
    </el-card>

    <el-card v-if="isWorker" class="page-card">
      <template #header>人工审核 / 更新工单</template>
      <el-form label-width="80px">
        <el-form-item label="状态">
          <el-select v-model="updateForm.status">
          <el-option label="待处理" value="待处理" />
          <el-option label="处理中" value="处理中" />
          <el-option label="待客户确认" value="待客户确认" />
          <el-option label="已解决" value="已解决" />
            <el-option label="待人工审核" value="待人工审核" />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方案">
          <el-input v-model="updateForm.resolution" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="updateTicket">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="isWorker" class="page-card">
      <template #header>RLHF 数据收集</template>
      <el-form label-width="90px">
        <el-form-item label="AI 回复">
          <el-input :model-value="reply || ticket.resolution || ''" type="textarea" :rows="3" disabled />
        </el-form-item>
        <el-form-item label="人工修正">
          <el-input v-model="rlhfForm.human_reply" type="textarea" :rows="3" placeholder="填写修正后的回复" />
        </el-form-item>
        <el-form-item label="质量标签">
          <el-radio-group v-model="rlhfForm.label">
            <el-radio value="good">采纳</el-radio>
            <el-radio value="bad">修正</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="评分">
          <el-rate v-model="rlhfForm.rating" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="rlhfForm.comment" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitRlhf">保存反馈</el-button>
        </el-form-item>
      </el-form>
      <el-divider v-if="rlhfRecords.length" />
      <div v-for="record in rlhfRecords" :key="record.id" class="rlhf-item">
        <b>{{ record.label }} · {{ record.rating }} 分</b>
        <div>修正：{{ record.human_reply }}</div>
      </div>
    </el-card>

    <el-card v-if="!isStaff" class="page-card">
      <template #header>满意度评价</template>
      <el-rate v-model="feedbackForm.rating" />
      <el-input v-model="feedbackForm.comment" class="feedback-input" placeholder="补充意见（可选）" />
      <el-button type="primary" class="feedback-btn" @click="submitFeedback">提交评价</el-button>
      <el-divider v-if="feedbacks.length" />
      <div v-for="item in feedbacks" :key="item.id" class="feedback-item">
        <el-rate :model-value="item.rating" disabled />
        <span>{{ item.comment }}</span>
      </div>
    </el-card>

    <el-card class="page-card">
      <template #header>Agent 执行日志</template>
      <el-timeline>
        <el-timeline-item
          v-for="log in logs"
          :key="log.created_at + log.step"
          :timestamp="log.created_at"
          :type="log.step.includes('失败') ? 'danger' : 'primary'"
        >
          <b>{{ log.step }}</b>
          <div>{{ log.input }}</div>
          <div class="log-output">{{ log.output }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<style scoped>
.detail-wrap {
  display: grid;
  gap: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.process-btn {
  margin-top: 16px;
}
.assign-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.reply-text {
  white-space: pre-wrap;
  line-height: 1.7;
}
.log-output {
  color: #606266;
  font-size: 13px;
}
.feedback-input {
  margin-top: 12px;
}
.feedback-btn {
  margin-top: 12px;
}
.feedback-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.rlhf-item {
  border-bottom: 1px solid #f0f0f0;
  padding: 8px 0;
}
.chat-box {
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 2px;
}
.chat-empty {
  color: #909399;
  text-align: center;
  padding: 24px 0;
}
.chat-msg {
  display: flex;
}
.chat-msg-user {
  justify-content: flex-end;
}
.chat-msg-assistant {
  justify-content: flex-start;
}
.chat-bubble {
  max-width: 78%;
  background: #f4f4f5;
  border-radius: 8px;
  padding: 10px 12px;
}
.chat-msg-user .chat-bubble {
  background: #ecf5ff;
}
.chat-bubble-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
  font-size: 13px;
}
.chat-time {
  color: #909399;
  font-size: 12px;
}
.chat-bubble-text {
  white-space: pre-wrap;
  line-height: 1.6;
  word-break: break-word;
}
.chat-tools {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.logi-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.logi-hint {
  color: #909399;
  font-size: 13px;
}
.confirm-text {
  margin-bottom: 12px;
  color: #606266;
}
.confirm-row {
  display: flex;
  gap: 12px;
}
.chat-input-row {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  align-items: flex-end;
}
</style>
