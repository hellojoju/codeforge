/** 前后端契约类型定义 — 对齐后端 Python models.py。 */

/** Agent 实例状态枚举。 */
export type AgentStatus =
  | 'idle'
  | 'busy'
  | 'paused'
  | 'error'
  | 'waiting_approval'
  | 'waiting_pm'

/** Feature 卡片状态枚举。 */
export type FeatureStatus =
  | 'pending'
  | 'in_progress'
  | 'review'
  | 'done'
  | 'blocked'

/** Command 状态枚举。 */
export type CommandStatus =
  | 'pending'
  | 'accepted'
  | 'applied'
  | 'rejected'
  | 'failed'
  | 'cancelled'

/** Chat 消息角色。 */
export type ChatRole = 'user' | 'pm'

/** Agent 静默检测等级。 */
export type AgentSilenceLevel = 'active' | 'warning' | 'notify' | 'intervention'

export const SILENCE_LEVEL_LABELS: Record<AgentSilenceLevel, string> = {
  active: '正常',
  warning: '静默警告',
  notify: '需要关注',
  intervention: '需要干预',
}

export const SILENCE_LEVEL_COLORS: Record<AgentSilenceLevel, string> = {
  active: 'text-green-500',
  warning: 'text-yellow-500',
  notify: 'text-orange-500',
  intervention: 'text-red-500',
}

export const SILENCE_LEVEL_BG: Record<AgentSilenceLevel, string> = {
  active: 'bg-green-500',
  warning: 'bg-yellow-500',
  notify: 'bg-orange-500',
  intervention: 'bg-red-500',
}

/** 扩展 Agent 实例，包含静默和进程状态。 */
export interface AgentWithSilence extends AgentInstance {
  silence_status?: {
    level: AgentSilenceLevel
    idle_seconds: number
    last_activity: string
  }
  process_status?: {
    exists: boolean
    running: boolean
    exit_code: number | null
    pid: number | null
  }
  pid?: number | null
  current_activity?: string
}

/** 事件流条目类型。 */
export interface EventStreamItem {
  id: string
  timestamp: string
  type: string
  agent_id?: string
  feature_id?: string
  message: string
  severity?: 'info' | 'warning' | 'error'
}

export interface AgentInstance {
  id: string
  role: string
  instance_number: number
  status: AgentStatus
  current_feature: string | null
  workspace_id: string
  workspace_path: string
  total_tasks_completed: number
  started_at: string
}

export interface Feature {
  id: string
  category: string
  description: string
  priority: string
  assigned_to: string
  assigned_instance: string
  status: FeatureStatus
  dependencies: string[]
  workspace_id: string
  files_changed: string[]
  started_at: string
  completed_at: string
  error_log: string[]
  blocking_issues?: string[]
}

export interface BlockingIssue {
  issue_id: string
  issue_type: string
  feature_id: string
  detected_by: string
  detected_at: string
  description: string
  context: Record<string, unknown>
  resolved: boolean
  resolved_at: string
  resolution: string
}

export interface Command {
  schema_version: number
  command_id: string
  project_id: string
  run_id: string
  type: string
  target_id: string
  payload: Record<string, unknown>
  issued_by: string
  issued_at: string
  updated_at: string
  status: CommandStatus
  result: Record<string, unknown>
}

export interface DashboardEvent {
  schema_version: number
  event_id: number
  project_id: string
  run_id: string
  type: string
  timestamp: string
  caused_by_command_id: string | null
  payload: Record<string, unknown>
}

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  timestamp: string
  action_triggered: string
}

/** 同角色多 Agent 的模块分配记录。 */
export interface ModuleAssignment {
  module_id: string
  role: string
  assigned_agent_id: string
  module_name: string
  description: string
  dependencies: string[]
  status: 'pending' | 'in_progress' | 'blocked' | 'completed'
  interface_contract: Record<string, unknown>
}

export interface Snapshot {
  schema_version: number
  project_id: string
  run_id: string
  snapshot_version: number
  last_event_id: number
  project_name: string
  summary: Record<string, unknown>
  agents: AgentInstance[]
  features: Feature[]
  pending_approvals: Record<string, unknown>[]
  chat_history: ChatMessage[]
  module_assignments: ModuleAssignment[]
  blocking_issues: BlockingIssue[]
}

/** 看板列配置（用于 UI 渲染）。 */
export type Column = {
  id: FeatureStatus
  title: string
  color: string
}

export const COLUMNS: Column[] = [
  { id: 'pending', title: '待处理', color: 'border-gray-400' },
  { id: 'in_progress', title: '进行中', color: 'border-blue-500' },
  { id: 'review', title: '审查中', color: 'border-yellow-500' },
  { id: 'done', title: '已完成', color: 'border-green-500' },
  { id: 'blocked', title: '已阻塞', color: 'border-red-500' },
]

/** Agent 状态显示文本。 */
export const AGENT_STATUS_LABELS: Record<AgentStatus, string> = {
  idle: '空闲',
  busy: '工作中',
  paused: '已暂停',
  error: '错误',
  waiting_approval: '等待审批',
  waiting_pm: '等待 PM 指令',
}

/** 后端执行循环状态。 */
export type ExecutionStatus = 'idle' | 'starting' | 'running' | 'completed' | 'error'

export const EXECUTION_STATUS_LABELS: Record<ExecutionStatus, string> = {
  idle: '未启动',
  starting: '启动中',
  running: '运行中',
  completed: '已完成',
  error: '错误',
}

export const EXECUTION_STATUS_COLORS: Record<ExecutionStatus, string> = {
  idle: 'bg-gray-400',
  starting: 'bg-yellow-400',
  running: 'bg-green-500',
  completed: 'bg-blue-500',
  error: 'bg-red-500',
}
