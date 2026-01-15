/**
 * 格式化工具函数
 */

/**
 * 格式化日期为中文格式
 * @param dateString - 日期字符串 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS)
 * @returns 格式化后的日期 (2024年1月15日)
 */
export function formatDate(dateString: string): string {
  if (!dateString) return '-';
  
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    
    return `${year}年${month}月${day}日`;
  } catch {
    return dateString;
  }
}

/**
 * 格式化日期时间为中文格式
 * @param dateString - 日期时间字符串
 * @returns 格式化后的日期时间 (2024年1月15日 14:30:25)
 */
export function formatDateTime(dateString: string): string {
  if (!dateString) return '-';
  
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    const dateStr = formatDate(dateString);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const seconds = date.getSeconds().toString().padStart(2, '0');
    
    return `${dateStr} ${hours}:${minutes}:${seconds}`;
  } catch {
    return dateString;
  }
}

/**
 * 格式化金额为千分位
 * @param amount - 金额数字
 * @param withCurrency - 是否包含货币符号
 * @returns 格式化后的金额 (¥1,000,000.00)
 */
export function formatCurrency(amount: number, withCurrency: boolean = true): string {
  if (typeof amount !== 'number' || isNaN(amount)) return '-';
  
  const formatted = amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
  
  return withCurrency ? `¥${formatted}` : formatted;
}

/**
 * 格式化金额为万元单位
 * @param amount - 金额数字
 * @param withCurrency - 是否包含货币符号
 * @returns 格式化后的金额 (¥100.00万)
 */
export function formatAmountInWan(amount: number, withCurrency: boolean = true): string {
  if (typeof amount !== 'number' || isNaN(amount)) return '-';
  
  const wan = amount / 10000;
  const prefix = withCurrency ? '¥' : '';
  return `${prefix}${wan.toFixed(2)}万`;
}

/**
 * 格式化时间差为友好的中文描述
 * @param hours - 小时数
 * @returns 格式化后的时间差 (2小时30分钟)
 */
export function formatTimeDifference(hours: number): string {
  if (typeof hours !== 'number' || isNaN(hours)) return '-';
  
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  
  if (h === 0 && m === 0) return '0分钟';
  
  const parts: string[] = [];
  if (h > 0) parts.push(`${h}小时`);
  if (m > 0) parts.push(`${m}分钟`);
  
  return parts.join('');
}

/**
 * 截断长文本
 * @param text - 原始文本
 * @param maxLength - 最大长度
 * @returns 截断后的文本（带省略号）
 */
export function truncate(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * 格式化文件大小
 * @param bytes - 字节数
 * @returns 格式化后的文件大小 (1.5 MB)
 */
export function formatFileSize(bytes: number): string {
  if (typeof bytes !== 'number' || bytes < 0) return '-';
  
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * 获取风险等级对应的颜色类名
 * @param riskLevel - 风险等级
 * @returns Tailwind CSS 颜色类名
 */
export function getRiskLevelColor(riskLevel: string): string {
  const level = riskLevel?.toLowerCase() || '';
  switch (level) {
    case '高风险':
    case 'high':
      return 'text-red-400 bg-red-500/10 border-red-500/30';
    case '中风险':
    case 'medium':
      return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
    case '低风险':
    case 'low':
      return 'text-green-400 bg-green-500/10 border-green-500/30';
    default:
      return 'text-gray-400 bg-gray-500/10 border-gray-500/30';
  }
}

/**
 * 获取风险等级对应的标签样式
 * @param riskLevel - 风险等级
 * @returns Tailwind CSS 类名
 */
export function getRiskLevelBadgeStyle(riskLevel: string): string {
  const level = riskLevel?.toLowerCase() || '';
  switch (level) {
    case '高风险':
    case 'high':
      return 'badge badge-red';
    case '中风险':
    case 'medium':
      return 'badge badge-yellow';
    case '低风险':
    case 'low':
      return 'badge badge-green';
    default:
      return 'badge badge-gray';
  }
}
