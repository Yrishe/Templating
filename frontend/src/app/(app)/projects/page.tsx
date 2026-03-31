import type { Metadata } from 'next'
import { ProjectsContent } from './projects-content'

export const metadata: Metadata = { title: 'Projects' }

export default function ProjectsPage() {
  return <ProjectsContent />
}
