/**
 * 研发报告 — /ralph/reports
 *
 * 浏览已生成的报告、生成新报告、查看报告内容
 */

'use client';

import { useEffect, useState } from 'react';
import { FileText, Plus, RefreshCw, ChevronLeft, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import { listReports, generateReport, getReport, type ReportInfo } from '@/lib/ralph-api';
import { formatDate } from '@/lib/ralph-utils';
import { toast } from 'sonner';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportContent, setReportContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);

  const loadReports = async () => {
    setLoading(true);
    try {
      const list = await listReports();
      setReports(list);
    } catch {
      toast.error('加载报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadReports();
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await generateReport();
      toast.success('报告已生成', { description: result.name });
      await loadReports();
      // Auto-select the new report
      setSelectedReport(result.name);
      setReportContent(result.content);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败');
    } finally {
      setGenerating(false);
    }
  };

  const handleView = async (name: string) => {
    setSelectedReport(name);
    setContentLoading(true);
    try {
      const content = await getReport(name);
      setReportContent(content);
    } catch {
      toast.error('加载报告失败');
      setReportContent(null);
    } finally {
      setContentLoading(false);
    }
  };

  const handleBack = () => {
    setSelectedReport(null);
    setReportContent(null);
  };

  // Report content view
  if (selectedReport) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <button
              onClick={handleBack}
              className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 transition-colors"
            >
              <ChevronLeft size={14} />
              返回列表
            </button>
            <h1 className="text-lg font-semibold text-slate-900">{selectedReport}</h1>
          </div>
        </div>

        {/* Content */}
        {contentLoading ? (
          <div className="flex items-center justify-center py-16 text-sm text-slate-400">
            <RefreshCw size={16} className="animate-spin mr-2" />
            加载中...
          </div>
        ) : reportContent ? (
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div
              className="prose prose-sm max-w-none prose-slate"
              dangerouslySetInnerHTML={{ __html: reportContent }}
            />
            {!reportContent.includes('<') && (
              <pre className="font-mono text-sm text-slate-700 whitespace-pre-wrap">{reportContent}</pre>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center py-16 text-sm text-slate-400">
            无法加载报告内容
          </div>
        )}
      </div>
    );
  }

  // Report list view
  return (
    <div className="max-w-4xl mx-auto px-6 py-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-slate-900">研发报告</h1>
          <p className="text-sm text-slate-500 mt-0.5">浏览和生成研发报告</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className={cn(
            'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors',
            'bg-slate-800 text-white hover:bg-slate-700',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          {generating ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          生成报告
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-sm text-slate-400">
          <RefreshCw size={16} className="animate-spin mr-2" />
          加载中...
        </div>
      )}

      {/* Empty */}
      {!loading && reports.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center mb-3">
            <FileText size={20} className="text-slate-400" />
          </div>
          <p className="text-sm text-slate-500">暂无报告</p>
          <p className="text-xs text-slate-400 mt-1">点击「生成报告」创建第一份研发报告</p>
        </div>
      )}

      {/* Report list */}
      {!loading && reports.length > 0 && (
        <div className="space-y-2">
          {reports.map((report) => (
            <button
              key={report.name}
              onClick={() => handleView(report.name)}
              className={cn(
                'w-full text-left rounded-lg border border-slate-200 bg-white p-4',
                'hover:border-slate-300 hover:bg-slate-50 transition-colors',
              )}
            >
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 h-8 w-8 rounded-md bg-blue-50 flex items-center justify-center">
                  <FileText size={14} className="text-blue-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 truncate">{report.name}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {formatSize(report.size_bytes)} · {formatDate(report.created_at)}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
