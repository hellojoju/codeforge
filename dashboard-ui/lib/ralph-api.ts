/**
 * Ralph Runtime Console - REST API 客户端
 *
 * 提供与 Ralph Runtime 后端 API 的完整交互能力
 */

import type {
  WorkUnit,
  WorkUnitStatus,
  Evidence,
  ReviewResult,
  Blocker,
  PendingAction,
  RalphCommand,
  RalphCommandRaw,
  CommandType,
  CommandStatus,
  RunStatus,
  CreateCommandRequest,
  CreateCommandResponse,
  Transition,
} from './ralph-types';
import { normalizeCommand } from './ralph-types';

const BASE = '/api/ralph';

/**
 * API 错误类
 * 包含状态码和响应体信息
 */
export class RalphApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly responseBody: unknown,
  ) {
    super(message);
    this.name = 'RalphApiError';
  }
}

/**
 * 统一请求封装
 * @template T 响应数据类型
 * @param url 请求路径（相对于 BASE）
 * @param options fetch 选项
 * @returns Promise<T>
 * @throws RalphApiError 当响应非 2xx 时
 */
async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const fullUrl = url.startsWith('http') ? url : `${BASE}${url}`;
  const res = await fetch(fullUrl, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new RalphApiError(
      `API Error ${res.status}: ${res.statusText}`,
      res.status,
      body,
    );
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ============================================================================
// 只读 API - WorkUnit
// ============================================================================

/**
 * 列出所有工作单元
 * @param status 可选状态过滤
 * @returns Promise<WorkUnit[]>
 */
export async function listWorkUnits(
  status?: WorkUnitStatus,
): Promise<WorkUnit[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const query = params.toString() ? `?${params.toString()}` : '';
  return request<WorkUnit[]>(`/work-units${query}`);
}

/**
 * 获取单个工作单元详情
 * @param workId 工作单元 ID
 * @returns Promise<WorkUnit>
 */
export async function getWorkUnit(workId: string): Promise<WorkUnit> {
  return request<WorkUnit>(`/work-units/${encodeURIComponent(workId)}`);
}

// ============================================================================
// 只读 API - Evidence
// ============================================================================

/**
 * 列出工作单元的所有证据文件
 * @param workId 工作单元 ID
 * @returns Promise<Evidence[]>
 */
export async function listEvidence(workId: string): Promise<Evidence[]> {
  return request<Evidence[]>(
    `/work-units/${encodeURIComponent(workId)}/evidence`,
  );
}

/**
 * 获取证据文件内容
 * @param workId 工作单元 ID
 * @param filePath 文件路径
 * @returns Promise<string> 文件内容
 */
export async function getEvidenceFile(
  workId: string,
  filePath: string,
): Promise<string> {
  const encodedPath = encodeURIComponent(filePath);
  const res = await fetch(
    `${BASE}/work-units/${encodeURIComponent(workId)}/evidence/${encodedPath}`,
  );

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => null);
    }
    throw new RalphApiError(
      `API Error ${res.status}: ${res.statusText}`,
      res.status,
      body,
    );
  }

  return res.text();
}

// ============================================================================
// 只读 API - Review
// ============================================================================

/**
 * 获取工作单元的审核结果
 * @param workId 工作单元 ID
 * @returns Promise<ReviewResult[]>
 */
export async function getReviews(workId: string): Promise<ReviewResult[]> {
  return request<ReviewResult[]>(
    `/work-units/${encodeURIComponent(workId)}/reviews`,
  );
}

// ============================================================================
// 只读 API - Blocker
// ============================================================================

/**
 * 列出所有阻塞项
 * @returns Promise<Blocker[]>
 */
export async function listBlockers(): Promise<Blocker[]> {
  return request<Blocker[]>('/blockers');
}

// ============================================================================
// 只读 API - Pending Action
// ============================================================================

/**
 * 列出所有待处理的人工干预请求
 * @returns Promise<PendingAction[]>
 */
export async function listPendingActions(): Promise<PendingAction[]> {
  return request<PendingAction[]>('/pending-actions');
}

// ============================================================================
// 只读 API - Transitions
// ============================================================================

/**
 * 获取工作单元可用的状态转换
 * @param workId 工作单元 ID
 * @returns Promise<Transition[]>
 */
export async function getTransitions(workId: string): Promise<Transition[]> {
  return request<Transition[]>(
    `/work-units/${encodeURIComponent(workId)}/transitions`,
  );
}

// ============================================================================
// 只读 API - Summary
// ============================================================================

/**
 * 获取运行状态摘要
 * @returns Promise<RunStatus>
 */
export async function getSummary(): Promise<RunStatus> {
  return request<RunStatus>('/summary');
}

// ============================================================================
// Command API
// ============================================================================

/**
 * 创建新命令
 * @param params 命令参数
 * @returns Promise<RalphCommand>
 */
export async function createCommand(
  params: CreateCommandRequest,
): Promise<RalphCommand> {
  const response = await request<CreateCommandResponse>('/commands', {
    method: 'POST',
    body: JSON.stringify(params),
  });

  // 根据响应构造完整的 RalphCommand 对象
  const now = new Date().toISOString();
  const command: RalphCommand = {
    command_id: response.command_id,
    command_type: params.command_type,
    target_id: params.target_id,
    payload: params.payload || {},
    status: response.status as CommandStatus,
    idempotency_key: response.idempotency_key,
    issued_by: 'user',
    issued_at: now,
    updated_at: now,
    result: {},
  };

  return command;
}

/**
 * 获取命令详情
 * @param commandId 命令 ID
 * @returns Promise<RalphCommand>
 */
export async function getCommand(commandId: string): Promise<RalphCommand> {
  const raw = await request<RalphCommandRaw>(`/commands/${encodeURIComponent(commandId)}`);
  return normalizeCommand(raw);
}

/**
 * 列出所有命令，支持 status 过滤
 * @param status 可选状态过滤
 * @returns Promise<RalphCommand[]>
 */
export async function listCommands(
  status?: string,
): Promise<RalphCommand[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const query = params.toString() ? `?${params.toString()}` : '';
  const rawList = await request<RalphCommandRaw[]>(`/commands${query}`);
  return rawList.map(normalizeCommand);
}

/**
 * 取消命令
 * @param commandId 命令 ID
 * @returns Promise<void>
 */
export async function cancelCommand(commandId: string): Promise<void> {
  await request<void>(`/commands/${encodeURIComponent(commandId)}/cancel`, {
    method: 'POST',
  });
}

// ============================================================================
// Reports API
// ============================================================================

export interface ReportInfo {
  name: string;
  size_bytes: number;
  created_at: string;
}

export interface ReportContent {
  success: boolean;
  name: string;
  path: string;
  content: string;
}

/**
 * 列出所有已生成的报告
 */
export async function listReports(): Promise<ReportInfo[]> {
  return request<ReportInfo[]>('/reports');
}

/**
 * 生成新报告
 */
export async function generateReport(
  title?: string,
  filename?: string,
): Promise<ReportContent> {
  return request<ReportContent>('/reports/generate', {
    method: 'POST',
    body: JSON.stringify({ title: title || '研发报告', filename }),
  });
}

/**
 * 获取单个报告内容
 */
export async function getReport(name: string): Promise<string> {
  const res = await fetch(`${BASE}/reports/${encodeURIComponent(name)}`);
  if (!res.ok) {
    throw new RalphApiError(
      `API Error ${res.status}: ${res.statusText}`,
      res.status,
      await res.text().catch(() => null),
    );
  }
  return res.text();
}

// ============================================================================
// 快捷命令工厂
// ============================================================================

/**
 * 快捷命令创建辅助函数
 */
export const commandActions = {
  /**
   * 接受审核
   */
  acceptReview: (workId: string, notes?: string) =>
    createCommand({
      command_type: 'accept_review',
      target_id: workId,
      payload: { notes },
    }),

  /**
   * 请求返工
   */
  requestRework: (workId: string, reason: string) =>
    createCommand({
      command_type: 'request_rework',
      target_id: workId,
      payload: { reason },
    }),

  /**
   * 覆盖接受（紧急情况下使用）
   */
  overrideAccept: (workId: string, justification: string) =>
    createCommand({
      command_type: 'override_accept',
      target_id: workId,
      payload: { justification },
    }),

  /**
   * 扩展范围
   */
  expandScope: (workId: string, additionalScope: string[]) =>
    createCommand({
      command_type: 'expand_scope',
      target_id: workId,
      payload: { additional_scope: additionalScope },
    }),

  /**
   * 重试工作单元
   */
  retryWorkUnit: (workId: string) =>
    createCommand({
      command_type: 'retry_work_unit',
      target_id: workId,
      payload: {},
    }),

  /**
   * 取消工作单元
   */
  cancelWorkUnit: (workId: string, reason: string) =>
    createCommand({
      command_type: 'cancel_work_unit',
      target_id: workId,
      payload: { reason },
    }),

  /**
   * 准备工作单元
   */
  prepareWorkUnit: (workId: string) =>
    createCommand({
      command_type: 'prepare_work_unit',
      target_id: workId,
      payload: {},
    }),

  /**
   * 执行工作单元
   */
  executeWorkUnit: (workId: string) =>
    createCommand({
      command_type: 'execute_work_unit',
      target_id: workId,
      payload: {},
    }),

  /**
   * 解决阻塞
   */
  resolveBlocker: (workId: string, blockerId: string, resolution: string, reason?: string) =>
    createCommand({
      command_type: 'resolve_blocker',
      target_id: workId,
      payload: { blocker_id: blockerId, resolution, reason: reason || '' },
    }),
};

// ============================================================================
// Settings API
// ============================================================================

export interface ProviderConfig {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  default_model: string;
  models: string[];
  enabled: boolean;
  last_tested_at: string | null;
  last_test_result: string | null;
}

export interface ModelAssignmentConfig {
  task_type: string;
  provider_id: string;
  model: string;
}

export interface ToolchainConfig {
  enabled_tools: string[];
  priority: string[];
  fallback_strategy: string;
  task_assignments?: Record<string, string>;
  max_parallel?: number;
}

export interface IssuePolicyConfig {
  issue_sources: string[];
  classification_rules: Record<string, string>;
  pull_interval: string;
}

// Providers
export async function listProviders(): Promise<ProviderConfig[]> {
  return request<ProviderConfig[]>('/settings/providers');
}

export async function createOrUpdateProvider(provider: Partial<ProviderConfig>): Promise<ProviderConfig> {
  return request<ProviderConfig>('/settings/providers', {
    method: 'POST',
    body: JSON.stringify(provider),
  });
}

export async function updateProvider(id: string, updates: Partial<ProviderConfig>): Promise<ProviderConfig> {
  return request<ProviderConfig>(`/settings/providers/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function deleteProvider(id: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/settings/providers/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export async function testProviderConnection(id: string): Promise<{ ok: boolean; error?: string }> {
  return request<{ ok: boolean; error?: string }>(`/settings/providers/${encodeURIComponent(id)}/test`, {
    method: 'POST',
  });
}

// Model Assignments
export async function listAssignments(): Promise<ModelAssignmentConfig[]> {
  return request<ModelAssignmentConfig[]>('/settings/model-assignments');
}

export async function saveAssignments(assignments: ModelAssignmentConfig[]): Promise<ModelAssignmentConfig[]> {
  return request<ModelAssignmentConfig[]>('/settings/model-assignments', {
    method: 'PUT',
    body: JSON.stringify(assignments),
  });
}

// Toolchain
export async function getToolchain(): Promise<ToolchainConfig> {
  return request<ToolchainConfig>('/settings/toolchain');
}

export async function saveToolchain(config: ToolchainConfig): Promise<ToolchainConfig> {
  return request<ToolchainConfig>('/settings/toolchain', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export async function dispatchParallel(maxParallel?: number): Promise<{ success: boolean; message: string; result?: any }> {
  return request('/settings/toolchain/dispatch-parallel', {
    method: 'POST',
    body: JSON.stringify({ max_parallel: maxParallel ?? 3 }),
  });
}

// Issue Policy
export async function getIssuePolicy(): Promise<IssuePolicyConfig> {
  return request<IssuePolicyConfig>('/settings/issue-policy');
}

export async function saveIssuePolicy(policy: IssuePolicyConfig): Promise<IssuePolicyConfig> {
  return request<IssuePolicyConfig>('/settings/issue-policy', {
    method: 'PUT',
    body: JSON.stringify(policy),
  });
}

// Events
export async function listEvents(limit?: number, afterId?: number): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (afterId) params.set('after_id', String(afterId));
  const query = params.toString() ? `?${params.toString()}` : '';
  return request<Record<string, unknown>[]>(`/events${query}`);
}

// ============================================================================
// Project API
// ============================================================================

export interface ProjectInfo {
  name: string;
  path: string;
  last_opened_at: string | null;
  has_ralph: boolean;
  work_unit_count?: number;
}

export interface ProjectAnalysis {
  project_name: string;
  total_files: number;
  file_stats: Record<string, number>;
  key_files: string[];
  git: { branch: string; last_commit: string };
}

export async function listProjects(): Promise<ProjectInfo[]> {
  return request<ProjectInfo[]>('/projects');
}

export async function openProject(path: string): Promise<Record<string, unknown>> {
  return request('/projects/open', { method: 'POST', body: JSON.stringify({ path }) });
}

export async function analyzeProject(path?: string): Promise<{ success: boolean; analysis: ProjectAnalysis }> {
  return request('/projects/analyze', { method: 'POST', body: JSON.stringify(path ? { path } : {}) });
}

export async function getProjectAnalysis(): Promise<{ analysis: ProjectAnalysis }> {
  return request('/projects/analysis');
}

export async function initProject(path: string, name: string): Promise<Record<string, unknown>> {
  return request('/projects/init', { method: 'POST', body: JSON.stringify({ path, name }) });
}

// ============================================================================
// File Browser API
// ============================================================================

export interface FileEntry {
  name: string;
  type: 'file' | 'dir';
  path: string;
  size: number | null;
  children?: FileEntry[];
}

export async function listDirectory(dirPath?: string): Promise<FileEntry[]> {
  const params = dirPath ? `?path=${encodeURIComponent(dirPath)}` : '';
  return request<FileEntry[]>(`/files${params}`);
}

export async function getFileContent(filePath: string): Promise<{ name: string; path: string; size: number; content: string }> {
  return request(`/files/content?path=${encodeURIComponent(filePath)}`);
}

export async function getFileTree(depth?: number): Promise<{ tree: FileEntry[] }> {
  const params = depth ? `?depth=${depth}` : '';
  return request<{ tree: FileEntry[] }>(`/files/tree${params}`);
}

// ============================================================================
// Agent Provider API (per-agent LLM config)
// ============================================================================

export interface AgentProviderConfig {
  agent_id?: string;
  provider_id: string;
  model: string;
  enabled: boolean;
  overrides?: { base_url?: string; api_key?: string };
}

export async function listAgentProviders(): Promise<Record<string, AgentProviderConfig>> {
  return request('/settings/agent-providers');
}

export async function saveAgentProvider(agentId: string, config: AgentProviderConfig): Promise<AgentProviderConfig> {
  return request(`/settings/agent-providers/${encodeURIComponent(agentId)}`, {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export async function resolveProvider(agentRole: string, taskType?: string): Promise<Record<string, unknown>> {
  return request('/settings/resolve-provider', {
    method: 'POST',
    body: JSON.stringify({ agent_role: agentRole, task_type: taskType }),
  });
}

// ============================================================================
// Agent Definitions API
// ============================================================================

export interface AgentDefinition {
  role: string;
  display_name: string;
  agent_class: string;
  system_prompt_override: string;
  allowed_tools: string[];
  workspace_subdir: string;
  max_instances: number;
  enabled: boolean;
}

export async function listAgentDefinitions(): Promise<AgentDefinition[]> {
  return request<AgentDefinition[]>('/agents/definitions');
}

export async function saveAgentDefinition(def: AgentDefinition): Promise<AgentDefinition> {
  return request<AgentDefinition>('/agents/definitions', {
    method: 'POST',
    body: JSON.stringify(def),
  });
}

export async function deleteAgentDefinition(role: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/agents/definitions/${encodeURIComponent(role)}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Scheduling API
// ============================================================================

export async function getSchedulingStatus(): Promise<Record<string, unknown>> {
  return request('/scheduling/status');
}

export async function getSchedulingTimeline(): Promise<Record<string, unknown>[]> {
  return request('/scheduling/timeline');
}

// ============================================================================
// Brainstorm API
// ============================================================================

export async function listBrainstormSessions(): Promise<Record<string, unknown>[]> {
  return request('/brainstorm/sessions');
}
export async function startBrainstorm(projectName: string, userMessage: string): Promise<Record<string, unknown>> {
  return request('/brainstorm/start', { method: 'POST', body: JSON.stringify({ project_name: projectName, user_message: userMessage }) });
}
export async function brainstormRespond(recordId: string, userResponse: string): Promise<Record<string, unknown>> {
  return request('/brainstorm/respond', { method: 'POST', body: JSON.stringify({ record_id: recordId, user_response: userResponse }) });
}

// ============================================================================
// PRD API
// ============================================================================

export async function listPRDs(): Promise<Record<string, unknown>[]> {
  return request('/prd/list');
}
export async function generatePRD(brainstormRecordId: string): Promise<Record<string, unknown>> {
  return request('/prd/generate', { method: 'POST', body: JSON.stringify({ brainstorm_record_id: brainstormRecordId }) });
}
export async function freezePRD(prdId: string): Promise<Record<string, unknown>> {
  return request('/prd/freeze', { method: 'POST', body: JSON.stringify({ prd_id: prdId }) });
}

// ============================================================================
// Task Decomposition API
// ============================================================================

export async function decomposeTasks(prdId: string): Promise<Record<string, unknown>> {
  return request('/tasks/decompose', { method: 'POST', body: JSON.stringify({ prd_id: prdId }) });
}

// ============================================================================
// Memory API
// ============================================================================

export async function getMemoryStatus(): Promise<Record<string, unknown>> {
  return request('/memory/status');
}
export async function searchMemory(q: string): Promise<Record<string, unknown>[]> {
  return request(`/memory/search?q=${encodeURIComponent(q)}`);
}

// ============================================================================
// 类型导出
// ============================================================================

export type {
  WorkUnit,
  WorkUnitStatus,
  Evidence,
  ReviewResult,
  Blocker,
  PendingAction,
  RalphCommand,
  RalphCommandRaw,
  CommandType,
  CommandStatus,
  RunStatus,
  CreateCommandRequest,
  CreateCommandResponse,
  Transition,
};
