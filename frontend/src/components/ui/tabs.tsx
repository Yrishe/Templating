'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface TabsContextValue {
  activeTab: string
  setActiveTab: (tab: string) => void
}

const TabsContext = React.createContext<TabsContextValue | undefined>(undefined)

function useTabsContext() {
  const context = React.useContext(TabsContext)
  if (!context) throw new Error('Tabs components must be used within a Tabs provider')
  return context
}

interface TabsProps {
  defaultValue: string
  value?: string
  onValueChange?: (value: string) => void
  className?: string
  children: React.ReactNode
}

function Tabs({ defaultValue, value, onValueChange, className, children }: TabsProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue)
  const activeTab = value ?? internalValue

  const setActiveTab = React.useCallback(
    (tab: string) => {
      setInternalValue(tab)
      onValueChange?.(tab)
    },
    [onValueChange]
  )

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={cn('', className)}>{children}</div>
    </TabsContext.Provider>
  )
}

const TabsList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground',
        className
      )}
      {...props}
    />
  )
)
TabsList.displayName = 'TabsList'

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, ...props }, ref) => {
    const { activeTab, setActiveTab } = useTabsContext()
    const isActive = activeTab === value
    return (
      <button
        ref={ref}
        role="tab"
        aria-selected={isActive}
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
          isActive
            ? 'bg-background text-foreground shadow-sm'
            : 'hover:bg-background/50 hover:text-foreground',
          className
        )}
        onClick={() => setActiveTab(value)}
        {...props}
      />
    )
  }
)
TabsTrigger.displayName = 'TabsTrigger'

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
}

const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, ...props }, ref) => {
    const { activeTab } = useTabsContext()
    if (activeTab !== value) return null
    return (
      <div
        ref={ref}
        role="tabpanel"
        className={cn(
          'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          className
        )}
        {...props}
      />
    )
  }
)
TabsContent.displayName = 'TabsContent'

export { Tabs, TabsList, TabsTrigger, TabsContent }
