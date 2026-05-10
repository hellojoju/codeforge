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
