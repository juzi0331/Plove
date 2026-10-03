/**
 * HTTP 层：**每个请求都走这里**，界面层永远不直接 fetch。
 *
 * 它负责四件在别处重复会出错的事：
 *
 * 1. **拆信封**。后端所有响应都是 `{ok, data, error, request_id}`，
 *    `ok: false` 时抛异常 —— 于是业务代码里只有正常路径，不用到处 `if (res.ok)`。
 * 2. **带上设备令牌**。少一个接口忘了带，那个接口就永远 401。
 * 3. **超时**。后端最坏情况是「爬虫超时 25s + 排队 20s」约 45 秒；
 *    不设超时，用户会对着转圈一直等下去。
 * 4. **把错误码翻译成人话**（见 :func:`describeError`）。
 *
 * 错误一律是 :class:`ApiError`，带 `code`（后端错误码）、`status`、
 * `requestId`。**排查问题时把 `requestId` 打给用户看** —— 拿它能在服务端日志里
 * 直接定位这一次请求，比\"什么时候、哪个接口\"这种描述有用得多。
 */

import { getDeviceToken, notifySessionKicked } from './session'
import type { ApiEnvelope, ErrorCode, ErrorInfo } from './types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'
const TIMEOUT_MS = Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS ?? 60_000)

/** 只属于客户端的三个\"码\"，和服务端的错误码放在一个类型里方便统一处理 */
export type ClientErrorCode = 'NETWORK' | 'TIMEOUT' | 'BAD_RESPONSE'
export type AnyErrorCode = ErrorCode | ClientErrorCode

export interface RequestOptions {
  method?: 'GET' | 'POST'
  /** 查询参数。`undefined` / `null` 的项会被丢掉（而不是发成 `?a=undefined`） */
  query?: Record<string, string | number | boolean | undefined | null>
  body?: unknown
  /** 后台接口要的另一个头，和内容接口的设备令牌是**两套凭证** */
  adminToken?: string
}

export class ApiError extends Error {
  readonly code: AnyErrorCode
  readonly status: number
  readonly requestId: string | null
  readonly detail: unknown

  constructor(params: {
    code: AnyErrorCode
    message: string
    status?: number
    requestId?: string | null
    detail?: unknown
  }) {
    super(params.message)
    this.name = 'ApiError'
    this.code = params.code
    this.status = params.status ?? 0
    this.requestId = params.requestId ?? null
    this.detail = params.detail ?? null
  }

  /** 供界面判断：这类错误重试有意义吗 */
  get retryable(): boolean {
    switch (this.code) {
      case 'UPSTREAM_TIMEOUT':
      case 'UPSTREAM_BUSY':
      case 'UPSTREAM_HTTP_ERROR':
      case 'UPSTREAM_UNKNOWN':
      case 'UPSTREAM_CIRCUIT_OPEN':
      case 'NETWORK':
      case 'TIMEOUT':
      case 'INTERNAL':
        return true
      default:
        return false
    }
  }
}

function buildUrl(path: string, query: RequestOptions['query']): string {
  const url = `${BASE}${path}`
  if (!query) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    search.append(key, String(value))
  }
  const qs = search.toString()
  return qs ? `${url}?${qs}` : url
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }

  const token = getDeviceToken()
  if (token) headers['X-Device-Token'] = token
  if (options.adminToken) headers['X-Admin-Token'] = options.adminToken

  let body: string | undefined
  if (options.body !== undefined) {
    // 中文放在请求体里没问题；**头里不行**（HTTP 头在协议层是 Latin-1，
    // 后端那边为这个踩过两次）。所以设备名这类自由文本一律走 body。
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError({
        code: 'TIMEOUT',
        message: `等了 ${Math.round(TIMEOUT_MS / 1000)} 秒还没有响应`,
      })
    }
    throw new ApiError({ code: 'NETWORK', message: '连不上服务器' })
  } finally {
    clearTimeout(timer)
  }

  let envelope: ApiEnvelope<T>
  try {
    envelope = (await response.json()) as ApiEnvelope<T>
  } catch {
    // 拿到 HTML（nginx 的 502 / 504 页）时会走到这里。这**不是**应用的错误，
    // 所以文案要说清\"谁\"回的，否则会误以为是后端逻辑坏了。
    throw new ApiError({
      code: 'BAD_RESPONSE',
      status: response.status,
      message:
        response.status >= 500
          ? `服务器返回了非 JSON（HTTP ${response.status}）—— 多半是网关/反向代理的页面，不是应用的响应`
          : `响应不是 JSON（HTTP ${response.status}）`,
    })
  }

  if (!envelope.ok) {
    const error: ErrorInfo = envelope.error ?? { code: 'INTERNAL', message: '未知错误' }
    if (error.code === 'SESSION_KICKED') notifySessionKicked()
    throw new ApiError({
      code: error.code,
      message: error.message,
      status: response.status,
      requestId: envelope.request_id,
      detail: error.detail,
    })
  }

  // 内容接口的 data 一定非空；`null` 只可能出现在 204 这类场景（我们目前没有）。
  return envelope.data as T
}

/** 错误码 → 人话。界面层只管展示，不要在组件里再写一遍 switch。 */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const base = CODE_TEXT[error.code]
    if (base) return base
    return error.message
  }
  if (error instanceof Error) return error.message
  return '出了点问题'
}

const CODE_TEXT: Partial<Record<AnyErrorCode, string>> = {
  UPSTREAM_TIMEOUT: '片源响应太慢，超时了。稍后再试，或换一个源。',
  UPSTREAM_HTTP_ERROR: '片源那边返回了错误，可能正在维护。换一个源试试。',
  UPSTREAM_PARSE_ERROR: '片源页面结构变了，这个源暂时解析不出来。',
  UPSTREAM_BLOCKED: '服务器被片源拦住了（反爬）。换一个源试试。',
  UPSTREAM_UNKNOWN: '片源出了未知问题，稍后再试。',
  UPSTREAM_BUSY: '服务器正忙（排队超时），过一会儿再试。',
  UPSTREAM_CIRCUIT_OPEN: '这个源连续失败已被暂时熔断，等一分钟再试，或换一个源。',
  SITE_DISABLED: '这个源已被管理员关闭，换一个源试试。',
  NOT_FOUND: '没有找到这个内容。',
  UNSUPPORTED: '这个源不支持该功能。',
  BAD_REQUEST: '请求参数不对。',
  VALIDATION_ERROR: '请求参数不对。',
  UNAUTHORIZED: '需要先激活才能看内容。',
  FORBIDDEN: '没有权限。',
  RATE_LIMITED: '操作太频繁了，稍等一下。',
  ACTIVATION_INVALID: '激活码无效，请检查有没有输错。',
  ACTIVATION_EXPIRED: '激活码已过期。',
  SESSION_KICKED: '这个激活码已经在别的设备上使用了。',
  NOT_IMPLEMENTED: '这个功能还没做。',
  INTERNAL: '服务器内部错误。',
  NETWORK: '连不上服务器，检查一下网络。',
  TIMEOUT: '服务器响应超时，稍后再试。',
  BAD_RESPONSE: '服务器返回了看不懂的内容（多半是网关的错误页）。',
}

export { BASE as API_BASE }
