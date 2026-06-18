/**
 * 角色显示工具
 *
 * 消除 Settings.vue / AppHeader.vue / UserManagement.vue 中重复的
 * roleLabel / roleTagType 映射。
 */

const ROLE_LABEL_MAP: Record<string, string> = {
  admin: '管理员',
  ops: '运维',
  operator: '运营',
  viewer: '只读',
}

const ROLE_TAG_TYPE_MAP: Record<string, '' | 'success' | 'warning' | 'info' | 'danger'> = {
  admin: 'danger',
  ops: '',
  operator: 'success',
  viewer: 'info',
}

/** 角色英文标识 → 中文显示名。 */
export function roleLabel(role: string | undefined): string {
  return ROLE_LABEL_MAP[role || ''] || role || ''
}

/** 角色英文标识 → Element Plus tag type。 */
export function roleTagType(role: string | undefined): '' | 'success' | 'warning' | 'info' | 'danger' {
  return ROLE_TAG_TYPE_MAP[role || ''] || 'info'
}
