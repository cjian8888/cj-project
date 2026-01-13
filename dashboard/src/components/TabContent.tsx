import React, { useState } from 'react';
import {
    Activity,
    AlertTriangle,
    Network,
    FileText,
    Download,
    ExternalLink,
    Filter,
    ChevronRight,
    TrendingUp,
    Wallet,
    ArrowUpRight,
    ArrowDownLeft,
    Clock,
    MapPin
} from 'lucide-react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import { useApp } from '../contexts/AppContext';

export function TabContent() {
    const { data, ui, setActiveTab } = useApp();

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
    const { data } = useApp();

    // Generate chart data
    const trendData = Array.from({ length: 30 }, (_, i) => ({
        date: `${i + 1}日`,
        收入: Math.floor(Math.random() * 50000) + 20000,
        支出: Math.floor(Math.random() * 40000) + 15000,
    }));

    const categoryData = [
        { name: '转账收入', value: 45, color: '#3b82f6' },
        { name: '工资薪金', value: 25, color: '#06b6d4' },
        { name: '理财收益', value: 15, color: '#8b5cf6' },
        { name: '其他收入', value: 10, color: '#10b981' },
        { name: '待核实', value: 5, color: '#f59e0b' },
    ];

    const topEntities = Object.entries(data.profiles)
        .map(([name, profile]) => ({
            name,
            income: profile.totalIncome,
            expense: profile.totalExpense,
            transactions: profile.transactionCount,
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
                            <p className="text-xs text-gray-500">近30日收支情况</p>
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
                                tickFormatter={(value) => `¥${(value / 10000).toFixed(0)}万`}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#111827',
                                    border: '1px solid #374151',
                                    borderRadius: '8px',
                                    boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)'
                                }}
                                labelStyle={{ color: '#9ca3af' }}
                                formatter={(value: number) => [`¥${value.toLocaleString()}`, '']}
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
                    <button className="btn-secondary text-xs">
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
                                                    <span className="text-green-400 font-medium">¥{(entity.income / 10000).toFixed(2)}万</span>
                                                </div>
                                            </td>
                                            <td className="py-4 text-right">
                                                <div className="flex items-center justify-end gap-1">
                                                    <ArrowUpRight className="w-3 h-3 text-red-400" />
                                                    <span className="text-red-400 font-medium">¥{(entity.expense / 10000).toFixed(2)}万</span>
                                                </div>
                                            </td>
                                            <td className="py-4 text-right text-gray-300">{entity.transactions.toLocaleString()}</td>
                                            <td className="py-4 text-right">
                                                <span className={`font-medium ${netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {netFlow >= 0 ? '+' : ''}¥{(netFlow / 10000).toFixed(2)}万
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="w-16 h-16 rounded-2xl bg-gray-800/50 flex items-center justify-center mb-4">
                            <Activity className="w-8 h-8 text-gray-600" />
                        </div>
                        <p className="text-gray-400 font-medium">等待分析数据</p>
                        <p className="text-gray-500 text-sm mt-1">请点击"启动引擎"开始分析</p>
                    </div>
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
        { id: 'all', label: '全部风险', count: data.suspicions.directTransfers.length + data.suspicions.cashCollisions.length },
        { id: 'direct', label: '直接转账', count: data.suspicions.directTransfers.length },
        { id: 'cash', label: '现金碰撞', count: data.suspicions.cashCollisions.length },
        { id: 'timing', label: '时序异常', count: data.suspicions.cashTimingPatterns.length },
    ] as const;

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
                        <p className="text-xs text-gray-500">按风险等级排序</p>
                    </div>
                </div>

                {data.suspicions.directTransfers.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-800">
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">日期</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">转出方</th>
                                    <th className="pb-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">转入方</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">金额</th>
                                    <th className="pb-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">风险等级</th>
                                    <th className="pb-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.suspicions.directTransfers.slice(0, 10).map((tx, idx) => (
                                    <tr key={idx} className="border-b border-gray-800/50 hover:bg-red-500/5 transition-colors">
                                        <td className="py-4">
                                            <div className="flex items-center gap-2 text-gray-300">
                                                <Clock className="w-3 h-3 text-gray-500" />
                                                {tx.date}
                                            </div>
                                        </td>
                                        <td className="py-4 text-gray-200 font-medium">{tx.from}</td>
                                        <td className="py-4 text-gray-200 font-medium">{tx.to}</td>
                                        <td className="py-4 text-right">
                                            <span className="text-red-400 font-bold">¥{tx.amount.toLocaleString()}</span>
                                        </td>
                                        <td className="py-4 text-center">
                                            <span className="badge badge-red">高风险</span>
                                        </td>
                                        <td className="py-4 text-right">
                                            <button className="text-blue-400 hover:text-blue-300 text-sm font-medium">
                                                详情 →
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-16 text-center">
                        <div className="w-16 h-16 rounded-2xl bg-green-500/10 flex items-center justify-center mb-4">
                            <AlertTriangle className="w-8 h-8 text-green-500" />
                        </div>
                        <p className="text-gray-400 font-medium">暂无可疑活动</p>
                        <p className="text-gray-500 text-sm mt-1">系统未检测到高风险交易</p>
                    </div>
                )}
            </div>
        </div>
    );
}

// ==================== Graph View Tab ====================

function GraphViewTab() {
    return (
        <div className="card h-[500px] flex flex-col">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-violet-500/10">
                        <Network className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">关联关系图谱</h3>
                        <p className="text-xs text-gray-500">实体间资金往来可视化</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button className="btn-secondary text-xs">
                        <Filter className="w-3 h-3" />
                        筛选
                    </button>
                    <button className="btn-secondary text-xs">
                        <ExternalLink className="w-3 h-3" />
                        全屏
                    </button>
                </div>
            </div>

            <div className="flex-1 flex items-center justify-center bg-gray-900/50 rounded-xl border border-dashed border-gray-700">
                <div className="text-center">
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 flex items-center justify-center mx-auto mb-4">
                        <Network className="w-10 h-10 text-violet-400" />
                    </div>
                    <p className="text-gray-300 font-medium mb-2">交互式图谱可视化</p>
                    <p className="text-gray-500 text-sm max-w-xs">
                        运行分析后，此处将显示实体间的资金流向关系网络
                    </p>
                </div>
            </div>
        </div>
    );
}

// ==================== Audit Report Tab ====================

function AuditReportTab() {
    const reports = [
        {
            name: '核查底稿 Excel',
            desc: '完整的分析结果 Excel 格式',
            icon: FileText,
            size: '2.4 MB',
            type: 'xlsx',
            ready: true
        },
        {
            name: '综合分析报告',
            desc: '详细的文字分析报告',
            icon: FileText,
            size: '856 KB',
            type: 'html',
            ready: true
        },
        {
            name: '资金流向图',
            desc: '交互式 HTML 资金流向图',
            icon: Network,
            size: '1.2 MB',
            type: 'html',
            ready: false
        },
        {
            name: '风险评估报告',
            desc: '实体风险等级评估',
            icon: AlertTriangle,
            size: '420 KB',
            type: 'pdf',
            ready: false
        },
    ];

    return (
        <div className="space-y-6">
            <div className="card">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 rounded-lg bg-green-500/10">
                        <FileText className="w-5 h-5 text-green-400" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">导出审计成果</h3>
                        <p className="text-xs text-gray-500">下载分析报告和数据文件</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {reports.map((report, idx) => (
                        <div
                            key={idx}
                            className={`
                flex items-center justify-between p-4 rounded-xl
                border transition-all duration-200
                ${report.ready
                                    ? 'bg-gray-800/30 border-gray-700 hover:border-gray-600'
                                    : 'bg-gray-900/30 border-gray-800 opacity-60'
                                }
              `}
                        >
                            <div className="flex items-center gap-4">
                                <div className={`
                  p-3 rounded-xl
                  ${report.ready ? 'bg-blue-500/10' : 'bg-gray-800'}
                `}>
                                    <report.icon className={`w-5 h-5 ${report.ready ? 'text-blue-400' : 'text-gray-500'}`} />
                                </div>
                                <div>
                                    <p className="font-medium text-gray-200">{report.name}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{report.desc}</p>
                                    <div className="flex items-center gap-2 mt-1">
                                        <span className="text-[10px] font-mono text-gray-500 uppercase">{report.type}</span>
                                        <span className="text-[10px] text-gray-600">•</span>
                                        <span className="text-[10px] text-gray-500">{report.size}</span>
                                    </div>
                                </div>
                            </div>
                            <button
                                disabled={!report.ready}
                                className={`
                  flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                  transition-all duration-200
                  ${report.ready
                                        ? 'bg-blue-600 hover:bg-blue-500 text-white'
                                        : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                                    }
                `}
                            >
                                <Download className="w-4 h-4" />
                                下载
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            {/* Report Preview */}
            <div className="card">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="font-semibold text-white">报告预览</h3>
                    <button className="btn-secondary text-xs">
                        <ExternalLink className="w-3 h-3" />
                        新窗口打开
                    </button>
                </div>
                <div className="h-64 flex items-center justify-center bg-gray-900/50 rounded-xl border border-dashed border-gray-700">
                    <p className="text-gray-500 text-sm">选择报告后在此预览内容</p>
                </div>
            </div>
        </div>
    );
}
