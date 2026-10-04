import type { PlaygroundProbeRequest, PlaygroundProbeResult } from '@/api/types'
import { admin } from './client'

export function probePlayground(payload: PlaygroundProbeRequest): Promise<PlaygroundProbeResult> {
  return admin('/admin/playground/probe', {
    method: 'POST',
    body: payload,
  })
}
