import type { Metadata } from 'next'
import { AuthGuard } from '@/components/auth/auth-guard'
import { CreateProjectForm } from '@/components/projects/create-project-form'
import { USER_ROLES } from '@/lib/constants'

export const metadata: Metadata = { title: 'New Project' }

export default function NewProjectPage() {
  return (
    <AuthGuard requiredRoles={[USER_ROLES.MANAGER, USER_ROLES.SUBSCRIBER]}>
      <div className="py-4">
        <CreateProjectForm />
      </div>
    </AuthGuard>
  )
}
