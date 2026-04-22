'use client'

import React, { useEffect, useRef, useState } from 'react'
import { ThumbsUp, ThumbsDown } from 'lucide-react'
import { useSubmitFeatureFeedback } from '@/hooks/use-feedback'
import { useFeatureFlag } from '@/hooks/use-feature-flag'
import { cn } from '@/lib/utils'

interface FeatureFeedbackProps {
  /** Dotted key identifying the feature, e.g. ``projects.overview``. */
  featureKey: string
  /** Omit for app-global features (dashboard, profile). */
  projectId?: string
  className?: string
  /** Override the prompt text above the thumbs. */
  label?: string
}

const COMMENT_DEBOUNCE_MS = 3000
const DEFAULT_LABEL = "How's this feature?"

/**
 * Per-feature 👍 / 👎 + optional comment. Mount on any feature page to
 * collect improvement feedback from users without a full help-desk
 * surface. Gated by the ``feature_feedback`` flag so it can be pulled
 * without a redeploy.
 *
 * UX mirrors ``<AiFeedback>`` — rating POSTs immediately; the comment
 * textarea opens after a click and debounces 3 s of idle before re-
 * POSTing. Backend treats both as an idempotent upsert on the same row.
 */
export function FeatureFeedback({
  featureKey,
  projectId,
  className,
  label = DEFAULT_LABEL,
}: FeatureFeedbackProps) {
  const enabled = useFeatureFlag('feature_feedback')
  const submit = useSubmitFeatureFeedback()
  const [rating, setRating] = useState<1 | -1 | null>(null)
  const [comment, setComment] = useState('')
  const [showComment, setShowComment] = useState(false)
  const commentTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (commentTimer.current) clearTimeout(commentTimer.current)
    }
  }, [])

  if (!enabled) return null

  const currentRoute =
    typeof window !== 'undefined' ? window.location.pathname : ''

  function rate(next: 1 | -1) {
    const previous = rating
    setRating(next)
    setShowComment(true)
    submit.mutate(
      {
        feature_key: featureKey,
        rating: next,
        comment,
        project: projectId,
        route: currentRoute,
      },
      {
        onError: () => setRating(previous),
      },
    )
  }

  function onCommentChange(value: string) {
    setComment(value)
    if (rating === null) return
    if (commentTimer.current) clearTimeout(commentTimer.current)
    commentTimer.current = setTimeout(() => {
      submit.mutate({
        feature_key: featureKey,
        rating,
        comment: value,
        project: projectId,
        route: currentRoute,
      })
    }, COMMENT_DEBOUNCE_MS)
  }

  const submitted = rating !== null && !submit.isError

  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3 text-sm',
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <span className="text-muted-foreground">{label}</span>
        <button
          type="button"
          aria-label="This feature works well"
          aria-pressed={rating === 1}
          onClick={() => rate(1)}
          className={cn(
            'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/80 hover:text-accent-foreground',
            rating === 1 && 'bg-green-100 text-green-700 hover:bg-green-200',
          )}
        >
          <ThumbsUp className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="This feature needs improvement"
          aria-pressed={rating === -1}
          onClick={() => rate(-1)}
          className={cn(
            'inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/80 hover:text-accent-foreground',
            rating === -1 && 'bg-red-100 text-red-700 hover:bg-red-200',
          )}
        >
          <ThumbsDown className="h-4 w-4" />
        </button>
        {submitted && (
          <span className="text-xs text-muted-foreground">Thanks for the feedback.</span>
        )}
      </div>
      {showComment && (
        <textarea
          rows={2}
          maxLength={1000}
          placeholder="Optional: what could be better?"
          value={comment}
          onChange={(e) => onCommentChange(e.target.value)}
          className="w-full resize-none rounded-md border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
      )}
    </div>
  )
}
