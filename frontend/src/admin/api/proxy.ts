import type {
  ImageProxyClearResult,
  ImageProxyConfig,
  ImageProxyStats,
  SamplePostersPayload,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function getImageProxyStats(): Promise<ImageProxyStats> {
  return admin('/admin/proxy/stats')
}

export function getImageProxyConfig(): Promise<ImageProxyConfig> {
  return admin('/admin/proxy/config')
}

export function updateImageProxyConfig(payload: ImageProxyConfig): Promise<ImageProxyConfig> {
  assertWritable()
  return admin('/admin/proxy/config', {
    method: 'PUT',
    body: payload,
  })
}

export function clearImageProxy(): Promise<ImageProxyClearResult> {
  assertWritable()
  return admin('/admin/proxy/clear', { method: 'POST' })
}

export function getSamplePosters(site?: string): Promise<SamplePostersPayload> {
  return admin('/admin/proxy/sample-posters', {
    query: { site: site || undefined },
  })
}
