import type {
  SiteCategoryRulePayload,
  SiteCategoryRuleUpdateRequest,
  SiteDetailPolicyPayload,
  SiteDetailPolicyUpdateRequest,
  SiteCachePolicy,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function getSiteCategories(key: string): Promise<SiteCategoryRulePayload> {
  return admin(`/admin/sites/${encodeURIComponent(key)}/categories`)
}

export function updateSiteCategories(
  key: string,
  payload: SiteCategoryRuleUpdateRequest,
): Promise<SiteCategoryRulePayload> {
  assertWritable()
  return admin(`/admin/sites/${encodeURIComponent(key)}/categories`, { method: 'PUT', body: payload })
}

export function getSiteDetailPolicy(key: string): Promise<SiteDetailPolicyPayload> {
  return admin(`/admin/sites/${encodeURIComponent(key)}/detail-policy`)
}

export function updateSiteDetailPolicy(
  key: string,
  payload: SiteDetailPolicyUpdateRequest,
): Promise<SiteDetailPolicyPayload> {
  assertWritable()
  return admin(`/admin/sites/${encodeURIComponent(key)}/detail-policy`, { method: 'PUT', body: payload })
}

export function getSiteCachePolicy(key: string): Promise<SiteCachePolicy> {
  return admin(`/admin/sites/${key}/cache-policy`)
}

export function updateSiteCachePolicy(key: string, payload: SiteCachePolicy): Promise<SiteCachePolicy> {
  assertWritable()
  return admin(`/admin/sites/${key}/cache-policy`, {
    method: 'PUT',
    body: payload,
  })
}
