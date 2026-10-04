/**
 * 后台 API 模块聚合入口。
 * 所有子域 API 统一从这里导出，保持与原单文件 api.ts 100% 导入兼容。
 */

export * from './client'
export * from './status'
export * from './sites'
export * from './site-control'
export * from './crawlers'
export * from './codes'
export * from './devices'
export * from './cache'
export * from './playground'
export * from './search'
export * from './proxy'
export * from './proxy-nodes'
export * from './proxy-engine'
export * from './system'
export * from './experience'
export * from './webhooks'

// 重新导出外部所需类型
export type { SitePreheatDetail } from '@/api/types'
