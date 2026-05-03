import { describe, it, expect } from 'vitest';
import {
  STATUS_TRANSITIONS,
  type WorkUnitStatus,
  type CommandType,
  type RalphEventType,
  type PendingActionType,
} from '@/lib/ralph-types';

describe('STATUS_TRANSITIONS', () => {
  it('allows draft -> ready', () => {
    expect(STATUS_TRANSITIONS.draft).toContain('ready');
  });

  it('does not allow draft -> running directly', () => {
    expect(STATUS_TRANSITIONS.draft).not.toContain('running');
  });

  it('accepted has no next states (terminal)', () => {
    expect(STATUS_TRANSITIONS.accepted).toHaveLength(0);
  });

  it('covers all 8 statuses', () => {
    const allStatuses: WorkUnitStatus[] = [
      'draft',
      'ready',
      'running',
      'needs_review',
      'accepted',
      'needs_rework',
      'blocked',
      'failed',
    ];
    for (const s of allStatuses) {
      expect(STATUS_TRANSITIONS[s]).toBeDefined();
    }
  });

  it('running can transition to needs_review, failed, or blocked', () => {
    expect(STATUS_TRANSITIONS.running).toContain('needs_review');
    expect(STATUS_TRANSITIONS.running).toContain('failed');
    expect(STATUS_TRANSITIONS.running).toContain('blocked');
    expect(STATUS_TRANSITIONS.running).toHaveLength(3);
  });

  it('needs_review can transition to accepted, needs_rework, or blocked', () => {
    expect(STATUS_TRANSITIONS.needs_review).toContain('accepted');
    expect(STATUS_TRANSITIONS.needs_review).toContain('needs_rework');
    expect(STATUS_TRANSITIONS.needs_review).toContain('blocked');
    expect(STATUS_TRANSITIONS.needs_review).toHaveLength(3);
  });

  it('blocked can only transition to ready', () => {
    expect(STATUS_TRANSITIONS.blocked).toContain('ready');
    expect(STATUS_TRANSITIONS.blocked).toHaveLength(1);
  });
});

describe('CommandType', () => {
  it('has all expected command types', () => {
    const expectedTypes: CommandType[] = [
      'prepare_work_unit',
      'execute_work_unit',
      'retry_work_unit',
      'cancel_work_unit',
      'expand_scope',
      'accept_review',
      'request_rework',
      'override_accept',
      'resolve_blocker',
      'dangerous_op_confirm',
    ];
    // Type check - if this compiles, the types are correct
    const checkTypes: CommandType[] = expectedTypes;
    expect(checkTypes).toHaveLength(10);
  });
});

describe('RalphEventType', () => {
  it('has all expected event types', () => {
    const expectedTypes: RalphEventType[] = [
      'work_unit_created',
      'work_unit_status_changed',
      'evidence_saved',
      'review_completed',
      'command_applied',
      'command_failed',
      'blocker_created',
      'blocker_resolved',
      'pending_action_created',
      'pending_action_resolved',
      'heartbeat',
    ];
    // Type check - if this compiles, the types are correct
    const checkTypes: RalphEventType[] = expectedTypes;
    expect(checkTypes).toHaveLength(11);
  });
});

describe('PendingActionType', () => {
  it('has all expected pending action types', () => {
    const expectedTypes: PendingActionType[] = [
      'dangerous_op',
      'scope_expansion',
      'review_dispute',
      'missing_dep',
      'execution_error',
      'manual_intervention',
    ];
    // Type check - if this compiles, the types are correct
    const checkTypes: PendingActionType[] = expectedTypes;
    expect(checkTypes).toHaveLength(6);
  });
});

describe('WorkUnitStatus', () => {
  it('has all expected statuses', () => {
    const expectedStatuses: WorkUnitStatus[] = [
      'draft',
      'ready',
      'running',
      'needs_review',
      'accepted',
      'needs_rework',
      'blocked',
      'failed',
    ];
    // Type check - if this compiles, the types are correct
    const checkStatuses: WorkUnitStatus[] = expectedStatuses;
    expect(checkStatuses).toHaveLength(8);
  });
});
