'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Filter } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { EmailOrganiserPanel } from '@/components/email-organiser/email-organiser-panel'
import { AnalysisPanel } from '@/components/email-organiser/analysis-panel'
import type { IncomingEmail, EmailCategory } from '@/types'

const CATEGORY_FILTERS: { value: EmailCategory; label: string }[] = [
  { value: 'costs', label: 'Costs' },
  { value: 'delay', label: 'Delay' },
  { value: 'scope_change', label: 'Scope Change' },
  { value: 'damage', label: 'Damage' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'quality', label: 'Quality' },
  { value: 'dispute', label: 'Dispute' },
  { value: 'general', label: 'General' },
]

const RELEVANCE_FILTERS = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

export function EmailOrganiserContent() {
  const { projectId } = useParams<{ projectId: string }>()
  const [selected, setSelected] = useState<IncomingEmail | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [relevanceFilter, setRelevanceFilter] = useState<string>('')
  const [showResolved, setShowResolved] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Email Organiser</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Incoming emails are automatically classified by AI, assessed against
          the project contract, and organised by category and relevance.
          Relevant emails generate timeline events with risk assessments.
        </p>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          variant={showFilters ? 'default' : 'outline'}
          size="sm"
          onClick={() => setShowFilters(!showFilters)}
          className="h-8"
        >
          <Filter className="h-3.5 w-3.5 mr-1.5" />
          Filters
          {(categoryFilter || relevanceFilter) && (
            <Badge variant="secondary" className="ml-1.5 h-4 px-1 text-[10px]">
              {[categoryFilter, relevanceFilter].filter(Boolean).length}
            </Badge>
          )}
        </Button>

        <Button
          variant={showResolved ? 'default' : 'outline'}
          size="sm"
          onClick={() => setShowResolved(!showResolved)}
          className="h-8 text-xs"
        >
          {showResolved ? 'Showing All' : 'Show Resolved'}
        </Button>

        {(categoryFilter || relevanceFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setCategoryFilter('')
              setRelevanceFilter('')
            }}
            className="h-8 text-xs text-muted-foreground"
          >
            Clear filters
          </Button>
        )}
      </div>

      {showFilters && (
        <div className="border rounded-lg p-3 space-y-3 bg-muted/30">
          <div>
            <p className="text-xs font-medium mb-1.5">Category</p>
            <div className="flex gap-1.5 flex-wrap">
              {CATEGORY_FILTERS.map((f) => (
                <Button
                  key={f.value}
                  variant={categoryFilter === f.value ? 'default' : 'outline'}
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() =>
                    setCategoryFilter(categoryFilter === f.value ? '' : f.value)
                  }
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium mb-1.5">Relevance</p>
            <div className="flex gap-1.5 flex-wrap">
              {RELEVANCE_FILTERS.map((f) => (
                <Button
                  key={f.value}
                  variant={relevanceFilter === f.value ? 'default' : 'outline'}
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() =>
                    setRelevanceFilter(relevanceFilter === f.value ? '' : f.value)
                  }
                >
                  {f.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EmailOrganiserPanel
          projectId={projectId}
          selectedEmailId={selected?.id ?? null}
          onSelectEmail={setSelected}
          categoryFilter={categoryFilter}
          relevanceFilter={relevanceFilter}
          showResolved={showResolved}
        />
        <AnalysisPanel projectId={projectId} email={selected} />
      </div>
    </div>
  )
}
