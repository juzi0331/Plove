import { request } from '@/api/http'
import type {
  SystemMaintenancePayload,
  SystemNoticePayload,
  SystemStatusPayload,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function getSystemNotice(): Promise<SystemNoticePayload> {
  return admin('/admin/system/notice')
}

export function updateSystemNotice(payload: SystemNoticePayload): Promise<SystemNoticePayload> {
  assertWritable()
  return admin('/admin/system/notice', {
    method: 'PUT',
    body: payload,
  })
}

export function getSystemMaintenance(): Promise<SystemMaintenancePayload> {
  return admin('/admin/system/maintenance')
}

export function updateSystemMaintenance(payload: SystemMaintenancePayload): Promise<SystemMaintenancePayload> {
  assertWritable()
  return admin('/admin/system/maintenance', {
    method: 'PUT',
    body: payload,
  })
}

export function getPublicSystemStatus(): Promise<SystemStatusPayload> {
  return request<SystemStatusPayload>('/system/status')
}
