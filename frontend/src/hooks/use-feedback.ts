import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { AiFeedbackTargetType, AiSuggestionFeedback } from '@/types'

interface SubmitAiFeedbackInput {
  target_type: AiFeedbackTargetType
  target_id: string
  rating: 1 | -1
  reason?: string
}

/**
 * POST /api/feedback/ai/ — idempotent upsert. The backend keys on
 * (user, target_type, target_id); re-submitting flips the rating or
 * attaches a reason on the same row. No cache invalidation needed —
 * feedback is write-only from the UI's perspective.
 */
export function useSubmitAiFeedback() {
  return useMutation({
    mutationFn: (input: SubmitAiFeedbackInput) =>
      api.post<AiSuggestionFeedback>('/api/feedback/ai/', input),
  })
}
