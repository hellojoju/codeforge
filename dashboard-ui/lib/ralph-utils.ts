/**
 * Ralph Runtime Console - 工具函数
 *
 * 提供状态映射、ID生成、文本处理等通用工具函数
 */

// ==================== ID 生成 ====================

/**
 * 生成 Tab ID
 * 格式: tab-{timestamp}-{random}
 * @returns Tab ID 字符串
 */
export function generateTabId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 6);
  return `tab-${timestamp}-${random}`;
}

/**
 * 生成幂等性键
 * 格式: idem-{timestamp}-{random}
 * @returns 幂等性键字符串
 */
export function generateIdempotencyKey(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `idem-${timestamp}-${random}`;
}

// ==================== 文本处理 ====================

/**
 * 截断标签文本
 * @param label - 原始标签文本
 * @param maxLen - 最大长度
 * @returns 截断后的文本（超长时添加省略号）
 */
export function truncateLabel(label: string, maxLen: number): string {
  if (label.length <= maxLen) {
    return label;
  }
  return label.substring(0, maxLen - 1) + '…';
}

// ==================== 状态映射 ====================

/**
 * 状态中文标签映射
 * @param status - 状态码
 * @returns 中文状态标签
 */
export function statusLabel(status: string): string {
  const labelMap: Record<string, string> = {
    draft: '草稿',
    ready: '就绪',
    pending: '待处理',
    running: '运行中',
    paused: '已暂停',
    needs_review: '待审核',
    accepted: '已验收',
    needs_rework: '需返工',
    rejected: '已驳回',
    blocked: '已阻塞',
    failed: '失败',
    completed: '已完成',
    cancelled: '已取消',
  };
  return labelMap[status] || status;
}

/**
 * 状态颜色映射（Tailwind CSS 类名）
 * @param status - 状态码
 * @returns Tailwind 颜色类名
 */
export function statusColor(status: string): string {
  const colorMap: Record<string, string> = {
    draft: 'text-gray-400',
    ready: 'text-green-500',
    pending: 'text-gray-500',
    running: 'text-blue-500',
    paused: 'text-amber-500',
    needs_review: 'text-yellow-500',
    needs_rework: 'text-orange-500',
    accepted: 'text-emerald-500',
    rejected: 'text-orange-600',
    blocked: 'text-red-500',
    failed: 'text-red-600',
    completed: 'text-emerald-500',
    cancelled: 'text-gray-400',
  };
  return colorMap[status] || 'text-gray-500';
}

// ==================== 日期格式化 ====================

/**
 * 格式化日期为中文本地化字符串
 * @param dateStr - ISO 日期字符串
 * @returns 格式化后的中文日期字符串
 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);

  if (isNaN(date.getTime())) {
    return '无效日期';
  }

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  // 相对时间
  if (diffSec < 60) {
    return '刚刚';
  }
  if (diffMin < 60) {
    return `${diffMin}分钟前`;
  }
  if (diffHour < 24) {
    return `${diffHour}小时前`;
  }
  if (diffDay < 7) {
    return `${diffDay}天前`;
  }

  // 绝对时间
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hour = date.getHours().toString().padStart(2, '0');
  const minute = date.getMinutes().toString().padStart(2, '0');

  const isThisYear = year === now.getFullYear();

  if (isThisYear) {
    return `${month}月${day}日 ${hour}:${minute}`;
  }

  return `${year}年${month}月${day}日 ${hour}:${minute}`;
}
