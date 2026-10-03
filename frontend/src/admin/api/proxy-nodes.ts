import type {
  ProxyNodeBindRequest,
  ProxyNodeCreateRequest,
  ProxyNodeItem,
  ProxyNodeListPayload,
  ProxyTestRequest,
  ProxyTestResult,
} from '@/api/types'
import { assertWritable } from '../ui'
import { admin } from './client'

export function listProxyNodes(): Promise<ProxyNodeListPayload> {
  return admin('/admin/proxy-nodes')
}

export function addProxyNode(payload: ProxyNodeCreateRequest): Promise<ProxyNodeItem> {
  assertWritable()
  return admin('/admin/proxy-nodes', {
    method: 'POST',
    body: payload,
  })
}

export function deleteProxyNode(nodeId: string): Promise<{ message: string; deleted: boolean }> {
  assertWritable()
  return admin(`/admin/proxy-nodes/${encodeURIComponent(nodeId)}`, {
    method: 'DELETE',
  })
}

export function testProxyNode(payload: ProxyTestRequest): Promise<ProxyTestResult> {
  return admin('/admin/proxy-nodes/test', {
    method: 'POST',
    body: payload,
  })
}

export function exportNodeXray(nodeId: string, httpPort = 10809, socksPort = 10808): Promise<Record<string, unknown>> {
  return admin(`/admin/proxy-nodes/${encodeURIComponent(nodeId)}/xray?http_port=${httpPort}&socks_port=${socksPort}`)
}

export function bindSiteProxyNode(payload: ProxyNodeBindRequest): Promise<{ message: string }> {
  assertWritable()
  return admin('/admin/proxy-nodes/bind', {
    method: 'POST',
    body: payload,
  })
}
