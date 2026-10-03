import type { AdminStatusPayload, RefreshResult } from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function status(): Promise<AdminStatusPayload> {
  return admin('/admin/status')
}

export function refreshCache(wait = false): Promise<RefreshResult> {
  assertWritable()
  return admin('/admin/cache/refresh', { method: 'POST', query: { wait: wait ? 'true' : undefined } })
}
