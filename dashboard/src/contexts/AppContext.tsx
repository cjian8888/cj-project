import React, { createContext, useContext, useState, useCallback } from 'react';
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
    sidebarCollapsed: false,
};

const initialLogs: LogEntry[] = [
    { time: '09:00:01', level: 'INFO', msg: 'System initialized successfully. Version 2.4.0' },
    { time: '09:00:02', level: 'INFO', msg: 'Connected to secure data warehouse (Node A-7)' },
    { time: '09:00:05', level: 'INFO', msg: 'Loading entity relationships...' },
    { time: '09:00:08', level: 'WARN', msg: 'Latency detected in data stream (24ms)' },
    { time: '09:00:12', level: 'INFO', msg: 'Entity indexing complete. 1,248 nodes active.' },
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

    const startAnalysis = useCallback(() => {
        setAnalysis({
            isRunning: true,
            progress: 0,
            currentPhase: 'Initializing...',
            lastRunTime: new Date(),
            status: 'running',
        });

        // Add start log
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        setLogs(prev => [...prev, { time: timeStr, level: 'INFO', msg: '>>> ENGINE STARTED: Full Analysis Sequence Initiated <<<' }]);
    }, []);

    const stopAnalysis = useCallback(() => {
        setAnalysis(prev => ({ ...prev, isRunning: false, status: 'failed' }));
    }, []);

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

    const clearLogs = useCallback(() => {
        setLogs([]);
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
