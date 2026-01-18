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
    Building2
} from 'lucide-react';
import { api } from '../services/api';
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
import { formatDate, formatCurrency, formatAmountInWan, truncate, getRiskLevelBadgeStyle, formatFileSize, formatRiskLevel, formatRiskDescription, formatPartyName, formatAnalysisType, formatAuditDateTime } from '../utils/formatters';
import { EmptyState } from './common/EmptyState';
import NetworkGraph from './NetworkGraph';
import { ReportBuilder } from './ReportBuilder';

export function TabContent() {
    const { ui, setActiveTab } = useApp();

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* Tab Navigation */}
            <div className="flex items-center gap-1 p-1 bg-gray-900/50 rounded-xl border border-gray-800/50 mb-6 w-fit backdrop-blur-sm">
                <TabButton
                    label="数据概览"
                    icon={Activity}
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
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
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
    'related_direct' | 'cash_collision' | 'risk_critical' | 'risk_high' | 'risk_all';

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

    // 从真实数据生成趋势图数据（如果分析未完成，使用空数组）
    const hasRealData = analysis.status === 'completed' && Object.keys(data.profiles).length > 0;

    // 分离个人和公司
    const personProfiles = useMemo(() => {
        if (!hasRealData) return [];
        return Object.entries(data.profiles)
            .filter(([name]) => data.persons.includes(name))
            .map(([name, profile]) => ({
                name: truncate(name, 10),
                fullName: name,
                收入: (profile?.totalIncome || 0) / 10000,
                支出: (profile?.totalExpense || 0) / 10000,
                total: ((profile?.totalIncome || 0) + (profile?.totalExpense || 0)) / 10000,
            }))
            .sort((a, b) => b.total - a.total)
            .slice(0, 8);
    }, [hasRealData, data.profiles, data.persons]);

    const companyProfiles = useMemo(() => {
        if (!hasRealData) return [];
        return Object.entries(data.profiles)
            .filter(([name]) => data.companies.includes(name))
            .map(([name, profile]) => ({
                name: truncate(name, 10),
                fullName: name,
                收入: (profile?.totalIncome || 0) / 10000,
                支出: (profile?.totalExpense || 0) / 10000,
                total: ((profile?.totalIncome || 0) + (profile?.totalExpense || 0)) / 10000,
            }))
            .sort((a, b) => b.total - a.total)
            .slice(0, 8);
    }, [hasRealData, data.profiles, data.companies]);

    // 当前显示的流量数据
    const currentFlowData = entityType === 'person' ? personProfiles : companyProfiles;

    // 实体列表（用于选择器）
    const entityList = useMemo(() => {
        return data.persons || [];
    }, [data.persons]);

    // 收入来源分布 - 基于选中实体的资金画像
    const incomeDistributionData = useMemo(() => {
        if (!hasRealData) return [{ name: '等待分析', value: 100, color: '#374151' }];

        // 如果选中了特定实体
        if (selectedEntity !== 'all') {
            const profile = data.profiles[selectedEntity];
            if (!profile) return [{ name: '无数据', value: 100, color: '#374151' }];

            const income = profile.totalIncome || 0;
            const expense = profile.totalExpense || 0;
            const total = income + expense;

            if (total === 0) return [{ name: '无交易', value: 100, color: '#374151' }];

            return [
                { name: '收入', value: Math.round((income / total) * 100), color: '#10b981' },
                { name: '支出', value: Math.round((expense / total) * 100), color: '#ef4444' },
            ];
        }

        // 全部实体汇总 - 显示可疑交易类型分布
        const directCount = (data.suspicions.directTransfers || []).length;
        const cashCount = (data.suspicions.cashCollisions || []).length;
        const timingCount = (data.suspicions.cashTimingPatterns || []).length;
        const total = directCount + cashCount + timingCount;

        if (total === 0) return [{ name: '无可疑交易', value: 100, color: '#374151' }];

        const categories = [];
        if (directCount > 0) {
            categories.push({ name: '直接转账', value: directCount, percent: Math.round((directCount / total) * 100), color: '#3b82f6' });
        }
        if (cashCount > 0) {
            categories.push({ name: '现金碰撞', value: cashCount, percent: Math.round((cashCount / total) * 100), color: '#06b6d4' });
        }
        if (timingCount > 0) {
            categories.push({ name: '时序异常', value: timingCount, percent: Math.round((timingCount / total) * 100), color: '#f59e0b' });
        }

        return categories;
    }, [hasRealData, data.suspicions, data.profiles, selectedEntity]);

    const topEntities = Object.entries(data.profiles || {})
        .map(([name, profile]) => ({
            name,
            income: profile?.totalIncome || 0,
            expense: profile?.totalExpense || 0,
            transactions: profile?.transactionCount || 0,
        }))
        .sort((a, b) => b.income - a.income)
        .slice(0, 5);

    // 从 analysisResults 提取审计关键指标（后端返回的核心数据）
    const loanSummary = data.analysisResults?.loan?.summary || {};
    const loanDetails = data.analysisResults?.loan?.details || [];
    const incomeSummary = data.analysisResults?.income?.summary || {};
    const incomeDetails = data.analysisResults?.income?.details || [];
    const aggregationSummary = data.analysisResults?.aggregation?.summary || {};
    const rankedEntities = data.analysisResults?.aggregation?.rankedEntities || [];

    // 直接从 suspicions 计算实际数据条数
    const directTransfersCount = (data.suspicions.directTransfers || []).length;
    const cashCollisionsCount = (data.suspicions.cashCollisions || []).length;

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
            desc: '点击查看分类汇总',
            icon: Users
        },
        // 2. 异常收入分析 - 显示所有收入类型总数，弹窗中分类展示
        {
            key: 'income_analysis',
            label: '异常收入分析',
            value: incomeDetails.length,
            color: 'text-orange-400',
            desc: '点击查看分类汇总',
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
    ];

    // 获取指标详情数据 - 分类汇总表格展示
    // 【核心设计原则】审计人员需要看到分类清晰的汇总表格
    const getMetricDetails = (metric: AuditMetric): any[] => {
        switch (metric.key) {
            case 'loan_analysis':
                // 借贷风险分析 - 返回分类汇总数据
                // 【优化】对象/来源列显示涉及人员，让核查对象更清晰
                const loanTypes = [
                    { type: 'regular_repayment', label: '规律还款模式', desc: '每月定期还款' },
                    { type: 'no_repayment', label: '无还款借贷', desc: '借了钱没还过' },
                    { type: 'online_loan', label: '网贷平台交易', desc: '白条、花呗等' },
                    { type: 'bidirectional', label: '双向往来关系', desc: '同一人既借又还' },
                ];
                return loanTypes.map(t => {
                    const items = loanDetails.filter((x: any) => x._type === t.type);
                    const persons = [...new Set(items.map((x: any) => x.person))].filter(Boolean);
                    return {
                        // 【对象/来源】显示涉及的核查对象
                        name: persons.length > 0 ? persons.slice(0, 3).join('、') + (persons.length > 3 ? '等' : '') : '无',
                        // 【交易对手】显示类型名称
                        counterparty: t.label,
                        // 【金额】显示总金额
                        amount: items.reduce((sum: number, x: any) => sum + (x.amount || x.income_total || 0), 0),
                        // 【日期】显示记录数
                        date: `${items.length}条`,
                        // 【风险说明】显示类型描述
                        description: t.desc,
                        reasons: [],
                        _subType: t.type,
                        _count: items.length
                    };
                }).filter(x => x._count > 0);

            case 'income_analysis':
                // 异常收入分析 - 返回分类汇总数据
                // 【优化】对象/来源列显示涉及人员
                const incomeTypes = [
                    { type: 'high_risk', label: '高风险项目', desc: '综合评分高风险' },
                    { type: 'large_single', label: '大额单笔收入', desc: '单笔≥10万' },
                    { type: 'medium_risk', label: '中风险项目', desc: '综合评分中风险' },
                    { type: 'large_individual', label: '个人大额转入', desc: '来自个人的大额' },
                    { type: 'unknown_source', label: '来源不明收入', desc: '对手方不明' },
                    { type: 'same_source_multi', label: '同源多次收入', desc: '同一来源多次' },
                    { type: 'regular_non_salary', label: '规律非工资收入', desc: '固定周期非工资' },
                    { type: 'bribe_installment', label: '疑似分期受贿', desc: '分期模式' },
                ];
                return incomeTypes.map(t => {
                    const items = incomeDetails.filter((x: any) => x._type === t.type);
                    const persons = [...new Set(items.map((x: any) => x.person))].filter(Boolean);
                    return {
                        // 【对象/来源】显示涉及的核查对象
                        name: persons.length > 0 ? persons.slice(0, 3).join('、') + (persons.length > 3 ? '等' : '') : '无',
                        // 【交易对手】显示类型名称
                        counterparty: t.label,
                        // 【金额】显示总金额
                        amount: items.reduce((sum: number, x: any) => sum + (x.amount || x.avg_amount || x.total_amount || 0), 0),
                        // 【日期】显示记录数
                        date: `${items.length}条`,
                        // 【风险说明】显示类型描述
                        description: t.desc,
                        reasons: [],
                        _subType: t.type,
                        _count: items.length
                    };
                }).filter(x => x._count > 0);

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
                        source_file: tx.sourceFile,
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

            default:
                return [];
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Metric Detail Modal - Excel 式表格布局 */}
            {selectedMetric && (
                <div className="fixed inset-0 lg:left-72 z-50 flex items-center justify-center p-8 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedMetric(null)}>
                    <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b border-gray-800">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${selectedMetric.color.replace('text-', 'bg-').replace('-400', '-500/20').replace('-500', '-500/20')}`}>
                                    <selectedMetric.icon className={`w-5 h-5 ${selectedMetric.color}`} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-white">{selectedMetric.label}</h3>
                                    <p className="text-xs text-gray-500">共 {getMetricDetails(selectedMetric).length} 条记录</p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedMetric(null)} className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
                                <X className="w-5 h-5 text-gray-400" />
                            </button>
                        </div>

                        {/* Table Content */}
                        <div className="p-4 overflow-auto max-h-[70vh]">
                            {(() => {
                                const details = getMetricDetails(selectedMetric);
                                if (details.length === 0) {
                                    return <div className="text-center py-8 text-gray-500">暂无详细数据</div>;
                                }

                                return (
                                    <div className="overflow-x-auto rounded-lg border border-gray-700 mx-auto">
                                        <table className="w-full text-sm">
                                            <thead className="bg-gray-800 sticky top-0">
                                                <tr className="text-left text-gray-300 text-xs">
                                                    <th className="px-4 py-3 font-medium w-12">#</th>
                                                    <th className="px-4 py-3 font-medium">对象/来源</th>
                                                    <th className="px-4 py-3 font-medium">交易对手</th>
                                                    <th className="px-4 py-3 font-medium text-right">金额</th>
                                                    <th className="px-4 py-3 font-medium">交易时间</th>
                                                    <th className="px-4 py-3 font-medium">风险说明</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {details.slice(0, 50).map((item: any, idx: number) => (
                                                    <tr key={idx} className={`border-t border-gray-800 ${idx % 2 === 0 ? 'bg-gray-900/30' : 'bg-gray-900/60'} hover:bg-gray-800/50 transition-colors`}>
                                                        <td className="px-4 py-3 text-gray-500 font-mono text-xs">{idx + 1}</td>
                                                        <td className="px-4 py-3">
                                                            <div className="text-white font-medium">
                                                                {formatPartyName(item.name || item.entity || item.from || item.person || item.platform)}
                                                            </div>
                                                        </td>
                                                        <td className="px-4 py-3 text-gray-300">
                                                            {formatPartyName(item.counterparty || item.to || item.lender || '--')}
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
                                                        <td className="px-4 py-3 text-gray-400 font-mono text-xs whitespace-nowrap">
                                                            {formatAuditDateTime(item.date || item.first_income_date || item.loan_date || '--')}
                                                        </td>
                                                        <td className="px-4 py-3">
                                                            <div className="text-gray-300 text-xs" title={item.description || item.loan_type || item.risk_reason || ''}>
                                                                {formatRiskDescription(item.description || item.loan_type || item.risk_reason || '--')}
                                                            </div>
                                                            {item.reasons && item.reasons.length > 0 && (
                                                                <div className="text-[10px] text-gray-500 mt-1">
                                                                    {item.reasons.slice(0, 2).map((r: string) => formatRiskDescription(r)).join(' | ')}
                                                                </div>
                                                            )}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>

                                        {details.length > 50 && (
                                            <div className="text-center py-3 text-gray-500 text-sm bg-gray-800/50 border-t border-gray-700">
                                                仅显示前 50 条，共 {details.length} 条记录
                                            </div>
                                        )}
                                    </div>
                                );
                            })()}
                        </div>
                    </div>
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
                        <p className="text-xs text-gray-500">点击查看详情</p>
                    </div>
                </div>
                {hasRealData ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
                        {auditMetrics.map((metric, idx) => (
                            <div
                                key={idx}
                                className="bg-gray-800/40 rounded-lg p-3 text-center hover:bg-gray-800/60 transition-colors cursor-pointer hover:ring-1 hover:ring-blue-500/50"
                                onClick={() => setSelectedMetric(metric)}
                            >
                                <div className={`text-2xl font-bold ${metric.color}`}>{metric.value}</div>
                                <div className="text-xs text-gray-400 mt-1">{metric.label}</div>
                                <div className="text-[10px] text-gray-600">{metric.desc}</div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-6 text-gray-500 text-sm">完成分析后查看审计指标</div>
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
                            <p className="text-xs text-gray-500">
                                {hasRealData ? 'TOP 8 按总流量排序' : '等待分析数据'}
                            </p>
                        </div>
                    </div>
                    {/* Person/Company Tab Switcher */}
                    <div className="flex items-center gap-1 bg-gray-800/50 rounded-lg p-1">
                        <button
                            onClick={() => setEntityType('person')}
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${entityType === 'person'
                                ? 'bg-blue-500 text-white shadow-lg'
                                : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            <Users className="w-3 h-3 inline mr-1" />
                            个人
                        </button>
                        <button
                            onClick={() => setEntityType('company')}
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${entityType === 'company'
                                ? 'bg-cyan-500 text-white shadow-lg'
                                : 'text-gray-400 hover:text-white'
                                }`}
                        >
                            <Building2 className="w-3 h-3 inline mr-1" />
                            企业
                        </button>
                    </div>
                </div>

                <div className="h-64">
                    {hasRealData && currentFlowData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%" minHeight={100}>
                            <BarChart data={currentFlowData} layout="vertical" margin={{ left: 10, right: 20 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={true} vertical={false} />
                                <XAxis
                                    type="number"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#6b7280', fontSize: 10 }}
                                    tickFormatter={(value) => `${value.toFixed(0)}万`}
                                />
                                <YAxis
                                    type="category"
                                    dataKey="name"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#9ca3af', fontSize: 11 }}
                                    width={80}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#111827',
                                        border: '1px solid #374151',
                                        borderRadius: '8px',
                                        boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)'
                                    }}
                                    labelStyle={{ color: '#9ca3af' }}
                                    formatter={(value: number | undefined) => value !== undefined ? [`¥${value.toFixed(2)}万`, ''] : ['', '']}
                                    labelFormatter={(label, payload) => {
                                        const item = payload?.[0]?.payload;
                                        return item?.fullName || label;
                                    }}
                                />
                                <Bar dataKey="收入" fill={entityType === 'person' ? '#3b82f6' : '#10b981'} radius={[0, 4, 4, 0]} barSize={14} />
                                <Bar dataKey="支出" fill={entityType === 'person' ? '#f97316' : '#ef4444'} radius={[0, 4, 4, 0]} barSize={14} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <EmptyState type="data" message={`完成分析后查看${entityType === 'person' ? '个人' : '企业'}资金流量`} />
                    )}
                </div>
            </div>

            {/* Suspicion Type Distribution - Pie Chart with bright colors */}
            <div className="card">
                <div className="flex items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-violet-500/10">
                            <Wallet className="w-5 h-5 text-violet-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">可疑交易分布</h3>
                            <p className="text-xs text-gray-500">按类型统计</p>
                        </div>
                    </div>
                    {/* Entity Selector */}
                    {entityList.length > 0 && (
                        <select
                            value={selectedEntity}
                            onChange={(e) => setSelectedEntity(e.target.value)}
                            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                            <option value="all">全部实体</option>
                            {entityList.slice(0, 20).map(name => (
                                <option key={name} value={name}>{truncate(name, 12)}</option>
                            ))}
                        </select>
                    )}
                </div>

                <div className="h-48 mb-4">
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
                                    backgroundColor: '#111827',
                                    border: '1px solid #4b5563',
                                    borderRadius: '8px'
                                }}
                                formatter={(value: number | undefined, name?: string) => value !== undefined ? [`${value} 条`, name || ''] : ['', '']}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                <div className="space-y-2">
                    {incomeDistributionData.map((item: { name: string; value: number; percent?: number; color: string }) => (
                        <div key={item.name} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                                <span className="text-gray-300">{item.name}</span>
                            </div>
                            <span className="font-medium text-white">{item.percent || item.value}%</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Top Entities Table */}
            <div className="lg:col-span-3 card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-cyan-500/10">
                            <Activity className="w-5 h-5 text-cyan-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">主要实体资金画像</h3>
                            <p className="text-xs text-gray-500">按收入金额排序</p>
                        </div>
                    </div>
                    <button className="btn-secondary text-xs opacity-50 cursor-not-allowed" disabled title="功能开发中">
                        查看全部
                        <ChevronRight className="w-3 h-3" />
                    </button>
                </div>

                {topEntities.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-800">
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">实体名称</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">总收入</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">总支出</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">交易笔数</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">净流量</th>
                                </tr>
                            </thead>
                            <tbody>
                                {topEntities.map((entity, idx) => {
                                    const netFlow = entity.income - entity.expense;
                                    return (
                                        <tr key={idx} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
                                            <td className="py-4">
                                                <div className="font-medium text-gray-200">{entity.name}</div>
                                            </td>
                                            <td className="py-4 text-right">
                                                <div className="flex items-center justify-end gap-1">
                                                    <ArrowDownLeft className="w-3 h-3 text-green-400" />
                                                    <span className="text-green-400 font-medium">{formatAmountInWan(entity.income)}</span>
                                                </div>
                                            </td>
                                            <td className="py-4 text-right">
                                                <div className="flex items-center justify-end gap-1">
                                                    <ArrowUpRight className="w-3 h-3 text-red-400" />
                                                    <span className="text-red-400 font-medium">{formatAmountInWan(entity.expense)}</span>
                                                </div>
                                            </td>
                                            <td className="py-4 text-right text-gray-300">{entity.transactions.toLocaleString()}</td>
                                            <td className="py-4 text-right">
                                                <span className={`font-medium ${netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {netFlow >= 0 ? '+' : ''}{formatAmountInWan(netFlow)}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <EmptyState type="data" message="等待分析数据" />
                )}
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
                                : 'bg-gray-800/50 text-gray-400 border border-gray-700 hover:border-gray-600 hover:text-gray-200'
                            }
            `}
                    >
                        {f.label}
                        <span className={`
              px-1.5 py-0.5 rounded text-[10px] font-bold
              ${filter === f.id ? 'bg-red-500/30' : 'bg-gray-700'}
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
                        <p className="text-xs text-gray-500">
                            {filter === 'all' ? '显示所有类型' : `筛选: ${riskFilters.find(f => f.id === filter)?.label}`}
                            {' • '}共 {filteredData.length} 条记录
                        </p>
                    </div>
                </div>

                {filteredData.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-800">
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">类型</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">日期</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">转出方/当事人</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">转入方/关联方</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">金额</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">说明</th>
                                    <th className="pb-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">风险等级</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredData.slice(0, 20).map((item: SuspiciousActivity, idx: number) => (
                                    <tr key={idx} className="border-b border-gray-800/50 hover:bg-red-500/5 transition-colors">
                                        <td className="py-4">
                                            <span className={getRiskLevelBadgeStyle(item.riskLevel)}>
                                                {getTypeLabel(item.type)}
                                            </span>
                                        </td>
                                        <td className="py-4">
                                            <div className="flex items-center gap-2 text-gray-300">
                                                <Clock className="w-3 h-3 text-gray-500" />
                                                <span className="text-xs">{formatDate(item.date)}</span>
                                            </div>
                                        </td>
                                        <td className="py-4 text-gray-200 font-medium" title={formatPartyName(item.from)}>
                                            {truncate(formatPartyName(item.from), 12)}
                                        </td>
                                        <td className="py-4 text-gray-200 font-medium" title={formatPartyName(item.to)}>
                                            {truncate(formatPartyName(item.to), 12)}
                                        </td>
                                        <td className="py-4 text-right">
                                            <span className="text-red-400 font-bold">{formatCurrency(item.amount)}</span>
                                        </td>
                                        <td className="py-4 max-w-[200px]" title={formatRiskDescription(item.description)}>
                                            <span className="text-xs text-gray-400 truncate block">{truncate(formatRiskDescription(item.description), 20)}</span>
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
                        {filteredData.length > 20 && (
                            <div className="text-center py-4 text-gray-500 text-sm">
                                仅显示前 20 条记录，共 {filteredData.length} 条
                            </div>
                        )}
                    </div>
                ) : (
                    <EmptyState type="data" message={hasAnyData ? '当前筛选条件下暂无记录' : '暂无可疑活动'} />
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

    return (
        <div className="space-y-6">
            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-green-500/10">
                            <FileText className="w-5 h-5 text-green-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">导出审计成果</h3>
                            <p className="text-xs text-gray-500">下载分析报告和数据文件</p>
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
                        <div className="w-12 h-12 rounded-2xl bg-gray-800/50 flex items-center justify-center mb-4">
                            <RefreshCw className="w-6 h-6 text-gray-500 animate-spin mb-4" />
                            <span className="ml-3 text-gray-400 font-medium">加载报告列表...</span>
                        </div>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mb-4">
                            <AlertTriangle className="w-8 h-8 text-red-500" />
                            <p className="text-gray-400 font-medium">加载失败</p>
                            <p className="text-gray-500 text-sm mt-1">{error}</p>
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
                                    className="flex items-center justify-between p-4 rounded-xl border bg-gray-800/30 border-gray-700 hover:border-gray-600 transition-all duration-200"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="p-3 rounded-xl bg-blue-500/10">
                                            <Icon className="w-5 h-5 text-blue-400" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-gray-200">{truncate(report.name, 25)}</p>
                                            <p className="text-xs text-gray-500 mt-0.5">{getFileTypeDescription(report.name)}</p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="text-[10px] font-mono text-gray-500 uppercase">{getFileType(report.name)}</span>
                                                <span className="text-[10px] text-gray-600">•</span>
                                                <span className="text-[10px] text-gray-500">{formatFileSize(report.size)}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleDownload(report.name)}
                                        disabled={isDownloading}
                                        className={`
                                            flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                                            transition-all duration-200
                                            ${isDownloading
                                                ? 'bg-gray-700 text-gray-400 cursor-wait'
                                                : 'bg-blue-600 hover:bg-blue-500 text-white'
                                            }
                                        `}
                                    >
                                        {isDownloading ? (
                                            <>
                                                <RefreshCw className="w-4 h-4 animate-spin" />
                                                下载中
                                            </>
                                        ) : (
                                            <>
                                                <Download className="w-4 h-4" />
                                                下载
                                            </>
                                        )}
                                    </button>
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
                            <p className="text-xs text-gray-500">选择模块、生成专业审计报告</p>
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
