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
    fundPenetration: boolean;
    relatedParty: boolean;
    multiSourceCorrelation: boolean;
    loanAnalysis: boolean;
    incomeAnalysis: boolean;
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
    // 新增审计关键字段（对应后端 serialize_profiles 扩展）
    cashTotal?: number;        // 现金交易总额（取现+存现）
    thirdPartyTotal?: number;  // 第三方支付交易总额
    wealthTotal?: number;      // 理财产品交易总额
    maxTransaction?: number;   // 最大单笔交易金额
    salaryRatio?: number;      // 工资收入占比
    // 旧字段保留向后兼容
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
    // 新增审计关键字段（对应后端 serialize_suspicions 扩展）
    direction?: string;     // 交易方向 (payment/receive/突变/延迟转账等)
    bank?: string;          // 银行来源
    sourceFile?: string;    // 数据来源文件
    riskLevel?: string;     // 风险等级
    riskReason?: string;    // 风险原因
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
    // 新增后端返回的字段
    timeDiff?: number;
    riskLevel?: string;
    riskReason?: string;
    withdrawalBank?: string;
    depositBank?: string;
    withdrawalSource?: string;
    depositSource?: string;
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
    fund_cycles?: FundCycle[];
    analysis_metadata?: {
        fund_cycles?: AnalysisMetadata;
        pass_through_channels?: Record<string, unknown>;
    };
}

export interface FundCycle {
    path?: string;
    nodes?: string[];
    participants?: string[];
    length?: number;
    total_amount?: number;
    risk_score?: number;
    risk_level?: string;
    confidence?: number;
    evidence?: string[];
}

export interface DiscoveredNode {
    name: string;
    node_type?: string;
    occurrences?: number;
    relation_types?: string[];
    linked_cores?: string[];
    total_amount?: number;
    risk_score?: number;
    risk_level?: string;
    confidence?: number;
    evidence?: string[];
}

export interface RelationshipCluster {
    cluster_id: string;
    core_members: string[];
    external_members: string[];
    all_nodes?: string[];
    relation_types?: string[];
    direct_flow_count?: number;
    relay_count?: number;
    loop_count?: number;
    total_amount?: number;
    risk_score?: number;
    risk_level?: string;
    confidence?: number;
    evidence?: string[];
}

export interface AnalysisMetadata {
    timed_out?: boolean;
    search_node_truncated?: boolean;
    cycle_limit_hit?: boolean;
    truncated?: boolean;
    truncated_reasons?: string[];
    requested_start_nodes?: number;
    searched_start_nodes?: number;
    returned_count?: number;
    raw_count?: number;
    timeout_seconds?: number;
    max_cycles?: number;
}

export interface RelatedPartyResult {
    summary: {
        直接往来笔数: number;
        第三方中转链数: number;
        资金闭环数: number;
        外围节点数?: number;
        关系簇数?: number;
    };
    details: any[];
    direct_flows?: any[];
    third_party_relays?: any[];
    fund_loops?: FundCycle[];
    discovered_nodes?: DiscoveredNode[];
    relationship_clusters?: RelationshipCluster[];
    analysis_metadata?: {
        fund_loops?: AnalysisMetadata;
        third_party_relays?: Record<string, unknown>;
    };
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
        中风险实体数?: number;
        风险实体总数?: number;
        高优先线索实体数?: number;
    };
    evidencePacks?: Record<string, AggregationEvidencePack>;
    analysisMetadata?: Record<string, unknown>;
}

export interface RankedEntity {
    name: string;
    riskLevel: 'critical' | 'high' | 'medium' | 'low';
    riskScore: number;
    reasons: string[];
    entity?: string;
    entityType?: 'person' | 'company';
    summary?: string;
    evidenceCount?: number;
    riskConfidence?: number;
    topEvidenceScore?: number;
    highPriorityClueCount?: number;
    aggregationExplainability?: {
        model_confidence?: number;
        average_evidence_confidence?: number;
        max_evidence_confidence?: number;
        scored_clue_count?: number;
        evidence_bucket_counts?: Record<string, number>;
        top_clues?: Array<{
            bucket?: string;
            risk_score?: number;
            confidence?: number;
            description?: string;
            evidence?: string[];
        }>;
    };
}

export interface AggregationEvidencePack {
    risk_score: number;
    risk_level: 'critical' | 'high' | 'medium' | 'low';
    risk_confidence?: number;
    top_evidence_score?: number;
    high_priority_clue_count?: number;
    summary?: string;
    evidence: Record<string, any[]>;
    statistics?: Record<string, number>;
    aggregation_explainability?: Record<string, unknown>;
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

export type ThemeType = 'dark' | 'light';

export interface UIState {
    activeTab: TabType;
    sidebarCollapsed: boolean;
    theme: ThemeType;
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
