import type {
  CrawlerCodePayload,
  CrawlerUploadRequest,
  CrawlerUploadResult,
  CrawlerValidateRequest,
  CrawlerValidateResult,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function validateCrawler(payload: CrawlerValidateRequest): Promise<CrawlerValidateResult> {
  return admin('/admin/crawlers/validate', { method: 'POST', body: payload })
}

export function uploadCrawler(payload: CrawlerUploadRequest): Promise<CrawlerUploadResult> {
  assertWritable()
  return admin('/admin/crawlers/upload', { method: 'POST', body: payload })
}

export function getCrawlerCode(key: string): Promise<CrawlerCodePayload> {
  return admin(`/admin/crawlers/${encodeURIComponent(key)}/code`)
}

export function deleteCrawler(key: string): Promise<void> {
  assertWritable()
  return admin(`/admin/crawlers/${encodeURIComponent(key)}`, { method: 'DELETE' })
}
