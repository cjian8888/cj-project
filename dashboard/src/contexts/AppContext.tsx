import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode } from 'react';
import type {
    AppState,
    AppConfig,
    AnalysisState,
    DataState,
    LogEntry,
    UIState,
    TabType,
    SuspicionResult,
    AnalysisResults as AppAnalysisResults,
} from '../types';
import { api, ws } from '../services/api';
import type { AnalysisStatus, WebSocketMessage } from '../services/api';

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
    isLoading: false, // 数据加载状态
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

    const startAnalysis = useCallback(async () => {
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

        try {
            // 将 AnalysisModules 转换为 Record<string, boolean>
            const modules: Record<string, boolean> = config.analysisModules as unknown as Record<string, boolean>;

            // 调用后端 API 启动分析
            await api.startAnalysis({
                inputDirectory: config.dataSources.inputDirectory,
                outputDirectory: config.dataSources.outputDirectory,
                cashThreshold: config.thresholds.cashThreshold,
                timeWindow: config.thresholds.timeWindow,
                modules: modules,
            });

            setAnalysis({
                isRunning: true,
                progress: 0,
                currentPhase: '初始化分析引擎...',
                lastRunTime: now,
                status: 'running',
                isLoading: false,
            });

            addLog({ time: timeStr, level: 'INFO', msg: '▶ 分析引擎已启动' });

            // 启动 WebSocket 连接接收实时日志
            ws.connect();

        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : '未知错误';
            addLog({ time: timeStr, level: 'ERROR', msg: `启动失败: ${errorMsg}` });
            setAnalysis(prev => ({
                ...prev,
                isRunning: false,
                status: 'failed',
                currentPhase: `启动失败: ${errorMsg}`,
                isLoading: false,
            }));
        }
    }, [config, addLog]);

    // WebSocket 消息处理
    useEffect(() => {
        const unsubscribe = ws.subscribe((message: WebSocketMessage) => {
            if (message.type === 'log') {
                const logEntry = message.data as LogEntry;
                addLog(logEntry);
            } else if (message.type === 'status') {
                const status = message.data as AnalysisStatus;
                setAnalysis(prev => ({
                    ...prev,
                    progress: status.progress,
                    currentPhase: status.currentPhase,
                    status: status.status as AnalysisState['status'],
                }));
            } else if (message.type === 'complete') {
                // 分析完成，先更新状态
                setAnalysis(prev => ({
                    ...prev,
                    isRunning: false,
                    progress: 100,
                    status: 'completed',
                    currentPhase: '分析完成',
                }));

                // 然后获取结果
                api.getResults().then(result => {
                    if (result.data) {
                        // 安全合并后端数据与默认值，防止缺失字段导致前端崩溃
                        const backendData = result.data as any;

                        // 合并 suspicions，确保所有字段都有默认值
                        const safeSuspicions: SuspicionResult = {
                            directTransfers: backendData.suspicions?.directTransfers || [],
                            cashCollisions: backendData.suspicions?.cashCollisions || [],
                            hiddenAssets: backendData.suspicions?.hiddenAssets || {},
                            fixedFrequency: backendData.suspicions?.fixedFrequency || {},
                            cashTimingPatterns: backendData.suspicions?.cashTimingPatterns || [],
                            holidayTransactions: backendData.suspicions?.holidayTransactions || {},
                            amountPatterns: backendData.suspicions?.amountPatterns || {},
                        };

                        // 合并 analysisResults，确保所有模块都有默认结构
                        const ar = backendData.analysisResults || {};
                        const safeAnalysisResults: AppAnalysisResults = {
                            loan: {
                                summary: { 双向往来关系数: 0, 网贷平台交易数: 0, 规律还款模式数: 0, ...ar.loan?.summary },
                                details: ar.loan?.details || [],
                            },
                            income: {
                                summary: { 规律性非工资收入: 0, 个人大额转入: 0, 来源不明收入: 0, ...ar.income?.summary },
                                details: ar.income?.details || [],
                            },
                            ml: {
                                summary: { anomalyCount: 0, highRiskCount: 0, ...ar.ml?.summary },
                                predictions: ar.ml?.predictions || [],
                            },
                            penetration: {
                                summary: { 资金穿透链数: 0, 中间节点数: 0, ...ar.penetration?.summary },
                                chains: ar.penetration?.chains || [],
                            },
                            relatedParty: {
                                summary: { 直接往来笔数: 0, 第三方中转链数: 0, 资金闭环数: 0, ...ar.relatedParty?.summary },
                                details: ar.relatedParty?.details || [],
                            },
                            correlation: {
                                summary: { 资金碰撞总数: 0, ...ar.correlation?.summary },
                                correlations: ar.correlation?.correlations || [],
                            },
                            timeSeries: {
                                summary: { 异常时间点数: 0, ...ar.timeSeries?.summary },
                                anomalies: ar.timeSeries?.anomalies || [],
                            },
                            aggregation: {
                                rankedEntities: ar.aggregation?.rankedEntities || [],
                                summary: { 极高风险实体数: 0, 高风险实体数: 0, ...ar.aggregation?.summary },
                            },
                        };

                        setData({
                            persons: backendData.persons || [],
                            companies: backendData.companies || [],
                            profiles: backendData.profiles || {},
                            suspicions: safeSuspicions,
                            analysisResults: safeAnalysisResults,
                            categorizedFiles: defaultData.categorizedFiles,
                        });

                        // 添加完成日志
                        const now = new Date();
                        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
                        addLog({ time: timeStr, level: 'INFO', msg: '✓ 分析完成，数据已加载' });
                    }
                }).catch(error => {
                    console.error('获取分析结果失败:', error);
                    const errorMsg = error instanceof Error ? error.message : '未知错误';
                    const now = new Date();
                    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
                    addLog({ time: timeStr, level: 'ERROR', msg: `获取结果失败: ${errorMsg}` });
                    
                    // 更新状态为失败
                    setAnalysis(prev => ({
                        ...prev,
                        isRunning: false,
                        status: 'failed',
                        currentPhase: `获取结果失败: ${errorMsg}`
                    }));
                });
            }
        });

        return () => {
            unsubscribe();
            ws.disconnect();
        };
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
