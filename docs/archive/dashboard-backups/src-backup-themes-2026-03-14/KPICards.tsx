import React from 'react';
import { Users, Activity, ShieldAlert, TrendingUp, TrendingDown, Minus, Banknote } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { formatAmountInWan } from '../utils/formatters';

export function KPICards() {
    const { data } = useApp();

    // Calculate real stats from data
    const entityCount = data.persons.length + data.companies.length;
    
    // Calculate financial metrics from profiles
    const profiles = Object.values(data.profiles || {});
    const totalTransactions = profiles.reduce(
        (sum, p) => sum + (p.transactionCount || 0), 0
    );
    const totalFlow = profiles.reduce(
        (sum, p) => sum + (p.totalIncome || 0) + (p.totalExpense || 0), 0
    );
    const maxSingleTx = Math.max(...profiles.map(p => p.maxTransaction || 0), 0);
    const totalCash = profiles.reduce(
        (sum, p) => sum + (p.cashTotal || 0), 0
    );
    
    const highRiskFunds = (data.suspicions.directTransfers || []).reduce(
        (sum, tx) => sum + (tx.amount || 0), 0
    );
    const suspicionCount = (data.suspicions.directTransfers || []).length +
        (data.suspicions.cashCollisions || []).length +
        (data.suspicions.cashTimingPatterns || []).length;

    const kpis = [
        {
            id: 'overview',
            label: '审计概览',
            value: entityCount.toLocaleString(),
            subLabel: `${totalTransactions.toLocaleString()} 笔交易 / ${data.persons.length}人 ${data.companies.length}企`,
            icon: Users,
            trend: (entityCount > 0 ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: entityCount > 0 ? '数据已导入' : '等待数据',
            gradient: 'from-blue-500 to-cyan-500',
            glowColor: 'shadow-blue-500/20',
            iconBg: 'bg-blue-500/10',
            iconColor: 'text-blue-400',
        },
        {
            id: 'flow',
            label: '资金规模',
            value: formatAmountInWan(totalFlow),
            subLabel: `最大单笔: ${formatAmountInWan(maxSingleTx)}`,
            icon: Activity,
            trend: (totalFlow > 1000000 ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: totalFlow > 0 ? '资金充裕' : '无流水',
            gradient: 'from-cyan-500 to-teal-500',
            glowColor: 'shadow-cyan-500/20',
            iconBg: 'bg-cyan-500/10',
            iconColor: 'text-cyan-400',
        },
        {
            id: 'cash',
            label: '现金交易',
            value: formatAmountInWan(totalCash),
            subLabel: totalFlow > 0 ? `占比 ${((totalCash / totalFlow) * 100).toFixed(1)}%` : '占比 0%',
            icon: Banknote,
            trend: (totalCash > 500000 ? 'up' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: totalCash > 0 ? '现金密集' : '正常',
            gradient: 'from-violet-500 to-purple-500',
            glowColor: 'shadow-violet-500/20',
            iconBg: 'bg-violet-500/10',
            iconColor: 'text-violet-400',
        },
        {
            id: 'risk',
            label: '风险研判',
            value: formatAmountInWan(highRiskFunds),
            subLabel: `${suspicionCount} 条异常线索`,
            icon: ShieldAlert,
            trend: (highRiskFunds > 0 ? 'down' : 'neutral') as 'up' | 'neutral' | 'down',
            trendValue: highRiskFunds > 0 ? '❗ 需核查' : '✅ 无异常',
            gradient: 'from-red-500 to-orange-500',
            glowColor: 'shadow-red-500/20',
            iconBg: 'bg-red-500/10',
            iconColor: 'text-red-400',
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
