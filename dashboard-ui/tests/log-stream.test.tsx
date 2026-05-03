
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LogStream } from '@/components/log-stream'
import type { DashboardEvent } from '@/lib/types'

const makeEvent = (overrides: Partial<DashboardEvent> = {}): DashboardEvent => ({
  schema_version: 1,
  event_id: 1,
  project_id: 'default',
  run_id: '',
  type: 'agent_log',
  timestamp: new Date().toISOString(),
  caused_by_command_id: null,
  payload: {},
  ...overrides,
})

describe('LogStream', () => {
  it('renders empty state message', () => {
    render(<LogStream events={[]} />)
    expect(screen.getByText('等待事件...')).toBeInTheDocument()
  })

  it('renders events in reverse chronological order', () => {
    const events: DashboardEvent[] = [
      makeEvent({
        event_id: 1,
        type: 'agent_log',
        timestamp: '2026-04-19T10:00:00Z',
        payload: { agent_id: 'agent-1', message: 'First event' },
      }),
      makeEvent({
        event_id: 2,
        type: 'feature_completed',
        timestamp: '2026-04-19T10:01:00Z',
        payload: { agent_id: 'agent-2', message: 'Second event' },
      }),
    ]

    render(<LogStream events={events} />)

    // Reversed order: second event first
    const texts = screen.getAllByText(/(First event|Second event)/)
    expect(texts[0].textContent).toBe('Second event')
    expect(texts[1].textContent).toBe('First event')
  })

  it('renders event icons based on type', () => {
    const events: DashboardEvent[] = [
      makeEvent({
        event_id: 1,
        type: 'error_occurred',
        timestamp: '2026-04-19T10:00:00Z',
        payload: { agent_id: 'agent-1', message: 'Error happened' },
      }),
    ]

    render(<LogStream events={events} />)
    expect(screen.getByText('❌')).toBeInTheDocument()
  })

  it('renders default icon for unknown event type', () => {
    const events: DashboardEvent[] = [
      makeEvent({
        event_id: 1,
        type: 'unknown_type',
        timestamp: '2026-04-19T10:00:00Z',
        payload: { agent_id: 'agent-1', message: 'Unknown event' },
      }),
    ]

    render(<LogStream events={events} />)
    expect(screen.getByText('📌')).toBeInTheDocument()
  })

  it('shows fallback timestamp when missing', () => {
    const events: DashboardEvent[] = [
      { ...makeEvent({ event_id: 1, type: 'agent_log', payload: { agent_id: 'agent-1', message: 'No timestamp' } }), timestamp: undefined as unknown as string },
    ]

    render(<LogStream events={events} />)
    expect(screen.getByText('--:--:--')).toBeInTheDocument()
  })

  it('shows fallback agent_id when missing', () => {
    const events: DashboardEvent[] = [
      makeEvent({
        event_id: 1,
        type: 'agent_log',
        timestamp: '2026-04-19T10:00:00Z',
        payload: { message: 'No agent' },
      }),
    ]

    render(<LogStream events={events} />)
    expect(screen.getByText('-')).toBeInTheDocument()
  })

  it('limits display to last 50 events', () => {
    const events: DashboardEvent[] = Array.from({ length: 60 }, (_, i) =>
      makeEvent({
        event_id: i,
        type: 'agent_log',
        timestamp: `2026-04-19T10:${String(i).padStart(2, '0')}:00Z`,
        payload: { agent_id: 'agent-1', message: `Event ${i}` },
      })
    )

    render(<LogStream events={events} />)
    // Should show 50 events, not 60
    const eventMessages = screen.getAllByText(/Event \d+/)
    expect(eventMessages.length).toBe(50)
  })
})
