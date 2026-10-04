import type {
  CacheClearResult,
  CacheEntryDetail,
  CacheKeyEntry,
  CachePreheatResult,
  CacheStatsPayload,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export interface CacheGlobalConfig {
  cache_enabled: boolean
  warmup_enabled: boolean
  warmup_interval_seconds: number
}

export function getCacheStats(): Promise<CacheStatsPayload> {
  return admin('/admin/cache/stats')
}

export function listCacheKeys(site?: string, namespace?: string): Promise<CacheKeyEntry[]> {
  return admin('/admin/cache/keys', {
    query: { site: site || undefined, namespace: namespace || undefined },
  })
}

export function getCacheEntry(key: string): Promise<CacheEntryDetail> {
  return admin('/admin/cache/entry', {
    query: { key },
  })
}

export function clearCache(site?: string, key?: string): Promise<CacheClearResult> {
  assertWritable()
  return admin('/admin/cache/clear', {
    method: 'POST',
    body: { site: site || null, key: key || null },
  })
}

export function preheatCache(site?: string): Promise<CachePreheatResult> {
  assertWritable()
  return admin('/admin/cache/preheat', {
    method: 'POST',
    body: { site: site || null },
  })
}

export function getCacheGlobalConfig(): Promise<CacheGlobalConfig> {
  return admin('/admin/cache/config')
}

export function updateCacheGlobalConfig(payload: CacheGlobalConfig): Promise<CacheGlobalConfig> {
  assertWritable()
  return admin('/admin/cache/config', {
    method: 'PUT',
    body: payload,
  })
}
