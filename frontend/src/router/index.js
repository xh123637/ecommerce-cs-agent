import { createRouter, createWebHistory } from 'vue-router'
import { isAgent } from '../utils/permissions'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
    { path: '/', redirect: '/tickets' },
    { path: '/workbench', name: 'workbench', component: () => import('../views/Workbench.vue'), meta: { agentOnly: true } },
    { path: '/dashboard', name: 'dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/notifications', name: 'notifications', component: () => import('../views/Notifications.vue') },
    { path: '/tickets', name: 'tickets', component: () => import('../views/TicketList.vue') },
    { path: '/tickets/new', name: 'ticket-new', component: () => import('../views/TicketCreate.vue') },
    { path: '/tickets/:id', name: 'ticket-detail', component: () => import('../views/TicketDetail.vue') },
    { path: '/knowledge', name: 'knowledge', component: () => import('../views/Knowledge.vue') },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.name !== 'login' && !token) {
    return { name: 'login' }
  }
  if (to.name === 'login' && token) {
    return { name: 'tickets' }
  }
  if (to.meta?.agentOnly) {
    const stored = JSON.parse(localStorage.getItem('user') || 'null')
    if (!isAgent(stored?.role)) {
      return { name: 'tickets' }
    }
  }
  return true
})

export default router
