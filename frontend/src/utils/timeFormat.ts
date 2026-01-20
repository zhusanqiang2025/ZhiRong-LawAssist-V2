/**
 * 时间格式化工具函数
 */

/**
 * 格式化相对时间显示
 * @param dateString ISO格式日期字符串
 * @returns 相对时间字符串，如"10分钟前"
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 60000); // 分钟

  if (diff < 1) return '刚刚';
  if (diff < 60) return `${diff}分钟前`;
  if (diff < 1440) return `${Math.floor(diff / 60)}小时前`;
  if (diff < 43200) return `${Math.floor(diff / 1440)}天前`;
  return date.toLocaleDateString('zh-CN');
}

/**
 * 格式化完整日期时间
 * @param dateString ISO格式日期字符串
 * @returns 格式化的日期时间字符串
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * 格式化短日期（月-日）
 * @param dateString ISO格式日期字符串
 * @returns 格式化的短日期字符串
 */
export function formatShortDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  });
}

/**
 * 格式化时间（时:分）
 * @param dateString ISO格式日期字符串
 * @returns 格式化的时间字符串
 */
export function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * 判断日期是否为今天
 * @param dateString ISO格式日期字符串
 * @returns 是否为今天
 */
export function isToday(dateString: string): boolean {
  const date = new Date(dateString);
  const today = new Date();
  return (
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  );
}

/**
 * 判断日期是否为本周
 * @param dateString ISO格式日期字符串
 * @returns 是否为本周
 */
export function isThisWeek(dateString: string): boolean {
  const date = new Date(dateString);
  const today = new Date();
  const diffTime = date.getTime() - today.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
  return diffDays >= -7 && diffDays <= 0;
}
