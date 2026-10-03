/**
 * 后台基础请求底座。
 * 统一附加 X-Admin-Token，并在令牌未配置时快速失败抛出 UNAUTHORIZED。
 */

import { ApiError, request, type RequestOptions } from '@/api/http'
import { getAdminToken } from '../token'

export async function admin<T>(path: string, options: Omit<RequestOptions, 'adminToken'> = {}): Promise<T> {
  const token = getAdminToken()
  if (!token) {
    throw new ApiError({ code: 'UNAUTHORIZED', message: '还没有输入后台令牌' })
  }
  return request<T>(path, { ...options, adminToken: token })
}
