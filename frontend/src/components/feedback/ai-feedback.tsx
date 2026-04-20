'use client'

import React, { useEffect, useRef, useState } from 'react'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
import { useSubmitAiFeedback } from '@/hooks/use-feedback'
import { useFeatureFlag } from '@/hooks/use-feature-flag'
import { cn } from '@/lib/utils'
import type { AiFeedbackTargetType } from '@/types'

interface AiFeedbackProps {
  targetType: AiFeedbackTargetType
  targetId: string
  className?: string
}

const REASON_DEBOUNCE_MS = 3000

/**
 * 👍 / 👎 on a specific AI output (classification or suggestion). The
 * rating POSTs immediately; if the user types a reason we debounce 3 s
 * of idle and re-POST — the backend treats both calls as an idempotent
 * upsert on the same row.
 *
 * Gated by the `ai_thumbs` feature flag so the widget can be dark-
 * launched and pulled from the UI without a redeploy.
 */
export function AiFeedback({ targetType, targetId, className }: AiFeedbackProps) {
  const enabled = useFeatureFlag('ai_thumbs')
  const submit = useSubmitAiFeedback()
  const [rating, setRating] = useState<1 | -1 | null>(null)
  const [reason, setReason] = useState('')
  const [showReason, setShowReason] = useState(false)
  const reasonTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // If the user navigates away mid-edit the debounced submit should not
  // fire against an unmounted component.
  useEffect(() => {
    return () => {
      if (reasonTimer.current) clearTimeout(reasonTimer.current)
    }
  }, [])

  if (!enabled) return null

  function rate(next: 1 | -1) {
    // Optimistic local state. On error, revert — the only failure modes
    // are transient (401, 429) and a silent revert is better than a
    // modal for a low-stakes widget.
    const previous = rating
    setRating(next)
    setShowReason(true)
    submit.mutate(
      { target_type: targetType, target_id: targetId, rating: next, reason },
      {
        onError: () => setRating(previous),
      },
    )
  }

  function onReasonChange(value: string) {
    setReason(value)
    if (rating === null) return
    if (reasonTimer.current) clearTimeout(reasonTimer.current)
    reasonTimer.current = setTimeout(() => {
      submit.mutate({
        target_type: targetType,
        target_id: targetId,
        rating,
        reason: value,
      })
    }, REASON_DEBOUNCE_MS)
  }

  const submitted = rating !== null && !submit.isError

  return (
    <div className={cn('inline-flex flex-col gap-1', className)}>
      <div className="inline-flex items-center gap-1">
        <button
          type="button"
          aria-label="This AI output was helpful"
          aria-pressed={rating === 1}
          onClick={() => rate(1)}
          className={cn(
            'inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/80 hover:text-accent-foreground',
            rating === 1 && 'bg-green-100 text-green-700 hover:bg-green-200',
          )}
        >
          <ThumbsUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label="This AI output was not helpful"
          aria-pressed={rating === -1}
          onClick={() => rate(-1)}
          className={cn(
            'inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/80 hover:text-accent-foreground',
            rating === -1 && 'bg-red-100 text-red-700 hover:bg-red-200',
          )}
        >
          <ThumbsDown className="h-3.5 w-3.5" />
        </button>
        {submitted && (
          <span className="text-[10px] text-muted-foreground">Thanks for the feedback.</span>
        )}
      </div>
      {showReason && (
        <textarea
          rows={1}
          maxLength={500}
          placeholder="Optional: tell us why"
          value={reason}
          onChange={(e) => onReasonChange(e.target.value)}
          className="w-full resize-none rounded-md border bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
      )}
    </div>
  )
}
