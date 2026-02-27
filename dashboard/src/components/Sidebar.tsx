import { useState } from 'react';
import {
    FileText,
    Play,
    Square,
    FolderOpen,
    HardDrive,
    ChevronDown,
    Network,
    TrendingUp,
    Cpu,
    GitBranch,
    Clock,
    Layers,
    Wallet,
    Users,
    AlertTriangle,
    BarChart3,
    Zap,
    Menu,
    X
} from 'lucide-react';
import Logo from '../assets/logo.png';
import { useApp } from '../contexts/AppContext';
import type { TabType } from '../types';
import { api } from '../services/api';

export function Sidebar() {
    const {
        config,
        analysis,
        ui,
        updateDataSources,
        updateThresholds,
        updateAnalysisModules,
        startAnalysis,
        stopAnalysis,
        setActiveTab,
        toggleSidebar
    } = useApp();

    const [expandedSections, setExpandedSections] = useState({
        dataSources: true,
        thresholds: true,
        modules: false,
        navigation: true  // 快捷导航默认展开
    });

    const toggleSection = (section: keyof typeof expandedSections) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    // 处理文件夹选择 - 调用后端 API 弹出文件对话框
    const handleFolderSelect = async (type: 'input' | 'output') => {
        try {
            const currentPath = type === 'input' 
                ? config.dataSources.inputDirectory 
                : config.dataSources.outputDirectory;
            
            const result = await api.selectDirectory(type, currentPath);
            
            if (result.success && result.path) {
                if (type === 'input') {
                    updateDataSources({ inputDirectory: result.path });
                } else {
                    updateDataSources({ outputDirectory: result.path });
                }
            } else if (result.error) {
                console.log('选择目录:', result.error);
            }
        } catch (error) {
            console.error('选择目录失败:', error);
        }
    };

    const modulesList = [
        { key: 'profileAnalysis', label: '资金画像分析', icon: BarChart3 },
        { key: 'suspicionDetection', label: '疑点碰撞检测', icon: AlertTriangle },
        { key: 'assetAnalysis', label: '资产提取分析', icon: Wallet },
        { key: 'fundPenetration', label: '资金穿透分析', icon: GitBranch },
        { key: 'relatedParty', label: '关联方分析', icon: Users },
        { key: 'loanAnalysis', label: '借贷行为分析', icon: TrendingUp },
        { key: 'incomeAnalysis', label: '异常收入检测', icon: Zap },
        { key: 'mlAnalysis', label: 'ML风险预测', icon: Cpu },
        { key: 'timeSeriesAnalysis', label: '时间序列分析', icon: Clock },
        { key: 'clueAggregation', label: '线索聚合', icon: Layers },
    ] as const;

    const navItems: { id: TabType; label: string; icon: React.ElementType }[] = [
        { id: 'overview', label: '数据概览', icon: TrendingUp },
        { id: 'risk', label: '风险情报', icon: AlertTriangle },
        { id: 'graph', label: '关系图谱', icon: Network },
        { id: 'report', label: '审计报告', icon: FileText },
    ];

    return (
        <>
            {/* Mobile Toggle Button */}
            <button
                onClick={toggleSidebar}
                className="lg:hidden fixed top-4 left-4 z-50 p-2 theme-bg-surface border theme-border rounded-lg theme-text"
            >
                {ui.sidebarCollapsed ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
            </button>

            {/* Sidebar */}
            <aside className={`
        fixed lg:relative inset-y-0 left-0 z-40
        w-72 flex flex-col h-screen shrink-0
        theme-gradient-sidebar backdrop-blur-xl
        border-r theme-border
        transform transition-transform duration-300 ease-out
        ${ui.sidebarCollapsed ? '-translate-x-full lg:translate-x-0' : 'translate-x-0'}
      `}>
                {/* Logo Section */}
                <div className="p-6 border-b theme-border-muted flex flex-col items-center justify-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 via-cyan-500 to-blue-600 flex items-center justify-center shadow-lg relative overflow-hidden p-0.5">
                        <img src={Logo} alt="Logo" className="w-full h-full object-contain relative z-10" />
                        <div className="absolute inset-0 bg-gradient-to-t from-blue-600/50 to-transparent" />
                    </div>
                    <div className="text-center">
                        <h1 className="text-2xl font-bold theme-text tracking-tight mb-1">
                            穿云审计
                        </h1>
                        <p className="text-[10px] bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent font-semibold tracking-wide uppercase">
                            智能资金穿透与风险排查平台
                        </p>
                    </div>
                </div>

                {/* Engine Control Button */}
                <div className="p-4">
                    <button
                        onClick={analysis.isRunning ? stopAnalysis : startAnalysis}
                        className={`
              w-full relative overflow-hidden group
              font-semibold py-3.5 px-4 rounded-xl
              transition-all duration-300 transform
              ${analysis.isRunning
                                ? 'bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-500 hover:to-orange-500'
                                : 'bg-gradient-to-r from-blue-600 via-cyan-600 to-blue-600 hover:from-blue-500 hover:via-cyan-500 hover:to-blue-500'
                            }
              hover:-translate-y-0.5 
              shadow-lg ${analysis.isRunning ? 'shadow-red-500/25' : 'shadow-blue-500/25'}
            `}
                    >
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700" />

                        <div className="flex items-center justify-center gap-2.5 relative z-10">
                            {analysis.isRunning ? (
                                <>
                                    <Square className="w-4 h-4 fill-current" />
                                    <span className="uppercase tracking-wider text-sm">停止分析</span>
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 fill-current" />
                                    <span className="uppercase tracking-wider text-sm">开始分析</span>
                                </>
                            )}
                        </div>
                    </button>

                    {analysis.isRunning && (
                        <div className="mt-3 space-y-2">
                            {/* 进度条 */}
                            <div className="h-1.5 theme-bg-muted rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-500 ease-out"
                                    style={{ width: `${analysis.progress || 0}%` }}
                                />
                            </div>
                            {/* 进度文字 */}
                            <div className="flex items-center justify-between text-xs">
                                <div className="flex items-center gap-2 theme-text-muted">
                                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                                    <span className="truncate max-w-[160px]">{analysis.currentPhase || '正在分析...'}</span>
                                </div>
                                <span className="text-cyan-400 font-mono font-semibold">{analysis.progress || 0}%</span>
                            </div>
                        </div>
                    )}

                    {/* 分析完成状态 */}
                    {analysis.status === 'completed' && !analysis.isRunning && (
                        <div className="mt-3 flex items-center gap-2 text-xs">
                            <div className="w-4 h-4 rounded-full bg-green-500/20 flex items-center justify-center">
                                <svg className="w-2.5 h-2.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                            <span className="text-green-400">分析完成</span>
                            {analysis.lastRunTime && (
                                <span className="theme-text-dim ml-auto">
                                    {analysis.lastRunTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            )}
                        </div>
                    )}

                    {/* 分析失败状态 */}
                    {analysis.status === 'failed' && !analysis.isRunning && (
                        <div className="mt-3 flex items-center gap-2 text-xs">
                            <div className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center">
                                <span className="text-red-400 font-bold">×</span>
                            </div>
                            <span className="text-red-400 truncate">{analysis.currentPhase || '分析失败'}</span>
                        </div>
                    )}
                </div>

                {/* Scrollable Content */}
                <div className="flex-1 overflow-y-auto px-3 pb-4 scrollbar-thin">
                    {/* Data Sources Section */}
                    <ConfigSection
                        title="数据源配置"
                        expanded={expandedSections.dataSources}
                        onToggle={() => toggleSection('dataSources')}
                        accentColor="blue"
                    >
                        <div className="space-y-3">
                            <div>
                                <label className="text-[11px] font-medium theme-text-dim uppercase tracking-wider mb-1.5 block">
                                    输入目录
                                </label>
                                <div className="flex rounded-lg border theme-border overflow-hidden focus-within:border-blue-500/50 focus-within:ring-1 focus-within:ring-blue-500/30 transition-all theme-bg-muted/40">
                                    <input
                                        type="text"
                                        value={config.dataSources.inputDirectory}
                                        onChange={(e) => updateDataSources({ inputDirectory: e.target.value })}
                                        className="flex-1 min-w-0 bg-transparent text-sm px-3 py-2.5 theme-text placeholder:theme-text-dim outline-none"
                                        placeholder="选择数据文件夹"
                                    />
                                    <button
                                        onClick={() => handleFolderSelect('input')}
                                        className="flex-shrink-0 px-3 border-l theme-border theme-text-muted hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                                        title="选择文件夹"
                                    >
                                        <FolderOpen className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                            <div>
                                <label className="text-[11px] font-medium theme-text-dim uppercase tracking-wider mb-1.5 block">
                                    输出目录
                                </label>
                                <div className="flex rounded-lg border theme-border overflow-hidden focus-within:border-cyan-500/50 focus-within:ring-1 focus-within:ring-cyan-500/30 transition-all theme-bg-muted/40">
                                    <input
                                        type="text"
                                        value={config.dataSources.outputDirectory}
                                        onChange={(e) => updateDataSources({ outputDirectory: e.target.value })}
                                        className="flex-1 min-w-0 bg-transparent text-sm px-3 py-2.5 theme-text placeholder:theme-text-dim outline-none"
                                        placeholder="选择输出文件夹"
                                    />
                                    <button
                                        onClick={() => handleFolderSelect('output')}
                                        className="flex-shrink-0 px-3 border-l theme-border theme-text-muted hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                                        title="选择文件夹"
                                    >
                                        <HardDrive className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </ConfigSection>

                    {/* Thresholds Section */}
                    <ConfigSection
                        title="阈值参数"
                        expanded={expandedSections.thresholds}
                        onToggle={() => toggleSection('thresholds')}
                        accentColor="cyan"
                    >
                        <div className="space-y-3">
                            <div>
                                <label className="text-[11px] font-medium theme-text-dim uppercase tracking-wider mb-1.5 flex justify-between">
                                    <span>大额现金阈值</span>
                                    <span className="text-cyan-400 font-mono">¥{config.thresholds.cashThreshold.toLocaleString()}</span>
                                </label>
                                <input
                                    type="range"
                                    min={10000}
                                    max={500000}
                                    step={10000}
                                    value={config.thresholds.cashThreshold}
                                    onChange={(e) => updateThresholds({ cashThreshold: Number(e.target.value) })}
                                    className="w-full h-2 theme-bg-muted rounded-lg appearance-none cursor-pointer accent-cyan-500"
                                />
                                <div className="flex justify-between text-[10px] theme-text-dim mt-1">
                                    <span>¥1万</span>
                                    <span>¥50万</span>
                                </div>
                            </div>
                            <div>
                                <label className="text-[11px] font-medium theme-text-dim uppercase tracking-wider mb-1.5 flex justify-between">
                                    <span>时间窗口</span>
                                    <span className="text-cyan-400 font-mono">{config.thresholds.timeWindow}h</span>
                                </label>
                                <input
                                    type="range"
                                    min={1}
                                    max={168}
                                    step={1}
                                    value={config.thresholds.timeWindow}
                                    onChange={(e) => updateThresholds({ timeWindow: Number(e.target.value) })}
                                    className="w-full h-2 theme-bg-muted rounded-lg appearance-none cursor-pointer accent-cyan-500"
                                />
                                <div className="flex justify-between text-[10px] theme-text-dim mt-1">
                                    <span>1h</span>
                                    <span>168h (7天)</span>
                                </div>
                            </div>
                        </div>
                    </ConfigSection>

                    {/* Analysis Modules Section */}
                    <ConfigSection
                        title="分析模块"
                        expanded={expandedSections.modules}
                        onToggle={() => toggleSection('modules')}
                        accentColor="violet"
                        badge={`${Object.values(config.analysisModules).filter(Boolean).length}/${Object.keys(config.analysisModules).length}`}
                    >
                        <div className="space-y-1">
                            {modulesList.map(({ key, label, icon: Icon }) => (
                                <ModuleToggle
                                    key={key}
                                    label={label}
                                    icon={Icon}
                                    checked={config.analysisModules[key as keyof typeof config.analysisModules]}
                                    onChange={() => updateAnalysisModules({
                                        [key]: !config.analysisModules[key as keyof typeof config.analysisModules]
                                    })}
                                />
                            ))}
                        </div>
                    </ConfigSection>

                    {/* Navigation Section - Quick Access (可折叠) */}
                    <div className="mt-6 border-t theme-border-muted pt-4">
                        <button
                            onClick={() => toggleSection('navigation')}
                            className="w-full flex items-center justify-between py-2.5 px-2 text-left group theme-hover rounded-lg transition-colors"
                        >
                            <div className="flex items-center gap-2">
                                <span className="w-1 h-3 bg-gradient-to-b from-violet-500 to-fuchsia-500 rounded-full" />
                                <span className="text-[11px] font-semibold theme-text-muted uppercase tracking-wider group-hover:theme-text transition-colors">
                                    快捷导航
                                </span>
                            </div>
                            <div className="flex items-center gap-1">
                                <span className="text-[10px] theme-text-dim group-hover:theme-text-muted transition-colors">
                                    {expandedSections.navigation ? '收起' : '展开'}
                                </span>
                                <ChevronDown className={`w-4 h-4 theme-text-dim group-hover:theme-text-secondary transition-all duration-200 ${expandedSections.navigation ? 'rotate-0' : '-rotate-90'}`} />
                            </div>
                        </button>
                        {expandedSections.navigation && (
                            <nav className="space-y-1 px-2 pb-2 animate-fade-in">
                                {navItems.map(({ id, label, icon: Icon }) => (
                                    <button
                                        key={id}
                                        onClick={() => setActiveTab(id)}
                                        className={`
                        flex items-center gap-3 w-full px-3 py-2.5 rounded-lg
                        text-sm font-medium transition-all duration-200
                        ${ui.activeTab === id
                                                ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-500'
                                                : 'theme-text-muted theme-hover hover:theme-text border-l-2 border-transparent'
                                            }
                      `}
                                    >
                                        <Icon className="w-4 h-4" />
                                        {label}
                                    </button>
                                ))}
                            </nav>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t theme-border-muted theme-bg-muted">
                    <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                            <span className="theme-text-dim">系统在线</span>
                        </div>
                        <span className="theme-text-dim font-mono">v3.0.0</span>
                    </div>
                    {analysis.lastRunTime && (
                        <p className="text-[10px] theme-text-dim mt-2">
                            上次运行: {analysis.lastRunTime.toLocaleTimeString()}
                        </p>
                    )}
                </div>
            </aside>
        </>
    );
}

// ==================== Config Section Component ====================

interface ConfigSectionProps {
    title: string;
    expanded: boolean;
    onToggle: () => void;
    accentColor: 'blue' | 'cyan' | 'violet' | 'green';
    badge?: string;
    children: React.ReactNode;
}

function ConfigSection({ title, expanded, onToggle, accentColor, badge, children }: ConfigSectionProps) {
    const colorMap = {
        blue: 'from-blue-500 to-blue-600',
        cyan: 'from-cyan-500 to-cyan-600',
        violet: 'from-violet-500 to-fuchsia-500',
        green: 'from-green-500 to-emerald-500'
    };

    return (
        <div className="mb-4">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between py-2.5 px-2 text-left group"
            >
                <div className="flex items-center gap-2">
                    <span className={`w-1 h-3 bg-gradient-to-b ${colorMap[accentColor]} rounded-full`} />
                    <span className="text-[11px] font-semibold theme-text-muted uppercase tracking-wider group-hover:theme-text-secondary transition-colors">
                        {title}
                    </span>
                    {badge && (
                        <span className="px-1.5 py-0.5 text-[10px] font-mono theme-text-dim theme-bg-muted rounded">
                            {badge}
                        </span>
                    )}
                </div>
                <ChevronDown className={`w-3.5 h-3.5 theme-text-dim transition-transform duration-200 ${expanded ? 'rotate-0' : '-rotate-90'}`} />
            </button>
            {expanded && (
                <div className="px-2 pb-2 animate-fade-in">
                    {children}
                </div>
            )}
        </div>
    );
}

// ==================== Module Toggle Component ====================

interface ModuleToggleProps {
    label: string;
    icon: React.ElementType;
    checked: boolean;
    onChange: () => void;
}

function ModuleToggle({ label, icon: Icon, checked, onChange }: ModuleToggleProps) {
    return (
        <label className="flex items-center gap-3 px-2 py-2 rounded-lg theme-hover cursor-pointer transition-colors group">
            <div className="relative">
                <input
                    type="checkbox"
                    checked={checked}
                    onChange={onChange}
                    className="sr-only"
                />
                <div className={`
          w-4 h-4 rounded border-2 transition-all duration-200
          flex items-center justify-center
          ${checked
                        ? 'bg-blue-500 border-blue-500'
                        : 'theme-border bg-transparent group-hover:theme-border-strong'
                    }
        `}>
                    {checked && (
                        <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                    )}
                </div>
            </div>
            <Icon className={`w-3.5 h-3.5 transition-colors ${checked ? 'text-blue-400' : 'theme-text-dim'}`} />
            <span className={`text-sm transition-colors ${checked ? 'theme-text-secondary' : 'theme-text-muted'}`}>
                {label}
            </span>
        </label>
    );
}
