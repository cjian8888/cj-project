import React, { useState, useEffect, useMemo } from 'react';
import {
    Activity,
    AlertTriangle,
    Network,
    FileText,
    Download,
    ChevronRight,
    TrendingUp,
    Wallet,
    ArrowUpRight,
    ArrowDownLeft,
    Clock,
    RefreshCw,
    X,
    Users,
    Building2,
    Banknote,
    Eye,
    Folder,
    FileSpreadsheet,
    ExternalLink,
    Info
} from 'lucide-react';
import { api, API_BASE_URL } from '../services/api';
import type { Report } from '../services/api';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import { useApp } from '../contexts/AppContext';
import { formatDate, formatCurrency, formatAmountInWan, truncate, getRiskLevelBadgeStyle, formatFileSize, formatRiskLevel, formatRiskDescription, formatPartyName, formatAnalysisType, formatAuditDateTime, sanitizeValue } from '../utils/formatters';
import { EmptyState } from './common/EmptyState';
import NetworkGraph from './NetworkGraph';
import { ReportBuilder } from './ReportBuilder';

export function TabContent() {
    const { ui, setActiveTab } = useApp();

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* Tab Navigation */}
            <div className="flex items-center gap-1 p-1 theme-bg-muted rounded-xl border theme-border mb-6 w-fit backdrop-blur-sm">
                <TabButton
                    label="数据概览"
                    icon={TrendingUp}
                    active={ui.activeTab === 'overview'}
                    onClick={() => setActiveTab('overview')}
                />
                <TabButton
                    label="风险情报"
                    icon={AlertTriangle}
                    active={ui.activeTab === 'risk'}
                    onClick={() => setActiveTab('risk')}
                />
                <TabButton
                    label="关系图谱"
                    icon={Network}
                    active={ui.activeTab === 'graph'}
                    onClick={() => setActiveTab('graph')}
                />
                <TabButton
                    label="审计报告"
                    icon={FileText}
                    active={ui.activeTab === 'report'}
                    onClick={() => setActiveTab('report')}
                />
            </div>

            {/* Tab Content */}
            <div className="flex-1 min-h-0">
                {ui.activeTab === 'overview' && <OverviewTab />}
                {ui.activeTab === 'risk' && <RiskIntelTab />}
                {ui.activeTab === 'graph' && <GraphViewTab />}
                {ui.activeTab === 'report' && <AuditReportTab />}
            </div>
        </div>
    );
}

// ==================== Tab Button Component ====================

interface TabButtonProps {
    label: string;
    icon: React.ElementType;
    active: boolean;
    onClick: () => void;
}

function TabButton({ label, icon: Icon, active, onClick }: TabButtonProps) {
    return (
        <button
            onClick={onClick}
            className={`
        flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium
        transition-all duration-200
        ${active
                    ? 'bg-blue-500/20 text-blue-400 shadow-lg shadow-blue-500/10'
                    : 'theme-text-muted hover:theme-text-secondary hover:theme-bg-hover'
                }
      `}
        >
            <Icon className="w-4 h-4" />
            {label}
        </button>
    );
}

// ==================== Overview Tab ====================

// 指标详情类型映射
type MetricType = 'loan_analysis' | 'income_analysis' |
    'related_direct' | 'cash_collision' | 'risk_critical' | 'risk_high' | 'risk_all' | 'cash_transactions';

interface AuditMetric {
    key: MetricType;
    label: string;
    value: number;
    color: string;
    desc: string;
    icon: React.ElementType;
}

function OverviewTab() {
    const { data, analysis } = useApp();

    // Modal 状态
    const [selectedMetric, setSelectedMetric] = useState<AuditMetric | null>(null);

    // 实体选择器状态
    const [selectedEntity, setSelectedEntity] = useState<string>('all');

    // 实体类型切换：个人 vs 公司
    const [entityType, setEntityType] = useState<'person' | 'company'>('person');

    // 🆕 审计导航数据
    interface AuditNavigationData {
        persons: { name: string; filename: string; size: number; sizeFormatted: string; modified: string }[];
        companies: { name: string; filename: string; size: number; sizeFormatted: string; modified: string }[];
        reports: { name: string; size: number; sizeFormatted: string; modified: string; isPrimary: boolean }[];
        outputDir: string;  // 输出目录（相对路径）
        paths: {
            cleanedDataPerson: string;
            cleanedDataCompany: string;
            analysisResults: string;
        };
    }
    const [auditNavigation, setAuditNavigation] = useState<AuditNavigationData | null>(null);

    // 加载审计导航数据
    useEffect(() => {
        const loadNavigationData = async () => {
            try {
                const response = await fetch(`${API_BASE_URL}/api/audit-navigation`);
                if (response.ok) {
                    const navData = await response.json();
                    setAuditNavigation(navData);
                }
            } catch (error) {
                console.warn('加载审计导航数据失败:', error);
            }
        };

        // 分析完成后加载导航数据
        if (analysis.status === 'completed') {
            loadNavigationData();
        }
    }, [analysis.status]);

    // 从真实数据生成趋势图数据（如果分析未完成，使用空数组）
    const hasRealData = analysis.status === 'completed' && Object.keys(data.profiles).length > 0;

    // 分离个人和公司
    // 增强版个人画像数据（审计仪表板用）
    const personProfiles = useMemo(() => {
        if (!hasRealData) return [];

        // 获取每个人员的异常收入数量
        const personAnomalyCount: { [key: string]: number } = {};
        const incomeDetails = data.analysisResults?.income?.details || [];
        incomeDetails.forEach((item: any) => {
            const person = item.person || item.receiver;
            if (person) {
                personAnomalyCount[person] = (personAnomalyCount[person] || 0) + 1;
            }
        });

        return Object.entries(data.profiles)
            .filter(([name]) => data.persons.includes(name))
            .map(([name, profile]) => {
                const income = profile?.totalIncome || 0;
                const expense = profile?.totalExpense || 0;
                const cashTotal = profile?.cashTotal || 0;
                const cashTxCount = ((profile as any)?.cashTransactions || []).length;
                const netFlow = income - expense;
                const total = income + expense;
                const cashRatio = total > 0 ? (cashTotal / total) * 100 : 0;

                // 新增：工资、理财、第三方支付
                const salaryTotal = (profile as any)?.salaryTotal || 0;  // 工资金额
                const wealthTotal = profile?.wealthTotal || 0;  // 理财金额
                const thirdPartyTotal = profile?.thirdPartyTotal || 0;  // 第三方支付
                const transactionCount = profile?.transactionCount || 0;  // 交易笔数

                return {
                    name: truncate(name, 10),
                    fullName: name,
                    收入: income / 10000,
                    支出: expense / 10000,
                    income,
                    expense,
                    netFlow,
                    total: total / 10000,
                    cashTotal,
                    cashRatio,
                    cashTxCount,
                    anomalyCount: personAnomalyCount[name] || 0,
                    // 新增字段
                    salaryTotal: salaryTotal / 10000,  // 转万元
                    wealthTotal: wealthTotal / 10000,  // 转万元
                    thirdPartyTotal: thirdPartyTotal / 10000,  // 转万元
                    transactionCount,
                    // 风险等级：现金占比>15%为高，>8%为中
                    riskLevel: cashRatio > 15 ? 'high' : cashRatio > 8 ? 'medium' : 'low'
                };
            })
            .sort((a, b) => b.total - a.total)
            .slice(0, 8);
    }, [hasRealData, data.profiles, data.persons, data.analysisResults]);

    const companyProfiles = useMemo(() => {
        if (!hasRealData) return [];
        return Object.entries(data.profiles)
            .filter(([name]) => data.companies.includes(name))
            .map(([name, profile]) => {
                const income = profile?.totalIncome || 0;
                const expense = profile?.totalExpense || 0;
                const cashTotal = profile?.cashTotal || 0;
                const cashTxCount = ((profile as any)?.cashTransactions || []).length;
                const netFlow = income - expense;
                const total = income + expense;
                const cashRatio = total > 0 ? (cashTotal / total) * 100 : 0;

                // 审计关键字段
                const thirdPartyTotal = profile?.thirdPartyTotal || 0;
                const maxTransaction = profile?.maxTransaction || 0;
                const transactionCount = profile?.transactionCount || 0;

                return {
                    name: truncate(name, 10),
                    fullName: name,
                    收入: income / 10000,
                    支出: expense / 10000,
                    income,
                    expense,
                    netFlow,
                    total: total / 10000,
                    cashTotal,
                    cashRatio,
                    cashTxCount,
                    // 企业专属字段
                    thirdPartyTotal: thirdPartyTotal / 10000,  // 转万元
                    maxTransaction: maxTransaction / 10000,  // 转万元
                    transactionCount,
                    // 风险等级：现金占比>20%为高，>10%为中（企业阈值略高于个人）
                    riskLevel: cashRatio > 20 ? 'high' : cashRatio > 10 ? 'medium' : 'low'
                };
            })
            .sort((a, b) => b.total - a.total)
            .slice(0, 8);
    }, [hasRealData, data.profiles, data.companies]);

    // 当前显示的流量数据
    const currentFlowData = entityType === 'person' ? personProfiles : companyProfiles;

    // 实体列表（用于选择器）
    const entityList = useMemo(() => {
        return data.persons || [];
    }, [data.persons]);

    // 从 analysisResults 提取审计关键指标（后端返回的核心数据）- 移到前面解决依赖问题
    const loanSummary = data.analysisResults?.loan?.summary || {};
    const loanDetailsData = data.analysisResults?.loan?.details || [];
    const incomeSummary = data.analysisResults?.income?.summary || {};
    const incomeDetailsData = data.analysisResults?.income?.details || [];

    // 初步研判提示专用口径：拆分“总条目/去重条目/分类构成”，避免用户误解
    const preliminaryMetrics = useMemo(() => {
        const safeIncomeDetails = Array.isArray(incomeDetailsData) ? incomeDetailsData : [];
        const safeLoanDetails = Array.isArray(loanDetailsData) ? loanDetailsData : [];

        const toAmount = (item: any): number => {
            const candidates = [
                item?.amount,
                item?.income_total,
                item?.total_amount,
                item?.avg_amount,
                item?.income_amount,
                item?.loan_amount,
            ];
            for (const value of candidates) {
                const num = Number(value || 0);
                if (Number.isFinite(num) && num !== 0) return num;
            }
            return 0;
        };

        const getSourceFile = (item: any): string =>
            String(
                item?.source_file ||
                item?.sourceFile ||
                item?.loan_source_file ||
                item?.income_source_file ||
                ''
            ).trim();

        const getSourceRow = (item: any): string => {
            const row = item?.source_row_index ??
                item?.sourceRowIndex ??
                item?.loan_source_row ??
                item?.income_source_row ??
                item?.source_row;
            if (row === null || row === undefined) return '';
            const text = String(row).trim();
            return text && text.toLowerCase() !== 'nan' ? text : '';
        };

        const getSourceKey = (item: any): string => {
            const file = getSourceFile(item);
            if (!file) return '';
            const row = getSourceRow(item);
            return `${file}::${row || '*'}`;
        };

        const getRelationKey = (item: any): string => {
            const person = String(
                item?.person || item?.name || item?.borrower || item?.lender || ''
            ).trim();
            const counterparty = String(
                item?.counterparty || item?.platform || item?.company || item?.target || ''
            ).trim();
            if (!person || !counterparty) return '';
            return `${person}::${counterparty}`;
        };

        const incomeTypeCounts = safeIncomeDetails.reduce((acc: Record<string, number>, item: any) => {
            const key = String(item?._type || 'unknown');
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});

        const loanTypeCounts = safeLoanDetails.reduce((acc: Record<string, number>, item: any) => {
            const key = String(item?._type || 'unknown');
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});

        const incomeIndependentTypes = new Set([
            'large_single',
            'large_individual',
            'unknown_source',
            'regular_non_salary',
            'same_source_multi',
            'bribe_installment',
        ]);

        const incomeIndependentSourceKeys = new Set(
            safeIncomeDetails
                .filter((item: any) => incomeIndependentTypes.has(String(item?._type || '')))
                .map((item: any) => getSourceKey(item))
                .filter((key: string) => !!key)
        );
        const incomeAllSourceKeys = new Set(
            safeIncomeDetails.map((item: any) => getSourceKey(item)).filter((key: string) => !!key)
        );
        const incomeRiskRollupCount =
            (incomeTypeCounts.high_risk || 0) + (incomeTypeCounts.medium_risk || 0);
        const incomeAmount = safeIncomeDetails.reduce(
            (sum: number, item: any) => sum + toAmount(item),
            0
        );

        const loanAllSourceKeys = new Set(
            safeLoanDetails.map((item: any) => getSourceKey(item)).filter((key: string) => !!key)
        );
        const loanRelationKeys = new Set(
            safeLoanDetails.map((item: any) => getRelationKey(item)).filter((key: string) => !!key)
        );
        const loanTradeCount = loanTypeCounts.online_loan || 0;
        const loanPatternCount = loanTypeCounts.regular_repayment || 0;
        const loanRelationCount =
            (loanTypeCounts.bidirectional || 0) +
            (loanTypeCounts.no_repayment || 0) +
            (loanTypeCounts.loan_pair || 0) +
            (loanTypeCounts.abnormal_interest || 0);

        return {
            income: {
                total: safeIncomeDetails.length,
                amount: incomeAmount,
                independentSourceCount: incomeIndependentSourceKeys.size,
                allSourceCount: incomeAllSourceKeys.size,
                riskRollupCount: incomeRiskRollupCount,
                typeCounts: incomeTypeCounts,
            },
            loan: {
                total: safeLoanDetails.length,
                uniqueRelationCount: loanRelationKeys.size,
                sourceCount: loanAllSourceKeys.size,
                tradeCount: loanTradeCount,
                patternCount: loanPatternCount,
                relationCount: loanRelationCount,
                typeCounts: loanTypeCounts,
            },
        };
    }, [incomeDetailsData, loanDetailsData]);

    // 🆕 审计发现类型分布 - 按借贷分析和收入分析的分类显示
    const auditFindingsDistribution = useMemo(() => {
        if (!hasRealData) return [{ name: '等待分析', value: 100, color: '#374151' }];

        // 统计借贷分析各分类的数量
        const loanCounts = {
            regular_repayment: loanDetailsData.filter((x: any) => x._type === 'regular_repayment').length,
            no_repayment: loanDetailsData.filter((x: any) => x._type === 'no_repayment').length,
            online_loan: loanDetailsData.filter((x: any) => x._type === 'online_loan').length,
            bidirectional: loanDetailsData.filter((x: any) => x._type === 'bidirectional').length,
        };

        // 统计收入分析各分类的数量
        const incomeCounts = {
            large_single: incomeDetailsData.filter((x: any) => x._type === 'large_single').length,
            unknown_source: incomeDetailsData.filter((x: any) => x._type === 'unknown_source').length,
            regular_non_salary: incomeDetailsData.filter((x: any) => x._type === 'regular_non_salary').length,
            high_risk: incomeDetailsData.filter((x: any) => x._type === 'high_risk' || x._type === 'medium_risk').length,
        };

        // 组装饼图数据（只显示有数据的分类）
        const categories: { name: string; value: number; color: string }[] = [];
        const colorPalette = [
            '#3b82f6', // 蓝
            '#8b5cf6', // 紫
            '#06b6d4', // 青
            '#10b981', // 绿
            '#f59e0b', // 橙
            '#ef4444', // 红
            '#ec4899', // 粉
            '#6366f1', // 靛蓝
        ];

        let colorIndex = 0;

        // 借贷分析分类
        if (loanCounts.regular_repayment > 0) {
            categories.push({ name: '规律还款', value: loanCounts.regular_repayment, color: colorPalette[colorIndex++] });
        }
        if (loanCounts.no_repayment > 0) {
            categories.push({ name: '无还款借贷', value: loanCounts.no_repayment, color: colorPalette[colorIndex++] });
        }
        if (loanCounts.online_loan > 0) {
            categories.push({ name: '网贷交易', value: loanCounts.online_loan, color: colorPalette[colorIndex++] });
        }
        if (loanCounts.bidirectional > 0) {
            categories.push({ name: '双向往来', value: loanCounts.bidirectional, color: colorPalette[colorIndex++] });
        }

        // 收入分析分类
        if (incomeCounts.large_single > 0) {
            categories.push({ name: '大额收入', value: incomeCounts.large_single, color: colorPalette[colorIndex++ % 8] });
        }
        if (incomeCounts.unknown_source > 0) {
            categories.push({ name: '来源不明', value: incomeCounts.unknown_source, color: colorPalette[colorIndex++ % 8] });
        }
        if (incomeCounts.regular_non_salary > 0) {
            categories.push({ name: '规律非工资', value: incomeCounts.regular_non_salary, color: colorPalette[colorIndex++ % 8] });
        }
        if (incomeCounts.high_risk > 0) {
            categories.push({ name: '高风险收入', value: incomeCounts.high_risk, color: colorPalette[colorIndex++ % 8] });
        }

        if (categories.length === 0) {
            return [{ name: '暂无发现', value: 100, color: '#374151' }];
        }

        // 计算百分比
        const total = categories.reduce((sum, c) => sum + c.value, 0);
        return categories.map(c => ({
            ...c,
            percent: Math.round((c.value / total) * 100)
        }));
    }, [hasRealData, loanDetailsData, incomeDetailsData]);

    // 使用新的数据源（兼容旧变量名）
    const incomeDistributionData = auditFindingsDistribution;

    // 兼容旧变量名
    const loanDetails = loanDetailsData;
    const incomeDetails = incomeDetailsData;

    // 从 analysisResults 提取其他审计关键指标
    const aggregationSummary = data.analysisResults?.aggregation?.summary || {};
    const rankedEntities = data.analysisResults?.aggregation?.rankedEntities || [];

    // 直接从 suspicions 计算实际数据条数
    const directTransfersCount = (data.suspicions.directTransfers || []).length;
    const cashCollisionsCount = (data.suspicions.cashCollisions || []).length;

    // 从 profiles 中提取所有现金交易明细
    // 【修复】映射后端中文键名为前端英文键名
    const allCashTransactions = Object.values(data.profiles || {}).flatMap((p: any) =>
        (p.cashTransactions || []).map((tx: any) => ({
            ...tx,
            // 映射中文字段名为英文字段名（兼容两种格式）
            type: tx.type || tx['类型'] || '',
            amount: tx.amount || tx['金额'] || 0,
            date: tx.date || tx['日期'] || '',
            description: tx.description || tx['摘要'] || '',
            counterparty: tx.counterparty || tx['对手方'] || '',
            entity: p.entityName  // 添加归属人员
        }))
    );

    // 筛选极高风险和高风险实体
    const criticalRiskEntities = rankedEntities.filter((e: any) =>
        e.riskLevel === 'critical' || (e.riskScore && e.riskScore >= 80)
    );
    const highRiskEntities = rankedEntities.filter((e: any) =>
        e.riskLevel === 'high' || (e.riskScore && e.riskScore >= 60 && e.riskScore < 80)
    );

    const auditMetrics: AuditMetric[] = [
        // 1. 借贷风险分析 - 显示所有借贷类型总数，弹窗中分类展示
        {
            key: 'loan_analysis',
            label: '借贷风险分析',
            value: loanDetails.length,
            color: 'text-red-400',
            desc: '总条目（含交易/关系/模式）',
            icon: Users
        },
        // 2. 异常收入分析 - 显示所有收入类型总数，弹窗中分类展示
        {
            key: 'income_analysis',
            label: '异常收入分析',
            value: incomeDetails.length,
            color: 'text-orange-400',
            desc: '总条目（含风险汇总重叠）',
            icon: TrendingUp
        },
        // 4. 核心人员往来
        {
            key: 'related_direct',
            label: '核心人员往来',
            value: directTransfersCount,
            color: 'text-purple-400',
            desc: '与涉案公司/人员',
            icon: Network
        },
        // 5. 现金时空伴随 - 使用 cashCollisions（完全一致）
        {
            key: 'cash_collision',
            label: '现金时空伴随',
            value: cashCollisionsCount,
            color: 'text-cyan-400',
            desc: 'ATM取存配对',
            icon: Clock
        },
        // 6. 极高风险实体 - 使用筛选后的 rankedEntities
        {
            key: 'risk_critical',
            label: '极高风险实体',
            value: criticalRiskEntities.length > 0 ? criticalRiskEntities.length : (aggregationSummary['极高风险实体数'] || 0),
            color: 'text-red-500',
            desc: '风险评分≥80',
            icon: AlertTriangle
        },
        // 7. 高风险实体 - 使用筛选后的 rankedEntities
        {
            key: 'risk_high',
            label: '高风险实体',
            value: highRiskEntities.length > 0 ? highRiskEntities.length : (aggregationSummary['高风险实体数'] || 0),
            color: 'text-orange-500',
            desc: '风险评分60-79',
            icon: AlertTriangle
        },
        // 8. 全部风险实体 - 新增，展示所有排名实体
        {
            key: 'risk_all',
            label: '风险实体总数',
            value: rankedEntities.length,
            color: 'text-pink-400',
            desc: '全部风险排名',
            icon: Users
        },
        // 9. 物理现金存取 - 新增，显示现金交易明细
        {
            key: 'cash_transactions',
            label: '物理现金存取',
            value: allCashTransactions.length,
            color: 'text-green-400',
            desc: '取现/存现明细',
            icon: Banknote
        },
    ];

    // 分类定义
    const loanCategories = [
        { type: 'regular_repayment', label: '规律还款模式', desc: '每月定期还款' },
        { type: 'no_repayment', label: '无还款借贷', desc: '借了钱没还过' },
        { type: 'online_loan', label: '网贷平台交易', desc: '白条、花呗等' },
        { type: 'bidirectional', label: '双向往来关系', desc: '同一人既借又还' },
        { type: 'loan_pair', label: '借贷配对分析', desc: '借入-还款配对' },
        { type: 'abnormal_interest', label: '异常利息检测', desc: '高利贷或零息贷' },
    ];

    const incomeCategories = [
        { type: 'high_risk', label: '高风险项目', desc: '综合评分高风险' },
        { type: 'large_single', label: '大额单笔收入', desc: '单笔≥10万' },
        { type: 'medium_risk', label: '中风险项目', desc: '综合评分中风险' },
        { type: 'large_individual', label: '个人大额转入', desc: '来自个人的大额' },
        { type: 'unknown_source', label: '来源不明收入', desc: '对手方不明' },
        { type: 'same_source_multi', label: '同源多次收入', desc: '同一来源多次' },
        { type: 'regular_non_salary', label: '规律非工资收入', desc: '固定周期非工资' },
        { type: 'bribe_installment', label: '疑似分期受贿', desc: '分期模式' },
    ];

    // 现金交易分类（取现/存现）
    const cashCategories = [
        { type: '取现', label: '现金取出', desc: 'ATM取现、柜台取款' },
        { type: '存现', label: '现金存入', desc: 'ATM存现、柜台存款' },
    ];

    // 当前选中的子分类（用于钻取）
    const [selectedSubCategory, setSelectedSubCategory] = useState<string | null>(null);

    // 获取分类汇总数据（第一级）
    // 注意：不同分类的金额字段名不同，需要分别处理
    const getCategorySummary = (metric: AuditMetric): { type: string; label: string; desc: string; count: number; amount: number }[] => {
        if (metric.key === 'loan_analysis') {
            return loanCategories.map(cat => {
                const items = loanDetails.filter((x: any) => x._type === cat.type);
                // 根据不同类型使用不同的金额字段
                const getAmount = (item: any): number => {
                    switch (cat.type) {
                        case 'regular_repayment':
                            return item.total_amount || item.avg_amount || 0;
                        case 'no_repayment':
                            return item.income_amount || 0;
                        case 'online_loan':
                            return item.amount || 0;
                        case 'bidirectional':
                            return item.income_total || 0;
                        case 'loan_pair':
                            return item.loan_amount || 0;
                        case 'abnormal_interest':
                            return item.loan_amount || 0;
                        default:
                            return item.amount || item.income_total || item.total_amount || item.avg_amount || 0;
                    }
                };
                return {
                    ...cat,
                    count: items.length,
                    amount: items.reduce((sum: number, x: any) => sum + getAmount(x), 0)
                };
            }).filter(x => x.count > 0);
        }
        if (metric.key === 'income_analysis') {
            return incomeCategories.map(cat => {
                const items = incomeDetails.filter((x: any) => x._type === cat.type);
                return {
                    ...cat,
                    count: items.length,
                    amount: items.reduce((sum: number, x: any) =>
                        sum + (x.amount || x.total_amount || x.avg_amount || x.income_amount || 0), 0)
                };
            }).filter(x => x.count > 0);
        }
        if (metric.key === 'cash_transactions') {
            return cashCategories.map(cat => {
                const items = allCashTransactions.filter((x: any) => x.type === cat.type);
                return {
                    ...cat,
                    count: items.length,
                    amount: items.reduce((sum: number, x: any) => sum + (x.amount || 0), 0)
                };
            }).filter(x => x.count > 0);
        }
        return [];
    };

    // 获取指定分类的详细记录（第二级）
    // 注意：不同分类的后端数据结构不同，需要分别处理
    const getCategoryDetails = (metric: AuditMetric, categoryType: string): any[] => {
        if (metric.key === 'loan_analysis') {
            return loanDetails
                .filter((item: any) => item._type === categoryType)
                .map((item: any) => {
                    // 【溯源铁律】统一提取溯源字段
                    const sourceFile = item.source_file || item.loan_source_file || '';
                    const sourceRowIndex = item.source_row_index || item.loan_source_row || null;

                    // 根据不同的借贷类型，字段名不同
                    switch (categoryType) {
                        case 'regular_repayment':
                            // 规律还款：avg_amount, total_amount, day_of_month, occurrences, date_range
                            return {
                                name: item.person || '未知',
                                counterparty: item.counterparty || '--',
                                amount: item.avg_amount || item.total_amount || 0,
                                date: item.date_range ? `每月${item.day_of_month}日 (${item.occurrences}次)` : '--',
                                description: `月均¥${((item.avg_amount || 0) / 1).toLocaleString()}，共${item.occurrences || 0}期`,
                                expense_total: item.total_amount,
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: item.is_likely_loan ? ['疑似贷款还款'] : []
                            };
                        case 'no_repayment':
                            // 无还款借贷：income_amount, income_date, days_since, risk_reason
                            return {
                                name: item.person || '未知',
                                counterparty: item.counterparty || '--',
                                amount: item.income_amount || 0,
                                date: item.income_date || '--',
                                description: item.risk_reason || `${item.days_since}天未还款`,
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: [`还款比例: ${((item.repay_ratio || 0) * 100).toFixed(1)}%`]
                            };
                        case 'online_loan':
                            // 网贷平台交易：platform, amount, date, direction, description
                            return {
                                name: item.person || '未知',
                                counterparty: item.platform || item.counterparty || '--',
                                amount: item.amount || 0,
                                date: item.date || '--',
                                description: item.description || (item.direction === 'income' ? '借入' : '还款'),
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: [item.direction === 'income' ? '借入' : '还款']
                            };
                        case 'bidirectional':
                            // 双向往来关系：income_total, expense_total, loan_type, first_income_date
                            return {
                                name: item.person || '未知',
                                counterparty: item.counterparty || '--',
                                amount: item.income_total || 0,
                                date: item.first_income_date || '--',
                                description: item.loan_type || '双向往来',
                                expense_total: item.expense_total,
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: [`还款/借入比: ${((item.ratio || 0) * 100).toFixed(0)}%`]
                            };
                        case 'loan_pair':
                            // 借贷配对：loan_date, repay_date, loan_amount, repay_amount, interest_rate
                            return {
                                name: item.person || '未知',
                                counterparty: item.counterparty || '--',
                                amount: item.loan_amount || 0,
                                date: item.loan_date || '--',
                                description: `借¥${((item.loan_amount || 0) / 10000).toFixed(1)}万→还¥${((item.repay_amount || 0) / 10000).toFixed(1)}万，${item.days || 0}天`,
                                expense_total: item.repay_amount,
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: item.risk_reason ? [item.risk_reason] : [`年化利率: ${(item.annual_rate || 0).toFixed(1)}%`]
                            };
                        case 'abnormal_interest':
                            // 异常利息：loan_amount, repay_amount, annual_rate, abnormal_type
                            return {
                                name: item.person || '未知',
                                counterparty: item.counterparty || '--',
                                amount: item.loan_amount || 0,
                                date: item.loan_date || '--',
                                description: item.abnormal_type || `年化${(item.annual_rate || 0).toFixed(1)}%`,
                                expense_total: item.repay_amount,
                                riskLevel: item.risk_level || 'high',
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: [item.abnormal_type || '异常利息']
                            };
                        default:
                            return {
                                name: item.person || item.borrower || '未知',
                                counterparty: item.lender || item.counterparty || item.platform || '--',
                                amount: item.amount || item.income_total || item.avg_amount || item.total_amount || 0,
                                date: item.date || item.first_income_date || item.loan_date || item.income_date || '--',
                                description: item.loan_type || item.description || item.risk_reason || '--',
                                expense_total: item.expense_total,
                                riskLevel: item.risk_level,
                                source_file: sourceFile,
                                source_row_index: sourceRowIndex,
                                reasons: item.reasons || []
                            };
                    }
                });
        }
        if (metric.key === 'income_analysis') {
            return incomeDetails
                .filter((item: any) => item._type === categoryType)
                .map((item: any) => {
                    // 【增强】根据不同类型构建描述
                    let description = '';
                    const descRaw = item.description || item.risk_reason || item.reason || '';

                    switch (categoryType) {
                        case 'large_single':
                            // 大额单笔：优先用 income_type
                            description = item.income_type || (descRaw && descRaw !== 'nan' ? descRaw : '大额单笔收入');
                            break;
                        case 'large_individual':
                            // 个人大额转入：显示来源
                            description = descRaw && descRaw !== 'nan' ? descRaw : `来自个人: ${item.from_individual || item.counterparty || '未知'}`;
                            break;
                        case 'same_source_multi':
                            // 同源多次：显示次数和类型
                            description = `${item.source_type || '多次转入'}, 共${item.count || 0}次`;
                            break;
                        case 'regular_non_salary':
                            // 规律非工资：显示可能类型
                            description = item.possible_type || `规律性收入, 共${item.occurrences || 0}次`;
                            break;
                        case 'bribe_installment':
                            // 分期受贿：显示风险因素
                            // 【修复】兼容后端返回的字符串或数组格式
                            const rawFactors = item.risk_factors;
                            let factorsStr = '';
                            if (typeof rawFactors === 'string' && rawFactors) {
                                factorsStr = rawFactors;
                            } else if (Array.isArray(rawFactors) && rawFactors.length > 0) {
                                factorsStr = rawFactors.slice(0, 2).join('; ');
                            }
                            description = factorsStr || `疑似分期, 共${item.occurrences || 0}期, 月均¥${((item.avg_amount || 0) / 10000).toFixed(1)}万`;
                            break;
                        default:
                            description = descRaw && descRaw !== 'nan' ? descRaw : '--';
                    }

                    // 【增强】处理日期，聚合类型使用 first_date 或 date_range 或 records
                    let dateValue = item.date || item.first_income_date || item.first_date || null;
                    if (!dateValue && item.date_range) {
                        // date_range 是数组 [startDate, endDate]
                        dateValue = Array.isArray(item.date_range) ? item.date_range[0] : item.date_range;
                    }
                    if (!dateValue && item.records && Array.isArray(item.records) && item.records.length > 0) {
                        // 从 records 数组中获取第一个日期
                        dateValue = item.records[0].date || item.records[0].time;
                    }
                    if (!dateValue && item.last_date) {
                        dateValue = item.last_date;
                    }

                    return {
                        name: item.person || item.receiver || '未知',
                        counterparty: item.source || item.counterparty || item.payer || item.from_individual || '--',
                        // 金额：尝试多个可能的字段名
                        amount: item.amount || item.avg_amount || item.total_amount || item.total || item.income_amount || 0,
                        // 日期：增强处理
                        date: dateValue,
                        // 描述：增强处理
                        description: description,
                        bank: item.bank,
                        // 【溯源铁律】原始文件和行号
                        source_file: item.source_file,
                        source_row_index: item.source_row_index,
                        riskLevel: item.riskLevel || item.risk_level,
                        reasons: item.reasons || item.risk_factors || []
                    };
                });
        }
        if (metric.key === 'cash_transactions') {
            return allCashTransactions
                .filter((tx: any) => tx.type === categoryType)
                .map((tx: any) => ({
                    name: tx.entity || '未知',
                    counterparty: tx.counterparty || '--',
                    amount: tx.amount || 0,
                    date: tx.date || '--',
                    description: tx.description || '--',
                    riskLevel: categoryType === '取现' ? 'medium' : 'low',
                    // 【溯源铁律】原始文件和行号
                    source_file: tx.source_file,
                    source_row_index: tx.source_row_index,
                    reasons: [categoryType]
                }));
        }
        return [];
    };

    // 获取指标详情数据（其他类型直接显示明细）
    const getMetricDetails = (metric: AuditMetric): any[] => {
        switch (metric.key) {
            case 'loan_analysis':
            case 'income_analysis':
                // 这两个类型使用分类汇总，不在这里返回
                return [];

            case 'related_direct':
                // 核心人员往来 - 使用 suspicions.directTransfers
                const transfers = data.suspicions.directTransfers || [];
                if (transfers.length > 0) {
                    return transfers.map((tx: any) => ({
                        name: tx.from || '未知',
                        counterparty: tx.to || '',
                        amount: tx.amount || 0,
                        date: tx.date || '',
                        description: tx.description || '资金往来',
                        bank: tx.bank,
                        // 【溯源铁律】原始文件和行号
                        source_file: tx.sourceFile,
                        source_row_index: tx.sourceRowIndex,
                        reasons: [
                            tx.direction ? `方向: ${tx.direction === 'payment' ? '付款' : '收款'}` : null,
                            tx.riskLevel ? `风险: ${formatRiskLevel(tx.riskLevel)}` : null
                        ].filter(Boolean)
                    }));
                }
                return [{ name: '暂无数据', description: '未发现核心人员与涉案公司的直接往来' }];

            case 'cash_collision':
                // 现金时空伴随 - 使用 suspicions.cashCollisions
                const collisions = data.suspicions.cashCollisions || [];
                if (collisions.length > 0) {
                    return collisions.map((c: any) => ({
                        name: c.person1 || '未知',
                        counterparty: c.person2 || '',
                        amount: c.amount1 || 0,
                        date: c.time1 || '',
                        description: `取现¥${(c.amount1 || 0).toLocaleString()} → 存现¥${(c.amount2 || 0).toLocaleString()}`,
                        // 【溯源铁律】原始文件和行号
                        source_file: c.withdrawalSourceFile || '',
                        source_row_index: c.withdrawalRowIndex,
                        reasons: [
                            c.timeDiff ? `时间差: ${c.timeDiff}小时` : null,
                            c.withdrawalBank ? `取现银行: ${c.withdrawalBank}` : null,
                            c.depositBank ? `存现银行: ${c.depositBank}` : null,
                            c.riskLevel ? `风险: ${formatRiskLevel(c.riskLevel)}` : null
                        ].filter(Boolean)
                    }));
                }
                return [{ name: '暂无数据', description: '未发现现金时空伴随' }];

            case 'risk_critical':
                // 极高风险实体
                if (criticalRiskEntities.length > 0) {
                    return criticalRiskEntities.map((e: any) => ({
                        name: e.name || e.entity || '未知',
                        counterparty: '',
                        amount: 0,
                        date: '',
                        description: `风险评分: ${e.riskScore || e.score || 'N/A'}`,
                        riskScore: e.riskScore || e.score,
                        reasons: e.reasons || []
                    }));
                }
                return [{ name: '暂无数据', description: '未发现极高风险实体' }];

            case 'risk_high':
                // 高风险实体
                if (highRiskEntities.length > 0) {
                    return highRiskEntities.map((e: any) => ({
                        name: e.name || e.entity || '未知',
                        counterparty: '',
                        amount: 0,
                        date: '',
                        description: `风险评分: ${e.riskScore || e.score || 'N/A'}`,
                        riskScore: e.riskScore || e.score,
                        reasons: e.reasons || []
                    }));
                }
                return [{ name: '暂无数据', description: '未发现高风险实体' }];

            case 'risk_all':
                // 全部风险实体
                if (rankedEntities.length > 0) {
                    return rankedEntities.map((e: any) => ({
                        name: e.name || e.entity || '未知',
                        counterparty: '',
                        amount: 0,
                        date: '',
                        description: `风险评分: ${e.riskScore || e.score || 'N/A'} (${e.riskLevel || '未分级'})`,
                        riskScore: e.riskScore || e.score,
                        reasons: e.reasons || []
                    }));
                }
                return [{ name: '暂无数据', description: '未发现风险实体' }];

            case 'cash_transactions':
                // 物理现金存取 - 使用分类汇总，不在这里返回
                return [];

            default:
                return [];
        }
    };

    // 判断是否需要显示分类汇总（两级钻取）
    const needsCategorySummary = (metric: AuditMetric) => {
        return metric.key === 'loan_analysis' || metric.key === 'income_analysis' || metric.key === 'cash_transactions';
    };

    // 关闭弹窗时重置子分类
    const handleCloseModal = () => {
        setSelectedMetric(null);
        setSelectedSubCategory(null);
    };

    // 返回上一级（从明细返回分类汇总）
    const handleBackToSummary = () => {
        setSelectedSubCategory(null);
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Metric Detail Modal - 两级钻取设计 */}
            {selectedMetric && (
                <div className="fixed inset-0 lg:left-72 z-50 flex items-center justify-center p-8 bg-black/60 backdrop-blur-sm" onClick={handleCloseModal}>
                    <div className="theme-bg-elevated border theme-border rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b theme-border-muted">
                            <div className="flex items-center gap-3">
                                {selectedSubCategory && (
                                    <button onClick={handleBackToSummary} className="p-2 theme-hover rounded-lg transition-colors mr-1">
                                        <ChevronRight className="w-4 h-4 theme-text-muted rotate-180" />
                                    </button>
                                )}
                                <div className={`p-2 rounded-lg ${selectedMetric.color.replace('text-', 'bg-').replace('-400', '-500/20').replace('-500', '-500/20')}`}>
                                    <selectedMetric.icon className={`w-5 h-5 ${selectedMetric.color}`} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-white">
                                        {selectedMetric.label}
                                        {selectedSubCategory && (
                                            <span className="text-blue-400 ml-2">
                                                → {(selectedMetric.key === 'loan_analysis' ? loanCategories : incomeCategories).find(c => c.type === selectedSubCategory)?.label}
                                            </span>
                                        )}
                                    </h3>
                                    <p className="text-xs theme-text-dim">
                                        {selectedSubCategory
                                            ? `共 ${getCategoryDetails(selectedMetric, selectedSubCategory).length} 条明细记录`
                                            : needsCategorySummary(selectedMetric)
                                                ? `共 ${getCategorySummary(selectedMetric).length} 个分类，${selectedMetric.value} 条记录`
                                                : `共 ${getMetricDetails(selectedMetric).length} 条记录`
                                        }
                                    </p>
                                </div>
                            </div>
                            <button onClick={handleCloseModal} className="p-2 theme-hover rounded-lg transition-colors">
                                <X className="w-5 h-5 theme-text-muted" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="p-4 overflow-auto max-h-[70vh]">
                            {needsCategorySummary(selectedMetric) && !selectedSubCategory ? (
                                /* 第一级：分类汇总表格 */
                                <div className="overflow-x-auto rounded-lg border theme-border">
                                    <table className="w-full text-sm">
                                        <thead className="theme-bg-muted sticky top-0">
                                            <tr className="text-left theme-text-secondary text-xs">
                                                <th className="px-4 py-3 font-medium w-12">#</th>
                                                <th className="px-4 py-3 font-medium">分类名称</th>
                                                <th className="px-4 py-3 font-medium">说明</th>
                                                <th className="px-4 py-3 font-medium text-right">记录数</th>
                                                <th className="px-4 py-3 font-medium text-right">涉及金额</th>
                                                <th className="px-4 py-3 font-medium text-center">操作</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {getCategorySummary(selectedMetric).map((cat, idx) => (
                                                <tr
                                                    key={cat.type}
                                                    className={`border-t theme-border-muted ${idx % 2 === 0 ? 'theme-bg-surface/30' : 'theme-bg-surface/60'} hover:bg-blue-500/10 transition-colors cursor-pointer`}
                                                    onClick={() => setSelectedSubCategory(cat.type)}
                                                >
                                                    <td className="px-4 py-4 theme-text-dim font-mono text-xs">{idx + 1}</td>
                                                    <td className="px-4 py-4">
                                                        <div className="theme-text font-medium">{cat.label}</div>
                                                    </td>
                                                    <td className="px-4 py-4 theme-text-muted text-xs">{cat.desc}</td>
                                                    <td className="px-4 py-4 text-right">
                                                        <span className="font-mono text-blue-400 font-bold text-lg">{cat.count}</span>
                                                        <span className="theme-text-dim text-xs ml-1">条</span>
                                                    </td>
                                                    <td className="px-4 py-4 text-right">
                                                        <span className="font-mono text-orange-400 font-semibold">{formatCurrency(cat.amount)}</span>
                                                    </td>
                                                    <td className="px-4 py-4 text-center">
                                                        <button className="px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs rounded-lg transition-colors">
                                                            查看明细 →
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                            {/* 合计行 */}
                                            <tr className="border-t-2 theme-border-strong theme-bg-muted/80">
                                                <td className="px-4 py-4"></td>
                                                <td className="px-4 py-4 theme-text font-bold">合计</td>
                                                <td className="px-4 py-4"></td>
                                                <td className="px-4 py-4 text-right">
                                                    <span className="font-mono theme-text font-bold text-lg">{selectedMetric.value}</span>
                                                    <span className="theme-text-muted text-xs ml-1">条</span>
                                                </td>
                                                <td className="px-4 py-4 text-right">
                                                    <span className="font-mono text-orange-400 font-bold">
                                                        {formatCurrency(getCategorySummary(selectedMetric).reduce((sum, c) => sum + c.amount, 0))}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4"></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                /* 第二级：详细记录表格（或其他类型的直接明细） */
                                (() => {
                                    const details = selectedSubCategory
                                        ? getCategoryDetails(selectedMetric, selectedSubCategory)
                                        : getMetricDetails(selectedMetric);

                                    if (details.length === 0) {
                                        return <div className="text-center py-8 theme-text-dim">暂无详细数据</div>;
                                    }

                                    return (
                                        <div className="overflow-x-auto rounded-lg border theme-border">
                                            <table className="w-full text-sm">
                                                <thead className="theme-bg-muted sticky top-0">
                                                    <tr className="text-left theme-text-secondary text-xs">
                                                        <th className="px-4 py-3 font-medium w-12">#</th>
                                                        <th className="px-4 py-3 font-medium">对象/来源</th>
                                                        <th className="px-4 py-3 font-medium">交易对手</th>
                                                        <th className="px-4 py-3 font-medium text-right">金额</th>
                                                        <th className="px-4 py-3 font-medium">交易时间</th>
                                                        <th className="px-4 py-3 font-medium">风险说明</th>
                                                        <th className="px-4 py-3 font-medium theme-text-dim">来源文件</th>
                                                        <th className="px-4 py-3 font-medium theme-text-dim w-20 text-right">行号</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {details.map((item: any, idx: number) => (
                                                        <tr key={idx} className={`border-t theme-border-muted ${idx % 2 === 0 ? 'theme-bg-surface/30' : 'theme-bg-surface/60'} theme-hover transition-colors`}>
                                                            <td className="px-4 py-3 theme-text-dim font-mono text-xs">{idx + 1}</td>
                                                            <td className="px-4 py-3">
                                                                <div className="theme-text font-medium">
                                                                    {sanitizeValue(item.name || item.entity || item.from || item.person || item.platform)}
                                                                </div>
                                                            </td>
                                                            <td className="px-4 py-3 theme-text-secondary">
                                                                {sanitizeValue(item.counterparty || item.to || item.lender)}
                                                            </td>
                                                            <td className="px-4 py-3 text-right">
                                                                <span className="font-mono text-orange-400 font-semibold">
                                                                    {item.amount ? formatCurrency(item.amount) : (
                                                                        item.income_total ? formatCurrency(item.income_total) : '--'
                                                                    )}
                                                                </span>
                                                                {(item.expense_total && item.expense_total > 0) && (
                                                                    <div className="font-mono text-green-400 text-xs mt-0.5">
                                                                        还款: {formatCurrency(item.expense_total)}
                                                                    </div>
                                                                )}
                                                            </td>
                                                            <td className="px-4 py-3 theme-text-muted font-mono text-xs whitespace-nowrap">
                                                                {formatAuditDateTime(item.date || item.first_income_date || item.loan_date || null)}
                                                            </td>
                                                            <td className="px-4 py-3">
                                                                <div className="theme-text-secondary text-xs" title={sanitizeValue(item.description || item.loan_type || item.risk_reason)}>
                                                                    {sanitizeValue(item.description || item.loan_type || item.risk_reason)}
                                                                </div>
                                                                {item.reasons && item.reasons.length > 0 && (
                                                                    <div className="text-[10px] theme-text-dim mt-1">
                                                                        {item.reasons.slice(0, 2).map((r: string) => sanitizeValue(r)).join(' | ')}
                                                                    </div>
                                                                )}
                                                            </td>
                                                            {/* 【溯源铁律】来源文件 */}
                                                            <td className="px-4 py-3 theme-text-dim text-xs font-mono max-w-[150px] truncate" title={sanitizeValue(item.source_file)}>
                                                                {item.source_file ? (
                                                                    <span className="text-blue-400/70">
                                                                        {String(item.source_file).split('/').pop()?.split('\\').pop() || sanitizeValue(item.source_file)}
                                                                    </span>
                                                                ) : '--'}
                                                            </td>
                                                            {/* 【溯源铁律】原始行号 */}
                                                            <td className="px-4 py-3 theme-text-dim text-xs font-mono text-right w-20">
                                                                {item.source_row_index || item.source_row ? (
                                                                    <span className="text-blue-400/70">
                                                                        {item.source_row_index || item.source_row}
                                                                    </span>
                                                                ) : '--'}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    );
                                })()
                            )}
                        </div>
                    </div>
                </div>
            )}


            {/* 🆕 智能审计导航区域 - 重新设计 */}
            {hasRealData && (
                <div className="lg:col-span-3 space-y-4">
                    {/* 第一部分：初步研判提示 */}
                    <div className="card bg-gradient-to-r from-blue-500/10 via-indigo-500/5 to-purple-500/10 border border-blue-500/20">
                        <div className="flex items-start gap-4">
                            <div className="p-3 rounded-xl bg-blue-500/20 flex-shrink-0">
                                <Info className="w-6 h-6 text-blue-400" />
                            </div>
                            <div className="flex-1">
                                <h3 className="font-bold text-white text-lg mb-3 flex items-center gap-2">
                                    💡 初步研判提示
                                    <span className="text-xs font-normal theme-text-muted theme-bg-muted/50 px-2 py-0.5 rounded-full">
                                        系统自动分析
                                    </span>
                                </h3>

                                {/* 研判要点列表 */}
                                <div className="space-y-2 text-sm mb-4">
                                    {/* 数据范围说明 */}
                                    <div className="flex items-start gap-2 theme-text-secondary">
                                        <span className="text-blue-400 mt-0.5">•</span>
                                        <span>
                                            本次分析涵盖 <span className="text-blue-400 font-bold">{data.persons.length}</span> 名核心人员、
                                            <span className="text-cyan-400 font-bold">{data.companies.length}</span> 家关联公司的流水数据
                                        </span>
                                    </div>

                                    {/* 异常收入 */}
                                    {incomeDetails.length > 0 && (
                                        <div className="flex items-start gap-2 theme-text-secondary">
                                            <span className="text-orange-400 mt-0.5">•</span>
                                            <span className="space-y-1">
                                                <span>
                                                    异常收入线索共 <span className="text-orange-400 font-bold">{preliminaryMetrics.income.total}</span> 条
                                                    （含高/中风险汇总 <span className="text-orange-400 font-bold">{preliminaryMetrics.income.riskRollupCount}</span> 条），
                                                    涉及金额约 <span className="text-orange-400 font-bold">¥{(preliminaryMetrics.income.amount / 10000).toFixed(1)}万</span>
                                                </span>
                                                <span className="block text-xs theme-text-dim">
                                                    去重后独立源记录约 <span className="font-semibold">{preliminaryMetrics.income.independentSourceCount}</span> 条（按来源文件+行号）
                                                </span>
                                            </span>
                                        </div>
                                    )}

                                    {/* 借贷异常 */}
                                    {loanDetails.length > 0 && (
                                        <div className="flex items-start gap-2 theme-text-secondary">
                                            <span className="text-yellow-400 mt-0.5">•</span>
                                            <span className="space-y-1">
                                                <span>
                                                    借贷线索共 <span className="text-yellow-400 font-bold">{preliminaryMetrics.loan.total}</span> 条
                                                    （交易类{preliminaryMetrics.loan.tradeCount}、模式类{preliminaryMetrics.loan.patternCount}、关系类{preliminaryMetrics.loan.relationCount}）
                                                </span>
                                                <span className="block text-xs theme-text-dim">
                                                    去重后约 <span className="font-semibold">{preliminaryMetrics.loan.uniqueRelationCount}</span> 组人员-对手方关系
                                                </span>
                                            </span>
                                        </div>
                                    )}

                                    {/* 风险实体 */}
                                    {(criticalRiskEntities.length > 0 || highRiskEntities.length > 0) && (
                                        <div className="flex items-start gap-2 theme-text-secondary">
                                            <span className="text-red-400 mt-0.5">•</span>
                                            <span>
                                                发现 <span className="text-red-400 font-bold">{criticalRiskEntities.length}</span> 个疑似极高风险实体、
                                                <span className="text-orange-400 font-bold">{highRiskEntities.length}</span> 个疑似高风险实体，
                                                建议优先核实
                                            </span>
                                        </div>
                                    )}
                                </div>

                                {/* 重要提示 */}
                                <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 text-xs text-yellow-300/90">
                                    <span className="font-bold">⚠️ 重要提示：</span>{' '}
                                    以上结论由系统通过规则识别逻辑自动生成，仅供参考。<span className="font-medium">重要数据仍需人工复核确认</span>，
                                    且“总条目数”包含分类重叠，不等同于独立交易笔数，请优先参考去重口径。
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 第二部分：核查资料索引 */}
                    {auditNavigation && (
                        <div className="card">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-2 rounded-lg bg-emerald-500/10">
                                    <Folder className="w-5 h-5 text-emerald-400" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-white">📂 核查资料索引</h3>
                                    <p className="text-xs theme-text-dim">请以以下成品数据为准开展人工核查工作</p>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {/* 个人清洗数据 */}
                                <div className="theme-bg-muted/40 rounded-xl p-4 border theme-border flex flex-col">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Users className="w-4 h-4 text-blue-400" />
                                        <span className="font-medium text-white text-sm">个人清洗数据</span>
                                        <span className="ml-auto bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full">
                                            {auditNavigation.persons.length} 个
                                        </span>
                                    </div>
                                    <div className="text-xs theme-text-dim mb-3 font-mono">
                                        {auditNavigation.outputDir}/cleaned_data/个人/
                                    </div>
                                    <div className="space-y-1 flex-1 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800/50 pr-1">
                                        {auditNavigation.persons.map((p, idx) => (
                                            <div key={idx} className="flex items-center gap-2 text-xs theme-text-muted hover:theme-text transition-colors">
                                                <FileSpreadsheet className="w-3 h-3 text-emerald-500 flex-shrink-0" />
                                                <span className="truncate" title={p.filename}>{p.name}_合并流水.xlsx</span>
                                                <span className="theme-text-dim ml-auto flex-shrink-0">{p.sizeFormatted}</span>
                                            </div>
                                        ))}
                                    </div>
                                    {/* 打开文件夹按钮 */}
                                    <button
                                        onClick={() => {
                                            fetch(`${API_BASE_URL}/api/open-folder`, {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ relativePath: auditNavigation.paths.cleanedDataPerson })
                                            }).catch(console.error);
                                        }}
                                        className="mt-3 w-full flex items-center justify-center gap-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-medium py-2 rounded-lg transition-colors"
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                        打开文件夹
                                    </button>
                                </div>

                                {/* 公司清洗数据 */}
                                <div className="theme-bg-muted/40 rounded-xl p-4 border theme-border flex flex-col">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Building2 className="w-4 h-4 text-cyan-400" />
                                        <span className="font-medium text-white text-sm">公司清洗数据</span>
                                        <span className="ml-auto bg-cyan-500/20 text-cyan-400 text-xs px-2 py-0.5 rounded-full">
                                            {auditNavigation.companies.length} 个
                                        </span>
                                    </div>
                                    <div className="text-xs theme-text-dim mb-3 font-mono">
                                        {auditNavigation.outputDir}/cleaned_data/公司/
                                    </div>
                                    <div className="space-y-1 flex-1 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800/50 pr-1">
                                        {auditNavigation.companies.map((c, idx) => (
                                            <div key={idx} className="flex items-center gap-2 text-xs theme-text-muted hover:theme-text transition-colors">
                                                <FileSpreadsheet className="w-3 h-3 text-emerald-500 flex-shrink-0" />
                                                <span className="truncate" title={c.filename}>{truncate(c.name, 15)}_合并流水.xlsx</span>
                                                <span className="theme-text-dim ml-auto flex-shrink-0">{c.sizeFormatted}</span>
                                            </div>
                                        ))}
                                    </div>
                                    {/* 打开文件夹按钮 */}
                                    <button
                                        onClick={() => {
                                            fetch(`${API_BASE_URL}/api/open-folder`, {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ relativePath: auditNavigation.paths.cleanedDataCompany })
                                            }).catch(console.error);
                                        }}
                                        className="mt-3 w-full flex items-center justify-center gap-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 text-xs font-medium py-2 rounded-lg transition-colors"
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                        打开文件夹
                                    </button>
                                </div>

                                {/* 核查底稿报告 */}
                                <div className="theme-bg-muted/40 rounded-xl p-4 border theme-border flex flex-col">
                                    <div className="flex items-center gap-2 mb-3">
                                        <FileText className="w-4 h-4 text-orange-400" />
                                        <span className="font-medium text-white text-sm">核查底稿报告</span>
                                        <span className="ml-auto bg-orange-500/20 text-orange-400 text-xs px-2 py-0.5 rounded-full">
                                            {auditNavigation.reports.length} 个
                                        </span>
                                    </div>
                                    <div className="text-xs theme-text-dim mb-3 font-mono">
                                        {auditNavigation.outputDir}/analysis_results/
                                    </div>
                                    <div className="space-y-1.5 flex-1 max-h-40 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800/50 pr-1">
                                        {auditNavigation.reports.map((r, idx) => (
                                            <div key={idx} className={`flex items-center gap-2 text-xs transition-colors ${r.isPrimary ? 'text-orange-300 font-medium' : 'theme-text-muted hover:theme-text'}`}>
                                                {r.name.endsWith('.xlsx') ? (
                                                    <FileSpreadsheet className={`w-3 h-3 flex-shrink-0 ${r.isPrimary ? 'text-orange-400' : 'text-emerald-500'}`} />
                                                ) : (
                                                    <FileText className={`w-3 h-3 flex-shrink-0 ${r.isPrimary ? 'text-orange-400' : 'theme-text-dim'}`} />
                                                )}
                                                <span className="truncate" title={r.name}>
                                                    {r.isPrimary && '⭐ '}{truncate(r.name, 20)}
                                                </span>
                                                <span className="theme-text-dim ml-auto flex-shrink-0">{r.sizeFormatted}</span>
                                            </div>
                                        ))}
                                    </div>
                                    {/* 打开文件夹按钮 */}
                                    <button
                                        onClick={() => {
                                            fetch(`${API_BASE_URL}/api/open-folder`, {
                                                method: 'POST',
                                                headers: { 'Content-Type': 'application/json' },
                                                body: JSON.stringify({ relativePath: auditNavigation.paths.analysisResults })
                                            }).catch(console.error);
                                        }}
                                        className="mt-3 w-full flex items-center justify-center gap-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 text-xs font-medium py-2 rounded-lg transition-colors"
                                    >
                                        <ExternalLink className="w-3.5 h-3.5" />
                                        打开文件夹
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Audit Analysis Metrics - Clickable */}
            <div className="lg:col-span-3 card">
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-red-500/10">
                        <AlertTriangle className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">审计核心指标</h3>
                        <p className="text-xs theme-text-dim">点击查看详情</p>
                    </div>
                </div>
                {hasRealData ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
                        {auditMetrics.map((metric, idx) => (
                            <div
                                key={idx}
                                className="theme-bg-muted/40 rounded-lg p-3 text-center hover:theme-bg-muted/60 transition-colors cursor-pointer hover:ring-1 hover:ring-blue-500/50"
                                onClick={() => setSelectedMetric(metric)}
                            >
                                <div className={`text-2xl font-bold ${metric.color}`}>{metric.value}</div>
                                <div className="text-xs theme-text-muted mt-1">{metric.label}</div>
                                <div className="text-[10px] theme-text-dim">{metric.desc}</div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-6 theme-text-dim text-sm">完成分析后查看审计指标</div>
                )}
            </div>

            {/* Entity Fund Flow Comparison - Bar Chart with Person/Company Toggle */}
            <div className="lg:col-span-2 card">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <TrendingUp className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">
                                {entityType === 'person' ? '个人资金流量' : '企业资金流量'}
                            </h3>
                            <p className="text-xs theme-text-dim">
                                {hasRealData ? `共 ${entityType === 'person' ? personProfiles.length : companyProfiles.length} 位，按流水总额排序` : '等待分析数据'}
                            </p>
                        </div>
                    </div>
                    {/* Person/Company Tab Switcher */}
                    <div className="flex items-center gap-1 theme-bg-muted/50 rounded-lg p-1">
                        <button
                            onClick={() => setEntityType('person')}
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${entityType === 'person'
                                ? 'bg-blue-500 text-white shadow-lg'
                                : 'theme-text-muted hover:text-white'
                                }`}
                        >
                            <Users className="w-3 h-3 inline mr-1" />
                            个人
                        </button>
                        <button
                            onClick={() => setEntityType('company')}
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${entityType === 'company'
                                ? 'bg-cyan-500 text-white shadow-lg'
                                : 'theme-text-muted hover:text-white'
                                }`}
                        >
                            <Building2 className="w-3 h-3 inline mr-1" />
                            企业
                        </button>
                    </div>
                </div>

                {/* 审计仪表板卡片列表 */}
                <div className="space-y-3 max-h-[420px] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent pr-1">
                    {hasRealData && currentFlowData.length > 0 ? (
                        <>
                            {entityType === 'person' ? (
                                // 个人审计卡片（增强版）
                                personProfiles.map((person, index) => {
                                    const maxTotal = Math.max(...personProfiles.map(p => p.total));
                                    const widthPercent = maxTotal > 0 ? (person.total / maxTotal) * 100 : 0;

                                    return (
                                        <div
                                            key={person.fullName}
                                            className="group relative theme-bg-muted/40 hover:theme-bg-muted/70 rounded-xl p-4 transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 border border-transparent hover:border-blue-500/30"
                                        >
                                            {/* 排名标识 & 名称 & 金额 */}
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${index === 0 ? 'bg-gradient-to-br from-yellow-400 to-orange-500 text-white shadow-lg shadow-orange-500/30' :
                                                        index === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-400 theme-text' :
                                                            index === 2 ? 'bg-gradient-to-br from-amber-600 to-amber-700 text-white' :
                                                                'theme-bg-muted theme-text-muted'
                                                        }`}>
                                                        {index + 1}
                                                    </div>
                                                    <div>
                                                        <span className="font-semibold text-white text-sm" title={person.fullName}>
                                                            {person.name}
                                                        </span>
                                                        <span className="text-[10px] theme-text-dim ml-2">{person.transactionCount}笔</span>
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                                                        ¥{person.total.toFixed(0)}万
                                                    </span>
                                                    <div className="text-[10px] theme-text-dim">流水总额</div>
                                                </div>
                                            </div>

                                            {/* 渐变进度条 */}
                                            <div className="relative h-2 theme-bg-muted/50 rounded-full overflow-hidden mb-3">
                                                <div
                                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 via-cyan-500 to-teal-400 rounded-full transition-all duration-500"
                                                    style={{ width: `${widthPercent}%` }}
                                                />
                                                <div
                                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500/50 via-cyan-500/50 to-teal-400/50 rounded-full animate-pulse"
                                                    style={{ width: `${widthPercent}%` }}
                                                />
                                            </div>

                                            {/* 明细行：收入/支出/净流 */}
                                            <div className="flex items-center gap-4 text-xs theme-text-muted mb-2">
                                                <span className="flex items-center gap-1">
                                                    <ArrowDownLeft className="w-3 h-3 text-green-400" />
                                                    收入 <span className="text-green-400 font-medium">{person.收入.toFixed(0)}万</span>
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <ArrowUpRight className="w-3 h-3 text-orange-400" />
                                                    支出 <span className="text-orange-400 font-medium">{person.支出.toFixed(0)}万</span>
                                                </span>
                                                <span className={`flex items-center gap-1 ${person.netFlow >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                    净流 {person.netFlow >= 0 ? '+' : ''}{(person.netFlow / 10000).toFixed(0)}万
                                                </span>
                                            </div>

                                            {/* 指标徽章行 */}
                                            <div className="flex flex-wrap items-center gap-1.5">
                                                {/* 工资金额徽章 */}
                                                {person.salaryTotal > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/20 text-blue-400 ring-1 ring-blue-500/30 cursor-pointer hover:bg-blue-500/30 transition-colors">
                                                        💼 工资{person.salaryTotal.toFixed(0)}万
                                                    </span>
                                                )}

                                                {/* 理财金额徽章 */}
                                                {person.wealthTotal > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/20 text-indigo-400 ring-1 ring-indigo-500/30 cursor-pointer hover:bg-indigo-500/30 transition-colors">
                                                        📊 理财{person.wealthTotal.toFixed(0)}万
                                                    </span>
                                                )}

                                                {/* 现金占比徽章 */}
                                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium cursor-pointer transition-colors ${person.riskLevel === 'high' ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/30' :
                                                    person.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-400 ring-1 ring-yellow-500/30 hover:bg-yellow-500/30' :
                                                        'bg-green-500/20 text-green-400 ring-1 ring-green-500/30 hover:bg-green-500/30'
                                                    }`}>
                                                    <Banknote className="w-3 h-3" />
                                                    现金{person.cashRatio.toFixed(0)}% ({person.cashTxCount}笔)
                                                </span>

                                                {/* 第三方支付徽章 */}
                                                {person.thirdPartyTotal > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/30 cursor-pointer hover:bg-cyan-500/30 transition-colors">
                                                        📱 三方{person.thirdPartyTotal.toFixed(0)}万
                                                    </span>
                                                )}

                                                {/* 异常收入徽章 */}
                                                {person.anomalyCount > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-500/20 text-purple-400 ring-1 ring-purple-500/30 cursor-pointer hover:bg-purple-500/30 transition-colors">
                                                        <AlertTriangle className="w-3 h-3" />
                                                        异常{person.anomalyCount}笔
                                                    </span>
                                                )}

                                                {/* 查看详情按钮 */}
                                                <button className="ml-auto opacity-0 group-hover:opacity-100 text-[10px] text-blue-400 hover:text-blue-300 transition-all flex items-center gap-1 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-md">
                                                    详情 <ChevronRight className="w-3 h-3" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                // 企业审计仪表板卡片（增强版）
                                companyProfiles.map((company, index) => {
                                    const maxTotal = Math.max(...companyProfiles.map(c => c.total));
                                    const widthPercent = maxTotal > 0 ? (company.total / maxTotal) * 100 : 0;

                                    return (
                                        <div
                                            key={company.fullName}
                                            className="group relative theme-bg-muted/40 hover:theme-bg-muted/70 rounded-xl p-4 transition-all duration-300 hover:shadow-lg hover:shadow-cyan-500/10 border border-transparent hover:border-cyan-500/30"
                                        >
                                            {/* 排名标识 & 名称 & 金额 */}
                                            <div className="flex items-center justify-between mb-2">
                                                <div className="flex items-center gap-3">
                                                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold ${index === 0 ? 'bg-gradient-to-br from-cyan-400 to-teal-500 text-white shadow-lg shadow-teal-500/30' :
                                                        index === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-400 theme-text' :
                                                            index === 2 ? 'bg-gradient-to-br from-amber-600 to-amber-700 text-white' :
                                                                'theme-bg-muted theme-text-muted'
                                                        }`}>
                                                        {index + 1}
                                                    </div>
                                                    <div>
                                                        <span className="font-semibold text-white text-sm" title={company.fullName}>
                                                            {company.name}
                                                        </span>
                                                        <span className="text-[10px] theme-text-dim ml-2">{company.transactionCount}笔</span>
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <span className="text-lg font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
                                                        ¥{company.total.toFixed(0)}万
                                                    </span>
                                                    <div className="text-[10px] theme-text-dim">流水总额</div>
                                                </div>
                                            </div>

                                            {/* 渐变进度条（青色系） */}
                                            <div className="relative h-2 theme-bg-muted/50 rounded-full overflow-hidden mb-3">
                                                <div
                                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500 via-teal-500 to-emerald-400 rounded-full transition-all duration-500"
                                                    style={{ width: `${widthPercent}%` }}
                                                />
                                                <div
                                                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyan-500/50 via-teal-500/50 to-emerald-400/50 rounded-full animate-pulse"
                                                    style={{ width: `${widthPercent}%` }}
                                                />
                                            </div>

                                            {/* 明细行：收入/支出/净流 */}
                                            <div className="flex items-center gap-4 text-xs theme-text-muted mb-2">
                                                <span className="flex items-center gap-1">
                                                    <ArrowDownLeft className="w-3 h-3 text-green-400" />
                                                    收入 <span className="text-green-400 font-medium">{company.收入.toFixed(0)}万</span>
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <ArrowUpRight className="w-3 h-3 text-orange-400" />
                                                    支出 <span className="text-orange-400 font-medium">{company.支出.toFixed(0)}万</span>
                                                </span>
                                                <span className={`flex items-center gap-1 ${company.netFlow >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                    净流 {company.netFlow >= 0 ? '+' : ''}{(company.netFlow / 10000).toFixed(0)}万
                                                </span>
                                            </div>

                                            {/* 企业专属指标徽章行 */}
                                            <div className="flex flex-wrap items-center gap-1.5">
                                                {/* 现金占比徽章 */}
                                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium cursor-pointer transition-colors ${company.riskLevel === 'high' ? 'bg-red-500/20 text-red-400 ring-1 ring-red-500/30 hover:bg-red-500/30' :
                                                    company.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-400 ring-1 ring-yellow-500/30 hover:bg-yellow-500/30' :
                                                        'bg-green-500/20 text-green-400 ring-1 ring-green-500/30 hover:bg-green-500/30'
                                                    }`}>
                                                    <Banknote className="w-3 h-3" />
                                                    现金{company.cashRatio.toFixed(0)}% ({company.cashTxCount}笔)
                                                </span>

                                                {/* 第三方支付徽章 */}
                                                {company.thirdPartyTotal > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/30 cursor-pointer hover:bg-cyan-500/30 transition-colors">
                                                        📱 三方{company.thirdPartyTotal.toFixed(0)}万
                                                    </span>
                                                )}

                                                {/* 最大单笔交易徽章 */}
                                                {company.maxTransaction > 0 && (
                                                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-500/20 text-orange-400 ring-1 ring-orange-500/30 cursor-pointer hover:bg-orange-500/30 transition-colors">
                                                        💰 最大{company.maxTransaction.toFixed(0)}万
                                                    </span>
                                                )}

                                                {/* 查看详情按钮 */}
                                                <button className="ml-auto opacity-0 group-hover:opacity-100 text-[10px] text-cyan-400 hover:text-cyan-300 transition-all flex items-center gap-1 bg-cyan-500/10 hover:bg-cyan-500/20 px-2 py-0.5 rounded-md">
                                                    详情 <ChevronRight className="w-3 h-3" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </>
                    ) : (
                        <EmptyState type="data" message={`完成分析后查看${entityType === 'person' ? '个人' : '企业'}资金画像`} />
                    )}
                </div>
            </div>

            {/* 🆕 Audit Findings Distribution - Pie Chart */}
            <div className="card">
                <div className="flex items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-violet-500/10">
                            <Wallet className="w-5 h-5 text-violet-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">审计发现分布</h3>
                            <p className="text-xs theme-text-dim">按借贷/收入分类统计</p>
                        </div>
                    </div>
                </div>

                <div className="h-40 mb-2">
                    <ResponsiveContainer width="100%" height="100%" minHeight={80}>
                        <PieChart>
                            <Pie
                                data={incomeDistributionData}
                                cx="50%"
                                cy="50%"
                                innerRadius={45}
                                outerRadius={70}
                                paddingAngle={3}
                                dataKey="value"
                                stroke="#1f2937"
                                strokeWidth={2}
                            >
                                {incomeDistributionData.map((entry: { name: string; value: number; color: string }, index: number) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Pie>
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #3b82f6',
                                    borderRadius: '8px',
                                    padding: '8px 12px',
                                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)'
                                }}
                                itemStyle={{ color: '#f1f5f9' }}
                                labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                                formatter={(value: number | undefined, name?: string) => value !== undefined ? [`${value} 条`, name || ''] : ['', '']} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                {/* 图例区域 */}
                <div className="space-y-1.5">
                    {incomeDistributionData.map((item: { name: string; value: number; percent?: number; color: string }) => (
                        <div key={item.name} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                                <span className="theme-text-secondary">{item.name}</span>
                            </div>
                            <span className="font-medium text-white">{item.percent || item.value}%</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ==================== Risk Intel Tab ====================

function RiskIntelTab() {
    const { data } = useApp();
    const [filter, setFilter] = useState<'all' | 'direct' | 'cash' | 'timing'>('all');

    const riskFilters = [
        { id: 'all', label: '全部风险', count: data.suspicions.directTransfers.length + data.suspicions.cashCollisions.length + data.suspicions.cashTimingPatterns.length },
        { id: 'direct', label: '直接转账', count: data.suspicions.directTransfers.length },
        { id: 'cash', label: '现金碰撞', count: data.suspicions.cashCollisions.length },
        { id: 'timing', label: '时序异常', count: data.suspicions.cashTimingPatterns.length },
    ] as const;

    // 定义联合类型来处理不同数据类型的属性差异
    type SuspiciousActivity = {
        type: 'direct' | 'cash' | 'timing';
        date: string;
        from: string;
        to: string;
        amount: number;
        description: string;
        riskLevel: string;
        timeDiff?: number | null;
    };

    // 根据过滤器获取要显示的数据
    const getFilteredData = () => {
        const directTransfers = data.suspicions.directTransfers.map((tx: any): SuspiciousActivity => ({
            type: 'direct' as const,
            date: tx.date,
            from: tx.from,
            to: tx.to,
            amount: tx.amount,
            description: tx.description || '核心人员与涉案企业直接资金往来',
            riskLevel: tx.riskLevel || tx.risk_level || '高风险',
        }));

        const cashCollisions = data.suspicions.cashCollisions.map((collision: any): SuspiciousActivity => ({
            type: 'cash' as const,
            date: collision.time1,
            from: collision.person1,
            to: collision.person2,
            amount: (collision.amount1 || 0) + (collision.amount2 || 0),
            timeDiff: collision.timeDiff || null,
            description: collision.description || `现金取存时间差异常，疑似绕开银行转账监控`,
            riskLevel: collision.riskLevel || collision.risk_level || '高风险',
        }));

        const timingPatterns = data.suspicions.cashTimingPatterns.map((pattern: any): SuspiciousActivity => ({
            type: 'timing' as const,
            date: pattern.time1 || pattern.date || '-',
            from: pattern.person1 || '-',
            to: pattern.person2 || '-',
            amount: (pattern.amount1 || 0) + (pattern.amount2 || 0),
            timeDiff: pattern.timeDiff || null,
            description: pattern.description || `取现与存入存在时间规律，需进一步核查`,
            riskLevel: pattern.riskLevel || pattern.risk_level || '中风险',
        }));

        switch (filter) {
            case 'direct':
                return directTransfers;
            case 'cash':
                return cashCollisions;
            case 'timing':
                return timingPatterns;
            case 'all':
            default:
                return [...directTransfers, ...cashCollisions, ...timingPatterns];
        }
    };

    const filteredData = getFilteredData();
    const hasAnyData = data.suspicions.directTransfers.length > 0 ||
        data.suspicions.cashCollisions.length > 0 ||
        data.suspicions.cashTimingPatterns.length > 0;

    const getTypeLabel = (type: 'direct' | 'cash' | 'timing') => {
        switch (type) {
            case 'direct': return '直接转账';
            case 'cash': return '现金碰撞';
            case 'timing': return '时序异常';
        }
    };

    return (
        <div className="space-y-6">
            {/* Filter Bar */}
            <div className="flex items-center gap-2 flex-wrap">
                {riskFilters.map((f) => (
                    <button
                        key={f.id}
                        onClick={() => setFilter(f.id)}
                        className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
              transition-all duration-200
              ${filter === f.id
                                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                                : 'theme-bg-muted/50 theme-text-muted border theme-border hover:theme-border-strong hover:theme-text'
                            }
            `}
                    >
                        {f.label}
                        <span className={`
              px-1.5 py-0.5 rounded text-[10px] font-bold
              ${filter === f.id ? 'bg-red-500/30' : 'theme-bg-muted'}
            `}>
                            {f.count}
                        </span>
                    </button>
                ))}
            </div>

            {/* Suspicious Activity Table */}
            <div className="card">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 rounded-lg bg-red-500/10">
                        <AlertTriangle className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">可疑活动日志</h3>
                        <p className="text-xs theme-text-dim">
                            {filter === 'all' ? '显示所有类型' : `筛选: ${riskFilters.find(f => f.id === filter)?.label}`}
                            {' • '}共 {filteredData.length} 条记录
                        </p>
                    </div>
                </div>

                {filteredData.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b theme-border">
                                    <th className="pb-3 text-left text-xs font-semibold theme-text-dim uppercase tracking-wider">类型</th>
                                    <th className="pb-3 text-left text-xs font-semibold theme-text-dim uppercase tracking-wider">日期</th>
                                    <th className="pb-3 text-left text-xs font-semibold theme-text-dim uppercase tracking-wider">转出方/当事人</th>
                                    <th className="pb-3 text-left text-xs font-semibold theme-text-dim uppercase tracking-wider">转入方/关联方</th>
                                    <th className="pb-3 text-right text-xs font-semibold theme-text-dim uppercase tracking-wider">金额</th>
                                    <th className="pb-3 text-left text-xs font-semibold theme-text-dim uppercase tracking-wider">说明</th>
                                    <th className="pb-3 text-center text-xs font-semibold theme-text-dim uppercase tracking-wider">风险等级</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredData.map((item: SuspiciousActivity, idx: number) => (
                                    <tr key={idx} className="border-b theme-border/50 hover:bg-red-500/5 transition-colors">
                                        <td className="py-4">
                                            <span className={getRiskLevelBadgeStyle(item.riskLevel)}>
                                                {getTypeLabel(item.type)}
                                            </span>
                                        </td>
                                        <td className="py-4">
                                            <div className="flex items-center gap-2 theme-text-secondary">
                                                <Clock className="w-3 h-3 theme-text-dim" />
                                                <span className="text-xs">{formatDate(item.date)}</span>
                                            </div>
                                        </td>
                                        <td className="py-4 theme-text-secondary font-medium" title={formatPartyName(item.from)}>
                                            {truncate(formatPartyName(item.from), 12)}
                                        </td>
                                        <td className="py-4 theme-text-secondary font-medium" title={formatPartyName(item.to)}>
                                            {truncate(formatPartyName(item.to), 12)}
                                        </td>
                                        <td className="py-4 text-right">
                                            <span className="text-red-400 font-bold">{formatCurrency(item.amount)}</span>
                                        </td>
                                        <td className="py-4 max-w-[200px]" title={formatRiskDescription(item.description)}>
                                            <span className="text-xs theme-text-muted truncate block">{truncate(formatRiskDescription(item.description), 20)}</span>
                                        </td>
                                        <td className="py-4 text-center">
                                            <span className={getRiskLevelBadgeStyle(item.riskLevel)}>
                                                {formatRiskLevel(item.riskLevel)}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <EmptyState type={hasAnyData ? 'data' : 'safe'} message={hasAnyData ? '当前筛选条件下暂无记录' : undefined} />
                )}
            </div>
        </div>
    );
}

// ==================== Graph View Tab ====================

function GraphViewTab() {
    const { addLog } = useApp();

    const handleLog = (message: string) => {
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        addLog?.({ time: timeStr, level: 'INFO', msg: message });
    };

    return (
        <div className="w-full" style={{ height: 'calc(100vh - 200px)', minHeight: '700px' }}>
            <NetworkGraph onLog={handleLog} />
        </div>
    );
}

// ==================== Audit Report Tab ====================

function AuditReportTab() {
    const [reports, setReports] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState<string | null>(null);
    // P2-3: 预览状态
    const [previewFile, setPreviewFile] = useState<{ name: string; content: string; type: 'text' | 'html' } | null>(null);
    const [previewLoading, setPreviewLoading] = useState(false);

    // 从后端获取报告列表
    useEffect(() => {
        fetchReports();
    }, []);

    const fetchReports = async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await api.getReports();
            setReports(response.reports);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : '获取报告列表失败';
            setError(errorMsg);
            console.error('获取报告列表失败:', err);
        } finally {
            setLoading(false);
        }
    };

    // 下载报告
    const handleDownload = async (filename: string) => {
        try {
            setDownloading(filename);
            const blob = await api.downloadReport(filename);

            // 创建下载链接
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : '下载失败';
            console.error('下载报告失败:', err);
            alert(`下载失败: ${errorMsg}`);
        } finally {
            setDownloading(null);
        }
    };

    // P2-3: 预览报告
    const handlePreview = async (filename: string) => {
        // 只支持 txt/html 文件预览
        const ext = filename.toLowerCase().split('.').pop();
        if (!['txt', 'html', 'htm'].includes(ext || '')) {
            // 不支持的文件类型直接下载
            handleDownload(filename);
            return;
        }

        try {
            setPreviewLoading(true);
            // 使用专门的预览API端点
            const result = await api.previewReport(filename);

            if (result.success && result.content !== undefined) {
                setPreviewFile({
                    name: filename,
                    content: result.content,
                    type: result.type === 'text' ? 'text' : 'html'
                });
            } else {
                throw new Error('预览API返回无效数据');
            }
        } catch (err) {
            console.error('预览失败:', err);
            alert('预览失败，请尝试下载');
        } finally {
            setPreviewLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* P2-3: 预览 Modal */}
            {previewFile && (
                <div
                    className="fixed inset-0 lg:left-72 z-50 flex items-center justify-center p-4 lg:p-6 bg-black/80 backdrop-blur-sm"
                    onClick={() => setPreviewFile(null)}
                >
                    <div
                        className="theme-bg-base border theme-border rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden"
                        onClick={e => e.stopPropagation()}
                    >
                        {/* Modal Header */}
                        <div className="flex items-center justify-between p-4 border-b theme-border theme-bg-muted/50 flex-shrink-0">
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-lg bg-blue-500/10">
                                    <FileText className="w-5 h-5 text-blue-500" />
                                </div>
                                <div>
                                    <h3 className="font-semibold theme-text">{previewFile.name}</h3>
                                    <p className="text-xs theme-text-muted">
                                        {previewFile.type === 'html' ? 'HTML 格式报告' : '文本报告'}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => handleDownload(previewFile.name)}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border theme-border theme-text-muted hover:text-blue-500 hover:border-blue-500 hover:bg-blue-500/10 transition-colors"
                                >
                                    <Download className="w-4 h-4" />
                                    下载
                                </button>
                                <button
                                    onClick={() => setPreviewFile(null)}
                                    className="p-2 hover:theme-bg-muted rounded-lg transition-colors"
                                >
                                    <X className="w-5 h-5 theme-text-muted" />
                                </button>
                            </div>
                        </div>

                        {/* Modal Content */}
                        <div className={`flex-1 overflow-auto ${previewFile.type === 'html' ? 'bg-white' : 'theme-bg-base'}`}>
                            {previewFile.type === 'html' ? (
                                <iframe
                                    srcDoc={previewFile.content}
                                    className="w-full h-full border-none"
                                    title={previewFile.name}
                                    sandbox="allow-same-origin"
                                />
                            ) : (
                                <pre className="p-6 text-sm theme-text whitespace-pre-wrap font-mono leading-relaxed">
                                    {previewFile.content}
                                </pre>
                            )}
                        </div>
                    </div>
                </div>
            )}

            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-green-500/10">
                            <FileText className="w-5 h-5 text-green-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">导出审计成果</h3>
                            <p className="text-xs theme-text-dim">下载分析报告和数据文件</p>
                        </div>
                    </div>
                    <button
                        onClick={fetchReports}
                        disabled={loading}
                        className="btn-secondary text-xs"
                    >
                        <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                        刷新
                    </button>
                </div>

                {loading ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="w-12 h-12 rounded-2xl theme-bg-muted/50 flex items-center justify-center mb-4">
                            <RefreshCw className="w-6 h-6 theme-text-dim animate-spin mb-4" />
                            <span className="ml-3 theme-text-muted font-medium">加载报告列表...</span>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
                            <AlertTriangle className="w-8 h-8 text-red-500" />
                            <p className="theme-text-muted font-medium">加载失败</p>
                            <p className="theme-text-dim text-sm mt-1">{error}</p>
                            <button
                                onClick={fetchReports}
                                className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
                            >
                                重试
                            </button>
                        </div>
                    </div>
                ) : reports.length === 0 ? (
                    <EmptyState type="data" message="暂无报告" />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {reports.map((report, idx) => {
                            const Icon = (
                                report.name.includes('xlsx') || report.name.includes('xls') ? FileText :
                                    report.name.includes('html') || report.name.includes('htm') ? Network :
                                        report.name.includes('pdf') ? FileText : FileText
                            );
                            const isDownloading = downloading === report.name;

                            return (
                                <div
                                    key={idx}
                                    className="flex items-center justify-between p-4 rounded-xl border bg-gray-800/30 theme-border hover:theme-border-strong transition-all duration-200"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="p-3 rounded-xl bg-blue-500/10">
                                            <Icon className="w-5 h-5 text-blue-400" />
                                        </div>
                                        <div>
                                            <p className="font-medium theme-text-secondary">{truncate(report.name, 25)}</p>
                                            <p className="text-xs theme-text-dim mt-0.5">{getFileTypeDescription(report.name)}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-[10px] font-mono theme-text-dim uppercase">{getFileType(report.name)}</span>
                                                <span className="text-[10px] theme-text-dim">•</span>
                                                <span className="text-[10px] theme-text-dim">{formatFileSize(report.size)}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {/* 预览按钮 - 主操作 */}
                                        {['txt', 'html', 'htm'].includes(report.name.toLowerCase().split('.').pop() || '') && (
                                            <button
                                                onClick={() => handlePreview(report.name)}
                                                disabled={previewLoading}
                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30 hover:border-cyan-400 transition-colors"
                                            >
                                                <Eye className="w-4 h-4" />
                                                预览
                                            </button>
                                        )}
                                        {/* 下载按钮 - 次操作 */}
                                        <button
                                            onClick={() => handleDownload(report.name)}
                                            disabled={isDownloading}
                                            className={`
                                                flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm
                                                transition-all duration-200
                                                ${isDownloading
                                                    ? 'theme-bg-muted/50 theme-text-dim cursor-wait border theme-border-strong'
                                                    : 'border theme-border-strong hover:border-blue-500 theme-text-muted hover:text-blue-400 hover:bg-blue-500/10'
                                                }
                                            `}
                                            title="下载文件"
                                        >
                                            {isDownloading ? (
                                                <RefreshCw className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <Download className="w-4 h-4" />
                                            )}
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Report Builder - Interactive Report Generator */}
            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/10">
                            <FileText className="w-5 h-5 text-cyan-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">自定义报告生成器</h3>
                            <p className="text-xs theme-text-dim">选择模块、生成专业审计报告</p>
                        </div>
                    </div>
                    <span className="text-[10px] text-cyan-400 bg-cyan-500/10 px-2 py-1 rounded">Protocol Omega</span>
                </div>
                <ReportBuilder />
            </div>
        </div>
    );
}

// ==================== Helper Functions ====================

function getFileTypeDescription(filename: string): string {
    const name = filename.toLowerCase();
    if (name.includes('excel') || name.includes('xlsx') || name.includes('xls')) {
        return '完整的分析结果 Excel 格式';
    }
    if (name.includes('html') || name.includes('report')) {
        return '详细的文字分析报告';
    }
    if (name.includes('flow') || name.includes('graph')) {
        return '交互式 HTML 资金流向图';
    }
    if (name.includes('risk') || name.includes('assessment')) {
        return '实体风险等级评估';
    }
    return '分析报告文件';
}

function getFileType(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'xlsx' || ext === 'xls') return 'Excel';
    if (ext === 'html' || ext === 'htm') return 'HTML';
    if (ext === 'pdf') return 'PDF';
    return ext || 'File';
}
