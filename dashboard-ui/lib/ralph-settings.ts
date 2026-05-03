/**
 * Ralph 设置管理 — localStorage 持久化
 *
 * 管理 LLM Provider、模型路由等配置
 */

export interface LLMProvider {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  defaultModel: string;
  models: string[];
  enabled: boolean;
  lastTestedAt: string | null;
  lastTestResult: 'ok' | 'fail' | null;
}

export interface ModelAssignment {
  taskType: string;
  providerId: string;
  model: string;
}

const STORAGE_KEYS = {
  providers: 'ralph-settings-providers',
  assignments: 'ralph-settings-assignments',
} as const;

function load<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function save<T>(key: string, value: T): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // silent
  }
}

// ==================== Providers ====================

const DEFAULT_PROVIDERS: LLMProvider[] = [
  {
    id: 'claude',
    name: 'Claude',
    baseUrl: 'https://api.anthropic.com',
    apiKey: '',
    defaultModel: 'claude-opus-4-7',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
    enabled: true,
    lastTestedAt: null,
    lastTestResult: null,
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com',
    apiKey: '',
    defaultModel: 'deepseek-v4-pro',
    models: ['deepseek-v4-pro', 'deepseek-chat'],
    enabled: false,
    lastTestedAt: null,
    lastTestResult: null,
  },
];

export function getProviders(): LLMProvider[] {
  return load(STORAGE_KEYS.providers, DEFAULT_PROVIDERS);
}

export function saveProviders(providers: LLMProvider[]): void {
  save(STORAGE_KEYS.providers, providers);
}

export function addProvider(provider: LLMProvider): LLMProvider[] {
  const providers = getProviders();
  providers.push(provider);
  saveProviders(providers);
  return providers;
}

export function updateProvider(id: string, updates: Partial<LLMProvider>): LLMProvider[] {
  const providers = getProviders().map((p) =>
    p.id === id ? { ...p, ...updates } : p
  );
  saveProviders(providers);
  return providers;
}

export function deleteProvider(id: string): LLMProvider[] {
  const providers = getProviders().filter((p) => p.id !== id);
  saveProviders(providers);
  return providers;
}

export function testProviderConnection(provider: LLMProvider): Promise<{ ok: boolean; error?: string }> {
  // 前端不能直接发跨域 API 请求，返回模拟结果
  // 实际连通性测试应由后端代理完成
  return new Promise((resolve) => {
    setTimeout(() => {
      if (!provider.baseUrl) {
        resolve({ ok: false, error: 'Base URL 为空' });
      } else {
        resolve({ ok: true });
      }
    }, 800);
  });
}

// ==================== Model Assignments ====================

const DEFAULT_ASSIGNMENTS: ModelAssignment[] = [
  { taskType: 'brainstorm', providerId: 'claude', model: 'claude-haiku-4-5' },
  { taskType: 'code_gen', providerId: 'deepseek', model: 'deepseek-v4-pro' },
  { taskType: 'review', providerId: 'claude', model: 'claude-sonnet-4-6' },
  { taskType: 'test', providerId: 'claude', model: 'claude-haiku-4-5' },
  { taskType: 'report', providerId: 'claude', model: 'claude-haiku-4-5' },
];

export function getAssignments(): ModelAssignment[] {
  return load(STORAGE_KEYS.assignments, DEFAULT_ASSIGNMENTS);
}

export function saveAssignments(assignments: ModelAssignment[]): void {
  save(STORAGE_KEYS.assignments, assignments);
}
