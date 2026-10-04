import type {
  TelegramDetectChatResult,
  TelegramVerifyResult,
  WebhookConfigPayload,
  WebhookLogsPayload,
  WebhookSendEventRequest,
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
    body: payload,
  })
}

export function testWebhookChannel(payload: WebhookTestRequest): Promise<WebhookTestResult> {
  return admin('/admin/webhooks/test', {
    method: 'POST',
    body: payload,
  })
}

export function sendWebhookEvent(payload: WebhookSendEventRequest): Promise<WebhookTestResult> {
  return admin('/admin/webhooks/send-event', {
    method: 'POST',
    body: payload,
  })
}

export function verifyTelegramBot(bot_token: string, proxy_url?: string): Promise<TelegramVerifyResult> {
  return admin('/admin/webhooks/telegram/verify', {
    method: 'POST',
    body: { bot_token, proxy_url: proxy_url || '' },
  })
}

export function detectTelegramChat(bot_token: string, proxy_url?: string): Promise<TelegramDetectChatResult> {
  return admin('/admin/webhooks/telegram/detect-chat', {
    method: 'POST',
    body: { bot_token, proxy_url: proxy_url || '' },
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
