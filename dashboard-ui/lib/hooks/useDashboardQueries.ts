/** TanStack Query hooks — 服务端状态查询。 */

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listAgents,
  getAgentStatus,
  listBlockingIssues,
  fetchStateSnapshot,
  getExecutionStatus,
  startExecution,
  stopExecution,
  resolveBlockingIssue,
  actions,
  interruptAgent,
  sendAgentMessage,
  listModules,
  fetchExecutionLedger,
} from '../api'
import { queryKeys } from '../query-keys'
import type { LedgerEntryStatus } from '../types'

// ─── Features ─────────────────────────────────────────────

export function useFeatures(projectId: string, runId: string) {
  return useQuery({
    queryKey: queryKeys.features(),
    queryFn: () => fetchStateSnapshot(projectId, runId),
    select: (data) => data.features,
  })
}

// ─── Agents ───────────────────────────────────────────────

export function useAgents() {
  return useQuery({
    queryKey: queryKeys.agents(),
    queryFn: listAgents,
  })
}

export function useAgentStatus(agentId: string) {
  return useQuery({
    queryKey: [...queryKeys.agents(), agentId],
    queryFn: () => getAgentStatus(agentId),
    enabled: !!agentId,
  })
}

// ─── Blocking Issues ──────────────────────────────────────

export function useBlockingIssues(featureId?: string, resolved = false) {
  return useQuery({
    queryKey: [...queryKeys.blockingIssues(), featureId, resolved],
    queryFn: () => listBlockingIssues(featureId, resolved),
  })
}

export function useResolveBlockingIssue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ issueId, resolution }: { issueId: string; resolution: string }) =>
      resolveBlockingIssue(issueId, resolution),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.blockingIssues() })
      qc.invalidateQueries({ queryKey: queryKeys.features() })
    },
  })
}

// ─── Execution Status ─────────────────────────────────────

export function useExecutionStatus() {
  return useQuery({
    queryKey: queryKeys.executionStatus(),
    queryFn: getExecutionStatus,
    refetchInterval: 5000,
  })
}

export function useExecutionLedger(filters?: {
  featureId?: string
  agentId?: string
  status?: LedgerEntryStatus
}) {
  return useQuery({
    queryKey: [...queryKeys.executionLedger(), filters?.featureId, filters?.agentId, filters?.status],
    queryFn: () => fetchExecutionLedger(filters),
  })
}

export function useStartExecution() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startExecution,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.executionStatus() })
      qc.invalidateQueries({ queryKey: queryKeys.features() })
    },
  })
}

export function useStopExecution() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: stopExecution,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.executionStatus() })
    },
  })
}

// ─── Actions (approve / reject / pause / resume / retry / skip) ───

export function useApprove() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (featureId: string) => actions.approve(featureId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.features() }),
  })
}

export function useReject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (featureId: string) => actions.reject(featureId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.features() }),
  })
}

export function usePauseFeature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (targetId: string) => actions.pause(targetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.features() })
      qc.invalidateQueries({ queryKey: queryKeys.agents() })
    },
  })
}

export function useResumeFeature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (targetId: string) => actions.resume(targetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.features() })
      qc.invalidateQueries({ queryKey: queryKeys.agents() })
    },
  })
}

export function useRetryFeature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (featureId: string) => actions.retry(featureId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.features() }),
  })
}

export function useSkipFeature() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (featureId: string) => actions.skip(featureId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.features() }),
  })
}

// ─── Agent Operations ─────────────────────────────────────

export function useInterruptAgent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ agentId, force }: { agentId: string; force?: boolean }) =>
      interruptAgent(agentId, { force }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents() })
    },
  })
}

export function useSendAgentMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ agentId, message }: { agentId: string; message: string }) =>
      sendAgentMessage(agentId, message),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.agents() })
    },
  })
}

// ─── Module Assignments ───────────────────────────────────

export function useModuleAssignments(role?: string) {
  return useQuery({
    queryKey: [...queryKeys.modules(), role],
    queryFn: () => listModules(role),
  })
}
