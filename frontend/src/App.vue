<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useNotificationsStore } from './stores/notifications'
import { isAgent, roleLabel } from './utils/permissions'

const auth = useAuthStore()
const notifications = useNotificationsStore()
const route = useRoute()
const router = useRouter()

const showLayout = computed(() => route.name !== 'login')
const isWorker = computed(() => isAgent(auth.user?.role))

onMounted(() => notifications.refresh())

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <router-view v-if="!showLayout" />
  <el-container v-else class="app-shell">
    <el-aside width="220px">
      <div class="brand">电商客服工单</div>
      <el-menu router :default-active="route.path" background-color="#001529" text-color="#fff" active-text-color="#ffd04b">
        <el-menu-item v-if="isWorker" index="/workbench">
          <el-icon><Monitor /></el-icon>
          <span>客服工作台</span>
        </el-menu-item>
        <el-menu-item index="/notifications">
          <el-icon><Bell /></el-icon>
          <span>通知</span>
          <el-badge v-if="notifications.unread" :value="notifications.unread" class="menu-badge" />
        </el-menu-item>
        <el-menu-item index="/tickets">
          <el-icon><Tickets /></el-icon>
          <span>工单列表</span>
        </el-menu-item>
        <el-menu-item index="/tickets/new">
          <el-icon><Plus /></el-icon>
          <span>新建工单</span>
        </el-menu-item>
        <el-menu-item v-if="isWorker" index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>统计看板</span>
        </el-menu-item>
        <el-menu-item v-if="isWorker" index="/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div />
        <div class="user-box">
          <el-tag v-if="auth.user" type="info">{{ auth.user.display_name }} · {{ roleLabel(auth.user.role) }}</el-tag>
          <el-button link type="primary" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  height: 100%;
}
.brand {
  height: 60px;
  line-height: 60px;
  color: #fff;
  font-weight: 700;
  text-align: center;
  background: #001529;
}
.el-aside {
  background: #001529;
}
.el-aside .el-menu {
  border-right: none;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.user-box {
  display: flex;
  align-items: center;
  gap: 10px;
}
.menu-badge {
  margin-left: auto;
}
</style>
