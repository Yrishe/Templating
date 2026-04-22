import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  AiFeedbackTargetType,
  AiSuggestionFeedback,
  FeatureFeedback,
} from '@/types'

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

interface SubmitFeatureFeedbackInput {
  feature_key: string
  rating: 1 | -1
  comment?: string
  project?: string
  route?: string
}

/**
 * POST /api/feedback/feature/ — per-feature thumbs + comment. Same
 * idempotent-upsert shape as ai feedback, keyed on
 * (user, feature_key, project). Omit `project` for app-global features.
 */
export function useSubmitFeatureFeedback() {
  return useMutation({
    mutationFn: (input: SubmitFeatureFeedbackInput) =>
      api.post<FeatureFeedback>('/api/feedback/feature/', input),
  })
}
