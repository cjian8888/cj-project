/**
 * 数据格式化工具 - 将后端原始数据转换为用户友好的中文展示
 * 
 * 用于解决前端显示 "income_spike", "high", "系统检测" 等原始数据的问题
 */

// ==================== 风险等级映射 ====================

export const RISK_LEVEL_MAP: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  critical: '极高风险',
  unknown: '未知',
};

export const RISK_LEVEL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  high: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500' },
  medium: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500' },
  low: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500' },
  critical: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500' },
  unknown: { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500' },
};

// ==================== 风险类型/描述映射 ====================

export const RISK_TYPE_MAP: Record<string, string> = {
  // 收入异常类型
  income_spike: '资金突变',
  income_change: '收入变动',
  sudden_income: '突增收入',
  
  // 交易模式类型
  structuring: '拆分洗钱',
  round_trip: '资金回流',
  dormant_activation: '休眠激活',
  frequent_transaction: '频繁交易',
  
  // 借贷相关（后端 loan_analyzer._type 映射）
  loan_repayment: '借贷还款',
  no_repayment: '无还款借贷',
  bidirectional: '借贷双向往来',
  online_loan: '网贷平台交易',
  regular_repayment: '规律性还款',
  loan_pair: '借贷配对',
  abnormal_interest: '异常利息',
  
  // 收入相关（后端 income_analyzer._type 映射）
  regular_non_salary: '规律非工资收入',
  large_individual: '个人大额转入',
  unknown_source: '来源不明收入',
  large_single: '大额单笔收入',
  same_source_multi: '同源多次收入',
  bribe_installment: '疑似分期受贿',
  high_risk: '高风险收入',
  medium_risk: '中风险收入',
  
  // 时间相关
  holiday_transaction: '节假日交易',
  night_transaction: '夜间交易',
  weekend_transaction: '周末交易',
  
  // 关联方
  related_party: '关联方交易',
  direct_transfer: '直接转账',
  third_party_relay: '第三方中转',
  
  // 系统检测
  system_detected: '系统自动检测',
  ml_detected: '机器学习检测',
  rule_detected: '规则检测',
  
  // 金额相关
  large_cash: '大额现金',
  round_amount: '整数金额',
  threshold_avoidance: '规避阈值',
};

// ==================== 格式化函数 ====================

/**
 * 格式化风险等级
 * @param level - 原始风险等级 (high, medium, low, etc.)
 * @returns 中文风险等级
 */
export const formatRiskLevel = (level: string | undefined | null): string => {
  if (!level) return '--';
  const normalized = level.toLowerCase().trim();
  return RISK_LEVEL_MAP[normalized] || level;
};

/**
 * 获取风险等级对应的颜色配置
 */
export const getRiskLevelColors = (level: string | undefined | null) => {
  if (!level) return RISK_LEVEL_COLORS.unknown;
  const normalized = level.toLowerCase().trim();
  return RISK_LEVEL_COLORS[normalized] || RISK_LEVEL_COLORS.unknown;
};

/**
 * 净化风险描述
 * - 移除冗余的英文代码 (如 "资金突变: income_spike" -> "资金突变")
 * - 翻译纯英文代码
 * @param text - 原始描述文本
 * @returns 清洗后的中文描述
 */
export const formatRiskDescription = (text: string | undefined | null): string => {
  if (!text) return '--';
  
  // 1. 移除冒号后的英文代码 (e.g., "资金突变: income_spike" -> "资金突变")
  let cleanText = text.replace(/[:：]\s*[a-z_]+$/i, '').trim();
  
  // 2. 如果是纯英文下划线格式，查字典翻译
  const lowerText = text.toLowerCase().trim();
  if (RISK_TYPE_MAP[lowerText]) {
    return RISK_TYPE_MAP[lowerText];
  }
  
  // 3. 如果清洗后是纯英文，尝试翻译
  const cleanLower = cleanText.toLowerCase();
  if (RISK_TYPE_MAP[cleanLower]) {
    return RISK_TYPE_MAP[cleanLower];
  }
  
  // 4. 返回清洗后的文本，或原文本
  return cleanText || text;
};

/**
 * 翻译借贷/收入分析类型（后端 _type 字段）
 * @param type - 后端返回的 _type 字段值
 * @returns 专业审计术语
 */
export const formatAnalysisType = (type: string | undefined | null): string => {
  if (!type) return '--';
  
  const normalized = type.toLowerCase().trim();
  return RISK_TYPE_MAP[normalized] || type;
};

/**
 * 格式化交易时间为审计友好格式
 * @param dateStr - 日期字符串（可能包含时间）
 * @returns 格式化后的日期时间字符串
 */
export const formatAuditDateTime = (dateStr: string | Date | undefined | null): string => {
  if (!dateStr) return '--';
  
  try {
    const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;
    
    if (isNaN(date.getTime())) {
      // 如果是简单的日期字符串格式，直接返回
      if (typeof dateStr === 'string') {
        // 移除时区信息，保留日期部分
        return dateStr.replace(/T.*$/, '').slice(0, 10);
      }
      return String(dateStr);
    }
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = date.getHours();
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    // 如果有时间部分，显示完整日期时间
    if (hours > 0 || date.getMinutes() > 0) {
      return `${year}年${month}月${day}日 ${hours}:${minutes}`;
    }
    
    return `${year}年${month}月${day}日`;
  } catch {
    return String(dateStr);
  }
};
/**
 * 净化交易对手名称
 * - 修复 "系统检测" 等无意义的对手方名称
 * @param name - 原始对手方名称
 * @returns 用户友好的对手方名称
 */
export const formatPartyName = (name: string | undefined | null): string => {
  if (!name) return '--';
  
  const trimmedName = name.trim();
  
  // 系统生成的占位符
  const systemPlaceholders = [
    '系统检测',
    'SYSTEM',
    'system',
    'N/A',
    'null',
    'undefined',
    '未知',
    '无',
  ];
  
  if (systemPlaceholders.includes(trimmedName)) {
    return '目标账户(本人)';
  }
  
  return trimmedName;
};

/**
 * 格式化金额显示
 * @param amount - 金额数值
 * @param options - 配置选项
 * @returns 格式化后的金额字符串
 */
export const formatAmount = (
  amount: number | undefined | null,
  options: {
    currency?: string;
    useWan?: boolean;
    precision?: number;
  } = {}
): string => {
  if (amount === undefined || amount === null || isNaN(amount)) {
    return '--';
  }
  
  const { currency = '¥', useWan = true, precision = 2 } = options;
  
  // 万元转换
  if (useWan && Math.abs(amount) >= 10000) {
    return `${currency}${(amount / 10000).toFixed(precision)}万`;
  }
  
  // 千分位格式化
  return `${currency}${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: precision,
  })}`;
};

/**
 * 格式化日期
 * @param dateStr - 日期字符串或Date对象
 * @returns 格式化后的日期字符串
 */
export const formatDate = (dateStr: string | Date | undefined | null): string => {
  if (!dateStr) return '--';
  
  try {
    const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;
    
    if (isNaN(date.getTime())) {
      // 如果是简单的日期字符串格式(如 "2024-01-15")，直接返回
      if (typeof dateStr === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
      }
      return String(dateStr);
    }
    
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return String(dateStr);
  }
};

/**
 * 格式化百分比
 */
export const formatPercent = (value: number | undefined | null, precision: number = 1): string => {
  if (value === undefined || value === null || isNaN(value)) {
    return '--';
  }
  return `${value.toFixed(precision)}%`;
};

/**
 * 格式化交易方向
 */
export const formatDirection = (direction: string | undefined | null): string => {
  if (!direction) return '--';
  
  const directionMap: Record<string, string> = {
    income: '收入',
    expense: '支出',
    in: '转入',
    out: '转出',
    inbound: '入账',
    outbound: '出账',
    payment: '付款',
    receipt: '收款',
    '突变': '资金突变',
    '延迟转账': '延迟转账',
    '周期收入': '周期性收入',
    '关联往来': '关联方往来',
  };
  
  return directionMap[direction.toLowerCase()] || direction;
};

// ==================== 向后兼容函数 (现有组件使用) ====================

/**
 * 格式化货币金额 (向后兼容)
 * @param amount - 金额
 * @returns 格式化后的货币字符串
 */
export const formatCurrency = (amount: number | undefined | null): string => {
  if (amount === undefined || amount === null || isNaN(amount)) {
    return '¥0';
  }
  
  if (Math.abs(amount) >= 10000) {
    return `¥${(amount / 10000).toFixed(2)}万`;
  }
  
  return `¥${amount.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
};

/**
 * 格式化金额为万元 (向后兼容)
 * @param amount - 金额
 * @returns 格式化后的万元字符串
 */
export const formatAmountInWan = (amount: number | undefined | null): string => {
  if (amount === undefined || amount === null || isNaN(amount)) {
    return '¥0';
  }
  
  const absAmount = Math.abs(amount);
  const prefix = amount < 0 ? '-' : '';
  
  if (absAmount >= 100000000) {
    return `${prefix}¥${(absAmount / 100000000).toFixed(2)}亿`;
  } else if (absAmount >= 10000) {
    return `${prefix}¥${(absAmount / 10000).toFixed(2)}万`;
  } else {
    return `${prefix}¥${absAmount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;
  }
};

/**
 * 截断文本 (向后兼容)
 * @param text - 原始文本
 * @param maxLength - 最大长度
 * @returns 截断后的文本
 */
export const truncate = (text: string | undefined | null, maxLength: number = 20): string => {
  if (!text) return '--';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
};

/**
 * 获取风险等级徽章样式 (向后兼容)
 * @param level - 风险等级
 * @returns Tailwind CSS 类名
 */
export const getRiskLevelBadgeStyle = (level: string | undefined | null): string => {
  if (!level) return 'px-2 py-0.5 rounded text-xs font-medium bg-gray-500/20 text-gray-400';
  
  const normalized = level.toLowerCase().trim();
  
  // 支持中英文混合
  if (normalized === 'high' || normalized === '高风险' || normalized.includes('高')) {
    return 'px-2 py-0.5 rounded text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30';
  }
  if (normalized === 'medium' || normalized === '中风险' || normalized.includes('中')) {
    return 'px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30';
  }
  if (normalized === 'low' || normalized === '低风险' || normalized.includes('低')) {
    return 'px-2 py-0.5 rounded text-xs font-medium bg-green-500/20 text-green-400 border border-green-500/30';
  }
  if (normalized === 'critical' || normalized === '极高风险' || normalized.includes('极')) {
    return 'px-2 py-0.5 rounded text-xs font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30';
  }
  
  return 'px-2 py-0.5 rounded text-xs font-medium bg-gray-500/20 text-gray-400';
};

/**
 * 格式化文件大小 (向后兼容)
 * @param bytes - 字节数
 * @returns 格式化后的文件大小
 */
export const formatFileSize = (bytes: number | undefined | null): string => {
  if (bytes === undefined || bytes === null || isNaN(bytes)) {
    return '0 B';
  }
  
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

// ==================== 导出工具对象 ====================

export const Formatters = {
  riskLevel: formatRiskLevel,
  riskDescription: formatRiskDescription,
  partyName: formatPartyName,
  amount: formatAmount,
  date: formatDate,
  percent: formatPercent,
  direction: formatDirection,
  getRiskLevelColors,
  // 新增审计专用函数
  analysisType: formatAnalysisType,
  auditDateTime: formatAuditDateTime,
  // 向后兼容
  currency: formatCurrency,
  amountInWan: formatAmountInWan,
  truncate,
  riskBadgeStyle: getRiskLevelBadgeStyle,
  fileSize: formatFileSize,
};

export default Formatters;
