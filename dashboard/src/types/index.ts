// ==================== Core Types ====================

export type LogLevel = 'INFO' | 'WARN' | 'ERROR';

export interface LogEntry {
    time: string;
    level: LogLevel;
    msg: string;
}

export type AnalysisStatus = 'idle' | 'running' | 'completed' | 'failed';

// ==================== Configuration Types ====================

export interface DataSourceConfig {
    inputDirectory: string;
    outputDirectory: string;
}

export interface ThresholdConfig {
    cashThreshold: number;
    timeWindow: number;
}

export interface AnalysisModules {
    profileAnalysis: boolean;
    suspicionDetection: boolean;
    assetAnalysis: boolean;
    dataValidation: boolean;
    fundPenetration: boolean;
    relatedParty: boolean;
    multiSourceCorrelation: boolean;
    loanAnalysis: boolean;
    incomeAnalysis: boolean;
    flowVisualization: boolean;
    mlAnalysis: boolean;
    timeSeriesAnalysis: boolean;
    clueAggregation: boolean;
}

export interface AppConfig {
    dataSources: DataSourceConfig;
    thresholds: ThresholdConfig;
    analysisModules: AnalysisModules;
}

// ==================== Analysis Types ====================

export interface AnalysisState {
    isRunning: boolean;
    progress: number;
    currentPhase: string;
    lastRunTime: Date | null;
    status: AnalysisStatus;
    isLoading?: boolean; // 数据加载状态
}

export interface Profile {
    entityName: string;
    totalIncome: number;
    totalExpense: number;
    transactionCount: number;
    accountAnalysisText?: string;
    wealthAccountAnalysis?: any;
    wealthAccountReport?: string;
}

export interface SuspicionResult {
    directTransfers: SuspiciousTransaction[];
    cashCollisions: CashCollision[];
    hiddenAssets: Record<string, HiddenAsset[]>;
    fixedFrequency: Record<string, FixedFrequency[]>;
    cashTimingPatterns: CashTimingPattern[];
    holidayTransactions: Record<string, HolidayTransaction[]>;
    amountPatterns: Record<string, AmountPattern[]>;
}

export interface SuspiciousTransaction {
    from: string;
    to: string;
    amount: number;
    date: string;
    description?: string;
}

export interface CashCollision {
    person1: string;
    person2: string;
    time1: string;
    time2: string;
    amount1: number;
    amount2: number;
    location1?: string;
    location2?: string;
}

export interface HiddenAsset {
    date: string;
    amount: number;
    description: string;
    counterparty: string;
}

export interface FixedFrequency {
    pattern: string;
    count: number;
    totalAmount: number;
    transactions: Array<{
        date: string;
        amount: number;
    }>;
}

export interface CashTimingPattern {
    person1: string;
    person2: string;
    time1: string;
    time2: string;
    amount1: number;
    amount2: number;
    timeDiff: number;
}

export interface HolidayTransaction {
    date: string;
    amount: number;
    description: string;
    holidayName: string;
}

export interface AmountPattern {
    pattern: string;
    count: number;
    totalAmount: number;
    riskLevel: 'low' | 'medium' | 'high';
}

export interface AnalysisResults {
    loan: LoanResult;
    income: IncomeResult;
    ml: MLResult;
    penetration: PenetrationResult;
    relatedParty: RelatedPartyResult;
    correlation: CorrelationResult;
    timeSeries: TimeSeriesResult;
    aggregation: AggregationResult;
}

export interface LoanResult {
    summary: {
        双向往来关系数: number;
        网贷平台交易数: number;
        规律还款模式数: number;
    };
    details: any[];
}

export interface IncomeResult {
    summary: {
        规律性非工资收入: number;
        个人大额转入: number;
        来源不明收入: number;
    };
    details: any[];
}

export interface MLResult {
    summary: {
        anomalyCount: number;
        highRiskCount: number;
    };
    predictions: any[];
}

export interface PenetrationResult {
    summary: {
        资金穿透链数: number;
        中间节点数: number;
    };
    chains: any[];
}

export interface RelatedPartyResult {
    summary: {
        直接往来笔数: number;
        第三方中转链数: number;
        资金闭环数: number;
    };
    details: any[];
}

export interface CorrelationResult {
    summary: {
        资金碰撞总数: number;
    };
    correlations: any[];
}

export interface TimeSeriesResult {
    summary: {
        异常时间点数: number;
    };
    anomalies: any[];
}

export interface AggregationResult {
    rankedEntities: RankedEntity[];
    summary: {
        极高风险实体数: number;
        高风险实体数: number;
    };
}

export interface RankedEntity {
    name: string;
    riskLevel: 'critical' | 'high' | 'medium' | 'low';
    riskScore: number;
    reasons: string[];
}

// ==================== Data Types ====================

export interface DataState {
    persons: string[];
    companies: string[];
    profiles: Record<string, Profile>;
    suspicions: SuspicionResult;
    analysisResults: AnalysisResults;
    categorizedFiles: CategorizedFiles;
}

export interface CategorizedFiles {
    persons: Record<string, string[]>;
    companies: Record<string, string[]>;
    transactionFiles: string[];
}

// ==================== UI Types ====================

export type TabType = 'overview' | 'risk' | 'graph' | 'report';

export interface UIState {
    activeTab: TabType;
    sidebarCollapsed: boolean;
}

// ==================== App State ====================

export interface AppState {
    config: AppConfig;
    analysis: AnalysisState;
    data: DataState;
    logs: LogEntry[];
    ui: UIState;
}

// ==================== API Types ====================

export interface StartAnalysisRequest {
    inputDirectory: string;
    outputDirectory: string;
    cashThreshold: number;
    timeWindow: number;
    analysisModules: AnalysisModules;
}

export interface StartAnalysisResponse {
    analysisId: string;
    status: 'started';
}

export interface AnalysisStatusResponse {
    status: AnalysisStatus;
    progress: number;
    currentPhase: string;
}

export interface AnalysisResultsResponse {
    persons: string[];
    companies: string[];
    profiles: Record<string, Profile>;
    suspicions: SuspicionResult;
    analysisResults: AnalysisResults;
}

// ==================== Component Props Types ====================

export interface StatsCardProps {
    label: string;
    value: string | number;
    icon: React.ComponentType<{ className?: string }>;
    color: string;
    isStatus?: boolean;
}

export interface LogConsoleProps {
    logs: LogEntry[];
}

export interface SidebarProps {
    config: AppConfig;
    analysis: AnalysisState;
    onConfigChange: (config: Partial<AppConfig>) => void;
    onStartAnalysis: () => void;
}

export interface TabContentProps {
    data: DataState;
}

export interface KPICardsProps {
    data: DataState;
}

// ==================== Chart Data Types ====================

export interface ChartDataPoint {
    name: string;
    value: number;
    risk?: number;
}

export interface FundDistributionData {
    entity: string;
    income: number;
    expense: number;
}

export interface TransactionTrendData {
    date: string;
    volume: number;
}

export interface RiskDistributionData {
    category: string;
    count: number;
}
