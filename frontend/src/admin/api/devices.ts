import type { DeviceListPayload, KickResult } from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function listDevices(codeId: number): Promise<DeviceListPayload> {
  return admin(`/admin/codes/${codeId}/devices`)
}

export function kickDevice(deviceId: number): Promise<KickResult> {
  assertWritable()
  return admin(`/admin/devices/${deviceId}/kick`, { method: 'POST' })
}

export function unbindDevice(deviceId: number): Promise<KickResult> {
  assertWritable()
  return admin(`/admin/devices/${deviceId}/unbind`, { method: 'POST' })
}
