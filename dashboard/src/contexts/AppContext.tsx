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

// ==================== Storage Keys ====================
const STORAGE_KEYS = {
    INPUT_DIR: 'fpas_input_directory',
    OUTPUT_DIR: 'fpas_output_directory',
} as const;

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
    theme: 'dark',
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
    clearCache: () => Promise<void>;
    // Data actions
    updateData: (data: Partial<DataState>) => void;
    resetData: () => void;

    // Log actions
    addLog: (log: LogEntry) => void;
    clearLogs: () => void;

    // UI actions
    setActiveTab: (tab: TabType) => void;
    toggleSidebar: () => void;
    toggleTheme: () => void;
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
        setConfig(prev => {
            const newConfig = {
                ...prev,
                dataSources: { ...prev.dataSources, ...dataSources },
            };
            
            // 持久化到 localStorage
            if (dataSources.inputDirectory) {
                localStorage.setItem(STORAGE_KEYS.INPUT_DIR, dataSources.inputDirectory);
            }
            if (dataSources.outputDirectory) {
                localStorage.setItem(STORAGE_KEYS.OUTPUT_DIR, dataSources.outputDirectory);
            }
            
            return newConfig;
        });
    }, [])

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

        // 如果分析已在运行，先停止旧的
        if (analysis.isRunning) {
            addLog({ time: timeStr, level: 'WARN', msg: '检测到分析正在运行，正在停止...' });
            try {
                await api.stopAnalysis();
                // 等待一下让后端完全停止
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch (e) {
                // 停止失败时，不继续启动新分析，避免状态混乱
                addLog({ time: timeStr, level: 'ERROR', msg: '无法停止正在运行的分析，请稍后重试' });
                return; // 关键修复：停止失败时中止操作
            }
        }

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
                    currentPhase: '分析完成，正在加载数据...',
                }));

                // 添加短暂延迟确保后端数据保存完成，然后获取结果
                setTimeout(() => {
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

                            // 更新状态为完成
                            setAnalysis(prev => ({
                                ...prev,
                                currentPhase: '分析完成',
                            }));

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
                }, 500); // 500ms 延迟确保后端数据保存完成
            }
        });

        return () => {
            unsubscribe();
            ws.disconnect();
        };
    }, [addLog]);

    const stopAnalysis = useCallback(async () => {
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

        try {
            // 调用后端停止分析
            await api.stopAnalysis();
            addLog({ time: timeStr, level: 'WARN', msg: '■ 分析已被用户终止' });
        } catch (error) {
            addLog({ time: timeStr, level: 'WARN', msg: '■ 分析终止（后端可能已停止）' });
        }

        setAnalysis(prev => ({
            ...prev,
            isRunning: false,
            status: 'idle',
            progress: 0,
            currentPhase: '已就绪，可重新开始'
        }));
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

    const clearCache = useCallback(async () => {
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

        try {
            addLog({ time: timeStr, level: 'INFO', msg: '正在清除缓存...' });
            
            const result = await api.clearCache();
            
            if (result.success) {
                // 清空前端状态
                resetData();
                setAnalysis({
                    isRunning: false,
                    progress: 0,
                    currentPhase: '缓存已清除，等待开始分析',
                    lastRunTime: null,
                    status: 'idle',
                    isLoading: false,
                });
                
                addLog({ time: timeStr, level: 'INFO', msg: '✓ 缓存已清除（内存+目录）' });
            } else {
                addLog({ time: timeStr, level: 'ERROR', msg: `清除缓存失败: ${result.error || '未知错误'}` });
            }
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : '未知错误';
            addLog({ time: timeStr, level: 'ERROR', msg: `清除缓存失败: ${errorMsg}` });
        }
    }, [addLog, resetData]);

    // ==================== Log Actions ====================

    const clearLogs = useCallback(() => {
        setLogs([]);
        const now = new Date();
        const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        setLogs([{ time: timeStr, level: 'INFO', msg: '日志已清除' }]);
    }, []);

    // ==================== 初始化：检查后端缓存数据 ====================

    /**
     * 页面加载时自动检查后端状态，如果已有分析结果则自动恢复
     * 解决问题：刷新页面后需要重新分析的问题
     */
    useEffect(() => {
        const initializeFromBackend = async () => {
            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

            try {
                // 设置加载状态
                setAnalysis(prev => ({ ...prev, isLoading: true }));
                addLog({ time: timeStr, level: 'INFO', msg: '正在检查后端缓存数据...' });

                // 1. 获取后端状态
                const status = await api.getStatus();

                // 2. 如果后端已有完成的分析结果，加载它们
                if (status.status === 'completed') {
                    addLog({ time: timeStr, level: 'INFO', msg: '检测到后端缓存，正在恢复数据...' });

                    const result = await api.getResults();

                    if (result.data) {
                        // 安全合并后端数据与默认值
                        const backendData = result.data as any;

                        const safeSuspicions: SuspicionResult = {
                            directTransfers: backendData.suspicions?.directTransfers || [],
                            cashCollisions: backendData.suspicions?.cashCollisions || [],
                            hiddenAssets: backendData.suspicions?.hiddenAssets || {},
                            fixedFrequency: backendData.suspicions?.fixedFrequency || {},
                            cashTimingPatterns: backendData.suspicions?.cashTimingPatterns || [],
                            holidayTransactions: backendData.suspicions?.holidayTransactions || {},
                            amountPatterns: backendData.suspicions?.amountPatterns || {},
                        };

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

                        // 更新分析状态
                        setAnalysis({
                            isRunning: false,
                            progress: 100,
                            currentPhase: '从缓存恢复完成',
                            lastRunTime: status.endTime ? new Date(status.endTime) : null,
                            status: 'completed',
                            isLoading: false,
                        });

                        addLog({ time: timeStr, level: 'INFO', msg: `✓ 已从缓存恢复: ${backendData.persons?.length || 0} 人员, ${backendData.companies?.length || 0} 企业` });
                    }
                } else if (status.status === 'running') {
                    // 如果分析正在运行，连接 WebSocket 跟踪进度
                    setAnalysis({
                        isRunning: true,
                        progress: status.progress,
                        currentPhase: status.currentPhase,
                        lastRunTime: status.startTime ? new Date(status.startTime) : null,
                        status: 'running',
                        isLoading: false,
                    });
                    ws.connect();
                    addLog({ time: timeStr, level: 'INFO', msg: '检测到分析正在进行中，已连接实时日志...' });
                } else {
                    // idle 或 failed 状态
                    setAnalysis(prev => ({
                        ...prev,
                        status: status.status as AnalysisState['status'],
                        currentPhase: status.currentPhase || '等待开始分析',
                        isLoading: false,
                    }));
                    // 无论状态如何，都尝试连接 WebSocket 以显示正确的连接状态
                    ws.connect();
                    addLog({ time: timeStr, level: 'INFO', msg: '系统就绪，等待启动分析' });
                }
            } catch (error) {
                const errorMsg = error instanceof Error ? error.message : '未知错误';
                console.error('初始化失败:', error);
                // 初始化失败不阻塞用户操作
                setAnalysis(prev => ({ ...prev, isLoading: false }));
                addLog({ time: new Date().toLocaleTimeString(), level: 'WARN', msg: `后端连接失败: ${errorMsg}，请确保后端服务已启动` });
            }
        };

        initializeFromBackend();

        // 获取默认路径配置
        const fetchDefaultPaths = async () => {
            try {
                // 1. 首先检查 localStorage 是否有用户保存的路径
                const savedInputDir = localStorage.getItem(STORAGE_KEYS.INPUT_DIR);
                const savedOutputDir = localStorage.getItem(STORAGE_KEYS.OUTPUT_DIR);
                
                if (savedInputDir || savedOutputDir) {
                    // 使用用户保存的路径
                    setConfig(prev => ({
                        ...prev,
                        dataSources: {
                            inputDirectory: savedInputDir || prev.dataSources.inputDirectory,
                            outputDirectory: savedOutputDir || prev.dataSources.outputDirectory,
                        }
                    }));
                    addLog({ 
                        time: new Date().toLocaleTimeString(), 
                        level: 'INFO', 
                        msg: `已恢复用户设置路径: 输入=${savedInputDir || '默认'}, 输出=${savedOutputDir || '默认'}` 
                    });
                    return; // 有保存的路径，不再获取后端默认路径
                }
                
                // 2. 没有保存的路径，获取后端默认路径
                const result = await api.getDefaultPaths();
                if (result.success && result.data) {
                    // 更新默认路径为绝对路径
                    setConfig(prev => ({
                        ...prev,
                        dataSources: {
                            inputDirectory: result.data!.inputDirectory,
                            outputDirectory: result.data!.outputDirectory,
                        }
                    }));
                    addLog({ 
                        time: new Date().toLocaleTimeString(), 
                        level: 'INFO', 
                        msg: `已加载默认路径: 输入=${result.data.inputDirectory}, 输出=${result.data.outputDirectory}` 
                    });
                }
            } catch (error) {
                // 获取默认路径失败不影响主流程，保持原有默认值
                console.warn('获取默认路径失败:', error);
            }
        };

        fetchDefaultPaths();
    }, []); // 只在组件挂载时执行一次

    // ==================== UI Actions ====================

    const setActiveTab = useCallback((tab: TabType) => {
        setUI(prev => ({ ...prev, activeTab: tab }));
    }, []);

    const toggleSidebar = useCallback(() => {
        setUI(prev => ({ ...prev, sidebarCollapsed: !prev.sidebarCollapsed }));
    }, []);

    const toggleTheme = useCallback(() => {
        setUI(prev => {
            const newTheme = prev.theme === 'dark' ? 'light' : 'dark';
            // Apply theme class to document root
            document.documentElement.classList.remove('dark', 'light');
            document.documentElement.classList.add(newTheme);
            return { ...prev, theme: newTheme };
        });
    }, []);

    // Apply initial theme on mount
    useEffect(() => {
        document.documentElement.classList.add(ui.theme);
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
        clearCache,
        updateData,
        resetData,
        addLog,
        clearLogs,
        setActiveTab,
        toggleSidebar,
        toggleTheme,
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
