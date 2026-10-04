/**
 * 体验与布局发布中心后台 API。
 */

import type {
  ClientBootstrapPayload,
  DraftSaveResult,
  ExperienceDraftPayload,
  ExperienceDraftUpdateRequest,
  ExperienceReleaseItem,
  PageViewModel,
  ReleasePublishRequest,
  ReleasePublishResult,
  ReleaseRollbackRequest,
} from '@/api/types'
import { admin } from './client'

export async function getExperienceDraft(draftId = 'default'): Promise<ExperienceDraftPayload> {
  return admin<ExperienceDraftPayload>(`/api/v2/admin/experience/drafts/${encodeURIComponent(draftId)}`)
}

export async function updateExperienceDraft(
  draftId: string,
  req: ExperienceDraftUpdateRequest,
): Promise<DraftSaveResult> {
  return admin<DraftSaveResult>(`/api/v2/admin/experience/drafts/${encodeURIComponent(draftId)}`, {
    method: 'PUT',
    body: req,
  })
}

export async function getPreviewBootstrap(draftId = 'default'): Promise<ClientBootstrapPayload> {
  return admin<ClientBootstrapPayload>(`/api/v2/admin/experience/preview/bootstrap?draft_id=${encodeURIComponent(draftId)}`)
}

export async function getPreviewPage(pageId = 'home', draftId = 'default'): Promise<PageViewModel> {
  return admin<PageViewModel>(
    `/api/v2/admin/experience/preview/pages/${encodeURIComponent(pageId)}?draft_id=${encodeURIComponent(draftId)}`,
  )
}

export async function publishExperienceRelease(req: ReleasePublishRequest): Promise<ReleasePublishResult> {
  return admin<ReleasePublishResult>('/api/v2/admin/experience/publish', {
    method: 'POST',
    body: req,
  })
}

export async function getExperienceReleases(limit = 20): Promise<ExperienceReleaseItem[]> {
  return admin<ExperienceReleaseItem[]>(`/api/v2/admin/experience/releases?limit=${limit}`)
}

export async function rollbackExperienceRelease(
  releaseId: string,
  req: ReleaseRollbackRequest = {},
): Promise<ReleasePublishResult> {
  return admin<ReleasePublishResult>(
    `/api/v2/admin/experience/releases/${encodeURIComponent(releaseId)}/rollback`,
    {
      method: 'POST',
      body: req,
    },
  )
}
