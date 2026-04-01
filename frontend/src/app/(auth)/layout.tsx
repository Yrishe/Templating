import { FileText } from 'lucide-react'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-muted/30 px-4">
      <div className="mb-8 flex items-center gap-2 text-primary">
        <FileText className="h-6 w-6" />
        <span className="text-xl font-bold">ContractMgr</span>
      </div>
      {children}
    </div>
  )
}
