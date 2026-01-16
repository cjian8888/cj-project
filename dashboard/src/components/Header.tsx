import { Bell, Search, User, Zap, Wifi, WifiOff } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { ws } from '../services/api';
import { useState, useEffect } from 'react';

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export function Header() {
    const { analysis } = useApp();
    const [wsStatus, setWsStatus] = useState<WSStatus>(ws.status);

    // 订阅 WebSocket 状态变化
    useEffect(() => {
        const unsubscribe = ws.subscribeStatus(setWsStatus);
        return unsubscribe;
    }, []);

    const getWSStatusConfig = () => {
        switch (wsStatus) {
            case 'connected':
                return { icon: Wifi, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', label: '已连接', pulse: false };
            case 'connecting':
                return { icon: Wifi, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: '连接中', pulse: true };
            case 'error':
                return { icon: WifiOff, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', label: '连接失败', pulse: false };
            default:
                return { icon: WifiOff, color: 'text-gray-400', bg: 'bg-gray-800/50', border: 'border-gray-700', label: '未连接', pulse: false };
        }
    };

    const wsConfig = getWSStatusConfig();
    const WSIcon = wsConfig.icon;

    return (
        <header className="px-6 lg:px-8 py-5 border-b border-gray-800/50 bg-[#030712]/80 backdrop-blur-xl shrink-0 relative z-20">
            <div className="flex items-center justify-between">
                {/* Left Section - Title */}
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shadow-lg glow-blue">
                            <Zap className="w-5 h-5 text-white" />
                        </div>
                        {/* Pulse indicator when running */}
                        {analysis.isRunning && (
                            <div className="absolute -top-1 -right-1 w-3 h-3">
                                <span className="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping" />
                                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
                            </div>
                        )}
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-white tracking-tight">
                            穿云审计 · 指挥中心
                        </h1>
                        <p className="text-xs bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent font-semibold tracking-wide">
                            智能资金穿透与风险排查平台
                        </p>
                    </div>
                </div>

                {/* Center Section - Search (Disabled - Under Development) */}
                <div className="hidden lg:flex items-center flex-1 max-w-md mx-8">
                    <div className="relative w-full group">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" />
                        <input
                            type="text"
                            placeholder="搜索功能开发中..."
                            disabled
                            className="w-full pl-10 pr-4 py-2.5 bg-gray-900/30 border border-gray-800/50 rounded-xl text-sm text-gray-500 placeholder:text-gray-600 cursor-not-allowed"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 px-2 py-0.5 text-[9px] font-medium text-amber-500/80 bg-amber-500/10 border border-amber-500/20 rounded">
                            待开发
                        </span>
                    </div>
                </div>

                {/* Right Section - Actions */}
                <div className="flex items-center gap-3">
                    {/* WebSocket Connection Status */}
                    <button
                        onClick={() => wsStatus !== 'connected' && ws.reconnect()}
                        className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all ${wsConfig.bg} ${wsConfig.color} border ${wsConfig.border} ${wsStatus !== 'connected' ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
                        title={wsStatus !== 'connected' ? '点击重连' : '实时连接正常'}
                    >
                        <WSIcon className={`w-3.5 h-3.5 ${wsConfig.pulse ? 'animate-pulse' : ''}`} />
                        <span className="hidden md:inline">{wsConfig.label}</span>
                    </button>

                    {/* Status Badge */}
                    <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${analysis.isRunning
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        : analysis.status === 'completed'
                            ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                            : 'bg-gray-800/50 text-gray-400 border border-gray-700'
                        }`}>
                        <span className={`w-2 h-2 rounded-full ${analysis.isRunning
                            ? 'bg-amber-400 animate-pulse'
                            : analysis.status === 'completed'
                                ? 'bg-green-400'
                                : 'bg-gray-500'
                            }`} />
                        {analysis.isRunning ? '分析进行中' : analysis.status === 'completed' ? '分析完成' : '系统就绪'}
                    </div>

                    {/* Notification Button (Disabled) */}
                    <button className="relative btn-icon opacity-50 cursor-not-allowed" title="通知功能开发中" disabled>
                        <Bell className="w-4 h-4" />
                    </button>

                    {/* User Info (Read-only, no dropdown) */}
                    <div className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl bg-gray-800/50 border border-gray-700">
                        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center">
                            <User className="w-4 h-4 text-white" />
                        </div>
                        <span className="text-sm font-medium text-gray-300 hidden sm:block">审计人员</span>
                    </div>
                </div>
            </div>
        </header>
    );
}
