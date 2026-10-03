import type { AggregateSearchPayload } from '@/api/types'
import { admin } from './client'

export function searchAggregate(kw: string): Promise<AggregateSearchPayload> {
  return admin('/admin/search/aggregate', {
    query: { kw },
  })
}
