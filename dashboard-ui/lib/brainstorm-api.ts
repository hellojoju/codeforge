const BASE = '/api/ralph/brainstorm'

export async function getFeatureTree(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/tree`)
  if (!res.ok) throw new Error(`Failed to get feature tree: ${res.status}`)
  return res.json()
}

export async function getSpecDocument(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/spec`)
  if (!res.ok) throw new Error(`Failed to get spec: ${res.status}`)
  return res.json()
}

export async function resumeSession(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/resume`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to resume: ${res.status}`)
  return res.json()
}

export async function advancePhase(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/advance`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to advance phase: ${res.status}`)
  return res.json()
}

export async function triggerReview(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/review`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger review: ${res.status}`)
  return res.json()
}

export async function triggerDecompose(recordId: string, childrenNames: string[] = []) {
  const res = await fetch(`${BASE}/${recordId}/decompose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ children_names: childrenNames }),
  })
  if (!res.ok) throw new Error(`Failed to trigger decompose: ${res.status}`)
  return res.json()
}

export async function getQuestionPlan(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/questions`)
  if (!res.ok) throw new Error(`Failed to get questions: ${res.status}`)
  return res.json()
}

export async function getTaskHandoffHints(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/handoff`)
  if (!res.ok) throw new Error(`Failed to get handoff hints: ${res.status}`)
  return res.json()
}

export async function generateTaskHandoffHints(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/handoff/generate`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to generate handoff hints: ${res.status}`)
  return res.json()
}

export async function confirmProactiveAnalysisItem(
  recordId: string,
  itemId: string,
  status: 'accepted' | 'rejected' | 'modified',
  revision = '',
) {
  const res = await fetch(`${BASE}/${recordId}/proactive-analysis/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item_id: itemId, status, revision }),
  })
  if (!res.ok) throw new Error(`Failed to confirm proactive item: ${res.status}`)
  return res.json()
}

export async function triggerDeliberation(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/deliberation`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger deliberation: ${res.status}`)
  return res.json()
}

export async function decideDeliberationFinding(
  recordId: string,
  findingId: string,
  decision: 'accept' | 'reject' | 'defer',
  reason = '',
) {
  const res = await fetch(`${BASE}/${recordId}/deliberation/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finding_id: findingId, decision, reason }),
  })
  if (!res.ok) throw new Error(`Failed to decide deliberation finding: ${res.status}`)
  return res.json()
}

export async function generateTechnicalRoute(recordId: string) {
  const res = await fetch(`/api/ralph/specs/${recordId}/technical-route`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to generate technical route: ${res.status}`)
  return res.json()
}

export async function confirmTechnicalRoute(routeId: string, status: 'accepted' | 'revision_requested', feedback = '') {
  const res = await fetch(`/api/ralph/technical-routes/${routeId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, feedback }),
  })
  if (!res.ok) throw new Error(`Failed to confirm technical route: ${res.status}`)
  return res.json()
}

export async function triggerToolDiscovery(routeId: string) {
  const res = await fetch(`/api/ralph/technical-routes/${routeId}/tool-discovery`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger tool discovery: ${res.status}`)
  return res.json()
}

export async function getExecutablePlan(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/executable-plan`)
  if (!res.ok) throw new Error(`Failed to get executable plan: ${res.status}`)
  return res.json()
}

export async function getExecutablePlanMarkdown(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/executable-plan/markdown`)
  if (!res.ok) throw new Error(`Failed to get executable plan markdown: ${res.status}`)
  return res.json()
}

export async function getProductDefProgress(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/product-def/progress`)
  if (!res.ok) throw new Error(`Failed to get progress: ${res.status}`)
  return res.json()
}

export async function confirmProductDefFinding(
  recordId: string,
  findingId: string,
  decision: 'accept' | 'reject' | 'defer',
  reason = '',
  revision = '',
) {
  const res = await fetch(`${BASE}/${recordId}/product-def/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finding_id: findingId, decision, reason, revision }),
  })
  if (!res.ok) throw new Error(`Failed to confirm product def finding: ${res.status}`)
  return res.json()
}

export async function confirmPhaseAdvance(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/phase/confirm`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to confirm phase: ${res.status}`)
  return res.json()
}

export async function rollbackToPhase(recordId: string, targetPhase: string) {
  const res = await fetch(`${BASE}/${recordId}/phase/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ record_id: recordId, target_phase: targetPhase }),
  })
  if (!res.ok) throw new Error(`Failed to rollback phase: ${res.status}`)
  return res.json()
}

export async function getPhaseOutputs(recordId: string) {
  const res = await fetch(`${BASE}/${recordId}/phase-outputs`)
  if (!res.ok) throw new Error(`Failed to get phase outputs: ${res.status}`)
  return res.json()
}
