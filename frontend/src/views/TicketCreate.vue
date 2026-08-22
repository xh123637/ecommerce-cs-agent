<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const router = useRouter()
const loading = ref(false)
const form = reactive({
  title: '',
  description: '',
  category: '其他',
  shipper_code: '',
  tracking_no: '',
  priority: '中',
  language: 'zh',
})

const isLogistics = () => form.category === '物流'

async function submit() {
  if (!form.title || !form.description) {
    ElMessage.warning('请填写标题和描述')
    return
  }
  loading.value = true
  try {
    const { data } = await client.post('/tickets', form)
    ElMessage.success('工单已创建')
    router.push(`/tickets/${data.id}`)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-card">
    <el-page-header content="新建工单" @back="router.push('/tickets')" />
    <el-form class="form" label-width="80px">
      <el-form-item label="标题">
        <el-input v-model="form.title" placeholder="简要描述问题" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="6" placeholder="详细描述，可包含订单号等信息" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="form.category">
          <el-option label="退换货" value="退换货" />
          <el-option label="技术咨询" value="技术咨询" />
          <el-option label="投诉" value="投诉" />
          <el-option label="物流" value="物流" />
          <el-option label="账户问题" value="账户问题" />
          <el-option label="其他" value="其他" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="isLogistics()" label="快递公司">
        <el-select v-model="form.shipper_code">
          <el-option label="顺丰" value="SF" />
          <el-option label="中通" value="ZTO" />
          <el-option label="圆通" value="YTO" />
          <el-option label="韵达" value="YD" />
          <el-option label="申通" value="STO" />
         <el-option label="极兔" value="JTSD" />
         <el-option label="京东" value="JD" />
         <el-option label="邮政/EMS" value="YZPY" />
          <el-option label="顺丰" value="shunfeng" />
          <el-option label="中通" value="zhongtong" />
          <el-option label="圆通" value="yuantong" />
          <el-option label="韵达" value="yunda" />
          <el-option label="申通" value="shentong" />
          <el-option label="极兔" value="jtexpress" />
          <el-option label="京东" value="jd" />
          <el-option label="邮政/EMS" value="youzhengguonei" />
          <el-option label="EMS" value="ems" />
          <el-option label="其他" value="" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="isLogistics()" label="快递单号">
        <el-input v-model="form.tracking_no" placeholder="填写真实运单号，可查物流轨迹" />
      </el-form-item>
      <el-form-item label="优先级">
        <el-radio-group v-model="form.priority">
          <el-radio value="高">高</el-radio>
          <el-radio value="中">中</el-radio>
          <el-radio value="低">低</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="语言">
        <el-select v-model="form.language">
          <el-option label="中文" value="zh" />
          <el-option label="English" value="en" />
          <el-option label="日本語" value="ja" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">创建</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.form {
  margin-top: 24px;
  max-width: 720px;
}
</style>
