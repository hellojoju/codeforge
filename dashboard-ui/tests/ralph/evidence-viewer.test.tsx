import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EvidenceViewer } from '@/components/ralph/evidence-viewer';
import * as apiModule from '@/lib/ralph-api';
import type { Evidence } from '@/lib/ralph-types';

// Mock the API module
vi.mock('@/lib/ralph-api', () => ({
  listEvidence: vi.fn(),
  getEvidenceFile: vi.fn(),
}));

const mockListEvidence = vi.mocked(apiModule.listEvidence);
const mockGetEvidenceFile = vi.mocked(apiModule.getEvidenceFile);

describe('EvidenceViewer', () => {
  const mockEvidence: Evidence[] = [
    {
      evidence_id: 'ev-1',
      work_id: 'work-1',
      file_name: 'changes.diff',
      file_type: 'diff',
      size_bytes: 1024,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      evidence_id: 'ev-2',
      work_id: 'work-1',
      file_name: 'test-output.txt',
      file_type: 'test_output',
      size_bytes: 2048,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      evidence_id: 'ev-3',
      work_id: 'work-1',
      file_name: 'screenshot.png',
      file_type: 'screenshot',
      size_bytes: 51200,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      evidence_id: 'ev-4',
      work_id: 'work-1',
      file_name: 'app.log',
      file_type: 'log',
      size_bytes: 4096,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      evidence_id: 'ev-5',
      work_id: 'work-1',
      file_name: 'lint-report.txt',
      file_type: 'lint',
      size_bytes: 1024,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      evidence_id: 'ev-6',
      work_id: 'work-1',
      file_name: 'readme.md',
      file_type: 'other',
      size_bytes: 512,
      created_at: '2024-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders null when no evidence files', async () => {
    mockListEvidence.mockResolvedValue([]);

    const { container } = render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it('renders file list with correct layout', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('file content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getByText('证据文件')).toBeTruthy();
    });

    // Check file names are displayed in the list (using getAllByText since they appear in both list and preview header)
    expect(screen.getAllByText('changes.diff').length).toBeGreaterThan(0);
    expect(screen.getAllByText('test-output.txt').length).toBeGreaterThan(0);
    expect(screen.getAllByText('screenshot.png').length).toBeGreaterThan(0);
  });

  it('displays correct file type labels', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('file content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getByText('代码差异')).toBeTruthy();
    });

    expect(screen.getByText('测试结果')).toBeTruthy();
    expect(screen.getByText('截图')).toBeTruthy();
    expect(screen.getByText('日志')).toBeTruthy();
    expect(screen.getByText('代码检查')).toBeTruthy();
    expect(screen.getByText('其他')).toBeTruthy();
  });

  it('displays correct file sizes', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('file content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getAllByText('1.0 KB').length).toBeGreaterThan(0);
    });

    expect(screen.getAllByText('2.0 KB').length).toBeGreaterThan(0);
    expect(screen.getAllByText('50.0 KB').length).toBeGreaterThan(0);
  });

  it('auto-selects first file on load', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('diff content here');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(mockGetEvidenceFile).toHaveBeenCalledWith('work-1', 'changes.diff');
    });
  });

  it('loads file content when clicking on file', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('file content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getAllByText('changes.diff').length).toBeGreaterThan(0);
    });

    // Click on second file (find in the list buttons)
    const buttons = screen.getAllByRole('button');
    const secondFileButton = buttons.find(btn => btn.textContent?.includes('test-output.txt'));
    expect(secondFileButton).toBeTruthy();
    fireEvent.click(secondFileButton!);

    await waitFor(() => {
      expect(mockGetEvidenceFile).toHaveBeenCalledWith('work-1', 'test-output.txt');
    });
  });

  it('highlights selected file', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('file content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getAllByText('changes.diff').length).toBeGreaterThan(0);
    });

    // Get all buttons and find the ones containing our file names
    const buttons = screen.getAllByRole('button');
    const firstFileButton = buttons.find(btn => btn.textContent?.includes('changes.diff'));
    const secondFileButton = buttons.find(btn => btn.textContent?.includes('test-output.txt'));

    // First file should be selected (auto-selected)
    expect(firstFileButton?.classList.contains('bg-muted')).toBe(true);

    // Click on second file
    fireEvent.click(secondFileButton!);

    await waitFor(() => {
      expect(secondFileButton?.classList.contains('bg-muted')).toBe(true);
    });
  });

  it('shows loading state for content', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getByText('加载中...')).toBeTruthy();
    });
  });

  it('displays content preview for text files', async () => {
    const content = 'line 1\nline 2\nline 3';
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue(content);

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      // Content is inside a <code> element
      const codeElement = screen.getByText((text) => text.includes('line 1'));
      expect(codeElement).toBeTruthy();
    });
  });

  it('applies custom className', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('content');

    const { container } = render(<EvidenceViewer workId="work-1" className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('证据文件')).toBeTruthy();
    });

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper?.classList.contains('custom-class')).toBe(true);
  });

  it('shows empty state when no file selected', async () => {
    mockListEvidence.mockResolvedValue([]);

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(document.querySelector('.flex')).toBeNull();
    });
  });

  it('handles API error gracefully', async () => {
    mockListEvidence.mockRejectedValue(new Error('Network error'));

    const { container } = render(<EvidenceViewer workId="work-1" />);

    // When listEvidence fails and returns empty list, component returns null
    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it('displays file count in header', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getByText('6 个文件')).toBeTruthy();
    });
  });

  it('uses monospace font for file names', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('content');

    render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      const fileNames = screen.getAllByText('changes.diff');
      expect(fileNames.length).toBeGreaterThan(0);
      // At least one element should have font-mono class
      const hasMonospace = fileNames.some(el => el.classList.contains('font-mono'));
      expect(hasMonospace).toBe(true);
    });
  });

  it('uses rounded-sm for container', async () => {
    mockListEvidence.mockResolvedValue(mockEvidence);
    mockGetEvidenceFile.mockResolvedValue('content');

    const { container } = render(<EvidenceViewer workId="work-1" />);

    await waitFor(() => {
      expect(screen.getByText('证据文件')).toBeTruthy();
    });

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper?.classList.contains('rounded-sm')).toBe(true);
  });
});
