/**
 * Ralph API Client Tests
 *
 * 使用 mock fetch 测试所有 API 方法
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  listWorkUnits,
  getWorkUnit,
  listEvidence,
  getEvidenceFile,
  getReviews,
  listBlockers,
  listPendingActions,
  getTransitions,
  getSummary,
  createCommand,
  getCommand,
  cancelCommand,
  commandActions,
  RalphApiError,
} from '@/lib/ralph-api';
import type {
  WorkUnit,
  WorkUnitStatus,
  Evidence,
  ReviewResult,
  Blocker,
  PendingAction,
  RalphCommand,
  RunStatus,
  Transition,
} from '@/lib/ralph-types';

// Mock fetch globally
global.fetch = vi.fn();

// Test fixtures
const mockWorkUnit = (id: string, status: WorkUnitStatus = 'draft'): WorkUnit => ({
  work_id: id,
  work_type: 'development',
  title: `Test Work ${id}`,
  status,
  background: 'Test background',
  target: 'Test target',
  scope_allow: [],
  scope_deny: [],
  dependencies: [],
  input_files: [],
  expected_output: 'test.txt',
  acceptance_criteria: [],
  test_command: '',
  rollback_strategy: '',
  context_pack: null,
  task_harness: null,
  assumptions: [],
  impact_if_wrong: '',
  risk_notes: '',
  producer_role: 'backend_dev',
  reviewer_role: 'code_reviewer',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
});

const mockEvidence = (id: string): Evidence => ({
  evidence_id: id,
  work_id: 'wu-1',
  file_name: `test-${id}.txt`,
  file_type: 'log',
  size_bytes: 1024,
  created_at: '2024-01-01T00:00:00Z',
});

const mockReviewResult = (workId: string): ReviewResult => ({
  work_id: workId,
  reviewer_context_id: 'ctx-1',
  review_type: 'code_review',
  criteria_results: [{ criterion: 'quality', passed: true, notes: 'Good' }],
  issues_found: [],
  evidence_checked: [],
  harness_checked: true,
  conclusion: 'passed',
  recommended_action: 'accept',
});

const mockBlocker = (id: string): Blocker => ({
  blocker_id: id,
  work_id: 'wu-1',
  reason: 'Dependency missing',
  category: 'dependency',
  created_at: '2024-01-01T00:00:00Z',
  resolved: false,
});

const mockPendingAction = (id: string): PendingAction => ({
  action_id: id,
  action_type: 'dangerous_op',
  work_id: 'wu-1',
  description: 'Dangerous operation requires confirmation',
  context: { operation: 'delete' },
  created_at: '2024-01-01T00:00:00Z',
});

const mockTransition = (): Transition => ({
  from_status: 'draft',
  to_status: 'ready',
  requires_approval: false,
});

const mockRunStatus = (): RunStatus => ({
  total_work_units: 10,
  status_counts: {
    running: 2,
    needs_review: 3,
    blocked: 1,
    accepted: 4,
    failed: 0,
  },
  success_rate_percent: 40,
  unresolved_blockers: 0,
  timestamp: '2024-01-01T00:00:00Z',
});

describe('Ralph API Client', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // ============================================================================
  // Error Handling
  // ============================================================================

  describe('RalphApiError', () => {
    it('should include status and responseBody', () => {
      const error = new RalphApiError('Test error', 404, { detail: 'Not found' });
      expect(error.message).toBe('Test error');
      expect(error.status).toBe(404);
      expect(error.responseBody).toEqual({ detail: 'Not found' });
      expect(error.name).toBe('RalphApiError');
    });
  });

  describe('request error handling', () => {
    it('should throw RalphApiError on non-2xx status with JSON body', async () => {
      vi.mocked(fetch).mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
      );

      await expect(listWorkUnits()).rejects.toThrow(RalphApiError);
      await expect(listWorkUnits()).rejects.toThrow('API Error 404');
    });

    it('should throw RalphApiError with text body when JSON parsing fails', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response('Server error', { status: 500 })
      );

      try {
        await listWorkUnits();
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(RalphApiError);
        expect((error as RalphApiError).status).toBe(500);
        // Response body should contain the text (may be null if empty)
        expect(typeof (error as RalphApiError).responseBody === 'string' ||
               (error as RalphApiError).responseBody === null).toBe(true);
      }
    });
  });

  // ============================================================================
  // WorkUnit API
  // ============================================================================

  describe('listWorkUnits', () => {
    it('should return list of work units', async () => {
      const workUnits = [mockWorkUnit('wu-1'), mockWorkUnit('wu-2')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(workUnits))
      );

      const result = await listWorkUnits();

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units',
        expect.objectContaining({ headers: expect.objectContaining({ 'Content-Type': 'application/json' }) })
      );
      expect(result).toHaveLength(2);
      expect(result[0].work_id).toBe('wu-1');
    });

    it('should filter by status when provided', async () => {
      const workUnits = [mockWorkUnit('wu-1', 'running')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(workUnits))
      );

      const result = await listWorkUnits('running');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units?status=running',
        expect.any(Object)
      );
      expect(result[0].status).toBe('running');
    });
  });

  describe('getWorkUnit', () => {
    it('should return single work unit', async () => {
      const workUnit = mockWorkUnit('wu-1');
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(workUnit))
      );

      const result = await getWorkUnit('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/wu-1',
        expect.any(Object)
      );
      expect(result.work_id).toBe('wu-1');
    });

    it('should encode workId in URL', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(mockWorkUnit('test/id')))
      );

      await getWorkUnit('test/id');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/test%2Fid',
        expect.any(Object)
      );
    });
  });

  // ============================================================================
  // Evidence API
  // ============================================================================

  describe('listEvidence', () => {
    it('should return list of evidence for work unit', async () => {
      const evidence = [mockEvidence('ev-1'), mockEvidence('ev-2')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(evidence))
      );

      const result = await listEvidence('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/wu-1/evidence',
        expect.any(Object)
      );
      expect(result).toHaveLength(2);
      expect(result[0].evidence_id).toBe('ev-1');
    });
  });

  describe('getEvidenceFile', () => {
    it('should return file content as text', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response('file content here')
      );

      const result = await getEvidenceFile('wu-1', 'logs/test.log');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/wu-1/evidence/logs%2Ftest.log'
      );
      expect(result).toBe('file content here');
    });

    it('should throw RalphApiError on failure', async () => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response('Not found', { status: 404 })
      );

      await expect(getEvidenceFile('wu-1', 'missing.txt')).rejects.toThrow(RalphApiError);
    });
  });

  // ============================================================================
  // Review API
  // ============================================================================

  describe('getReviews', () => {
    it('should return reviews for work unit', async () => {
      const reviews = [mockReviewResult('wu-1')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(reviews))
      );

      const result = await getReviews('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/wu-1/reviews',
        expect.any(Object)
      );
      expect(result).toHaveLength(1);
      expect(result[0].conclusion).toBe('passed');
    });
  });

  // ============================================================================
  // Blocker API
  // ============================================================================

  describe('listBlockers', () => {
    it('should return all blockers', async () => {
      const blockers = [mockBlocker('blk-1'), mockBlocker('blk-2')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(blockers))
      );

      const result = await listBlockers();

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/blockers',
        expect.any(Object)
      );
      expect(result).toHaveLength(2);
      expect(result[0].blocker_id).toBe('blk-1');
    });
  });

  // ============================================================================
  // Pending Action API
  // ============================================================================

  describe('listPendingActions', () => {
    it('should return all pending actions', async () => {
      const actions = [mockPendingAction('pa-1')];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(actions))
      );

      const result = await listPendingActions();

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/pending-actions',
        expect.any(Object)
      );
      expect(result).toHaveLength(1);
      expect(result[0].action_type).toBe('dangerous_op');
    });
  });

  // ============================================================================
  // Transitions API
  // ============================================================================

  describe('getTransitions', () => {
    it('should return available transitions for work unit', async () => {
      const transitions = [mockTransition()];
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(transitions))
      );

      const result = await getTransitions('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/work-units/wu-1/transitions',
        expect.any(Object)
      );
      expect(result).toHaveLength(1);
      expect(result[0].from_status).toBe('draft');
      expect(result[0].to_status).toBe('ready');
    });
  });

  // ============================================================================
  // Summary API
  // ============================================================================

  describe('getSummary', () => {
    it('should return run status summary', async () => {
      const summary = mockRunStatus();
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(summary))
      );

      const result = await getSummary();

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/summary',
        expect.any(Object)
      );
      expect(result.total).toBe(10);
      expect(result.running).toBe(2);
      expect(result.needs_review).toBe(3);
      expect(result.accepted).toBe(4);
      expect(result.blocked).toBe(1);
      expect(result.failed).toBe(0);
    });
  });

  // ============================================================================
  // Command API
  // ============================================================================

  describe('createCommand', () => {
    it('should create command and return RalphCommand', async () => {
      const mockResponse = {
        command_id: 'cmd-1',
        idempotency_key: 'idem-123',
        status: 'pending' as const,
      };
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(mockResponse))
      );

      const result = await createCommand({
        command_type: 'accept_review',
        target_id: 'wu-1',
        payload: { notes: 'LGTM' },
      });

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            command_type: 'accept_review',
            target_id: 'wu-1',
            payload: { notes: 'LGTM' },
          }),
        })
      );
      expect(result.command_id).toBe('cmd-1');
      expect(result.command_type).toBe('accept_review');
      expect(result.status).toBe('pending');
      expect(result.target_id).toBe('wu-1');
      expect(result.payload).toEqual({ notes: 'LGTM' });
    });

    it('should handle empty payload', async () => {
      const mockResponse = {
        command_id: 'cmd-2',
        idempotency_key: 'idem-456',
        status: 'pending' as const,
      };
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(mockResponse))
      );

      const result = await createCommand({
        command_type: 'prepare_work_unit',
        target_id: 'wu-1',
      });

      expect(result.payload).toEqual({});
    });
  });

  describe('getCommand', () => {
    it('should return command details', async () => {
      const rawCommand = {
        command_id: 'cmd-1',
        type: 'accept_review',
        target_id: 'wu-1',
        payload: {},
        status: 'applied',
        idempotency_key: 'idem-123',
        issued_by: 'user',
        issued_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:01:00Z',
        result: {},
      };
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify(rawCommand))
      );

      const result = await getCommand('cmd-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands/cmd-1',
        expect.any(Object)
      );
      expect(result.command_id).toBe('cmd-1');
      expect(result.status).toBe('applied');
    });
  });

  describe('cancelCommand', () => {
    it('should send cancel request', async () => {
      // Mock a 204 response - Response constructor doesn't accept 204 directly
      const mockResponse = {
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error('No content')),
        text: () => Promise.resolve(''),
      } as Response;
      vi.mocked(fetch).mockResolvedValueOnce(mockResponse);

      await cancelCommand('cmd-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands/cmd-1/cancel',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });

  // ============================================================================
  // Command Actions
  // ============================================================================

  describe('commandActions', () => {
    beforeEach(() => {
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(JSON.stringify({
          command_id: 'cmd-test',
          idempotency_key: 'idem-test',
          status: 'pending',
        }))
      );
    });

    it('acceptReview should create accept_review command', async () => {
      await commandActions.acceptReview('wu-1', 'Great work');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"accept_review"'),
        })
      );
    });

    it('requestRework should create request_rework command', async () => {
      await commandActions.requestRework('wu-1', 'Needs fixes');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"request_rework"'),
        })
      );
    });

    it('overrideAccept should create override_accept command', async () => {
      await commandActions.overrideAccept('wu-1', 'Emergency fix');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"override_accept"'),
        })
      );
    });

    it('expandScope should create expand_scope command', async () => {
      await commandActions.expandScope('wu-1', ['new-feature']);

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"expand_scope"'),
        })
      );
    });

    it('retryWorkUnit should create retry_work_unit command', async () => {
      await commandActions.retryWorkUnit('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"retry_work_unit"'),
        })
      );
    });

    it('cancelWorkUnit should create cancel_work_unit command', async () => {
      await commandActions.cancelWorkUnit('wu-1', 'No longer needed');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"cancel_work_unit"'),
        })
      );
    });

    it('prepareWorkUnit should create prepare_work_unit command', async () => {
      await commandActions.prepareWorkUnit('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"prepare_work_unit"'),
        })
      );
    });

    it('executeWorkUnit should create execute_work_unit command', async () => {
      await commandActions.executeWorkUnit('wu-1');

      expect(fetch).toHaveBeenCalledWith(
        '/api/ralph/commands',
        expect.objectContaining({
          body: expect.stringContaining('"command_type":"execute_work_unit"'),
        })
      );
    });
  });
});
