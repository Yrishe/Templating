'use client'

import React from 'react'
import {
  Shield,
  AlertTriangle,
  BookOpen,
  Lightbulb,
  Route,
  Clock,
  CheckCircle2,
  RefreshCw,
  ExternalLink,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useResolveEmail, useReanalyseEmail } from '@/hooks/use-email-organiser'
import { CategoryBadge, RelevanceBadge } from './email-organiser-panel'
import { AiFeedback } from '@/components/feedback/ai-feedback'
import type { IncomingEmail } from '@/types'

function RiskBadge({ level }: { level: string }) {
  const config: Record<string, { variant: 'outline' | 'info' | 'warning' | 'destructive'; label: string }> = {
    low: { variant: 'outline', label: 'Low Risk' },
    medium: { variant: 'info', label: 'Medium Risk' },
    high: { variant: 'warning', label: 'High Risk' },
    critical: { variant: 'destructive', label: 'Critical Risk' },
  }
  const c = config[level] ?? config.medium
  return (
    <Badge variant={c.variant} className="gap-1">
      <Shield className="h-3 w-3" />
      {c.label}
    </Badge>
  )
}

interface AnalysisSectionProps {
  icon: React.ReactNode
  title: string
  content: string
}

function AnalysisSection({ icon, title, content }: AnalysisSectionProps) {
  if (!content) return null
  return (
    <div className="space-y-1.5">
      <h4 className="text-sm font-medium flex items-center gap-1.5">
        {icon}
        {title}
      </h4>
      <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
        {content}
      </p>
    </div>
  )
}

interface AnalysisPanelProps {
  projectId: string
  email: IncomingEmail | null
}

export function AnalysisPanel({ projectId, email }: AnalysisPanelProps) {
  const resolveEmail = useResolveEmail(projectId)
  const reanalyseEmail = useReanalyseEmail(projectId)
  const analysis = email?.analysis

  if (!email) {
    return (
      <Card>
        <CardContent className="py-16">
          <div className="text-center">
            <Shield className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
            <p className="text-sm text-muted-foreground">
              Select an email to view its AI analysis.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base mb-1.5">
              {email.subject || '(no subject)'}
            </CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <CategoryBadge category={email.category} />
              <RelevanceBadge relevance={email.relevance} />
              {analysis && <RiskBadge level={analysis.risk_level} />}
              {email.is_resolved && (
                <Badge variant="success" className="gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Resolved
                </Badge>
              )}
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => reanalyseEmail.mutate(email.id)}
              disabled={reanalyseEmail.isPending}
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1 ${reanalyseEmail.isPending ? 'animate-spin' : ''}`} />
              Re-analyse
            </Button>
            {!email.is_resolved && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => resolveEmail.mutate(email.id)}
                disabled={resolveEmail.isPending}
              >
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                {resolveEmail.isPending ? 'Resolving...' : 'Mark Resolved'}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Email context */}
        <div className="rounded-md border bg-muted/30 p-3 text-xs space-y-1 mb-4">
          <div className="text-muted-foreground">
            From: {email.sender_name || email.sender_email}
          </div>
          {email.keywords && (
            <div className="flex gap-1 flex-wrap mt-1">
              {email.keywords.split(',').map((kw, i) => (
                <span
                  key={i}
                  className="inline-block rounded bg-background border px-1.5 py-0 text-[10px]"
                >
                  {kw.trim()}
                </span>
              ))}
            </div>
          )}
        </div>

        {!email.is_processed && (
          <div className="text-center py-8">
            <Clock className="h-6 w-6 text-muted-foreground mx-auto animate-pulse mb-2" />
            <p className="text-sm text-muted-foreground">
              AI is analysing this email...
            </p>
          </div>
        )}

        {email.is_processed && !analysis && (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">
              No analysis available. Click &ldquo;Re-analyse&rdquo; to process this email.
            </p>
          </div>
        )}

        {analysis && (
          <div className="space-y-4">
            <AnalysisSection
              icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
              title="Risk Assessment"
              content={analysis.risk_summary}
            />

            <AnalysisSection
              icon={<BookOpen className="h-4 w-4 text-blue-500" />}
              title="Contract References"
              content={analysis.contract_references}
            />

            <AnalysisSection
              icon={<Shield className="h-4 w-4 text-green-500" />}
              title="Mitigation"
              content={analysis.mitigation}
            />

            {analysis.suggested_response && (
              <div className="space-y-2">
                <AnalysisSection
                  icon={<Lightbulb className="h-4 w-4 text-yellow-500" />}
                  title="Suggested Response"
                  content={analysis.suggested_response}
                />
                <AiFeedback targetType="suggestion" targetId={analysis.id} />
              </div>
            )}

            <AnalysisSection
              icon={<Route className="h-4 w-4 text-purple-500" />}
              title="Resolution Path"
              content={analysis.resolution_path}
            />

            <AnalysisSection
              icon={<Clock className="h-4 w-4 text-orange-500" />}
              title="Timeline Impact"
              content={analysis.timeline_impact}
            />

            {analysis.generated_timeline_event && (
              <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground flex items-center gap-2">
                <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                A timeline event was auto-generated for this occurrence.
                Check the project timeline for details.
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
