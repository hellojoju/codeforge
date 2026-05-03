/**
 * GlobalSearch — Cmd+K 全局搜索弹窗
 *
 * 搜索 WorkUnit（work_id/title/target）和 Command（command_id/type/target_id）
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, ListTodo, Terminal, CornerDownLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRalphStore } from '@/lib/ralph-store';
import { statusColor, statusLabel } from '@/lib/ralph-utils';
import type { WorkUnit, RalphCommand } from '@/lib/ralph-types';
import { listCommands } from '@/lib/ralph-api';

interface SearchResult {
  type: 'work_unit' | 'command';
  title: string;
  subtitle: string;
  url: string;
  object: WorkUnit | RalphCommand;
}

export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [commands, setCommands] = useState<RalphCommand[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const { workUnits } = useRalphStore();

  // Load recent commands for search
  useEffect(() => {
    listCommands().then(setCommands).catch(() => {});
  }, []);

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  // Search
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setSelectedIndex(0);
      return;
    }

    const q = query.toLowerCase();
    const items: SearchResult[] = [];

    for (const wu of workUnits) {
      if (wu.work_id.toLowerCase().includes(q) || wu.title.toLowerCase().includes(q) || wu.target.toLowerCase().includes(q)) {
        items.push({
          type: 'work_unit',
          title: wu.title,
          subtitle: `${wu.work_id} · ${statusLabel(wu.status)} · ${wu.work_type}`,
          url: `/ralph/${wu.work_id}`,
          object: wu,
        });
      }
    }

    for (const cmd of commands) {
      if (cmd.command_id.toLowerCase().includes(q) || cmd.command_type.toLowerCase().includes(q) || cmd.target_id.toLowerCase().includes(q)) {
        items.push({
          type: 'command',
          title: cmd.command_type,
          subtitle: `${cmd.command_id} · ${cmd.status} · → ${cmd.target_id}`,
          url: '/ralph/commands',
          object: cmd,
        });
      }
    }

    // Limit to 20 results
    setResults(items.slice(0, 20));
    setSelectedIndex(0);
  }, [query, workUnits, commands]);

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(results.length, 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + results.length) % Math.max(results.length, 1));
    } else if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault();
      const selected = results[selectedIndex];
      if (selected) {
        if (selected.type === 'work_unit') {
          useRalphStore.getState().addTab({
            label: selected.title,
            type: 'work_unit',
            work_id: (selected.object as WorkUnit).work_id,
            pinned: false,
          });
        }
        router.push(selected.url);
        setOpen(false);
      }
    }
  }, [results, selectedIndex, router]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />

      {/* Dialog */}
      <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg">
        <div className="bg-white rounded-lg border border-slate-200 shadow-2xl overflow-hidden">
          {/* Input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
            <Search size={16} className="text-slate-400 flex-shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="搜索 WorkUnit、命令..."
              className="flex-1 text-sm outline-none placeholder:text-slate-400 text-slate-900"
            />
            <kbd className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
              ESC
            </kbd>
          </div>

          {/* Results */}
          <div className="max-h-80 overflow-auto">
            {query && results.length === 0 && (
              <div className="py-12 text-center text-sm text-slate-400">
                无匹配结果
              </div>
            )}

            {!query && (
              <div className="py-12 text-center">
                <Search size={24} className="text-slate-200 mx-auto mb-2" />
                <p className="text-sm text-slate-400">输入关键词搜索</p>
                <p className="text-xs text-slate-400 mt-1">
                  搜索范围：WorkUnit ID/标题/目标，Command ID/类型/目标
                </p>
              </div>
            )}

            {results.map((item, i) => {
              const isWorkUnit = item.type === 'work_unit';
              const wu = isWorkUnit ? item.object as WorkUnit : null;
              return (
                <button
                  key={`${item.type}-${isWorkUnit ? (item.object as WorkUnit).work_id : (item.object as RalphCommand).command_id}`}
                  onClick={() => {
                    if (item.type === 'work_unit') {
                      useRalphStore.getState().addTab({
                        label: item.title,
                        type: 'work_unit',
                        work_id: (item.object as WorkUnit).work_id,
                        pinned: false,
                      });
                    }
                    router.push(item.url);
                    setOpen(false);
                  }}
                  className={cn(
                    'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
                    i === selectedIndex ? 'bg-slate-100' : 'hover:bg-slate-50',
                  )}
                >
                  {/* Icon */}
                  <div className={cn(
                    'flex-shrink-0 h-8 w-8 rounded-md flex items-center justify-center',
                    isWorkUnit ? 'bg-blue-50' : 'bg-slate-100',
                  )}>
                    {isWorkUnit
                      ? <ListTodo size={14} className="text-blue-500" />
                      : <Terminal size={14} className="text-slate-500" />
                    }
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 truncate">
                        {item.title}
                      </span>
                      {wu && (
                        <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', statusColor(wu.status))} />
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 truncate mt-0.5">{item.subtitle}</p>
                  </div>

                  {/* Hint */}
                  {i === selectedIndex && (
                    <CornerDownLeft size={12} className="text-slate-300 flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center gap-3 px-4 py-2 border-t border-slate-100 text-[10px] text-slate-400">
            <span><kbd className="font-mono bg-slate-100 px-1 rounded">↑↓</kbd> 导航</span>
            <span><kbd className="font-mono bg-slate-100 px-1 rounded">Enter</kbd> 打开</span>
            <span><kbd className="font-mono bg-slate-100 px-1 rounded">Esc</kbd> 关闭</span>
            <span className="ml-auto">{results.length} 结果</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default GlobalSearch;
