export const AGENT_ROLES = ['staff', 'supervisor', 'admin']
export const SUPERVISOR_ROLES = ['supervisor', 'admin']

export function isAgent(role) {
  return AGENT_ROLES.includes(role)
}

export function isSupervisor(role) {
  return SUPERVISOR_ROLES.includes(role)
}

export function roleLabel(role) {
  return {
    customer: '客户',
    staff: '客服专员',
    supervisor: '客服主管',
    admin: '管理员',
  }[role] || role
}
