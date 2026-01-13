import { useState, useRef } from 'react';
import {
    LayoutDashboard,
    FileText,
    Play,
    Square,
    FolderOpen,
    HardDrive,
    ChevronDown,
    ShieldCheck,
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
    X,
    CloudCog
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import type { TabType } from '../types';

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
        modules: false
    });

    // 文件夹选择的隐藏 input refs
    const inputDirRef = useRef<HTMLInputElement>(null);
    const outputDirRef = useRef<HTMLInputElement>(null);

    const toggleSection = (section: keyof typeof expandedSections) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    // 处理文件夹选择
    const handleFolderSelect = (type: 'input' | 'output') => {
        const ref = type === 'input' ? inputDirRef : outputDirRef;
        ref.current?.click();
    };

    // 处理文件夹选择结果
    const handleFolderChange = (event: React.ChangeEvent<HTMLInputElement>, type: 'input' | 'output') => {
        const files = event.target.files;
        if (files && files.length > 0) {
            // 从文件路径中提取目录路径
            const firstFile = files[0];
            const relativePath = firstFile.webkitRelativePath;
            const folderName = relativePath.split('/')[0];

            if (type === 'input') {
                updateDataSources({ inputDirectory: `./${folderName}` });
            } else {
                updateDataSources({ outputDirectory: `./${folderName}` });
            }
        }
        event.target.value = '';
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
        { id: 'overview', label: '数据概览', icon: LayoutDashboard },
        { id: 'risk', label: '风险情报', icon: ShieldCheck },
        { id: 'graph', label: '关系图谱', icon: Network },
        { id: 'report', label: '审计报告', icon: FileText },
    ];

    return (
        <>
            {/* 隐藏的文件夹选择 input */}
            <input
                ref={inputDirRef}
                type="file"
                {...{ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>}
                multiple
                className="hidden"
                onChange={(e) => handleFolderChange(e, 'input')}
            />
            <input
                ref={outputDirRef}
                type="file"
                {...{ webkitdirectory: '', directory: '' } as React.InputHTMLAttributes<HTMLInputElement>}
                multiple
                className="hidden"
                onChange={(e) => handleFolderChange(e, 'output')}
            />

            {/* Mobile Toggle Button */}
            <button
                onClick={toggleSidebar}
                className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-gray-900 border border-gray-700 rounded-lg"
            >
                {ui.sidebarCollapsed ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
            </button>

            {/* Sidebar */}
            <aside className={`
        fixed lg:relative inset-y-0 left-0 z-40
        w-72 flex flex-col h-screen shrink-0
        bg-[#0a0f1a]/95 backdrop-blur-xl
        border-r border-gray-800/80
        transform transition-transform duration-300 ease-out
        ${ui.sidebarCollapsed ? '-translate-x-full lg:translate-x-0' : 'translate-x-0'}
      `}>
                {/* Logo Section */}
                <div className="p-5 border-b border-gray-800/50">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-cyan-500 to-blue-600 flex items-center justify-center shadow-lg relative overflow-hidden">
                            <CloudCog className="w-5 h-5 text-white relative z-10" />
                            <div className="absolute inset-0 bg-gradient-to-t from-blue-600/50 to-transparent" />
                        </div>
                        <div>
                            <h1 className="text-lg font-bold text-white tracking-tight">
                                穿云审计
                            </h1>
                            <p className="text-[10px] text-gray-500 font-medium tracking-wider">
                                资金穿透与关联排查系统
                            </p>
                        </div>
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
                                    <span className="uppercase tracking-wider text-sm">终止分析</span>
                                </>
                            ) : (
                                <>
                                    <Play className="w-4 h-4 fill-current" />
                                    <span className="uppercase tracking-wider text-sm">启动引擎</span>
                                </>
                            )}
                        </div>
                    </button>

                    {analysis.isRunning && (
                        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                            <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                            <span>{analysis.currentPhase || '正在分析...'}</span>
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
                                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider mb-1.5 block">
                                    输入目录
                                </label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={config.dataSources.inputDirectory}
                                        onChange={(e) => updateDataSources({ inputDirectory: e.target.value })}
                                        className="flex-1 input-field text-sm"
                                        placeholder="./data"
                                    />
                                    <button
                                        onClick={() => handleFolderSelect('input')}
                                        className="btn-icon shrink-0 hover:border-blue-500 hover:text-blue-400"
                                        title="选择文件夹"
                                    >
                                        <FolderOpen className="w-4 h-4" />
                                    </button>
                                </div>
                                <p className="text-[10px] text-gray-600 mt-1">点击图标选择数据文件夹</p>
                            </div>
                            <div>
                                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider mb-1.5 block">
                                    输出目录
                                </label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={config.dataSources.outputDirectory}
                                        onChange={(e) => updateDataSources({ outputDirectory: e.target.value })}
                                        className="flex-1 input-field text-sm"
                                        placeholder="./output"
                                    />
                                    <button
                                        onClick={() => handleFolderSelect('output')}
                                        className="btn-icon shrink-0 hover:border-cyan-500 hover:text-cyan-400"
                                        title="选择文件夹"
                                    >
                                        <HardDrive className="w-4 h-4" />
                                    </button>
                                </div>
                                <p className="text-[10px] text-gray-600 mt-1">点击图标选择输出文件夹</p>
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
                                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider mb-1.5 flex justify-between">
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
                                    className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider mb-1.5 flex justify-between">
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
                                    className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                                />
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

                    {/* Navigation Section */}
                    <div className="mt-6">
                        <h3 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-3 px-2 flex items-center gap-2">
                            <span className="w-1 h-3 bg-gradient-to-b from-violet-500 to-fuchsia-500 rounded-full" />
                            导航菜单
                        </h3>
                        <nav className="space-y-1">
                            {navItems.map(({ id, label, icon: Icon }) => (
                                <button
                                    key={id}
                                    onClick={() => setActiveTab(id)}
                                    className={`
                    flex items-center gap-3 w-full px-3 py-2.5 rounded-lg
                    text-sm font-medium transition-all duration-200
                    ${ui.activeTab === id
                                            ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-500'
                                            : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border-l-2 border-transparent'
                                        }
                  `}
                                >
                                    <Icon className="w-4 h-4" />
                                    {label}
                                </button>
                            ))}
                        </nav>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-800/50 bg-gray-900/30">
                    <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                            <span className="text-gray-500">系统在线</span>
                        </div>
                        <span className="text-gray-600 font-mono">v3.0.0</span>
                    </div>
                    {analysis.lastRunTime && (
                        <p className="text-[10px] text-gray-600 mt-2">
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
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider group-hover:text-gray-300 transition-colors">
                        {title}
                    </span>
                    {badge && (
                        <span className="px-1.5 py-0.5 text-[10px] font-mono text-gray-500 bg-gray-800 rounded">
                            {badge}
                        </span>
                    )}
                </div>
                <ChevronDown className={`w-3.5 h-3.5 text-gray-500 transition-transform duration-200 ${expanded ? 'rotate-0' : '-rotate-90'}`} />
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
        <label className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-800/30 cursor-pointer transition-colors group">
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
                        : 'border-gray-600 bg-transparent group-hover:border-gray-500'
                    }
        `}>
                    {checked && (
                        <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={4}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                    )}
                </div>
            </div>
            <Icon className={`w-3.5 h-3.5 transition-colors ${checked ? 'text-blue-400' : 'text-gray-500'}`} />
            <span className={`text-sm transition-colors ${checked ? 'text-gray-200' : 'text-gray-400'}`}>
                {label}
            </span>
        </label>
    );
}
