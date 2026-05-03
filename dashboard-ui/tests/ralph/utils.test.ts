import { describe, it, expect } from 'vitest';
import {
  generateTabId,
  generateIdempotencyKey,
  truncateLabel,
  statusLabel,
  statusColor,
  formatDate,
} from '@/lib/ralph-utils';

describe('generateTabId', () => {
  it('should generate tab id with correct format', () => {
    const tabId = generateTabId();
    expect(tabId).toMatch(/^tab-[a-z0-9]+-[a-z0-9]+$/);
  });

  it('should generate unique ids', () => {
    const id1 = generateTabId();
    const id2 = generateTabId();
    expect(id1).not.toBe(id2);
  });

  it('should start with tab- prefix', () => {
    const tabId = generateTabId();
    expect(tabId.startsWith('tab-')).toBe(true);
  });
});

describe('generateIdempotencyKey', () => {
  it('should generate idempotency key with correct format', () => {
    const key = generateIdempotencyKey();
    expect(key).toMatch(/^idem-[a-z0-9]+-[a-z0-9]+$/);
  });

  it('should generate unique keys', () => {
    const key1 = generateIdempotencyKey();
    const key2 = generateIdempotencyKey();
    expect(key1).not.toBe(key2);
  });

  it('should start with idem- prefix', () => {
    const key = generateIdempotencyKey();
    expect(key.startsWith('idem-')).toBe(true);
  });
});

describe('truncateLabel', () => {
  it('should return original label if within max length', () => {
    const label = 'short';
    expect(truncateLabel(label, 10)).toBe('short');
  });

  it('should truncate long labels with ellipsis', () => {
    const label = 'this is a very long label';
    expect(truncateLabel(label, 10)).toBe('this is a…');
  });

  it('should handle exact length', () => {
    const label = 'exactlyten';
    expect(truncateLabel(label, 10)).toBe('exactlyten');
  });

  it('should handle empty string', () => {
    expect(truncateLabel('', 10)).toBe('');
  });

  it('should handle unicode characters', () => {
    const label = '这是一个很长的中文标签';
    // Unicode characters are counted as 1 char each
    expect(truncateLabel(label, 5)).toBe('这是一个…');
  });
});

describe('statusLabel', () => {
  it('should return correct Chinese labels for known statuses', () => {
    expect(statusLabel('pending')).toBe('待处理');
    expect(statusLabel('running')).toBe('运行中');
    expect(statusLabel('paused')).toBe('已暂停');
    expect(statusLabel('needs_review')).toBe('待审核');
    expect(statusLabel('accepted')).toBe('已验收');
    expect(statusLabel('rejected')).toBe('已驳回');
    expect(statusLabel('blocked')).toBe('已阻塞');
    expect(statusLabel('failed')).toBe('失败');
    expect(statusLabel('completed')).toBe('已完成');
    expect(statusLabel('cancelled')).toBe('已取消');
  });

  it('should return original status for unknown status', () => {
    expect(statusLabel('unknown')).toBe('unknown');
    expect(statusLabel('custom_status')).toBe('custom_status');
  });

  it('should handle empty string', () => {
    expect(statusLabel('')).toBe('');
  });
});

describe('statusColor', () => {
  it('should return correct Tailwind color classes for known statuses', () => {
    expect(statusColor('pending')).toBe('text-gray-500');
    expect(statusColor('running')).toBe('text-blue-500');
    expect(statusColor('paused')).toBe('text-amber-500');
    expect(statusColor('needs_review')).toBe('text-yellow-500');
    expect(statusColor('accepted')).toBe('text-emerald-500');
    expect(statusColor('rejected')).toBe('text-orange-600');
    expect(statusColor('blocked')).toBe('text-red-500');
    expect(statusColor('failed')).toBe('text-red-600');
    expect(statusColor('completed')).toBe('text-emerald-500');
    expect(statusColor('cancelled')).toBe('text-gray-400');
  });

  it('should return default gray color for unknown status', () => {
    expect(statusColor('unknown')).toBe('text-gray-500');
    expect(statusColor('custom_status')).toBe('text-gray-500');
  });

  it('should handle empty string', () => {
    expect(statusColor('')).toBe('text-gray-500');
  });
});

describe('formatDate', () => {
  it('should return "刚刚" for dates within 60 seconds', () => {
    const now = new Date().toISOString();
    expect(formatDate(now)).toBe('刚刚');
  });

  it('should return minutes ago for dates within 1 hour', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatDate(fiveMinutesAgo)).toBe('5分钟前');
  });

  it('should return hours ago for dates within 24 hours', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    expect(formatDate(twoHoursAgo)).toBe('2小时前');
  });

  it('should return days ago for dates within 7 days', () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatDate(threeDaysAgo)).toBe('3天前');
  });

  it('should return formatted date without year for this year', () => {
    const thisYear = new Date();
    // Set to 10 days ago to avoid "刚刚" or relative time formats
    thisYear.setDate(thisYear.getDate() - 10);
    thisYear.setHours(14, 30, 0, 0);
    const result = formatDate(thisYear.toISOString());
    expect(result).toMatch(/\d+月\d+日 \d{2}:\d{2}/);
  });

  it('should return formatted date with year for previous years', () => {
    const lastYear = new Date();
    lastYear.setFullYear(lastYear.getFullYear() - 1);
    lastYear.setMonth(5);
    lastYear.setDate(15);
    lastYear.setHours(14, 30, 0, 0);
    const result = formatDate(lastYear.toISOString());
    expect(result).toMatch(/\d{4}年\d+月\d+日 \d{2}:\d{2}/);
  });

  it('should return "无效日期" for invalid date string', () => {
    expect(formatDate('invalid')).toBe('无效日期');
    expect(formatDate('')).toBe('无效日期');
  });
});
