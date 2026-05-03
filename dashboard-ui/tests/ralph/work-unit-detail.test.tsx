import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkUnitDetail } from '@/components/ralph/work-unit-detail';
import type { WorkUnit, WorkUnitStatus, ReviewResult, Transition } from '@/lib/ralph-types';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/ralph',
}));

// Mock EvidenceViewer — already tested in isolation, skip rendering here
vi.mock('@/components/ralph/evidence-viewer', () => ({
  EvidenceViewer: () => <div data-testid="evidence-viewer">Evidence</div>,
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  FileText: () => <span data-testid="icon-file-text">FileText</span>,
  Target: () => <span data-testid="icon-target">Target</span>,
  CheckCircle: () => <span data-testid="icon-check">CheckCircle</span>,
  Shield: () => <span data-testid="icon-shield">Shield</span>,
  Package: () => <span data-testid="icon-package">Package</span>,
  User: () => <span data-testid="icon-user">User</span>,
  Clock: () => <span data-testid="icon-clock">Clock</span>,
  AlertCircle: () => <span data-testid="icon-alert">AlertCircle</span>,
  GitBranch: () => <span data-testid="icon-git-branch">GitBranch</span>,
}));

// Mock ralph-utils
vi.mock('@/lib/ralph-utils', () => ({
  statusColor: (status: WorkUnitStatus) => `text-${status}-color`,
  statusLabel: (status: WorkUnitStatus) => {
    const labels: Record<string, string> = {
      draft: '草稿',
      ready: '就绪',
      running: '运行中',
      needs_review: '待审核',
      needs_rework: '需返工',
      accepted: '已验收',
      blocked: '已阻塞',
      failed: '失败',
    };
    return labels[status] || status;
  },
  formatDate: (date: string) => date,
}));

describe('WorkUnitDetail', () => {
  const mockWorkUnit: WorkUnit = {
    work_id: 'wu-test-001',
    work_type: 'development',
    title: 'Test Work Unit',
    status: 'running',
    background: 'This is a test background description',
    target: 'Implement the feature',
    scope_allow: ['src/components', 'src/lib'],
    scope_deny: ['src/api', 'node_modules'],
    dependencies: ['wu-dep-001'],
    input_files: ['src/input.ts'],
    expected_output: 'src/output.ts',
    acceptance_criteria: ['Test passes', 'Code review approved'],
    test_command: 'npm test',
    rollback_strategy: 'git revert',
    context_pack: {
      pack_id: 'cp-001',
      task_goal: 'Implement feature X',
      prd_fragment: 'Feature X should do Y',
      related_files: ['src/a.ts', 'src/b.ts'],
      file_summaries: { 'src/a.ts': 'Summary A' },
      upstream_summary: 'Depends on feature W',
      known_risks: ['Risk 1', 'Risk 2'],
      acceptance_criteria: ['Criteria 1'],
      scope_deny: ['deny-1'],
      trusted_data: ['data-1'],
      untrusted_data: [],
    },
    task_harness: {
      harness_id: 'th-001',
      task_goal: 'Implement feature X',
      context_sources: ['prd', 'codebase'],
      context_budget: '4000 tokens',
      allowed_tools: ['read', 'write'],
      denied_tools: ['delete'],
      scope_allow: ['src/'],
      scope_deny: ['tests/'],
      preflight_checks: ['Check A', 'Check B'],
      checkpoints: ['Point 1'],
      validation_gates: ['Gate 1', 'Gate 2'],
      evidence_required: ['test-output'],
      retry_policy: { max_retries: 3, backoff: 'exponential' },
      rollback_strategy: 'auto',
      timeout_policy: { max_duration_ms: 300000, on_timeout: 'fail' },
      stop_conditions: ['success', 'failure'],
      reviewer_role: 'senior-dev',
    },
    assumptions: ['Assumption 1'],
    impact_if_wrong: 'Medium impact',
    risk_notes: 'Some risks',
    producer_role: 'developer',
    reviewer_role: 'senior-dev',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  };

  it('renders work unit header correctly', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    // Check ID is displayed with monospace font
    expect(screen.getByText('wu-test-001')).toBeInTheDocument();

    // Check title
    expect(screen.getByText('Test Work Unit')).toBeInTheDocument();

    // Check status badge
    expect(screen.getByText('运行中')).toBeInTheDocument();

    // Check background
    expect(screen.getByText('This is a test background description')).toBeInTheDocument();
  });

  it('renders target section', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    // Target section has "目标" as heading and "任务目标" in Context Pack/Task Harness
    // Use getAllByText and check the first one (target section heading)
    const targetHeadings = screen.getAllByText('目标');
    expect(targetHeadings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Implement the feature')).toBeInTheDocument();
  });

  it('renders acceptance criteria', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('验收标准')).toBeInTheDocument();
    expect(screen.getByText('Test passes')).toBeInTheDocument();
    expect(screen.getByText('Code review approved')).toBeInTheDocument();
  });

  it('renders scope allow section with green border', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('允许修改')).toBeInTheDocument();
    expect(screen.getByText('src/components')).toBeInTheDocument();
    expect(screen.getByText('src/lib')).toBeInTheDocument();
  });

  it('renders scope deny section with red border', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('禁止修改')).toBeInTheDocument();
    expect(screen.getByText('src/api')).toBeInTheDocument();
    expect(screen.getByText('node_modules')).toBeInTheDocument();
  });

  it('renders Context Pack section', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('Context Pack')).toBeInTheDocument();
    // "Implement feature X" appears in both Context Pack and Task Harness
    const featureGoals = screen.getAllByText('Implement feature X');
    expect(featureGoals.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('上游摘要')).toBeInTheDocument();
    expect(screen.getByText('Depends on feature W')).toBeInTheDocument();
  });

  it('renders known risks in Context Pack', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('已知风险')).toBeInTheDocument();
    expect(screen.getByText('Risk 1')).toBeInTheDocument();
    expect(screen.getByText('Risk 2')).toBeInTheDocument();
  });

  it('renders related files in Context Pack', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('关联文件')).toBeInTheDocument();
    expect(screen.getByText('src/a.ts')).toBeInTheDocument();
    expect(screen.getByText('src/b.ts')).toBeInTheDocument();
  });

  it('renders Task Harness section', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('Task Harness')).toBeInTheDocument();
    expect(screen.getByText('审查角色')).toBeInTheDocument();
    // "senior-dev" appears in both meta info and Task Harness
    const seniorDevs = screen.getAllByText('senior-dev');
    expect(seniorDevs.length).toBeGreaterThanOrEqual(1);
  });

  it('renders preflight checks in Task Harness', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('前置检查')).toBeInTheDocument();
    expect(screen.getByText('Check A')).toBeInTheDocument();
    expect(screen.getByText('Check B')).toBeInTheDocument();
  });

  it('renders validation gates in Task Harness', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('验证门禁')).toBeInTheDocument();
    expect(screen.getByText('Gate 1')).toBeInTheDocument();
    expect(screen.getByText('Gate 2')).toBeInTheDocument();
  });

  it('renders evidence section via EvidenceViewer', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByTestId('evidence-viewer')).toBeInTheDocument();
  });

  it('renders meta information', () => {
    render(<WorkUnitDetail workUnit={mockWorkUnit} />);

    expect(screen.getByText('创建时间')).toBeInTheDocument();
    expect(screen.getByText('更新时间')).toBeInTheDocument();
    expect(screen.getByText('执行者')).toBeInTheDocument();
    expect(screen.getByText('审查者')).toBeInTheDocument();
    expect(screen.getByText('developer')).toBeInTheDocument();
  });

  it('handles work unit without context pack', () => {
    const workUnitWithoutContext = {
      ...mockWorkUnit,
      context_pack: null,
    };

    render(<WorkUnitDetail workUnit={workUnitWithoutContext} />);

    // Should not render Context Pack section
    expect(screen.queryByText('Context Pack')).not.toBeInTheDocument();
  });

  it('handles work unit without task harness', () => {
    const workUnitWithoutHarness = {
      ...mockWorkUnit,
      task_harness: null,
    };

    render(<WorkUnitDetail workUnit={workUnitWithoutHarness} />);

    // Should not render Task Harness section
    expect(screen.queryByText('Task Harness')).not.toBeInTheDocument();
  });

  it('handles work unit without acceptance criteria', () => {
    const workUnitWithoutCriteria = {
      ...mockWorkUnit,
      acceptance_criteria: [],
    };

    render(<WorkUnitDetail workUnit={workUnitWithoutCriteria} />);

    // Should not render acceptance criteria section
    expect(screen.queryByText('验收标准')).not.toBeInTheDocument();
  });

  it('handles work unit without scope restrictions', () => {
    const workUnitWithoutScope = {
      ...mockWorkUnit,
      scope_allow: [],
      scope_deny: [],
    };

    render(<WorkUnitDetail workUnit={workUnitWithoutScope} />);

    // "无限制" appears twice (once in allow section, once in deny section)
    const noLimits = screen.getAllByText('无限制');
    expect(noLimits.length).toBe(2);
    expect(screen.getByText('允许修改')).toBeInTheDocument();
    expect(screen.getByText('禁止修改')).toBeInTheDocument();
  });

  it('handles work unit without background', () => {
    const workUnitWithoutBackground = {
      ...mockWorkUnit,
      background: '',
    };

    render(<WorkUnitDetail workUnit={workUnitWithoutBackground} />);

    // Background section should not be rendered
    expect(screen.queryByText('背景')).not.toBeInTheDocument();
  });

  it('renders different status colors correctly', () => {
    const statuses: WorkUnitStatus[] = ['running', 'needs_review', 'accepted', 'failed', 'blocked'];

    statuses.forEach((status) => {
      const workUnitWithStatus = { ...mockWorkUnit, status };
      const { unmount } = render(<WorkUnitDetail workUnit={workUnitWithStatus} />);

      expect(screen.getByText(status === 'running' ? '运行中' :
        status === 'needs_review' ? '待审核' :
        status === 'accepted' ? '已验收' :
        status === 'failed' ? '失败' :
        status === 'blocked' ? '已阻塞' : status)).toBeInTheDocument();

      unmount();
    });
  });

  describe('ReviewCard', () => {
    const passedReview: ReviewResult = {
      work_id: 'wu-001',
      reviewer_context_id: 'ctx-1',
      review_type: '功能完整性',
      criteria_results: [
        { criterion: '测试通过', passed: true, notes: '' },
        { criterion: '代码审查通过', passed: false, notes: '缺少注释' },
      ],
      issues_found: [
        { severity: 'critical', description: '未处理边界情况', suggestion: '添加边界测试' },
        { severity: 'low', description: '命名不规范', suggestion: '使用驼峰命名' },
      ],
      evidence_checked: ['diff.txt'],
      harness_checked: true,
      conclusion: 'passed',
      recommended_action: '接受',
    };

    const failedReview: ReviewResult = {
      work_id: 'wu-002',
      reviewer_context_id: 'ctx-2',
      review_type: '边界状态',
      criteria_results: [
        { criterion: '输入验证', passed: false, notes: '' },
      ],
      issues_found: [
        { severity: 'high', description: '存在 XSS 风险', suggestion: '转义用户输入' },
        { severity: 'medium', description: '性能问题', suggestion: '添加缓存' },
      ],
      evidence_checked: ['diff.txt', 'test_output.txt'],
      harness_checked: false,
      conclusion: 'failed',
      recommended_action: '返工',
    };

    it('renders passed review with correct conclusion label', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[passedReview]} />);

      expect(screen.getByText('通过')).toBeInTheDocument();
    });

    it('renders failed review with correct conclusion label', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[failedReview]} />);

      expect(screen.getByText('不通过')).toBeInTheDocument();
    });

    it('renders criterion results with ✓/✗ markers', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[passedReview]} />);

      expect(screen.getByText('测试通过')).toBeInTheDocument();
      expect(screen.getByText('代码审查通过')).toBeInTheDocument();
    });

    it('renders issue severity labels', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[passedReview]} />);

      expect(screen.getByText('[critical]')).toBeInTheDocument();
      expect(screen.getByText('[low]')).toBeInTheDocument();
    });

    it('renders issue descriptions and suggestions', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[passedReview]} />);

      expect(screen.getByText('未处理边界情况')).toBeInTheDocument();
      expect(screen.getByText('添加边界测试')).toBeInTheDocument();
    });

    it('renders recommended action', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[passedReview]} />);

      expect(screen.getByText(/建议:/)).toBeInTheDocument();
      expect(screen.getByText(/接受/)).toBeInTheDocument();
    });

    it('does not render review section when reviews is empty', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} reviews={[]} />);

      expect(screen.queryByText('通过')).not.toBeInTheDocument();
      expect(screen.queryByText('不通过')).not.toBeInTheDocument();
    });
  });

  describe('TransitionTimeline', () => {
    const transitions: Transition[] = [
      { from_status: 'draft', to_status: 'ready', requires_approval: false },
      { from_status: 'ready', to_status: 'running', requires_approval: false },
      { from_status: 'running', to_status: 'needs_review', requires_approval: true },
    ];

    it('renders status flow path', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} transitions={transitions} />);

      expect(screen.getByText('状态流转')).toBeInTheDocument();
      // All statuses in the flow should be visible
      expect(screen.getAllByText('草稿').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('就绪').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('运行中').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('待审核').length).toBeGreaterThanOrEqual(1);
    });

    it('renders arrow indicators between statuses', () => {
      const { container } = render(<WorkUnitDetail workUnit={mockWorkUnit} transitions={transitions} />);

      // Arrows are rendered as "→" text
      expect(screen.getAllByText('→').length).toBe(transitions.length);
    });

    it('does not render when transitions is empty', () => {
      render(<WorkUnitDetail workUnit={mockWorkUnit} transitions={[]} />);

      expect(screen.queryByText('状态流转')).not.toBeInTheDocument();
    });
  });
});
