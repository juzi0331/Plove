import type {
  WebhookConfigPayload,
  WebhookLogsPayload,
  WebhookTestRequest,
  WebhookTestResult,
} from '@/api/types'
import { admin } from './client'

export function getWebhookConfig(): Promise<WebhookConfigPayload> {
  return admin('/admin/webhooks/config')
}

export function saveWebhookConfig(payload: WebhookConfigPayload): Promise<WebhookConfigPayload> {
  return admin('/admin/webhooks/config', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function testWebhookChannel(payload: WebhookTestRequest): Promise<WebhookTestResult> {
  return admin('/admin/webhooks/test', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function verifyTelegramBot(bot_token: string, proxy_url?: string): Promise<{ ok: boolean; id?: number; username?: string; first_name?: string; error?: string | null }> {
  return admin('/admin/webhooks/telegram/verify', {
    method: 'POST',
    body: JSON.stringify({ bot_token, proxy_url }),
  })
}

export function getWebhookLogs(limit = 30): Promise<WebhookLogsPayload> {
  return admin(`/admin/webhooks/logs?limit=${limit}`)
}

export function clearWebhookLogs(): Promise<{ cleared: boolean }> {
  return admin('/admin/webhooks/logs/clear', {
    method: 'POST',
  })
}
