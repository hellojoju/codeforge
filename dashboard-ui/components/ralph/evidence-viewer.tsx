/**
 * EvidenceViewer - 证据文件查看器组件
 *
 * 双栏布局：左侧文件列表，右侧内容预览
 */

import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { listEvidence, getEvidenceFile } from '@/lib/ralph-api';
import type { Evidence } from '@/lib/ralph-types';
import { Code, Terminal, Image, FileText, File } from 'lucide-react';

interface EvidenceViewerProps {
  workId: string;
  className?: string;
}

/**
 * 文件类型图标映射
 */
const FILE_TYPE_ICONS: Record<Evidence['file_type'], React.ReactNode> = {
  diff: <Code size={16} />,
  test_output: <Terminal size={16} />,
  lint: <Terminal size={16} />,
  // eslint-disable-next-line jsx-a11y/alt-text
  screenshot: <Image size={16} />,
  log: <FileText size={16} />,
  other: <File size={16} />,
};

/**
 * 文件类型标签映射
 */
const FILE_TYPE_LABELS: Record<Evidence['file_type'], string> = {
  diff: '代码差异',
  test_output: '测试结果',
  lint: '代码检查',
  screenshot: '截图',
  log: '日志',
  other: '其他',
};

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * 文件列表项组件
 */
interface EvidenceListItemProps {
  evidence: Evidence;
  isSelected: boolean;
  onClick: () => void;
}

function EvidenceListItem({ evidence, isSelected, onClick }: EvidenceListItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-3 p-3 text-left',
        'border-b border-border last:border-b-0',
        'hover:bg-muted/50 transition-colors duration-200',
        isSelected && 'bg-muted'
      )}
    >
      <span className="flex-shrink-0 text-muted-foreground mt-0.5">
        {FILE_TYPE_ICONS[evidence.file_type]}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-mono text-sm truncate text-foreground">
          {evidence.file_name}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">
            {FILE_TYPE_LABELS[evidence.file_type]}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatFileSize(evidence.size_bytes)}
          </span>
        </div>
      </div>
    </button>
  );
}

/**
 * 内容预览组件
 */
interface ContentPreviewProps {
  content: string | null;
  loading: boolean;
  fileName: string;
  fileType: Evidence['file_type'];
}

function ContentPreview({ content, loading, fileName, fileType }: ContentPreviewProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-sm text-muted-foreground">加载中...</span>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-sm text-muted-foreground">选择文件查看内容</span>
      </div>
    );
  }

  const isImage = fileType === 'screenshot';

  if (isImage) {
    return (
      <div className="flex items-center justify-center h-full p-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/png;base64,${content}`}
          alt={fileName}
          className="max-w-full max-h-full object-contain"
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <pre className="font-mono text-sm p-4 whitespace-pre">
        <code>{content}</code>
      </pre>
    </div>
  );
}

/**
 * EvidenceViewer 组件
 */
export function EvidenceViewer({ workId, className }: EvidenceViewerProps) {
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载证据文件列表
  useEffect(() => {
    let cancelled = false;

    async function loadEvidence() {
      setListLoading(true);
      setError(null);

      try {
        const list = await listEvidence(workId);
        if (!cancelled) {
          setEvidenceList(list);
          // 自动选择第一个文件
          if (list.length > 0 && !selectedEvidence) {
            setSelectedEvidence(list[0]);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载失败');
        }
      } finally {
        if (!cancelled) {
          setListLoading(false);
        }
      }
    }

    loadEvidence();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workId]);

  // 加载选中文件的内容
  useEffect(() => {
    let cancelled = false;
    const fileName = selectedEvidence?.file_name;

    async function loadContent() {
      if (!fileName) {
        setContent(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const fileContent = await getEvidenceFile(workId, fileName);
        if (!cancelled) {
          setContent(fileContent);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '加载内容失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadContent();

    return () => {
      cancelled = true;
    };
  }, [workId, selectedEvidence?.file_name]);

  const handleSelectEvidence = useCallback((evidence: Evidence) => {
    setSelectedEvidence(evidence);
  }, []);

  // 如果没有证据文件，返回 null（不渲染）
  if (!listLoading && evidenceList.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex border border-border rounded-sm overflow-hidden',
        'h-[500px] bg-card shadow-sm',
        className
      )}
    >
      {/* 左侧：文件列表 */}
      <div className="w-1/3 border-r border-border flex flex-col">
        <div className="px-3 py-2 border-b border-border bg-muted/30">
          <h3 className="text-sm font-medium text-foreground">证据文件</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {evidenceList.length} 个文件
          </p>
        </div>
        <div className="flex-1 overflow-auto">
          {listLoading ? (
            <div className="flex items-center justify-center h-32">
              <span className="text-sm text-muted-foreground">加载中...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-32 px-4">
              <span className="text-sm text-red-500 text-center">{error}</span>
            </div>
          ) : (
            evidenceList.map((evidence) => (
              <EvidenceListItem
                key={evidence.evidence_id}
                evidence={evidence}
                isSelected={selectedEvidence?.evidence_id === evidence.evidence_id}
                onClick={() => handleSelectEvidence(evidence)}
              />
            ))
          )}
        </div>
      </div>

      {/* 右侧：内容预览 */}
      <div className="w-2/3 flex flex-col">
        <div className="px-3 py-2 border-b border-border bg-muted/30">
          <h3 className="text-sm font-medium text-foreground">
            {selectedEvidence ? selectedEvidence.file_name : '内容预览'}
          </h3>
          {selectedEvidence && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {FILE_TYPE_LABELS[selectedEvidence.file_type]} · {formatFileSize(selectedEvidence.size_bytes)}
            </p>
          )}
        </div>
        <div className="flex-1 overflow-hidden">
          <ContentPreview
            content={content}
            loading={loading}
            fileName={selectedEvidence?.file_name || ''}
            fileType={selectedEvidence?.file_type || 'other'}
          />
        </div>
      </div>
    </div>
  );
}

export default EvidenceViewer;
