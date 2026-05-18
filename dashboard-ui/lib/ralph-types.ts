// Ralph Runtime Console - TypeScript Type Definitions
// Aligned with backend Python schema

// === Status Machine ===

export type WorkUnitStatus =
  | 'draft'
  | 'ready'
  | 'running'
  | 'needs_review'
  | 'accepted'
  | 'needs_rework'
  | 'blocked'
  | 'failed';

export const STATUS_TRANSITIONS: Record<WorkUnitStatus, WorkUnitStatus[]> = {
  draft: ['ready'],
  ready: ['running'],
  running: ['needs_review', 'failed', 'blocked'],
  needs_review: ['accepted', 'needs_rework', 'blocked'],
  failed: ['ready', 'blocked'],
  needs_rework: ['ready'],
  blocked: ['ready'],
  accepted: [], // terminal state
};

// === WorkUnit ===

export interface TaskHarness {
  harness_id: string;
  task_goal: string;
  context_sources: string[];
  context_budget: string;
  allowed_tools: string[];
  denied_tools: string[];
  scope_allow: string[];
  scope_deny: string[];
  preflight_checks: string[];
  checkpoints: string[];
  validation_gates: string[];
  evidence_required: string[];
  retry_policy: { max_retries: number; backoff: string };
  rollback_strategy: string;
  timeout_policy: { max_duration_ms: number; on_timeout: string };
  stop_conditions: string[];
  reviewer_role: string;
}

export interface ContextPack {
  pack_id: string;
  task_goal: string;
  // Backend Python field name is 'prd片段', serialized as 'prd_fragment'
  prd_fragment: string;
  related_files: string[];
  file_summaries: Record<string, string>;
  upstream_summary: string;
  known_risks: string[];
  acceptance_criteria: string[];
  scope_deny: string[];
  trusted_data: string[];
  untrusted_data: string[];
}

export interface WorkUnit {
  work_id: string;
  work_type: 'development' | 'test' | 'review' | 'rework' | 'recon';
  title: string;
  status: WorkUnitStatus;
  background: string;
  target: string;
  scope_allow: string[];
  scope_deny: string[];
  dependencies: string[];
  input_files: string[];
  expected_output: string;
  acceptance_criteria: string[];
  test_command: string;
  rollback_strategy: string;
  context_pack: ContextPack | null;
  task_harness: TaskHarness | null;
  assumptions: string[];
  impact_if_wrong: string;
  risk_notes: string;
  producer_role: string;
  reviewer_role: string;
  created_at: string;
  updated_at: string;
}

// === Evidence ===

export interface Evidence {
  evidence_id: string;
  work_id: string;
  file_name: string;
  file_type: 'diff' | 'test_output' | 'lint' | 'screenshot' | 'log' | 'other';
  size_bytes: number;
  created_at: string;
}

// === Review ===

export interface ReviewResult {
  work_id: string;
  reviewer_context_id: string;
  review_type: string;
  criteria_results: Array<{ criterion: string; passed: boolean; notes: string }>;
  issues_found: Array<{
    severity: 'critical' | 'high' | 'medium' | 'low';
    description: string;
    suggestion: string;
  }>;
  evidence_checked: string[];
  harness_checked: boolean;
  conclusion: 'passed' | 'failed';
  recommended_action: string;
}

// === Blocker ===

export interface Blocker {
  blocker_id: string;
  work_id: string;
  reason: string;
  category: 'permission' | 'scope' | 'harness' | 'dependency' | 'resource';
  created_at: string;
  resolved: boolean;
}

// === Command Types ===

export type CommandType =
  | 'prepare_work_unit'
  | 'execute_work_unit'
  | 'retry_work_unit'
  | 'cancel_work_unit'
  | 'expand_scope'
  | 'accept_review'
  | 'request_rework'
  | 'override_accept'
  | 'resolve_blocker'
  | 'dangerous_op_confirm'
  | 'start_run'
  | 'stop_run'
  | 'generate_report';

export type CommandStatus = 'pending' | 'accepted' | 'applied' | 'rejected' | 'failed' | 'cancelled';

/** API 原始返回的 Command 结构（后端字段名） */
export interface RalphCommandRaw {
  command_id: string;
  type: string;
  target_id: string;
  payload: Record<string, unknown>;
  status: string;
  idempotency_key: string;
  issued_by: string;
  issued_at: string;
  updated_at: string;
  result: Record<string, unknown>;
}

/** 前端规范化后的 Command 结构 */
export interface RalphCommand {
  command_id: string;
  command_type: string;
  target_id: string;
  payload: Record<string, unknown>;
  status: CommandStatus;
  idempotency_key: string;
  issued_by: string;
  issued_at: string;
  updated_at: string;
  result: Record<string, unknown>;
}

/** 将 API 返回的 raw command 转换为前端格式 */
export function normalizeCommand(raw: RalphCommandRaw): RalphCommand {
  return {
    command_id: raw.command_id,
    command_type: raw.type,
    target_id: raw.target_id,
    payload: raw.payload,
    status: raw.status as CommandStatus,
    idempotency_key: raw.idempotency_key,
    issued_by: raw.issued_by,
    issued_at: raw.issued_at,
    updated_at: raw.updated_at,
    result: raw.result,
  };
}

// === WebSocket Event ===

export type RalphEventType =
  | 'work_unit_created'
  | 'work_unit_status_changed'
  | 'evidence_saved'
  | 'review_completed'
  | 'command_applied'
  | 'command_failed'
  | 'blocker_created'
  | 'blocker_resolved'
  | 'pending_action_created'
  | 'pending_action_resolved'
  | 'heartbeat'
  | 'ralph_stream_chunk';

export interface RalphEvent {
  event_id: string; // UUID, for display only
  sequence: number; // Monotonically increasing integer for reconnection recovery
  event_type: RalphEventType;
  work_id: string | null;
  command_id: string | null;
  data: Record<string, unknown>;
  timestamp: string;
  source: string;
  agent_name: string | null;
  tags: string[];
  sequence_reset: boolean;
  correlation_id: string | null;
}

// === Pending Action (exceptional branches requiring human intervention) ===

export type PendingActionType =
  | 'dangerous_op'
  | 'scope_expansion'
  | 'review_dispute'
  | 'missing_dep'
  | 'execution_error'
  | 'manual_intervention';

export interface PendingAction {
  action_id: string;
  action_type: PendingActionType;
  work_id: string;
  description: string;
  context: Record<string, unknown>;
  created_at: string;
}

// === Tab Management ===

export interface Tab {
  id: string;
  label: string;
  type: 'work_unit' | 'work_unit_list' | 'approvals' | 'evidence' | 'overview' | 'commands' | 'events' | 'reports' | 'settings' | 'graph' | 'memory' | 'projects' | 'files' | 'pipeline' | 'scheduling' | 'brainstorm' | 'prd' | 'specs' | 'contracts' | 'usage' | 'history' | 'providers_health';
  work_id?: string;
  pinned: boolean;
  created_at: number;
}

// === Run Status ===

export interface RunStatus {
  total_work_units?: number;
  status_counts?: Record<string, number>;
  success_rate_percent?: number;
  unresolved_blockers?: number;
  timestamp?: string;
  total?: number;
  running?: number;
  needs_review?: number;
  blocked?: number;
  accepted?: number;
  failed?: number;
  latest_event?: unknown;
  next_action?: string | null;
}

// === API Request/Response Types ===

export interface ListWorkUnitsParams {
  status?: WorkUnitStatus;
  limit?: number;
  offset?: number;
}

export interface CreateCommandRequest {
  command_type: CommandType;
  target_id: string;
  payload?: Record<string, unknown>;
  idempotency_key?: string;
}

export interface CreateCommandResponse {
  command_id: string;
  idempotency_key: string;
  status: CommandStatus;
}

export interface RalphSummary {
  total_work_units: number;
  by_status: Record<WorkUnitStatus, number>;
  pending_commands: number;
  pending_actions: number;
  active_blockers: number;
  last_updated: string;
}

// === Transition ===

export interface Transition {
  from_status: WorkUnitStatus;
  to_status: WorkUnitStatus;
  requires_approval: boolean;
}

// === Retro (反思回顾) ===

export interface Lesson {
  category: 'went_well' | 'didnt_work' | 'to_improve';
  content: string;
  source: 'rule' | 'ai_enhanced';
  severity: 'low' | 'medium' | 'high';
}

export interface RetroRecord {
  retro_id: string;
  work_id: string;
  work_status: string;
  work_type: string;
  lessons: Lesson[];
  metrics: Record<string, number>;
  summary: string;
  ai_summary?: string;
  created_at: string;
  tags: string[];
}

export interface RetroSummary {
  period: string;
  total_retros: number;
  went_well: number;
  didnt_work: number;
  to_improve: number;
  top_issues: string[];
}

// === Review Matrix (多维度评审) ===

export interface DimensionResult {
  dimension: string;
  display_name: string;
  conclusion: '通过' | '不通过' | '跳过';
  confidence: 'high' | 'medium' | 'low';
  summary: string;
  findings: Array<{
    description: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
    suggested_action?: string;
    file_path?: string;
  }>;
  method: 'rule' | 'ai_enhanced';
}

export interface ReviewDimensionConfig {
  dimension: string;
  display_name: string;
  enabled: boolean;
  method: 'rule' | 'ai' | 'both';
  prompt_template: string;
  weight: number;
  required_for_types: string[];
}

export interface ReviewResultWithDimensions extends ReviewResult {
  dimension_results: DimensionResult[];
  overall_confidence: string;
}

// === Brainstorm V3 Types ===

export type BrainstormPhase =
  | 'product_def'
  | 'feature_decompose'
  | 'deliberation_review'
  | 'relationship'
  | 'independent_review'
  | 'clarification'
  | 'complete'
  | 'proactive_analysis'
  | 'technical_route_draft'
  | 'tool_discovery'
  | 'requirements_ready'
  | 'execution_plan_ready';

export type ProactiveItemStatus = 'pending' | 'accepted' | 'rejected' | 'modified';
export type DeliberationDecision = 'pending' | 'accept' | 'reject' | 'defer';
export type DeliberationSeverity = 'low' | 'medium' | 'high';
export type TechnicalRouteStatus = 'pending' | 'accepted' | 'revision_requested';
export type ToolRecommendation = 'adopt' | 'compare' | 'avoid';
export type SecurityRisk = 'low' | 'medium' | 'high' | 'unknown';
export type IntegrationCost = 'low' | 'medium' | 'high';
export type ToolSource = 'github' | 'web' | 'docs';

export interface ProactiveAnalysisItem {
  item_id: string;
  category: string;
  content: string;
  confidence: number;
  status: ProactiveItemStatus;
  user_revision: string;
}

export interface ProactiveAnalysis {
  analysis_id: string;
  items: ProactiveAnalysisItem[];
  summary: string;
  created_at: string;
  confirmed_at: string;
}

export interface ProductDefFinding {
  finding_id: string;
  dimension: string;
  dimension_name: string;
  content: string;
  suggestions: string[];
  questions: string[];
  confidence: number;
  status: string;
  user_revision: string;
  pm_decision: string;
  pm_reason: string;
}

export interface ProductDefRound {
  round_id: string;
  findings: ProductDefFinding[];
  summary: string;
  created_at: string;
  confirmed_at: string;
}

export interface ProductDefProgress {
  total_dimensions: number;
  dimensions_analyzed: string[];
  current_dimension: string | null;
  partial_findings: ProductDefFinding[];
  started_at: string;
  completed_at: string | null;
}

export interface PhaseOutputSnapshot {
  phase: string;
  label: string;
  completed_at: string;
  confirmed: boolean;
  confirmed_at: string;
  summary: string;
  detail: Record<string, unknown>;
}

export interface DeliberationFinding {
  finding_id: string;
  dimension: string;
  affected_feature_ids: string[];
  finding: string;
  severity: DeliberationSeverity;
  suggested_change: string;
  evidence: string;
  pm_decision: DeliberationDecision;
  pm_reason: string;
}

export interface DeliberationRound {
  round_id: string;
  findings: DeliberationFinding[];
  pm_summary: string;
  created_at: string;
  completed_at: string;
}

export interface TechnicalRoute {
  route_id: string;
  architecture_summary: string;
  frontend_stack: string[];
  backend_stack: string[];
  data_storage: string[];
  integrations: string[];
  non_functional_requirements: string[];
  key_risks: string[];
  tool_needs: string[];
  status: TechnicalRouteStatus;
  user_feedback: string;
  created_at: string;
  confirmed_at: string;
}

export interface ToolCandidate {
  candidate_id: string;
  name: string;
  source: ToolSource;
  url: string;
  description: string;
  license: string;
  stars: number | null;
  last_updated: string;
  package_name: string;
  evidence_urls: string[];
  evidence_snapshot: string;
}

export interface ToolEvaluation {
  candidate_id: string;
  functional_fit: number;
  maintenance_health: number;
  license_fit: number;
  stack_compatibility: number;
  security_risk: SecurityRisk;
  integration_cost: IntegrationCost;
  summary: string;
  recommendation: ToolRecommendation;
}

export interface ToolDiscoveryResult {
  discovery_id: string;
  tool_need: string;
  queries: string[];
  candidates: ToolCandidate[];
  evaluations: ToolEvaluation[];
  selected_candidate_ids: string[];
  created_at: string;
}

export const DIMENSION_DISPLAY_NAMES: Record<string, string> = {
  user_journey_analyst: '用户行为路径',
  feature_completeness_reviewer: '功能完整性',
  industry_benchmark_analyst: '行业对标',
  scenario_combiner: '场景组合',
};
