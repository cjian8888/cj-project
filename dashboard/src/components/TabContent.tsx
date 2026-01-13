import React from 'react';
import { Activity, AlertTriangle, Network, FileText, Download } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import type { TabContentProps } from '../types';

export function TabContent() {
    const { data, ui, setActiveTab } = useApp();

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* Tab Navigation */}
            <div className="flex border-b border-slate-800 mb-6 shrink-0">
                <TabButton
                    label="概览"
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
            <div className="flex-1 overflow-y-auto scrollbar-thin">
                {ui.activeTab === 'overview' && <OverviewTab data={data} />}
                {ui.activeTab === 'risk' && <RiskIntelTab data={data} />}
                {ui.activeTab === 'graph' && <GraphViewTab />}
                {ui.activeTab === 'report' && <AuditReportTab />}
            </div>
        </div>
    );
}

// ==================== Tab Button Component ====================

interface TabButtonProps {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    active: boolean;
    onClick: () => void;
}

function TabButton({ label, icon: Icon, active, onClick }: TabButtonProps) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${active
                ? 'text-blue-400 border-blue-500'
                : 'text-slate-400 border-transparent hover:text-slate-200'
                }`}
        >
            <Icon className="w-4 h-4" />
            {label}
        </button>
    );
}

// ==================== Overview Tab ====================

function OverviewTab({ data }: TabContentProps) {
    const profileData = Object.entries(data.profiles).map(([entity, profile]) => ({
        entity,
        income: profile.totalIncome,
        expense: profile.totalExpense,
    }));

    // Mock chart data
    const chartData = Array.from({ length: 15 }, (_, i) => ({
        date: `2024-01-${(i + 1).toString().padStart(2, '0')}`,
        volume: Math.floor(Math.random() * 5000) + 2000,
    }));

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Fund Distribution Table */}
            <div className="glass-panel p-5 rounded-xl lg:col-span-1">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-blue-500" />
                    资金分布
                </h3>
                {profileData.length > 0 ? (
                    <div className="space-y-2">
                        {profileData.map((item, idx) => (
                            <div
                                key={idx}
                                className="flex justify-between items-center p-3 bg-slate-800/30 rounded-lg hover:bg-slate-800/50 transition-colors"
                            >
                                <span className="text-sm text-slate-300">{item.entity}</span>
                                <div className="flex gap-4 text-xs">
                                    <span className="text-green-400">¥{(item.income / 10000).toFixed(1)}万</span>
                                    <span className="text-red-400">¥{(item.expense / 10000).toFixed(1)}万</span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-8 text-slate-500 text-sm">
                        等待分析数据...
                    </div>
                )}
            </div>

            {/* Transaction Trend Chart */}
            <div className="glass-panel p-5 rounded-xl lg:col-span-2">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-500" />
                    交易量趋势
                </h3>
                <div className="h-64 flex items-center justify-center bg-slate-800/20 rounded-lg">
                    <p className="text-slate-500 text-sm">图表可视化将使用 Recharts 实现</p>
                </div>
            </div>
        </div>
    );
}

// ==================== Risk Intel Tab ====================

function RiskIntelTab({ data }: TabContentProps) {
    const [filter, setFilter] = React.useState<'direct' | 'round' | 'cash'>('direct');

    return (
        <div className="space-y-6">
            {/* Filter */}
            <div className="flex gap-2">
                <FilterButton
                    label="直接转账"
                    active={filter === 'direct'}
                    onClick={() => setFilter('direct')}
                />
                <FilterButton
                    label="循环资金"
                    active={filter === 'round'}
                    onClick={() => setFilter('round')}
                />
                <FilterButton
                    label="现金异常"
                    active={filter === 'cash'}
                    onClick={() => setFilter('cash')}
                />
            </div>

            {/* Suspicious Activity Table */}
            <div className="glass-panel p-5 rounded-xl">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    可疑活动日志
                </h3>
                {data.suspicions.directTransfers.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-slate-400 border-b border-slate-700">
                                    <th className="pb-3 font-medium">日期</th>
                                    <th className="pb-3 font-medium">转出方</th>
                                    <th className="pb-3 font-medium">转入方</th>
                                    <th className="pb-3 font-medium">金额</th>
                                    <th className="pb-3 font-medium">风险等级</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.suspicions.directTransfers.slice(0, 10).map((tx, idx) => (
                                    <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                                        <td className="py-3 text-slate-300">{tx.date}</td>
                                        <td className="py-3 text-slate-300">{tx.from}</td>
                                        <td className="py-3 text-slate-300">{tx.to}</td>
                                        <td className="py-3 text-red-400 font-medium">¥{tx.amount.toLocaleString()}</td>
                                        <td className="py-3">
                                            <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
                                                高风险
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="text-center py-8 text-slate-500 text-sm">
                        未检测到可疑活动。请运行分析引擎。
                    </div>
                )}
            </div>
        </div>
    );
}

interface FilterButtonProps {
    label: string;
    active: boolean;
    onClick: () => void;
}

function FilterButton({ label, active, onClick }: FilterButtonProps) {
    return (
        <button
            onClick={onClick}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${active
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                : 'bg-slate-800/50 text-slate-400 border border-slate-700 hover:text-slate-200'
                }`}
        >
            {label}
        </button>
    );
}

// ==================== Graph View Tab ====================

function GraphViewTab() {
    return (
        <div className="glass-panel p-5 rounded-xl h-full">
            <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                <Network className="w-4 h-4 text-purple-500" />
                关联关系图谱
            </h3>
            <div className="h-96 flex items-center justify-center bg-slate-800/20 rounded-lg border-2 border-dashed border-slate-700">
                <div className="text-center">
                    <Network className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-500 text-sm">交互式图谱可视化模块</p>
                    <p className="text-slate-600 text-xs mt-1">将使用 D3.js 或 Cytoscape.js 实现</p>
                </div>
            </div>
        </div>
    );
}

// ==================== Audit Report Tab ====================

function AuditReportTab() {
    return (
        <div className="space-y-6">
            <div className="glass-panel p-5 rounded-xl">
                <h3 className="font-semibold text-slate-200 mb-4 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-green-500" />
                    导出审计成果
                </h3>
                <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                        <div>
                            <p className="text-sm font-medium text-slate-200">核查底稿 Excel</p>
                            <p className="text-xs text-slate-500 mt-1">完整的分析结果 Excel 格式</p>
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">
                            <Download className="w-4 h-4" />
                            下载
                        </button>
                    </div>
                    <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                        <div>
                            <p className="text-sm font-medium text-slate-200">分析报告</p>
                            <p className="text-xs text-slate-500 mt-1">详细的文字分析报告</p>
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium rounded-lg transition-colors">
                            <Download className="w-4 h-4" />
                            下载
                        </button>
                    </div>
                    <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg">
                        <div>
                            <p className="text-sm font-medium text-slate-200">资金流向图</p>
                            <p className="text-xs text-slate-500 mt-1">交互式 HTML 资金流向图</p>
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium rounded-lg transition-colors">
                            <Download className="w-4 h-4" />
                            下载
                        </button>
                    </div>
                </div>
            </div>

            {/* Report Preview */}
            <div className="glass-panel p-5 rounded-xl">
                <h3 className="font-semibold text-slate-200 mb-4">报告预览</h3>
                <div className="h-64 flex items-center justify-center bg-slate-800/20 rounded-lg">
                    <p className="text-slate-500 text-sm">分析完成后将显示报告预览</p>
                </div>
            </div>
        </div>
    );
}
