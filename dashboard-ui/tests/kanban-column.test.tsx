 
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KanbanColumn, FeatureCard } from '@/components/kanban-column'
import type { Feature, Column } from '@/lib/types'

const makeFeature = (overrides: Partial<Feature> = {}): Feature => ({
  id: 'f1',
  category: 'feature',
  description: 'Test feature',
  priority: 'medium',
  assigned_to: '',
  assigned_instance: '',
  status: 'pending',
  dependencies: [],
  workspace_id: 'ws-1',
  files_changed: [],
  started_at: new Date().toISOString(),
  completed_at: '',
  error_log: [],
  ...overrides,
})

describe('KanbanColumn', () => {
  const pendingColumn: Column = { id: 'pending', title: '待办', color: 'border-blue-500' }
  const features: Feature[] = [
    makeFeature({ id: 'f1', description: 'Build login page', status: 'pending' }),
    makeFeature({ id: 'f2', description: 'Add auth API', status: 'pending' }),
    makeFeature({ id: 'f3', description: 'Deploy app', status: 'done' }),
  ]

  it('renders column title and count', () => {
    render(<KanbanColumn column={pendingColumn} features={features} />)
    expect(screen.getByText('待办')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders only features matching column id', () => {
    render(<KanbanColumn column={pendingColumn} features={features} />)
    expect(screen.getAllByText('Build login page').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Add auth API').length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByText('Deploy app')).not.toBeInTheDocument()
  })

  it('shows empty state when no features match', () => {
    const doneColumn: Column = { id: 'done', title: '已完成', color: 'border-green-500' }
    render(<KanbanColumn column={doneColumn} features={features.filter((f) => f.status !== 'done')} />)
    expect(screen.getByText('暂无任务')).toBeInTheDocument()
  })
})

describe('FeatureCard', () => {
  it('renders feature description and id', () => {
    const feature = makeFeature({ id: 'f1', description: 'Build API', status: 'pending' })
    render(<FeatureCard feature={feature} />)
    expect(screen.getAllByText('Build API').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('f1')).toBeInTheDocument()
  })

  it('renders assigned instance when present', () => {
    const feature = makeFeature({ id: 'f1', description: 'Build API', status: 'in_progress', assigned_instance: 'agent-1' })
    render(<FeatureCard feature={feature} />)
    expect(screen.getByText('agent-1')).toBeInTheDocument()
  })

  it('does not render assigned instance when absent', () => {
    const feature = makeFeature({ id: 'f1', description: 'Build API', status: 'pending' })
    render(<FeatureCard feature={feature} />)
    const card = screen.getAllByText('Build API')[0].closest('div')
    expect(card?.textContent).not.toContain('undefined')
  })

  it('applies correct status color for in_progress', () => {
    const feature = makeFeature({ id: 'f1', description: 'Active task', status: 'in_progress' })
    render(<FeatureCard feature={feature} />)
    const card = screen.getAllByText('Active task')[0].closest('div.rounded-lg')
    expect(card?.className).toContain('bg-blue-50')
  })

  it('applies pending status color as default', () => {
    const feature = makeFeature({ id: 'f1', description: 'Waiting task', status: 'blocked' })
    render(<FeatureCard feature={feature} />)
    const card = screen.getAllByText('Waiting task')[0].closest('div.rounded-lg')
    expect(card?.className).toContain('bg-red-50')
  })
})
