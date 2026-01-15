import React, { useState, useEffect } from 'react';
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
    RefreshCw
} from 'lucide-react';
import { api } from '../services/api';
import type { Report } from '../services/api';
import {
    AreaChart,
    Area,
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
import { formatDate, formatCurrency, formatAmountInWan, formatTimeDifference, truncate, getRiskLevelBadgeStyle, formatFileSize } from '../utils/formatters';
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

function OverviewTab() {
    const { data, analysis } = useApp();

    // 从真实数据生成趋势图数据（如果分析未完成，使用空数组）
    const hasRealData = analysis.status === 'completed' && Object.keys(data.profiles).length > 0;

    // 检查是否有足够的数据来显示图表
    const hasChartData = hasRealData;

    // 生成趋势图数据（使用真实数据或占位符）
    const trendData = hasChartData
        ? Object.values(data.profiles)
            .slice(0, 30)
            .map((profile, index) => ({
                date: `实体${index + 1}`,
                收入: profile.totalIncome || 0,
                支出: profile.totalExpense || 0,
            }))
        : [];

    // 收入来源分布（基于真实数据）
    const categoryData = hasChartData
        ? (() => {
            // 从可疑交易中汇总收入类别
            const totalSuspicious = (data.suspicions.directTransfers || []).length +
                (data.suspicions.cashCollisions || []).length +
                (data.suspicions.cashTimingPatterns || []).length;

            const categories = [];
            if (data.suspicions.directTransfers.length > 0) {
                categories.push({
                    name: '直接转账',
                    value: Math.round((data.suspicions.directTransfers.length / totalSuspicious) * 100),
                    color: '#3b82f6'
                });
            }
            if (data.suspicions.cashCollisions.length > 0) {
                categories.push({
                    name: '现金碰撞',
                    value: Math.round((data.suspicions.cashCollisions.length / totalSuspicious) * 100),
                    color: '#06b6d4'
                });
            }
            if (data.suspicions.cashTimingPatterns.length > 0) {
                categories.push({
                    name: '时序异常',
                    value: Math.round((data.suspicions.cashTimingPatterns.length / totalSuspicious) * 100),
                    color: '#f59e0b'
                });
            }

            // 如果没有分类数据，显示提示
            if (categories.length === 0) {
                return [{ name: '暂无数据', value: 100, color: '#6b7280' }];
            }

            return categories;
        })()
        : [{ name: '等待分析', value: 100, color: '#6b7280' }];

    const topEntities = Object.entries(data.profiles || {})
        .map(([name, profile]) => ({
            name,
            income: profile?.totalIncome || 0,
            expense: profile?.totalExpense || 0,
            transactions: profile?.transactionCount || 0,
        }))
        .sort((a, b) => b.income - a.income)
        .slice(0, 5);

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Transaction Trend Chart */}
            <div className="lg:col-span-2 card">
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <TrendingUp className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-white">资金流动趋势</h3>
                            <p className="text-xs text-gray-500">
                                {hasChartData ? '实体收支分布' : '等待分析数据'}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-blue-500" />
                            <span className="text-gray-400">收入</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-cyan-500" />
                            <span className="text-gray-400">支出</span>
                        </div>
                    </div>
                </div>

                <div className="h-64">
                    {hasChartData && trendData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={trendData}>
                                <defs>
                                    <linearGradient id="incomeGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="expenseGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                                        <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#6b7280', fontSize: 11 }}
                                    interval={4}
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#6b7280', fontSize: 11 }}
                                    tickFormatter={(value) => `¥${formatAmountInWan(value, false)}万`}
                                />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: '#111827',
                                        border: '1px solid #374151',
                                        borderRadius: '8px',
                                        boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)'
                                    }}
                                    labelStyle={{ color: '#9ca3af' }}
                                    formatter={(value: number | undefined) => value !== undefined ? [formatCurrency(value), ''] : ['', '']}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="收入"
                                    stroke="#3b82f6"
                                    fill="url(#incomeGradient)"
                                    strokeWidth={2}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="支出"
                                    stroke="#06b6d4"
                                    fill="url(#expenseGradient)"
                                    strokeWidth={2}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : (
                        <EmptyState type="data" message="完成分析后查看资金流动趋势" />
                    )}
                </div>
            </div>

            {/* Income Category Distribution */}
            <div className="card">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 rounded-lg bg-violet-500/10">
                        <Wallet className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">收入来源分布</h3>
                        <p className="text-xs text-gray-500">按类别统计</p>
                    </div>
                </div>

                <div className="h-48 mb-4">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={categoryData}
                                cx="50%"
                                cy="50%"
                                innerRadius={50}
                                outerRadius={75}
                                paddingAngle={3}
                                dataKey="value"
                            >
                                {categoryData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Pie>
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#111827',
                                    border: '1px solid #374151',
                                    borderRadius: '8px'
                                }}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                <div className="space-y-2">
                    {categoryData.map((item) => (
                        <div key={item.name} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                                <span className="text-gray-400">{item.name}</span>
                            </div>
                            <span className="font-medium text-gray-200">{item.value}%</span>
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
            description: tx.description || '直接转账',
            riskLevel: '高风险',
        }));

        const cashCollisions = data.suspicions.cashCollisions.map((collision: any): SuspiciousActivity => ({
            type: 'cash' as const,
            date: collision.time1,
            from: collision.person1,
            to: collision.person2,
            amount: (collision.amount1 || 0) + (collision.amount2 || 0),
            timeDiff: collision.timeDiff || null,
            description: collision.description || '现金碰撞',
            riskLevel: '高风险',
        }));

        const timingPatterns = data.suspicions.cashTimingPatterns.map((pattern: any): SuspiciousActivity => ({
            type: 'timing' as const,
            date: pattern.time1 || pattern.date || '-',
            from: pattern.person1 || '-',
            to: pattern.person2 || '-',
            amount: (pattern.amount1 || 0) + (pattern.amount2 || 0),
            timeDiff: pattern.timeDiff || null,
            description: pattern.description || '时序异常',
            riskLevel: '中风险',
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
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">时间差</th>
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
                                        <td className="py-4 text-gray-200 font-medium">{truncate(item.from, 15)}</td>
                                        <td className="py-4 text-gray-200 font-medium">{truncate(item.to, 15)}</td>
                                        <td className="py-4 text-right">
                                            <span className="text-red-400 font-bold">{formatCurrency(item.amount)}</span>
                                        </td>
                                        <td className="py-4 text-right">
                                            <span className="text-xs text-gray-500">{item.timeDiff ? formatTimeDifference(item.timeDiff) : '-'}</span>
                                        </td>
                                        <td className="py-4 text-center">
                                            <span className={getRiskLevelBadgeStyle(item.riskLevel)}>
                                                {item.riskLevel}
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
