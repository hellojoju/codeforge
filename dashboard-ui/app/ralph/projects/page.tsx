/**
 * 项目管理 /ralph/projects
 *
 * 产品定位：项目启动台
 * - 找到项目 → 分析 → 看报告 → 打开 / 需求共创
 *
 * 设计：
 * - 单列居中，项目卡片列表
 * - 点击卡片展开行内详情
 * - 分析报告以 Markdown 渲染展示
 * - 「打开项目」和「需求共创」为主要行动点
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  FolderOpen, Plus, Search, Clock, GitBranch, FileText,
  RefreshCw, Code2, History, ExternalLink,
  ChevronRight, File, Terminal, BookOpen,
  Sparkles, MessageSquare, Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  listProjects, openProject, analyzeProject,
  getProjectAnalysis, initProject, browseFs, type FsEntry,
  type ProjectInfo, type ProjectAnalysis,
} from '@/lib/ralph-api';
import { useRalphStore } from '@/lib/ralph-store';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';

// ─── 分析进度类型 ────────────────────────────────────

interface AnalysisProgress {
  status: 'idle' | 'starting' | 'running' | 'complete' | 'error';
  progress: number;
  phase: string;
  message: string;
  currentFile: string | null;
}

const ANALYSIS_STORAGE_KEY = 'ralph-analysis-progress';

function loadAnalysisProgress(): Record<string, AnalysisProgress> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(ANALYSIS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}

function saveAnalysisProgress(data: Record<string, AnalysisProgress>) {
  try { localStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(data)); }
  catch { /* ignore */ }
}

// ─── 进度指示器组件 ───────────────────────────────────

function AnalysisProgressBar({ progress, phase, message, currentFile }:
  { progress: number; phase: string; message: string; currentFile: string | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <Loader2 size={14} className="animate-spin text-blue-500" />
        <span className="text-xs font-medium text-slate-700">{phase}</span>
        <span className="ml-auto text-[10px] text-slate-400 font-mono">{progress}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-200 mb-2 overflow-hidden">
        <div className="h-full rounded-full bg-blue-500 transition-all duration-500 ease-out"
          style={{ width: `${Math.max(progress, 2)}%` }} />
      </div>
      <p className="text-[10px] text-slate-400 truncate">{message}</p>
      {currentFile && (
        <p className="text-[10px] text-slate-400 font-mono mt-0.5 truncate">
          <File size={9} className="inline mr-1" />{currentFile}
        </p>
      )}
    </div>
  );
}

// ─── 简化的 Markdown 渲染 ────────────────────────────

function MarkdownRender({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: React.ReactElement[] = [];
  let inCodeBlock = false;
  let codeBlockContent: string[] = [];
  let codeBlockLang = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 代码块
    if (line.startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre key={i} className="my-2 rounded-lg bg-slate-50 border border-slate-200 p-3 overflow-x-auto">
            <code className="text-[11px] font-mono text-slate-700 whitespace-pre">{codeBlockContent.join('\n')}</code>
          </pre>,
        );
        codeBlockContent = [];
        codeBlockLang = '';
        inCodeBlock = false;
        continue;
      } else {
        inCodeBlock = true;
        codeBlockLang = line.slice(3).trim();
        continue;
      }
    }
    if (inCodeBlock) {
      codeBlockContent.push(line);
      continue;
    }

    // 空行
    if (line.trim() === '') {
      if (i > 0 && lines[i - 1].trim() !== '') {
        elements.push(<div key={i} className="h-2" />);
      }
      continue;
    }

    // 标题
    if (line.startsWith('### ')) {
      elements.push(<h3 key={i} className="text-sm font-bold text-slate-800 mt-4 mb-2">{line.slice(4)}</h3>);
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(<h2 key={i} className="text-base font-bold text-slate-900 mt-5 mb-2">{line.slice(3)}</h2>);
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(<h1 key={i} className="text-lg font-bold text-slate-900 mt-5 mb-3">{line.slice(2)}</h1>);
      continue;
    }

    // 列表
    if (line.match(/^[-*]\s/)) {
      elements.push(
        <li key={i} className="text-xs text-slate-600 ml-4 list-disc py-0.5">{line.replace(/^[-*]\s/, '')}</li>,
      );
      continue;
    }
    if (line.match(/^\d+\.\s/)) {
      elements.push(
        <li key={i} className="text-xs text-slate-600 ml-4 list-decimal py-0.5">{line.replace(/^\d+\.\s/, '')}</li>,
      );
      continue;
    }

    // 加粗
    const rendered = line.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    elements.push(
      <p key={i} className="text-xs text-slate-600 leading-relaxed" dangerouslySetInnerHTML={{ __html: rendered }} />,
    );
  }

  // 未关闭的代码块
  if (codeBlockContent.length > 0) {
    elements.push(
      <pre key="last-cb" className="my-2 rounded-lg bg-slate-50 border border-slate-200 p-3 overflow-x-auto">
        <code className="text-[11px] font-mono text-slate-700">{codeBlockContent.join('\n')}</code>
      </pre>,
    );
  }

  return <div className="space-y-0.5">{elements}</div>;
}

// ─── 项目展开详情 ───────────────────────────────────

function ProjectExpanded({
  project,
  analysis,
  deepReport,
  analysisProgress,
  onOpen,
  onDeepAnalyze,
  onBrainstorm,
}: {
  project: ProjectInfo;
  analysis: ProjectAnalysis | null;
  deepReport: string | null;
  analysisProgress: AnalysisProgress | null;
  onOpen: () => void;
  onDeepAnalyze: () => void;
  onBrainstorm: () => void;
}) {
  const [showReport, setShowReport] = useState(false);
  const isAnalyzing = analysisProgress != null && (analysisProgress.status === 'starting' || analysisProgress.status === 'running');

  return (
    <div className="px-4 pb-5 pt-2 border-t border-slate-100">
      {/* 快捷操作 */}
      <div className="flex items-center gap-2 mb-4 mt-2">
        <button
          onClick={onOpen}
          className="flex items-center gap-1.5 h-8 px-4 text-xs font-medium rounded-lg bg-slate-800 text-white hover:bg-slate-700 transition-colors"
        >
          <ExternalLink size={13} />
          打开项目
        </button>
        <button
          onClick={onBrainstorm}
          disabled={isAnalyzing}
          className="flex items-center gap-1.5 h-8 px-4 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          <MessageSquare size={13} />
          需求共创
        </button>
        <button
          onClick={onDeepAnalyze}
          disabled={isAnalyzing}
          className="flex items-center gap-1.5 h-8 px-3 text-xs rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40 transition-colors"
        >
          <Sparkles size={12} className={cn(isAnalyzing && 'animate-pulse')} />
          {isAnalyzing ? 'AI 分析中...' : 'AI 深度分析'}
        </button>
        <span className="ml-auto text-[10px] text-slate-400">
          {project.work_unit_count != null ? `${project.work_unit_count} 个工作单元` : ''}
        </span>
      </div>

      {/* 进度指示器 */}
      {isAnalyzing && analysisProgress && (
        <AnalysisProgressBar
          progress={analysisProgress.progress}
          phase={analysisProgress.phase}
          message={analysisProgress.message}
          currentFile={analysisProgress.currentFile}
        />
      )}

      {/* 分析报告（深度分析） */}
      {deepReport && (
        <div className="mb-4">
          <button
            onClick={() => setShowReport(!showReport)}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 mb-2"
          >
            <BookOpen size={12} />
            AI 分析报告
            <ChevronRight size={10} className={cn('transition-transform', showReport && 'rotate-90')} />
          </button>
          {showReport && (
            <div className="rounded-lg bg-slate-50/70 border border-slate-200 p-4 max-h-[400px] overflow-auto">
              <MarkdownRender content={deepReport} />
            </div>
          )}
        </div>
      )}

      {/* 文件分析摘要 */}
      {analysis && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-slate-50/60 border border-slate-100 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
              <GitBranch size={10} /> 分支
            </div>
            <p className="text-xs font-mono font-medium text-slate-700">{analysis.git.branch}</p>
          </div>
          <div className="rounded-lg bg-slate-50/60 border border-slate-100 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
              <FileText size={10} /> 最近提交
            </div>
            <p className="text-xs font-mono text-slate-700 truncate">{analysis.git.last_commit.slice(0, 14)}</p>
          </div>
          <div className="rounded-lg bg-slate-50/60 border border-slate-100 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1">
              <Code2 size={10} /> 文件数
            </div>
            <p className="text-xs font-mono font-medium text-slate-700">{analysis.total_files}</p>
          </div>
          {Object.keys(analysis.file_stats).length > 0 && (
            <div className="col-span-3">
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(analysis.file_stats)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 8)
                  .map(([ext, count]) => (
                    <span key={ext} className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-50/60 border border-slate-100 text-[10px] font-mono text-slate-600">
                      {ext || '?'} <span className="font-bold text-slate-500">{count}</span>
                    </span>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 未分析状态 */}
      {!deepReport && !analysis && (
        <p className="text-xs text-slate-400 text-center py-3">
          点击「AI 深度分析」获取项目代码分析报告
        </p>
      )}
    </div>
  );
}

// ─── 项目卡片 ───────────────────────────────────────

function ProjectCard({
  project,
  expanded,
  analysis,
  deepReport,
  analysisProgress,
  onToggle,
  onOpen,
  onDeepAnalyze,
  onBrainstorm,
}: {
  project: ProjectInfo;
  expanded: boolean;
  analysis: ProjectAnalysis | null;
  deepReport: string | null;
  analysisProgress: AnalysisProgress | null;
  onToggle: () => void;
  onOpen: () => void;
  onDeepAnalyze: () => void;
  onBrainstorm: () => void;
}) {
  return (
    <div className={cn(
      'rounded-xl border transition-all bg-white',
      expanded ? 'border-slate-300 shadow-sm' : 'border-slate-200 hover:border-slate-300 hover:shadow-sm',
    )}>
      <button onClick={onToggle} className="w-full text-left px-4 py-3.5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-400 shrink-0">
            <FolderOpen size={16} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900 truncate">{project.name}</span>
              {project.has_ralph && (
                <span className="shrink-0 text-[10px] font-medium bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded-md">Ralph</span>
              )}
            </div>
            <p className="text-[11px] text-slate-400 font-mono truncate mt-0.5">{project.path}</p>
            <div className="flex items-center gap-3 mt-1.5">
              {project.last_opened_at && (
                <span className="flex items-center gap-1 text-[10px] text-slate-400">
                  <Clock size={9} />{formatDate(project.last_opened_at)}
                </span>
              )}
              {project.work_unit_count != null && project.work_unit_count > 0 && (
                <span className="flex items-center gap-1 text-[10px] text-slate-400">
                  <Terminal size={9} />{project.work_unit_count} 个任务
                </span>
              )}
            </div>
          </div>
          <ChevronRight size={14} className={cn(
            'mt-1 text-slate-300 transition-transform duration-200',
            expanded && 'rotate-90',
          )} />
        </div>
      </button>

      {expanded && (
        <ProjectExpanded
          project={project}
          analysis={analysis}
          deepReport={deepReport}
          analysisProgress={analysisProgress}
          onOpen={onOpen}
          onDeepAnalyze={onDeepAnalyze}
          onBrainstorm={onBrainstorm}
        />
      )}
    </div>
  );
}

// ─── 目录选择器 ─────────────────────────────────────

function DirPickerModal({ onClose, onConfirm }: {
  onClose: () => void;
  onConfirm: (path: string) => void;
}) {
  const [currentPath, setCurrentPath] = useState('/Users');
  const [entries, setEntries] = useState<FsEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const navigate = async (dirPath: string) => {
    setLoading(true);
    try {
      const result = await browseFs(dirPath);
      setCurrentPath(result.path);
      setEntries(result.entries);
    } catch {
      toast.error('无法访问该目录');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void navigate('/Users'); }, []);

  const handleGoUp = () => {
    if (currentPath === '/') return;
    void navigate(currentPath.split('/').slice(0, -1).join('/') || '/');
  };

  const handleSelect = (entry: FsEntry) => {
    if (entry.is_dir) {
      void navigate(entry.path);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-900">选择目录</h3>
          <p className="text-[10px] text-slate-400 mt-0.5 truncate font-mono">{currentPath}</p>
        </div>
        <div className="max-h-64 overflow-auto py-1">
          {currentPath !== '/' && (
            <button onClick={handleGoUp}
              className="w-full px-4 py-2 text-left text-sm text-slate-500 hover:bg-slate-50 flex items-center gap-2">
              <span className="text-slate-400">↑</span> 返回上级
            </button>
          )}
          {loading && <p className="px-4 py-3 text-xs text-slate-400">加载中...</p>}
          {!loading && entries.length === 0 && <p className="px-4 py-3 text-xs text-slate-400">空目录</p>}
          {entries.map((e) => (
            <button key={e.path} onClick={() => handleSelect(e)}
              className="w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-blue-50 flex items-center gap-2">
              <span className="text-slate-400">{e.is_dir ? '📁' : '📄'}</span>
              {e.name}
            </button>
          ))}
        </div>
        <div className="px-4 py-3 border-t border-slate-100 flex gap-2">
          <button onClick={() => { onConfirm(currentPath); onClose(); }}
            className="flex-1 h-8 text-xs font-medium rounded-lg bg-slate-800 text-white hover:bg-slate-700">
            选择此目录
          </button>
          <button onClick={onClose}
            className="h-8 px-3 text-xs rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50">
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── 新建项目弹窗 ───────────────────────────────────

function NewProjectModal({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const router = useRouter();
  const { setCurrentProject } = useRalphStore();
  const [path, setPath] = useState('');
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [showDirPicker, setShowDirPicker] = useState(false);

  const handleCreate = async () => {
    if (!path) return;
    setCreating(true);
    try {
      const result = await initProject(path, name || path.split('/').pop() || 'untitled');
      setCurrentProject({ name: result.name as string, path: result.path as string });
      toast.success('项目已创建');
      onCreated();
      onClose();
      router.push('/ralph/brainstorm');
    } catch (e) {
      if (e instanceof Error && 'responseBody' in e) {
        const detail = (e as { responseBody: unknown }).responseBody;
        const msg = typeof detail === 'object' && detail !== null && 'detail' in detail
          ? String((detail as Record<string, string>).detail)
          : e.message;
        toast.error(msg);
      } else {
        toast.error('创建失败');
      }
    }
    finally { setCreating(false); }
  };

  return (
    <>
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-800 text-white"><Plus size={14} /></div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">新建项目</h2>
              <p className="text-[10px] text-slate-400">指定目录创建新项目</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-slate-100 text-slate-400">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div className="space-y-3.5">
          <div>
            <label className="text-[11px] font-medium text-slate-600 mb-1 block">项目路径</label>
            <div className="flex gap-2">
              <input value={path} onChange={(e) => { setPath(e.target.value); if (!name) setName(e.target.value.split('/').pop() || ''); }}
                className="flex-1 h-9 px-3 text-sm rounded-lg border border-slate-200 outline-none focus:border-slate-400 transition-colors"
                placeholder="/Users/xxx/my-project" />
              <button onClick={() => setShowDirPicker(true)}
                className="h-9 px-3 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors whitespace-nowrap">
                浏览
              </button>
            </div>
          </div>
          <div>
            <label className="text-[11px] font-medium text-slate-600 mb-1 block">项目名称（可选）</label>
            <input value={name} onChange={(e) => setName(e.target.value)}
              className="w-full h-9 px-3 text-sm rounded-lg border border-slate-200 outline-none focus:border-slate-400 transition-colors"
              placeholder={path ? path.split('/').pop() || 'untitled' : 'My Project'} />
          </div>
        </div>
        <div className="flex items-center gap-2 mt-5 pt-4 border-t border-slate-100">
          <button onClick={handleCreate} disabled={creating || !path}
            className="flex-1 h-9 text-sm font-medium rounded-lg bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-40 transition-colors">
            {creating ? '创建中...' : '创建'}
          </button>
          <button onClick={onClose}
            className="h-9 px-4 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors">取消</button>
        </div>
      </div>
    </div>
    {showDirPicker && (
      <DirPickerModal onClose={() => setShowDirPicker(false)} onConfirm={(p) => { setPath(p); if (!name) setName(p.split('/').pop() || ''); }} />
    )}
    </>
  );
}

// ─── 空状态 ─────────────────────────────────────────

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="flex items-center justify-center h-16 w-16 rounded-2xl bg-slate-50 mb-5">
        <History size={28} className="text-slate-300" />
      </div>
      <h2 className="text-lg font-semibold text-slate-500 mb-1">还没有项目</h2>
      <p className="text-sm text-slate-400 mb-7">创建一个新项目，或直接打开已有代码目录</p>
      <button onClick={onCreate}
        className="flex items-center gap-2 h-10 px-5 text-sm font-medium rounded-xl bg-slate-800 text-white hover:bg-slate-700 transition-colors">
        <Plus size={15} />新建项目
      </button>
    </div>
  );
}

// ─── 主页面 ─────────────────────────────────────────

export default function ProjectsPage() {
  const router = useRouter();
  const { currentProject, setCurrentProject } = useRalphStore();
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedPath, setExpandedPath] = useState<string | null>(null);
  const [analysisMap, setAnalysisMap] = useState<Record<string, ProjectAnalysis>>({});
  const [deepReportMap, setDeepReportMap] = useState<Record<string, string>>({});
  const [showNewModal, setShowNewModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  // 分析进度（持久化到 localStorage，切换页面不丢失）
  const [analysisProgressMap, setAnalysisProgressMap] = useState<Record<string, AnalysisProgress>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listProjects();
      setProjects(list);
      if (currentProject && !expandedPath) {
        const cur = list.find((p) => p.path === currentProject.path);
        if (cur) setExpandedPath(cur.path);
      }
    } catch { toast.error('加载项目列表失败'); }
    finally { setLoading(false); }
  }, [currentProject, expandedPath]);

  useEffect(() => { void load(); }, [load]);

  // 启动时从 localStorage 恢复分析进度
  useEffect(() => {
    const saved = loadAnalysisProgress();
    // 只恢复 running/starting 状态（旧的状态不恢复）
    const active: Record<string, AnalysisProgress> = {};
    for (const [path, prog] of Object.entries(saved)) {
      if (prog.status === 'running' || prog.status === 'starting') {
        active[path] = prog;
      }
    }
    if (Object.keys(active).length > 0) {
      setAnalysisProgressMap(active);
    }
  }, []);

  // 持久化分析进度到 localStorage
  useEffect(() => {
    saveAnalysisProgress(analysisProgressMap);
  }, [analysisProgressMap]);

  // 轮询正在进行的分析
  useEffect(() => {
    const running = Object.entries(analysisProgressMap)
      .filter(([, p]) => p.status === 'starting' || p.status === 'running');

    if (running.length === 0) return;

    const interval = setInterval(async () => {
      for (const [path] of running) {
        try {
          const res = await fetch(`/api/ralph/projects/analysis-progress?path=${encodeURIComponent(path)}`);
          if (!res.ok) continue;
          const data = await res.json();
          setAnalysisProgressMap((prev) => ({ ...prev, [path]: data }));

          if (data.status === 'complete' && data.report) {
            setDeepReportMap((prev) => ({ ...prev, [path]: data.report }));
            toast.success('深度分析完成');
          } else if (data.status === 'error') {
            toast.error(`分析失败: ${data.error || data.message}`);
          }
        } catch { /* 网络错误，下次重试 */ }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [analysisProgressMap]);

  // 展开时加载已有分析结果
  useEffect(() => {
    if (!expandedPath) return;
    const p = projects.find((x) => x.path === expandedPath);
    if (!p) return;

    if (!analysisMap[expandedPath] && p.has_ralph) {
      getProjectAnalysis()
        .then((res) => {
          if (res?.analysis) setAnalysisMap((prev) => ({ ...prev, [expandedPath!]: res.analysis }));
        })
        .catch(() => {});
    }

    if (!deepReportMap[expandedPath]) {
      fetch(`/api/ralph/projects/report?path=${encodeURIComponent(expandedPath)}`)
        .then((res) => res.ok ? res.json() : null)
        .then((data) => {
          if (data?.report) setDeepReportMap((prev) => ({ ...prev, [expandedPath!]: data.report }));
        })
        .catch(() => {});
    }
  }, [expandedPath, analysisMap, deepReportMap, projects]);

  const handleOpen = async (p: ProjectInfo) => {
    try {
      const result = await openProject(p.path);
      setCurrentProject({ name: (result.name as string) || p.name, path: p.path });
      toast.success(`已打开: ${p.name}`);
      router.push('/ralph');
    } catch { toast.error('打开项目失败'); }
  };

  const handleDeepAnalyze = async (p: ProjectInfo) => {
    // 立即设置初始进度
    setAnalysisProgressMap((prev) => ({
      ...prev,
      [p.path]: { status: 'starting', progress: 0, phase: '启动中', message: '正在启动分析...', currentFile: null },
    }));

    try {
      const res = await fetch('/api/ralph/projects/deep-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: p.path }),
      });
      if (!res.ok) throw new Error(`启动分析失败: HTTP ${res.status}`);
      const data = await res.json();
      if (data.already_running) {
        toast.info('分析已在后台运行');
      }
    } catch (e: any) {
      setAnalysisProgressMap((prev) => ({
        ...prev,
        [p.path]: { status: 'error', progress: 0, phase: '启动失败', message: e.message || '请检查后端是否运行', currentFile: null },
      }));
      toast.error(`分析失败: ${e.message || '请检查后端是否运行'}`);
    }
  };

  const handleBrainstorm = (p: ProjectInfo) => {
    setCurrentProject({ name: p.name, path: p.path });
    router.push('/ralph/brainstorm');
  };

  const filtered = searchQuery
    ? projects.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.path.toLowerCase().includes(searchQuery.toLowerCase()))
    : projects;

  return (
    <div className="max-w-2xl mx-auto px-6 py-6">
      {/* 顶栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-base font-semibold text-slate-900">项目管理</h1>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {currentProject ? `当前: ${currentProject.name}` : '选择一个项目开始工作'}
          </p>
        </div>
        <button onClick={() => setShowNewModal(true)}
          className="flex items-center gap-1.5 h-8 px-3.5 text-sm font-medium rounded-xl bg-slate-800 text-white hover:bg-slate-700 transition-colors">
          <Plus size={14} />新建项目
        </button>
      </div>

      {/* 搜索 */}
      {projects.length > 0 && (
        <div className="relative mb-4">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 pl-9 pr-3 text-sm rounded-xl border border-slate-200 outline-none focus:border-slate-400 transition-colors"
            placeholder="搜索项目..." />
        </div>
      )}

      {/* 项目列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-400">
          <RefreshCw size={14} className="animate-spin mr-2" />加载中...
        </div>
      ) : filtered.length === 0 ? (
        searchQuery ? (
          <div className="text-center py-20 text-slate-400">
            <Search size={24} className="mx-auto mb-2" />
            <p className="text-sm">未匹配到 "{searchQuery}"</p>
          </div>
        ) : (
          <EmptyState onCreate={() => setShowNewModal(true)} />
        )
      ) : (
        <div className="space-y-2">
          {filtered.map((p) => (
            <ProjectCard
              key={p.path}
              project={p}
              expanded={expandedPath === p.path}
              analysis={analysisMap[p.path] || null}
              deepReport={deepReportMap[p.path] || null}
              analysisProgress={analysisProgressMap[p.path] || null}
              onToggle={() => setExpandedPath(expandedPath === p.path ? null : p.path)}
              onOpen={() => handleOpen(p)}
              onDeepAnalyze={() => handleDeepAnalyze(p)}
              onBrainstorm={() => handleBrainstorm(p)}
            />
          ))}
        </div>
      )}

      {showNewModal && (
        <NewProjectModal onClose={() => setShowNewModal(false)} onCreated={() => load()} />
      )}
    </div>
  );
}
