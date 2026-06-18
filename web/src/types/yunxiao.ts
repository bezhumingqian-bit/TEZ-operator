/** 云霄平台 — 类型定义。 */

export interface HostMachineItem {
  asset_id: string
  ip?: string
  instance_family?: string
  device_type?: string
  zone?: string
  logical_zone?: string
  pool?: string
  sale_pool?: string
  module_label?: string
  cpu_available?: number
  cpu_total?: number
  mem_available?: number
  mem_total?: number
  gpu_available?: number
  gpu_total?: number
  disk_available?: number
  disk_total?: number
  local_disk_available?: number
  local_disk_total?: number
  is_empty_host?: string
  is_cdh?: string
  exclusive_owner?: string
  tags?: string
  machine_model?: string
  health_score?: number
  online_status?: string
  kernel_version?: string
  kernel_version_id?: string
  manufacturer_module?: string
  sale_pool_type?: string
  box_type?: string
  host_updated_at?: string
}

export interface InventoryItem {
  zone?: string
  instance_family?: string
  instance_type?: string
  status?: string
  pool?: string
  billing_type?: string
  inventory?: number
  inventory_threshold?: number
  safety_quota?: number
  cpu?: number
  gpu?: number
  storage_block?: number
  mem?: number
  device_type?: string
}

export interface YunxiaoQueryResponse {
  items: HostMachineItem[] | InventoryItem[]
  total: number
  mode: string
  snapshot_time?: string
}
