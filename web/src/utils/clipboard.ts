/**
 * 剪贴板工具
 *
 * 消除 HostSearch.vue 中多处重复的复制逻辑。
 */

import { ElMessage } from 'element-plus'

/** 将文本写入剪贴板，并显示成功提示。 */
export async function copyToClipboard(text: string, label = '内容'): Promise<boolean> {
  if (!text) {
    ElMessage.warning('没有可复制的内容')
    return false
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(`${label} 已复制到剪贴板`)
    return true
  } catch {
    // fallback：创建临时 textarea
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      ElMessage.success(`${label} 已复制到剪贴板`)
      return true
    } catch {
      ElMessage.error('复制失败，请手动复制')
      return false
    } finally {
      document.body.removeChild(ta)
    }
  }
}
