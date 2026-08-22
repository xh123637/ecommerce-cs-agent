<script setup>
import { onMounted, ref } from 'vue'
import client from '../api/client'

const stats = ref(null)
const evaluation = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await client.get('/stats')
    stats.value = data
    const evalData = await client.get('/stats/evaluation')
    evaluation.value = evalData.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-row v-if="stats" :gutter="16">
      <el-col :span="6">
        <el-card class="stat-card"><div class="num">{{ stats.total }}</div><div class="label">工单总数</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"><div class="num">{{ stats.resolved_count }}</div><div class="label">已解决</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="num">{{ stats.avg_resolve_seconds == null ? '-' : (stats.avg_resolve_seconds / 3600).toFixed(1) }}</div>
          <div class="label">平均解决时长（小时）</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card"><div class="num">{{ stats.avg_rating ?? '-' }}</div><div class="label">满意度均值（1-5）</div></el-card>
      </el-col>
    </el-row>

    <el-row v-if="evaluation" :gutter="16" class="charts">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="num">{{ evaluation.auto_solve_rate == null ? '-' : (evaluation.auto_solve_rate * 100).toFixed(1) + '%' }}</div>
          <div class="label">自动解决率</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="num">{{ evaluation.human_escalation_rate == null ? '-' : (evaluation.human_escalation_rate * 100).toFixed(1) + '%' }}</div>
          <div class="label">人工转接率</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="num">{{ evaluation.avg_llm_latency_ms == null ? '-' : evaluation.avg_llm_latency_ms + 'ms' }}</div>
          <div class="label">平均 LLM 延迟</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="num">{{ evaluation.total_processed }}</div>
          <div class="label">已处理工单</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="stats" :gutter="16" class="charts">
      <el-col :span="12">
        <el-card>
          <template #header>状态分布</template>
          <div v-for="(count, status) in stats.by_status" :key="status" class="bar-row">
            <span>{{ status }}</span>
            <el-progress :percentage="stats.total ? Math.round(count / stats.total * 100) : 0" />
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>分类分布</template>
          <div v-for="(count, category) in stats.by_category" :key="category" class="bar-row">
            <span>{{ category }}</span>
            <el-progress :percentage="stats.total ? Math.round(count / stats.total * 100) : 0" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="stats" :gutter="16" class="charts">
      <el-col :span="8">
        <el-card>
          <template #header>渠道分布</template>
          <el-tag v-for="(count, source) in stats.by_source" :key="source" class="tag-item">
            {{ source }} · {{ count }}
          </el-tag>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>语言分布</template>
          <el-tag v-for="(count, language) in stats.by_language" :key="language" class="tag-item" type="success">
            {{ language }} · {{ count }}
          </el-tag>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="num">{{ stats.rlhf_count }}</div>
          <div class="label">RLHF 反馈数据量</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stat-card {
  text-align: center;
}
.num {
  font-size: 28px;
  font-weight: 700;
}
.label {
  color: #909399;
  margin-top: 6px;
}
.charts {
  margin-top: 16px;
}
.bar-row {
  display: grid;
  grid-template-columns: 90px 1fr;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.tag-item {
  margin: 4px 6px 4px 0;
}
</style>
