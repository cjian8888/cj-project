import React from 'react';
import { Users, Activity, ShieldAlert, Server, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { formatAmountInWan } from '../utils/formatters';

export function KPICards() {
    const { data, analysis } = useApp();

    // Calculate real stats from data
    const entityCount = data.persons.length + data.companies.length;
    const totalTransactions = Object.values(data.profiles || {}).reduce(
        (sum, profile) => sum + (profile.transactionCount || 0),
        0
    );
    const highRiskFunds = (data.suspicions.directTransfers || []).reduce(
        (sum, tx) => sum + (tx.amount || 0),
        0
    );
    const suspicionCount = (data.suspicions.directTransfers || []).length +
        (data.suspicions.cashCollisions || []).length +
        (data.suspicions.cashTimingPatterns || []).length;

    const kpis = [
        {
            id: 'entities',
            label: '已分析实体',
            value: entityCount.toLocaleString(),
            subLabel: `${data.persons.length} 个人 / ${data.companies.length} 企业`,
            icon: Users,
            trend: (entityCount > 0 ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: entityCount > 0 ? '+' + entityCount : '-',
            gradient: 'from-blue-500 to-cyan-500',
            glowColor: 'shadow-blue-500/20',
            iconBg: 'bg-blue-500/10',
            iconColor: 'text-blue-400',
        },
        {
            id: 'transactions',
            label: '交易总数',
            value: totalTransactions.toLocaleString(),
            subLabel: '银行流水记录',
            icon: Activity,
            trend: (totalTransactions > 1000 ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: totalTransactions > 1000 ? '数据充足' : '待分析',
            gradient: 'from-cyan-500 to-teal-500',
            glowColor: 'shadow-cyan-500/20',
            iconBg: 'bg-cyan-500/10',
            iconColor: 'text-cyan-400',
        },
        {
            id: 'risk',
            label: '高风险资金',
            value: formatAmountInWan(highRiskFunds),
            subLabel: `${suspicionCount} 条可疑记录`,
            icon: ShieldAlert,
            trend: (highRiskFunds > 0 ? 'down' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: highRiskFunds > 0 ? '需关注' : '无异常',
            gradient: 'from-red-500 to-orange-500',
            glowColor: 'shadow-red-500/20',
            iconBg: 'bg-red-500/10',
            iconColor: 'text-red-400',
        },
        {
            id: 'status',
            label: '系统状态',
            value: analysis.isRunning ? '分析中' : analysis.status === 'completed' ? '已完成' : '就绪',
            subLabel: analysis.isRunning ? `${analysis.progress}% 完成` : '等待指令',
            icon: Server,
            trend: (analysis.isRunning ? 'up' : analysis.status === 'completed' ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: analysis.isRunning ? '运行中' : analysis.status === 'completed' ? '成功' : '待机',
            gradient: analysis.isRunning
                ? 'from-amber-500 to-yellow-500'
                : analysis.status === 'completed'
                    ? 'from-green-500 to-emerald-500'
                    : 'from-gray-500 to-slate-500',
            glowColor: analysis.isRunning
                ? 'shadow-amber-500/20'
                : analysis.status === 'completed'
                    ? 'shadow-green-500/20'
                    : 'shadow-gray-500/10',
            iconBg: analysis.isRunning
                ? 'bg-amber-500/10'
                : analysis.status === 'completed'
                    ? 'bg-green-500/10'
                    : 'bg-gray-500/10',
            iconColor: analysis.isRunning
                ? 'text-amber-400'
                : analysis.status === 'completed'
                    ? 'text-green-400'
                    : 'text-gray-400',
            isStatus: true,
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
            {kpis.map((kpi, index) => (
                <KPICard key={kpi.id} {...kpi} delay={index * 0.1} />
            ))}
        </div>
    );
}

// ==================== KPI Card Component ====================

interface KPICardProps {
    label: string;
    value: string;
    subLabel: string;
    icon: React.ElementType;
    trend: 'up' | 'down' | 'neutral';
    trendValue: string;
    gradient: string;
    glowColor: string;
    iconBg: string;
    iconColor: string;
    isStatus?: boolean;
    delay: number;
}

function KPICard({
    label, value, subLabel, icon: Icon, trend, trendValue,
    gradient, glowColor, iconBg, iconColor, isStatus, delay
}: KPICardProps) {
    const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
    const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400';

    return (
        <div
            className={`
        relative overflow-hidden rounded-2xl p-5
        bg-gradient-to-br from-gray-900/80 to-gray-900/40
        border border-gray-800/60
        backdrop-blur-xl
        transition-all duration-300
        hover:border-gray-700/80 hover:shadow-xl ${glowColor}
        group
      `}
            style={{ animationDelay: `${delay}s` }}
        >
            {/* Background Gradient Blob */}
            <div className={`
        absolute -top-12 -right-12 w-32 h-32
        bg-gradient-to-br ${gradient}
        rounded-full blur-3xl opacity-10
        group-hover:opacity-20 transition-opacity duration-500
      `} />

            {/* Header Row */}
            <div className="flex items-start justify-between mb-4 relative z-10">
                <div className={`p-2.5 rounded-xl ${iconBg} backdrop-blur-sm`}>
                    <Icon className={`w-5 h-5 ${iconColor}`} />
                </div>

                {/* Trend Badge */}
                <div className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
                    <TrendIcon className="w-3 h-3" />
                    <span>{trendValue}</span>
                </div>
            </div>

            {/* Value */}
            <div className="relative z-10">
                <div className="flex items-baseline gap-2">
                    <h3 className={`text-2xl lg:text-3xl font-bold text-white tracking-tight ${isStatus ? '' : ''}`}>
                        {value}
                    </h3>
                    {isStatus && (
                        <span className="relative flex h-2.5 w-2.5">
                            <span className={`
                animate-ping absolute inline-flex h-full w-full rounded-full opacity-75
                ${trend === 'up' ? 'bg-green-400' : 'bg-gray-400'}
              `} />
                            <span className={`
                relative inline-flex rounded-full h-2.5 w-2.5
                ${trend === 'up' ? 'bg-green-500' : 'bg-gray-500'}
              `} />
                        </span>
                    )}
                </div>
                <p className="text-sm text-gray-400 mt-1">{label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{subLabel}</p>
            </div>

            {/* Bottom Accent Line */}
            <div className={`
        absolute bottom-0 left-0 right-0 h-[2px]
        bg-gradient-to-r ${gradient}
        opacity-0 group-hover:opacity-100
        transition-opacity duration-300
      `} />
        </div>
    );
}
