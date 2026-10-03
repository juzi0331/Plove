import type {
  ProxyEngineActionResponse,
  ProxyEngineStatusPayload,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function getProxyEngineStatus(): Promise<ProxyEngineStatusPayload> {
  return admin('/admin/proxy-engine/status')
}

export function installProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/install', { method: 'POST' })
}

export function startProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/start', { method: 'POST' })
}

export function restartProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/restart', { method: 'POST' })
}

export function stopProxyEngine(): Promise<ProxyEngineActionResponse> {
  assertWritable()
  return admin('/admin/proxy-engine/stop', { method: 'POST' })
}
