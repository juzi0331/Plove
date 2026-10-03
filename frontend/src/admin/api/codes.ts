import type {
  CodeActionResult,
  CodeCleanupResult,
  CodeListPayload,
  IssueCodesRequest,
  IssueCodesResult,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export interface CodeQuery {
  query?: string
  page?: number
  pageSize?: number
}

export function listCodes(input: CodeQuery = {}): Promise<CodeListPayload> {
  return admin('/admin/codes', {
    query: { query: input.query, page: input.page ?? 1, page_size: input.pageSize ?? 20 },
  })
}

export function issueCodes(payload: IssueCodesRequest): Promise<IssueCodesResult> {
  assertWritable()
  return admin('/admin/codes', { method: 'POST', body: payload })
}

/** 停用。立即生效：那台设备的下一次请求就会拿到 403。 */
export function disableCode(codeId: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/disable`, { method: 'POST' })
}

export function enableCode(codeId: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/enable`, { method: 'POST' })
}

/**
 * 延长时长。
 *
 * 后端会自己判断该改哪个字段（还没激活的码加 duration_hours、
 * 激活过的码加 expires_at），并说明它做的是哪一种 —— 前端不用也不该复刻这个判断。
 */
export function extendCode(codeId: number, hours: number): Promise<CodeActionResult> {
  assertWritable()
  return admin(`/admin/codes/${codeId}/extend`, { method: 'POST', body: { hours } })
}

export function deleteCode(codeId: number): Promise<{ message: string; id: number }> {
  assertWritable()
  return admin(`/admin/codes/${codeId}`, { method: 'DELETE' })
}

export function cleanupExpiredCodes(days: number = 7): Promise<CodeCleanupResult> {
  assertWritable()
  return admin('/admin/codes/cleanup-expired', {
    method: 'POST',
    query: { days },
  })
}
