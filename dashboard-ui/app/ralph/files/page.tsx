/**
 * 文件浏览器 — /ralph/files
 */

'use client';

import { useEffect, useState } from 'react';
import { Folder, File, ChevronRight, ChevronDown, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getFileTree, getFileContent, type FileEntry } from '@/lib/ralph-api';
import { toast } from 'sonner';

export default function FilesPage() {
  const [tree, setTree] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  useEffect(() => {
    getFileTree(3)
      .then((r) => setTree(r.tree))
      .catch(() => toast.error('加载目录失败'))
      .finally(() => setLoading(false));
  }, []);

  const handleFileClick = async (entry: FileEntry) => {
    if (entry.type === 'dir') return;
    setSelectedFile(entry.path);
    setContentLoading(true);
    try {
      const result = await getFileContent(entry.path);
      setContent(result.content);
    } catch {
      toast.error('加载文件失败');
    } finally { setContentLoading(false); }
  };

  return (
    <div className="flex h-full">
      {/* Left: File tree */}
      <div className="w-72 border-r border-slate-200 bg-white overflow-auto flex-shrink-0">
        <div className="p-3 border-b border-slate-100">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">项目文件</h2>
        </div>
        {loading ? (
          <div className="p-4 text-xs text-slate-400"><RefreshCw size={12} className="animate-spin inline mr-1" />加载中...</div>
        ) : (
          <div className="py-1">
            {tree.map((entry) => (
              <TreeNode key={entry.path} entry={entry} depth={0} selectedFile={selectedFile} onFileClick={handleFileClick} />
            ))}
          </div>
        )}
      </div>

      {/* Right: Content */}
      <div className="flex-1 overflow-auto bg-white">
        {!selectedFile ? (
          <div className="flex items-center justify-center h-full text-sm text-slate-400">
            选择文件查看内容
          </div>
        ) : contentLoading ? (
          <div className="flex items-center justify-center h-full text-sm text-slate-400">
            <RefreshCw size={14} className="animate-spin mr-2" />加载中...
          </div>
        ) : content ? (
          <div>
            <div className="px-4 py-2 border-b border-slate-100 bg-slate-50/50 text-xs font-mono text-slate-500">
              {selectedFile}
            </div>
            <pre className="p-4 font-mono text-sm text-slate-700 whitespace-pre-wrap">{content}</pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TreeNode({ entry, depth, selectedFile, onFileClick }: {
  entry: FileEntry; depth: number; selectedFile: string | null;
  onFileClick: (e: FileEntry) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isFile = entry.type === 'file';
  const isSelected = selectedFile === entry.path;
  const hasChildren = entry.children && entry.children.length > 0;

  return (
    <div>
      <button
        onClick={() => { if (isFile) onFileClick(entry); else setExpanded(!expanded); }}
        className={cn(
          'w-full flex items-center gap-1.5 px-3 py-1.5 text-xs transition-colors hover:bg-slate-50',
          isSelected && 'bg-blue-50 text-blue-700',
          !isSelected && isFile && 'text-slate-600',
          !isSelected && !isFile && 'text-slate-700 font-medium',
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {!isFile && (expanded ? <ChevronDown size={12} className="text-slate-400" /> : <ChevronRight size={12} className="text-slate-400" />)}
        {isFile ? <File size={12} className="text-slate-400 flex-shrink-0" /> : <Folder size={12} className="text-amber-500 flex-shrink-0" />}
        <span className="truncate">{entry.name}</span>
      </button>
      {hasChildren && expanded && entry.children!.map((child) => (
        <TreeNode key={child.path} entry={child} depth={depth + 1} selectedFile={selectedFile} onFileClick={onFileClick} />
      ))}
    </div>
  );
}
