/**
 * 12 个接口的**唯一**调用入口。组件里不写 URL 字符串。
 *
 * 参数名和后端一一对应（`vod_id` 而不是 `id`、`play_id` 而不是 `playId`），
 * 这样对着 `/docs` 或契约排查时不用做心算翻译。
 *
 * 全部返回**已经拆过信封的 `data`**；出错就抛 `ApiError`。
 */

import { request } from './http'
import type {
  ActivationResult,
  DetailPayload,
  HealthPayload,
  HomePayload,
  ListPayload,
  Playback,
  PlaybackHeartbeatRequest,
  PlaybackHeartbeatResult,
  SessionState,
  SiteListPayload,
  SiteMeta,
  SystemStatusPayload,
  VodItem,
} from './types'

// ------------------------------------------------------------------ 基础

export function health(): Promise<HealthPayload> {
  return request('/health')
}

// ------------------------------------------------------------------ 激活

export interface RedeemInput {
  /** 首次激活必填 */
  code?: string
  /** 被踢之后拿已存的令牌抢回来时用；有它就不需要 code */
  deviceToken?: string
  deviceName?: string
}

/**
 * 激活 / 在此设备继续。
 *
 * 后端刻意把这两件事合成一个动作（都是\"把活跃位指到这台上\"），
 * 所以这里也只有一个函数。
 */
export function redeem(input: RedeemInput): Promise<ActivationResult> {
  return request('/activation/redeem', {
    method: 'POST',
    body: {
      code: input.code ?? null,
      device_token: input.deviceToken ?? null,
      device_name: input.deviceName ?? '',
    },
  })
}

export function heartbeat(): Promise<SessionState> {
  return request('/activation/heartbeat', { method: 'POST' })
}

/** 播放端定期上报播放心跳与观看历史足迹 */
export function reportPlaybackHeartbeat(
  payload: PlaybackHeartbeatRequest,
): Promise<PlaybackHeartbeatResult> {
  return request('/activation/playback-heartbeat', {
    method: 'POST',
    body: payload,
  })
}

/** 落地页获取现正热播片单与真实封面 */
export function getTrending(): Promise<VodItem[]> {
  return request('/activation/trending')
}

// ------------------------------------------------------------------ 站点

export function listSites(): Promise<SiteListPayload> {
  return request('/sites')
}

export function getSite(key: string): Promise<SiteMeta> {
  return request(`/sites/${encodeURIComponent(key)}`)
}

// ------------------------------------------------------------------ 目录

export function getHome(key: string): Promise<HomePayload> {
  return request(`/sites/${encodeURIComponent(key)}/home`)
}

export interface CategoryInput {
  tid?: string
  page?: number
}

export function getCategory(key: string, input: CategoryInput = {}): Promise<ListPayload> {
  return request(`/sites/${encodeURIComponent(key)}/category`, {
    query: { tid: input.tid, page: input.page ?? 1 },
  })
}

export function getDetail(key: string, vodId: string): Promise<DetailPayload> {
  return request(`/sites/${encodeURIComponent(key)}/detail`, {
    query: { vod_id: vodId },
  })
}

export function searchVideos(key: string, keyword: string, page = 1): Promise<ListPayload> {
  return request(`/sites/${encodeURIComponent(key)}/search`, {
    query: { kw: keyword, page },
  })
}

export interface PlaybackInput {
  vodId: string
  /** 1 起算的集号 */
  ep: number
  /** 多线路源才需要 */
  line?: number
  /**
   * 详情里那一集的 `play_id`，原样回传。
   *
   * **不是必填**，但强烈建议带上：实测 `ncat21` 带它能省掉爬虫的一次源站请求，
   * 播放约 7.2s → 4.0s。详情页已经拿到了它，顺手传过来就行。
   */
  playId?: string
}

export function getPlayback(key: string, input: PlaybackInput): Promise<Playback> {
  return request(`/sites/${encodeURIComponent(key)}/playback`, {
    query: {
      vod_id: input.vodId,
      ep: input.ep,
      line: input.line,
      play_id: input.playId,
    },
  })
}

export function getPublicSystemStatus(): Promise<SystemStatusPayload> {
  return request('/system/status')
}
