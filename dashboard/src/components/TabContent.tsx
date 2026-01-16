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
import { formatDate, formatCurrency, formatAmountInWan, truncate, getRiskLevelBadgeStyle, formatFileSize, formatRiskLevel, formatRiskDescription, formatPartyName } from '../utils/formatters';
import { EmptyState } from './common/EmptyState';
import NetworkGraph from './NetworkGraph';

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
type MetricType = 'loan_bilateral' | 'loan_platform' | 'income_regular' | 
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
        // 1. 借贷双向往来 - 使用后端 loan.details 或 summary
        { 
            key: 'loan_bilateral', 
            label: '借贷双向往来', 
            value: loanDetails.length > 0 ? loanDetails.length : (loanSummary['双向往来关系数'] || 0), 
            color: 'text-red-400', 
            desc: '同一对象有借有还', 
            icon: Users 
        },
        // 2. 网贷平台交易 - 使用 summary（后端应提供 details）
        { 
            key: 'loan_platform', 
            label: '网贷平台交易', 
            value: loanSummary['网贷平台交易数'] || 0, 
            color: 'text-orange-400', 
            desc: '互联网借贷平台', 
            icon: Building2 
        },
        // 3. 规律非工资收入 - 使用 income.details 或 summary
        { 
            key: 'income_regular', 
            label: '规律非工资收入', 
            value: incomeDetails.length > 0 ? incomeDetails.length : (incomeSummary['规律性非工资收入'] || 0), 
            color: 'text-yellow-400', 
            desc: '固定来源非工资', 
            icon: TrendingUp 
        },
        // 4. 核心人员往来 - 使用 directTransfers（完全一致）
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

    // 获取指标详情数据 - 确保与卡片数字来源完全一致
    const getMetricDetails = (metric: AuditMetric): any[] => {
        switch (metric.key) {
            case 'loan_bilateral':
                // 借贷双向往来 - 使用 _type = 'bidirectional' 过滤
                const bidirectionalLoans = loanDetails.filter((item: any) => 
                    item._type === 'bidirectional'
                );
                if (bidirectionalLoans.length > 0) {
                    return bidirectionalLoans.map((item: any) => ({
                        name: item.person || item.entity || '未知',
                        counterparty: item.counterparty || item.lender || '',
                        amount: item.income_total || item.amount || 0,
                        date: item.first_income_date || item.date || '',
                        description: item.loan_type || '借贷往来',
                        reasons: [
                            `收入${item.income_count || 0}笔/${(item.income_total/10000).toFixed(1)}万`,
                            `支出${item.expense_count || 0}笔/${(item.expense_total/10000).toFixed(1)}万`
                        ]
                    }));
                }
                // 兜底：使用全部 loanDetails
                if (loanDetails.length > 0) {
                    return loanDetails.slice(0, 50).map((item: any) => ({
                        name: item.person || item.entity || '未知',
                        counterparty: item.counterparty || '',
                        amount: item.amount || item.income_total || 0,
                        date: item.date || '',
                        description: item._type || '借贷往来'
                    }));
                }
                return [{ name: '暂无详情数据', description: '后端 loan.details 待填充' }];
                
            case 'loan_platform':
                // 网贷平台交易 - 使用 _type = 'online_loan' 过滤
                const platformLoans = loanDetails.filter((item: any) => 
                    item._type === 'online_loan'
                );
                if (platformLoans.length > 0) {
                    return platformLoans.map((item: any) => ({
                        name: item.platform || item.counterparty || '网贷平台',
                        amount: item.amount || 0,
                        date: item.date || '',
                        description: item.description || '网络借贷',
                        reasons: item.risk_level ? [`风险: ${item.risk_level}`] : []
                    }));
                }
                return [{ name: '暂无详情数据', description: '未发现网贷平台交易' }];
                
            case 'income_regular':
                // 规律非工资收入 - 使用 _type = 'regular_non_salary' 过滤
                const regularIncomes = incomeDetails.filter((item: any) => 
                    item._type === 'regular_non_salary'
                );
                if (regularIncomes.length > 0) {
                    return regularIncomes.map((item: any) => ({
                        name: item.source || item.counterparty || '未知来源',
                        amount: item.amount || item.total || 0,
                        date: item.date || '',
                        description: item.description || item.pattern || '规律性收入',
                        reasons: item.reasons || [item.frequency || '']
                    }));
                }
                // 兜底：使用全部 incomeDetails
                if (incomeDetails.length > 0) {
                    return incomeDetails.slice(0, 50).map((item: any) => ({
                        name: item.source || item.counterparty || '未知来源',
                        amount: item.amount || 0,
                        date: item.date || '',
                        description: item._type || '收入'
                    }));
                }
                return [{ name: '暂无详情数据', description: '后端 income.details 待填充' }];

            case 'related_direct':
                // 核心人员往来 - 使用 suspicions.directTransfers（与卡片一致）
                return (data.suspicions.directTransfers || []).map((tx: any) => ({
                    name: `${tx.from} → ${tx.to}`,
                    amount: tx.amount,
                    date: tx.date,
                    bank: tx.bank,
                    source_file: tx.source_file,
                    description: tx.description || '资金往来',
                    reasons: tx.riskLevel ? [`风险等级: ${formatRiskLevel(tx.riskLevel)}`] : undefined
                }));

            case 'cash_collision':
                // 现金时空伴随 - 使用 suspicions.cashCollisions（与卡片一致）
                return (data.suspicions.cashCollisions || []).map((collision: any) => ({
                    name: `${collision.person1} ⇄ ${collision.person2}`,
                    amount: (collision.amount1 || 0) + (collision.amount2 || 0),
                    date: collision.time1,
                    description: `取现: ¥${(collision.amount1 || 0).toLocaleString()} / 存现: ¥${(collision.amount2 || 0).toLocaleString()}`,
                    reasons: [
                        `时间差: ${collision.timeDiff ? collision.timeDiff + '小时' : '未知'}`,
                        collision.riskLevel ? `风险等级: ${formatRiskLevel(collision.riskLevel)}` : ''
                    ].filter(Boolean)
                }));

            case 'risk_critical':
                // 极高风险实体 - 使用筛选后的列表（与卡片一致）
                return criticalRiskEntities.map((e: any) => ({
                    name: e.name || e.entity,
                    riskScore: e.riskScore || e.score,
                    description: `风险评分: ${e.riskScore || e.score || 'N/A'}`,
                    reasons: e.reasons || []
                }));

            case 'risk_high':
                // 高风险实体 - 使用筛选后的列表（与卡片一致）
                return highRiskEntities.map((e: any) => ({
                    name: e.name || e.entity,
                    riskScore: e.riskScore || e.score,
                    description: `风险评分: ${e.riskScore || e.score || 'N/A'}`,
                    reasons: e.reasons || []
                }));

            case 'risk_all':
                // 全部风险实体
                return rankedEntities.map((e: any) => ({
                    name: e.name || e.entity,
                    riskScore: e.riskScore || e.score,
                    description: `风险评分: ${e.riskScore || e.score || 'N/A'} (${e.riskLevel || '未分级'})`,
                    reasons: e.reasons || []
                }));

            default:
                return [];
        }
    };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Metric Detail Modal */}
            {selectedMetric && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedMetric(null)}>
                    <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-4 border-b border-gray-800">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${selectedMetric.color.replace('text-', 'bg-').replace('-400', '-500/20').replace('-500', '-500/20')}`}>
                                    <selectedMetric.icon className={`w-5 h-5 ${selectedMetric.color}`} />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-white">{selectedMetric.label}</h3>
                                    <p className="text-xs text-gray-500">共 {selectedMetric.value} 条记录</p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedMetric(null)} className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
                                <X className="w-5 h-5 text-gray-400" />
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto max-h-[60vh]">
                            {(() => {
                                const details = getMetricDetails(selectedMetric);
                                if (details.length === 0) {
                                    return <div className="text-center py-8 text-gray-500">暂无详细数据</div>;
                                }
                                return (
                                    <div className="space-y-2">
                                        {details.slice(0, 20).map((item: any, idx: number) => (
                                            <div key={idx} className="p-3 bg-gray-800/50 rounded-lg border border-gray-700/50 hover:border-gray-600 transition-colors">
                                                <div className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-gray-200 font-medium">
                                                            {item.name || item.entity || item.from || item.person || `记录 ${idx + 1}`}
                                                        </span>
                                                        {item.counterparty && (
                                                            <span className="text-xs text-gray-500">
                                                            (来自: {formatPartyName(item.counterparty)})
                                                            </span>
                                                        )}
                                                    </div>
                                                    {item.amount && (
                                                        <span className="text-red-400 font-bold">{formatCurrency(item.amount)}</span>
                                                    )}
                                                </div>
                                                
                                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-400 mb-2">
                                                    {item.date && (
                                                        <div className="flex items-center gap-1.5">
                                                            <Clock className="w-3 h-3 text-gray-500" />
                                                            <span>{item.date}</span>
                                                        </div>
                                                    )}
                                                    {item.bank && (
                                                        <div className="flex items-center gap-1.5">
                                                            <Building2 className="w-3 h-3 text-gray-500" />
                                                            <span>{item.bank}</span>
                                                        </div>
                                                    )}
                                                </div>

                                                {item.source_file && (
                                                    <div className="flex items-center gap-1.5 text-[10px] text-gray-500 bg-gray-900/50 p-1.5 rounded mb-1">
                                                        <FileText className="w-3 h-3" />
                                                        <span className="truncate max-w-[280px]">{item.source_file}</span>
                                                    </div>
                                                )}

                                                {item.description && (
                                                    <p className="text-xs text-gray-300 mt-1 pl-2 border-l-2 border-gray-600">
                                                        {formatRiskDescription(item.description)}
                                                    </p>
                                                )}
                                                {item.reasons && (
                                                    <p className="text-xs text-gray-500 mt-1">{item.reasons.map((r: string) => formatRiskDescription(r)).join(', ')}</p>
                                                )}
                                            </div>
                                        ))}
                                        {details.length > 20 && (
                                            <div className="text-center py-2 text-gray-500 text-sm">
                                                仅显示前 20 条，共 {details.length} 条
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
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${
                                entityType === 'person' 
                                    ? 'bg-blue-500 text-white shadow-lg' 
                                    : 'text-gray-400 hover:text-white'
                            }`}
                        >
                            <Users className="w-3 h-3 inline mr-1" />
                            个人
                        </button>
                        <button 
                            onClick={() => setEntityType('company')}
                            className={`px-3 py-1.5 text-xs rounded-md transition-all ${
                                entityType === 'company' 
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
                        <ResponsiveContainer width="100%" height="100%">
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
                    <ResponsiveContainer width="100%" height="100%">
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
        <div className="card h-[600px] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 bg-gray-900/50 border-b border-gray-800">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-violet-500/10">
                        <Network className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">资金流向关系图谱</h3>
                        <p className="text-xs text-gray-500">实体间资金往来可视化分析</p>
                    </div>
                </div>
                <button 
                    onClick={() => {
                        // baseURL is http://localhost:8000, API reports are at /api/reports/
                        window.open(`${api.baseURL}/api/reports/资金流向可视化.html`, '_blank');
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-medium transition-colors"
                >
                    <ArrowUpRight className="w-3 h-3" />
                    全屏交互报告
                </button>
            </div>

            <div className="flex-1 overflow-hidden">
                <NetworkGraph onLog={handleLog} />
            </div>
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

            {/* Report Preview (Placeholder) */}
            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="font-semibold text-white">报告预览</h3>
                    <span className="text-[10px] text-gray-500 bg-gray-800 px-2 py-1 rounded">功能开发中</span>
                </div>
                <div className="h-64 flex flex-col items-center justify-center bg-gray-900/50 rounded-xl border border-dashed border-gray-700">
                    <p className="text-gray-500 text-sm mb-2">点击上方报告的"下载"按钮获取文件</p>
                    <p className="text-gray-600 text-xs">预览功能正在开发中</p>
                </div>
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
