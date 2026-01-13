import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { AppState, AppConfig, AnalysisState, DataState, LogEntry, UIState, TabType } from '../types';

// ==================== Default Values ====================

const defaultConfig: AppConfig = {
    dataSources: {
        inputDirectory: './data',
        outputDirectory: './output',
    },
    thresholds: {
        cashThreshold: 50000,
        timeWindow: 48,
    },
    analysisModules: {
        profileAnalysis: true,
        suspicionDetection: true,
        assetAnalysis: true,
        dataValidation: true,
        fundPenetration: true,
        relatedParty: true,
        multiSourceCorrelation: true,
        loanAnalysis: true,
        incomeAnalysis: true,
        flowVisualization: true,
        mlAnalysis: true,
        timeSeriesAnalysis: true,
        clueAggregation: true,
    },
};

const defaultAnalysis: AnalysisState = {
    isRunning: false,
    progress: 0,
    currentPhase: '',
    lastRunTime: null,
    status: 'idle',
};

const defaultData: DataState = {
    persons: [],
    companies: [],
    profiles: {},
    suspicions: {
        directTransfers: [],
        cashCollisions: [],
        hiddenAssets: {},
        fixedFrequency: {},
        cashTimingPatterns: [],
        holidayTransactions: {},
        amountPatterns: {},
    },
    analysisResults: {
        loan: { summary: { 双向往来关系数: 0, 网贷平台交易数: 0, 规律还款模式数: 0 }, details: [] },
        income: { summary: { 规律性非工资收入: 0, 个人大额转入: 0, 来源不明收入: 0 }, details: [] },
        ml: { summary: { anomalyCount: 0, highRiskCount: 0 }, predictions: [] },
        penetration: { summary: { 资金穿透链数: 0, 中间节点数: 0 }, chains: [] },
        relatedParty: { summary: { 直接往来笔数: 0, 第三方中转链数: 0, 资金闭环数: 0 }, details: [] },
        correlation: { summary: { 资金碰撞总数: 0 }, correlations: [] },
        timeSeries: { summary: { 异常时间点数: 0 }, anomalies: [] },
        aggregation: { rankedEntities: [], summary: { 极高风险实体数: 0, 高风险实体数: 0 } },
    },
    categorizedFiles: {
        persons: {},
        companies: {},
        transactionFiles: [],
    },
};

const defaultUI: UIState = {
    activeTab: 'overview',
    sidebarCollapsed: true,
};

const initialLogs: LogEntry[] = [
    { time: '00:00:01', level: 'INFO', msg: '系统初始化完成，版本 v3.0.0' },
    { time: '00:00:02', level: 'INFO', msg: '连接安全数据仓库 (节点 A-7)' },
    { time: '00:00:03', level: 'INFO', msg: '加载实体关系模型...' },
    { time: '00:00:05', level: 'INFO', msg: '分析引擎就绪，等待指令' },
];

// ==================== Context ====================

interface AppContextType extends AppState {
    // Config actions
    updateConfig: (config: Partial<AppConfig>) => void;
    updateDataSources: (dataSources: Partial<AppConfig['dataSources']>) => void;
    updateThresholds: (thresholds: Partial<AppConfig['thresholds']>) => void;
    updateAnalysisModules: (modules: Partial<AppConfig['analysisModules']>) => void;

    // Analysis actions
    startAnalysis: () => void;
    stopAnalysis: () => void;
    updateAnalysisProgress: (progress: number, phase: string) => void;
    setAnalysisStatus: (status: AnalysisState['status']) => void;

    // Data actions
    updateData: (data: Partial<DataState>) => void;
    resetData: () => void;

    // Log actions
    addLog: (log: LogEntry) => void;
    clearLogs: () => void;

    // UI actions
    setActiveTab: (tab: TabType) => void;
    toggleSidebar: () => void;
}

const AppContext = createContext<AppContextType | null>(null);

// ==================== Provider ====================

interface AppProviderProps {
    children: ReactNode;
}

export function AppProvider({ children }: AppProviderProps) {
    const [config, setConfig] = useState<AppConfig>(defaultConfig);
    const [analysis, setAnalysis] = useState<AnalysisState>(defaultAnalysis);
    const [data, setData] = useState<DataState>(defaultData);
    const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
    const [ui, setUI] = useState<UIState>(defaultUI);

    // ==================== Config Actions ====================

    const updateConfig = useCallback((newConfig: Partial<AppConfig>) => {
        setConfig(prev => ({ ...prev, ...newConfig }));
    }, []);

    const updateDataSources = useCallback((dataSources: Partial<AppConfig['dataSources']>) => {
        setConfig(prev => ({
            ...prev,
            dataSources: { ...prev.dataSources, ...dataSources },
        }));
    }, []);

    const updateThresholds = useCallback((thresholds: Partial<AppConfig['thresholds']>) => {
        setConfig(prev => ({
            ...prev,
            thresholds: { ...prev.thresholds, ...thresholds },
        }));
    }, []);

    const updateAnalysisModules = useCallback((modules: Partial<AppConfig['analysisModules']>) => {
        setConfig(prev => ({
            ...prev,
            analysisModules: { ...prev.analysisModules, ...modules },
        }));
    }, []);

    // ==================== Analysis Actions ====================

    const addLog = useCallback((log: LogEntry) => {
        setLogs(prev => {
            const newLogs = [...prev, log];
            // Keep only last 200 logs
            if (newLogs.length > 200) {
                return newLogs.slice(-200);
            }
            return newLogs;
        });
    }, []);

    const startAnalysis = useCallback(() => {
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

        setAnalysis({
            isRunning: true,
            progress: 0,
            currentPhase: '初始化分析引擎...',
            lastRunTime: now,
            status: 'running',
        });

        addLog({ time: timeStr, level: 'INFO', msg: '▶ 分析引擎已启动' });

        // Simulate analysis progress
        const phases = [
            { progress: 10, phase: '扫描数据目录...' },
            { progress: 25, phase: '读取银行流水记录...' },
            { progress: 40, phase: '数据清洗与标准化...' },
            { progress: 55, phase: '提取关联线索...' },
            { progress: 70, phase: '执行资金画像分析...' },
            { progress: 85, phase: '检测可疑交易模式...' },
            { progress: 95, phase: '生成审计报告...' },
            { progress: 100, phase: '分析完成' },
        ];

        phases.forEach((p, i) => {
            setTimeout(() => {
                setAnalysis(prev => ({
                    ...prev,
                    progress: p.progress,
                    currentPhase: p.phase,
                }));

                const t = new Date();
                const ts = `${t.getHours().toString().padStart(2, '0')}:${t.getMinutes().toString().padStart(2, '0')}:${t.getSeconds().toString().padStart(2, '0')}`;
                addLog({ time: ts, level: 'INFO', msg: p.phase });

                // Complete analysis
                if (p.progress === 100) {
                    setTimeout(() => {
                        setAnalysis(prev => ({
                            ...prev,
                            isRunning: false,
                            status: 'completed',
                        }));

                        // Add demo data
                        setData({
                            persons: ['张三', '李四', '王五', '赵六'],
                            companies: ['科技有限公司', '贸易发展公司', '投资咨询公司'],
                            profiles: {
                                '张三': { entityName: '张三', totalIncome: 2580000, totalExpense: 1890000, transactionCount: 342 },
                                '李四': { entityName: '李四', totalIncome: 1850000, totalExpense: 1650000, transactionCount: 256 },
                                '王五': { entityName: '王五', totalIncome: 980000, totalExpense: 1120000, transactionCount: 189 },
                                '科技有限公司': { entityName: '科技有限公司', totalIncome: 8500000, totalExpense: 7200000, transactionCount: 892 },
                                '贸易发展公司': { entityName: '贸易发展公司', totalIncome: 5600000, totalExpense: 4800000, transactionCount: 567 },
                            },
                            suspicions: {
                                directTransfers: [
                                    { from: '张三', to: '科技有限公司', amount: 500000, date: '2024-01-15' },
                                    { from: '科技有限公司', to: '李四', amount: 480000, date: '2024-01-16' },
                                    { from: '李四', to: '贸易发展公司', amount: 450000, date: '2024-01-17' },
                                    { from: '贸易发展公司', to: '王五', amount: 420000, date: '2024-01-18' },
                                ],
                                cashCollisions: [
                                    { person1: '张三', person2: '李四', time1: '10:15', time2: '10:18', amount1: 50000, amount2: 48000 }
                                ],
                                hiddenAssets: {},
                                fixedFrequency: {},
                                cashTimingPatterns: [],
                                holidayTransactions: {},
                                amountPatterns: {},
                            },
                            analysisResults: defaultData.analysisResults,
                            categorizedFiles: defaultData.categorizedFiles,
                        });

                        const ft = new Date();
                        const fts = `${ft.getHours().toString().padStart(2, '0')}:${ft.getMinutes().toString().padStart(2, '0')}:${ft.getSeconds().toString().padStart(2, '0')}`;
                        addLog({ time: fts, level: 'INFO', msg: '✓ 分析完成，共检测到 4 条可疑交易' });
                    }, 500);
                }
            }, (i + 1) * 800);
        });
    }, [addLog]);

    const stopAnalysis = useCallback(() => {
        setAnalysis(prev => ({
            ...prev,
            isRunning: false,
            status: 'failed',
            currentPhase: '分析已终止'
        }));

        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        addLog({ time: timeStr, level: 'WARN', msg: '■ 分析已被用户终止' });
    }, [addLog]);

    const updateAnalysisProgress = useCallback((progress: number, phase: string) => {
        setAnalysis(prev => ({ ...prev, progress, currentPhase: phase }));
    }, []);

    const setAnalysisStatus = useCallback((status: AnalysisState['status']) => {
        setAnalysis(prev => ({ ...prev, status, isRunning: status === 'running' }));
    }, []);

    // ==================== Data Actions ====================

    const updateData = useCallback((newData: Partial<DataState>) => {
        setData(prev => ({ ...prev, ...newData }));
    }, []);

    const resetData = useCallback(() => {
        setData(defaultData);
    }, []);

    // ==================== Log Actions ====================

    const clearLogs = useCallback(() => {
        setLogs([]);
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        setLogs([{ time: timeStr, level: 'INFO', msg: '日志已清除' }]);
    }, []);

    // ==================== UI Actions ====================

    const setActiveTab = useCallback((tab: TabType) => {
        setUI(prev => ({ ...prev, activeTab: tab }));
    }, []);

    const toggleSidebar = useCallback(() => {
        setUI(prev => ({ ...prev, sidebarCollapsed: !prev.sidebarCollapsed }));
    }, []);

    // ==================== Context Value ====================

    const value: AppContextType = {
        config,
        analysis,
        data,
        logs,
        ui,
        updateConfig,
        updateDataSources,
        updateThresholds,
        updateAnalysisModules,
        startAnalysis,
        stopAnalysis,
        updateAnalysisProgress,
        setAnalysisStatus,
        updateData,
        resetData,
        addLog,
        clearLogs,
        setActiveTab,
        toggleSidebar,
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// ==================== Hook ====================

export function useApp(): AppContextType {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error('useApp must be used within AppProvider');
    }
    return context;
}
