import { Navbar } from '@/components/layout/navbar'
import { Sidebar, MobileSidebar } from '@/components/layout/sidebar'
import { AuthGuard } from '@/components/auth/auth-guard'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen flex-col">
        <Navbar />
        <div className="flex flex-1">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <div className="container py-6 px-4 sm:px-6 lg:px-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </AuthGuard>
  )
}
