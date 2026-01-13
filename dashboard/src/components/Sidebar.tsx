import React from 'react';
import {
    LayoutDashboard,
    Search,
    Database,
    FileText,
    Settings,
    Play,
    FolderOpen,
    Save,
    ChevronDown,
    ChevronRight,
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import type { SidebarProps } from '../types';

export function Sidebar() {
    const { config, analysis, updateDataSources, updateThresholds, updateAnalysisModules, startAnalysis } = useApp();

    const handleBrowseInput = () => {
        // TODO: Implement native directory picker
        alert('目录选择功能将通过后端API实现');
    };

    const handleBrowseOutput = () => {
        // TODO: Implement native directory picker
        alert('目录选择功能将通过后端API实现');
    };

    const toggleModule = (key: keyof typeof config.analysisModules) => {
        updateAnalysisModules({ [key]: !config.analysisModules[key] });
    };

    return (
        <div className="w-72 border-r border-slate-800 bg-[#020617] flex flex-col h-screen shrink-0">
            {/* Logo Section */}
            <div className="p-6 border-b border-slate-800/50">
                <h1 className="text-xl font-bold tracking-wider text-slate-100 flex items-center gap-2">
                    <span className="text-blue-500">🛡️</span>
                    资金穿透审计系统
                </h1>
                <p className="text-xs text-slate-500 mt-1 uppercase tracking-widest">FUND PENETRATION AUDIT</p>
            </div>

            {/* Start Engine Button */}
            <div className="p-4">
                <button
                    onClick={startAnalysis}
                    disabled={analysis.isRunning}
                    className={`w-full relative overflow-hidden font-semibold py-3 px-4 rounded-lg transition-all duration-300 transform hover:-translate-y-0.5 ${analysis.isRunning
                        ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                        : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-glow-blue'
                        }`}
                >
                    <div className={`absolute inset-0 bg-white/20 ${analysis.isRunning ? '' : 'translate-y-full'} transition-transform duration-300`}></div>
                    <div className="flex items-center justify-center gap-2 relative z-10 uppercase tracking-wide text-sm">
                        <Play className="w-4 h-4 fill-current" />
                        {analysis.isRunning ? '分析中...' : '启动引擎'}
                    </div>
                </button>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-3 scrollbar-thin">
                {/* Data Source Section */}
                <div className="mb-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1 flex items-center gap-2">
                        <span className="w-1 h-3 bg-blue-500 rounded-sm"></span>
                        数据源配置
                    </h3>
                    <div className="space-y-3">
                        <div>
                            <label className="text-xs text-slate-400 mb-1 block">输入目录</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={config.dataSources.inputDirectory}
                                    onChange={(e) => updateDataSources({ inputDirectory: e.target.value })}
                                    className="flex-1 bg-slate-800/50 border border-slate-700 text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                    placeholder="./data"
                                />
                                <button
                                    onClick={handleBrowseInput}
                                    className="p-2 bg-slate-800 border border-slate-700 rounded-md text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
                                    title="浏览"
                                >
                                    <FolderOpen className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 mb-1 block">输出目录</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={config.dataSources.outputDirectory}
                                    onChange={(e) => updateDataSources({ outputDirectory: e.target.value })}
                                    className="flex-1 bg-slate-800/50 border border-slate-700 text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                    placeholder="./output"
                                />
                                <button
                                    onClick={handleBrowseOutput}
                                    className="p-2 bg-slate-800 border border-slate-700 rounded-md text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors"
                                    title="浏览"
                                >
                                    <Save className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Threshold Params Section */}
                <div className="mb-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1 flex items-center gap-2">
                        <span className="w-1 h-3 bg-cyan-500 rounded-sm"></span>
                        阈值参数
                    </h3>
                    <div className="space-y-3">
                        <div>
                            <label className="text-xs text-slate-400 mb-1 block">现金阈值 (元)</label>
                            <input
                                type="number"
                                value={config.thresholds.cashThreshold}
                                onChange={(e) => updateThresholds({ cashThreshold: Number(e.target.value) })}
                                className="w-full bg-slate-800/50 border border-slate-700 text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                step={10000}
                            />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 mb-1 block">时间窗口 (小时)</label>
                            <input
                                type="number"
                                value={config.thresholds.timeWindow}
                                onChange={(e) => updateThresholds({ timeWindow: Number(e.target.value) })}
                                className="w-full bg-slate-800/50 border border-slate-700 text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                                step={1}
                            />
                        </div>
                    </div>
                </div>

                {/* Analysis Modules Section */}
                <div className="mb-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1 flex items-center gap-2">
                        <span className="w-1 h-3 bg-green-500 rounded-sm"></span>
                        分析模块
                    </h3>
                    <div className="space-y-2">
                        <ModuleToggle
                            label="资金画像分析"
                            checked={config.analysisModules.profileAnalysis}
                            onChange={() => toggleModule('profileAnalysis')}
                        />
                        <ModuleToggle
                            label="疑点碰撞检测"
                            checked={config.analysisModules.suspicionDetection}
                            onChange={() => toggleModule('suspicionDetection')}
                        />
                        <ModuleToggle
                            label="资产提取与分析"
                            checked={config.analysisModules.assetAnalysis}
                            onChange={() => toggleModule('assetAnalysis')}
                        />
                        <ModuleToggle
                            label="数据验证"
                            checked={config.analysisModules.dataValidation}
                            onChange={() => toggleModule('dataValidation')}
                        />
                        <ModuleToggle
                            label="资金穿透分析"
                            checked={config.analysisModules.fundPenetration}
                            onChange={() => toggleModule('fundPenetration')}
                        />
                        <ModuleToggle
                            label="关联方资金分析"
                            checked={config.analysisModules.relatedParty}
                            onChange={() => toggleModule('relatedParty')}
                        />
                        <ModuleToggle
                            label="多源数据碰撞"
                            checked={config.analysisModules.multiSourceCorrelation}
                            onChange={() => toggleModule('multiSourceCorrelation')}
                        />
                        <ModuleToggle
                            label="借贷行为分析"
                            checked={config.analysisModules.loanAnalysis}
                            onChange={() => toggleModule('loanAnalysis')}
                        />
                        <ModuleToggle
                            label="异常收入检测"
                            checked={config.analysisModules.incomeAnalysis}
                            onChange={() => toggleModule('incomeAnalysis')}
                        />
                        <ModuleToggle
                            label="资金流向可视化"
                            checked={config.analysisModules.flowVisualization}
                            onChange={() => toggleModule('flowVisualization')}
                        />
                        <ModuleToggle
                            label="机器学习风险预测"
                            checked={config.analysisModules.mlAnalysis}
                            onChange={() => toggleModule('mlAnalysis')}
                        />
                        <ModuleToggle
                            label="时间序列分析"
                            checked={config.analysisModules.timeSeriesAnalysis}
                            onChange={() => toggleModule('timeSeriesAnalysis')}
                        />
                        <ModuleToggle
                            label="线索聚合"
                            checked={config.analysisModules.clueAggregation}
                            onChange={() => toggleModule('clueAggregation')}
                        />
                    </div>
                </div>

                {/* Navigation Section */}
                <div className="mb-6">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-1 flex items-center gap-2">
                        <span className="w-1 h-3 bg-purple-500 rounded-sm"></span>
                        导航菜单
                    </h3>
                    <div className="space-y-1">
                        <NavItem icon={LayoutDashboard} label="概览" active={true} />
                        <NavItem icon={Search} label="调查分析" />
                        <NavItem icon={Database} label="数据源" />
                        <NavItem icon={FileText} label="报告中心" />
                        <NavItem icon={Settings} label="系统设置" />
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-800">
                {analysis.lastRunTime && (
                    <p className="text-xs text-slate-500 text-center mb-2">
                        上次运行: {analysis.lastRunTime.toLocaleTimeString()}
                    </p>
                )}
                <p className="text-xs text-slate-600 text-center font-mono">v2.4.0-stable</p>
            </div>
        </div>
    );
}

// ==================== Sub Components ====================

interface ModuleToggleProps {
    label: string;
    checked: boolean;
    onChange: () => void;
}

function ModuleToggle({ label, checked, onChange }: ModuleToggleProps) {
    return (
        <label className="flex items-center gap-3 px-2 py-2 rounded-md hover:bg-slate-900/50 cursor-pointer transition-colors">
            <div className="relative">
                <input
                    type="checkbox"
                    checked={checked}
                    onChange={onChange}
                    className="sr-only"
                />
                <div className={`w-4 h-4 rounded border transition-colors ${checked ? 'bg-blue-500 border-blue-500' : 'border-slate-600 bg-slate-800'
                    }`}>
                    {checked && (
                        <svg className="w-3 h-3 text-white absolute top-0.5 left-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                    )}
                </div>
            </div>
            <span className="text-sm text-slate-300">{label}</span>
        </label>
    );
}

interface NavItemProps {
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    active?: boolean;
}

function NavItem({ icon: Icon, label, active = false }: NavItemProps) {
    return (
        <button
            className={`flex items-center gap-3 w-full px-4 py-3 text-sm font-medium rounded-md transition-all duration-200 ${active
                ? 'bg-slate-800/50 text-blue-400 border-l-2 border-blue-500'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
                }`}
        >
            <Icon className="w-4 h-4" />
            {label}
        </button>
    );
}
