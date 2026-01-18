/**
 * 审计术语映射模块 (Protocol Omega - Phase 2)
 * 
 * 将技术术语转换为专业审计术语，确保报告符合公文规范。
 */

// 英文代码 -> 中文审计术语
export const AUDIT_TERM_MAP: Record<string, string> = {
    // 风险等级
    'high_risk': '高风险',
    'medium_risk': '中风险',
    'low_risk': '低风险',
    'critical': '极高风险',
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险',

    // 交易方向
    'income': '收入',
    'expense': '支出',
    'payment': '付款',
    'receive': '收款',
    'inflow': '资金流入',
    'outflow': '资金流出',

    // 疑点类型
    'income_spike': '资金突变',
    'cash_collision': '现金时空伴随',
    'counterparty': '交易对手',
    'balance_zeroed': '账户清空',
    'pass_through': '过账通道',
    'hub_node': '资金枢纽',
    'fund_cycle': '资金闭环',
    'bidirectional': '双向往来',
    'periodic_income': '规律性收入',
    'sudden_change': '资金突变',
    'delayed_transfer': '固定延迟转账',
    'split_transaction': '拆分交易',
    'structured_deposit': '结构化存款',
    'round_trip': '资金回流',

    // 交易渠道
    'atm': 'ATM机',
    'counter': '柜面',
    'online': '网银',
    'mobile': '手机银行',
    'third_party': '第三方支付',

    // 分析模块
    'penetration': '资金穿透',
    'profiling': '资金画像',
    'suspicion': '疑点检测',
    'aggregation': '线索聚合',

    // 实体类型
    'person': '自然人',
    'company': '企业',
    'core_person': '核心人员',
    'related_party': '关联方',
};

/**
 * 将技术术语转换为审计术语
 */
export function translateAuditTerm(term: string): string {
    // 先尝试精确匹配
    if (AUDIT_TERM_MAP[term]) {
        return AUDIT_TERM_MAP[term];
    }

    // 尝试小写匹配
    const lowerTerm = term.toLowerCase();
    if (AUDIT_TERM_MAP[lowerTerm]) {
        return AUDIT_TERM_MAP[lowerTerm];
    }

    // 尝试替换下划线为空格后匹配
    const noUnderscore = term.replace(/_/g, ' ');
    if (AUDIT_TERM_MAP[noUnderscore]) {
        return AUDIT_TERM_MAP[noUnderscore];
    }

    // 未找到映射，返回原始术语
    return term;
}

/**
 * 翻译风险等级
 */
export function translateRiskLevel(level: string): string {
    const riskMap: Record<string, string> = {
        'critical': '极高风险',
        'high': '高风险',
        'medium': '中风险',
        'low': '低风险',
        'info': '信息提示',
        'none': '无风险',
    };
    return riskMap[level.toLowerCase()] || level;
}

/**
 * 翻译交易方向
 */
export function translateDirection(direction: string): string {
    const directionMap: Record<string, string> = {
        'income': '收入',
        'expense': '支出',
        'payment': '付款',
        'receive': '收款',
        'inflow': '流入',
        'outflow': '流出',
    };
    return directionMap[direction.toLowerCase()] || direction;
}

/**
 * 格式化金额（万元）
 */
export function formatAmount(amount: number, unit: '元' | '万元' = '元'): string {
    if (unit === '万元') {
        return (amount / 10000).toFixed(2) + ' 万元';
    }
    return amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' 元';
}

/**
 * 格式化日期
 */
export function formatDate(dateStr: string): string {
    if (!dateStr) return '-';

    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;

        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    } catch {
        return dateStr;
    }
}

/**
 * 获取风险等级样式
 */
export function getRiskLevelStyle(level: string): React.CSSProperties {
    const styles: Record<string, React.CSSProperties> = {
        critical: { color: '#fff', backgroundColor: '#c00', fontWeight: 'bold' },
        high: { color: '#c00', backgroundColor: '#fff0f0', fontWeight: 'bold' },
        medium: { color: '#f60', backgroundColor: '#fff8f0' },
        low: { color: '#060', backgroundColor: '#f0fff0' },
        info: { color: '#666', backgroundColor: '#f5f5f5' },
    };
    return styles[level.toLowerCase()] || {};
}

export default {
    AUDIT_TERM_MAP,
    translateAuditTerm,
    translateRiskLevel,
    translateDirection,
    formatAmount,
    formatDate,
    getRiskLevelStyle,
};
