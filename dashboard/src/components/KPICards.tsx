import React from 'react';
import { Users, Activity, ShieldAlert, Server } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import type { StatsCardProps } from '../types';

export function KPICards() {
    const { data, analysis } = useApp();

    // Calculate stats
    const entityCount = data.persons.length + data.companies.length;
    const totalTransactions = Object.values(data.profiles).reduce(
        (sum, profile) => sum + (profile.transactionCount || 0),
        0
    );
    const highRiskFunds = data.suspicions.directTransfers.reduce(
        (sum, tx) => sum + (tx.amount || 0),
        0
    );

    const stats: StatsCardProps[] = [
        {
            label: '已分析实体',
            value: entityCount.toLocaleString(),
            icon: Users,
            color: 'text-blue-500',
        },
        {
            label: '交易总数',
            value: totalTransactions.toLocaleString(),
            icon: Activity,
            color: 'text-cyan-500',
        },
        {
            label: '高风险资金',
            value: `¥ ${(highRiskFunds / 10000).toFixed(1)}万`,
            icon: ShieldAlert,
            color: 'text-red-500',
        },
        {
            label: '系统状态',
            value: analysis.isRunning ? '分析中' : '就绪',
            icon: Server,
            color: analysis.isRunning ? 'text-yellow-500' : 'text-green-500',
            isStatus: true,
        },
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {stats.map((stat, index) => (
                <StatsCard key={index} {...stat} />
            ))}
        </div>
    );
}

// ==================== Stats Card Component ====================

function StatsCard({ label, value, icon: Icon, color, isStatus = false }: StatsCardProps) {
    return (
        <div className="glass-panel p-5 rounded-xl flex items-start justify-between relative overflow-hidden group">
            <div className="relative z-10">
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">{label}</p>
                <div className="flex items-center gap-2">
                    <h3 className={`text-2xl font-bold font-sans ${isStatus ? (color === 'text-green-500' ? 'text-green-400' : 'text-yellow-400') : 'text-slate-100'}`}>
                        {value}
                    </h3>
                    {isStatus && (
                        <span className="relative flex h-3 w-3">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-3 w-3 bg-current"></span>
                        </span>
                    )}
                </div>
            </div>
            <div className={`p-2 rounded-lg bg-slate-800/50 ${color} bg-opacity-10 relative z-10`}>
                <Icon className={`w-6 h-6 ${color} opacity-80`} />
            </div>
            {/* Decorative gradient blob */}
            <div
                className={`absolute -right-6 -bottom-6 w-24 h-24 bg-gradient-to-br from-transparent to-${color.split('-')[1]}-500/10 rounded-full blur-xl group-hover:scale-110 transition-transform duration-500`}
            ></div>
        </div>
    );
}
