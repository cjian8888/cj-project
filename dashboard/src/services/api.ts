/**
 * API 服务 - 与 FastAPI 后端通信
 */

import type { ReportPackage } from '../types';

function isLoopbackHost(hostname: string): boolean {
    return hostname === 'localhost' || hostname === '127.0.0.1';
}

function normalizeLoopbackUrl(rawUrl: string): string {
    if (typeof window === 'undefined') {
        return rawUrl;
    }

    try {
        const parsed = new URL(rawUrl);
        const currentHostname = window.location.hostname;
        if (isLoopbackHost(parsed.hostname) && isLoopbackHost(currentHostname)) {
            parsed.hostname = currentHostname;
            return parsed.toString().replace(/\/$/, '');
        }
    } catch {
        return rawUrl;
    }

    return rawUrl;
}

function getDefaultApiBaseUrl(): string {
    if (typeof window === 'undefined') {
        return 'http://localhost:8000';
    }

    const { protocol, hostname, port } = window.location;
    if (port === '8000') {
        return '';
    }
    return `${protocol}//${hostname}:8000`;
}

function resolveApiBaseUrl(): string {
    const envValue = String(import.meta.env.VITE_API_URL || '').trim();
    if (typeof window !== 'undefined' && window.location.port === '8000') {
        return '';
    }
    if (!envValue) {
        return getDefaultApiBaseUrl();
    }
    return normalizeLoopbackUrl(envValue);
}

function getDefaultWsUrl(): string {
    if (typeof window === 'undefined') {
        return 'ws://localhost:8000/ws';
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    if (window.location.port === '8000') {
        return `${protocol}//${window.location.host}/ws`;
    }
    return `${protocol}//${window.location.hostname}:8000/ws`;
}

function resolveWsUrl(): string {
    const envValue = String(import.meta.env.VITE_WS_URL || '').trim();
    if (typeof window !== 'undefined' && window.location.port === '8000') {
        return getDefaultWsUrl();
    }
    if (!envValue) {
        return getDefaultWsUrl();
    }
    return normalizeLoopbackUrl(envValue);
}

export const API_BASE_URL = resolveApiBaseUrl();
const WS_URL = resolveWsUrl();

// ==================== Types ====================

export interface AnalysisConfig {
    inputDirectory: string;
    outputDirectory: string;
    cashThreshold: number;
    timeWindow: number;
    modules: Record<string, boolean>;
}

export interface AnalysisStatus {
    status: 'idle' | 'running' | 'completed' | 'failed';
    progress: number;
    currentPhase: string;
    phase?: string; // 兼容后端旧字段
    startTime: string | null;
    endTime: string | null;
}

export interface Profile {
    entityName: string;
    totalIncome: number;
    totalExpense: number;
    transactionCount: number;
    cashTotal?: number;
    maxTransaction?: number;
    realIncome?: number;
    realExpense?: number;
    thirdPartyTotal?: number;
    wealthTotal?: number;
    wealthTransactionCount?: number;
}

export interface SuspiciousTransaction {
    from: string;
    to: string;
    amount: number;
    date: string;
    description?: string;
    direction?: string;
    bank?: string;
    sourceFile?: string;
    sourceRowIndex?: number;
    transactionId?: string;
    riskLevel?: string;
    riskReason?: string;
}

export interface CashCollision {
    person1: string;
    person2: string;
    time1: string;
    time2: string;
    amount1: number;
    amount2: number;
}

export interface WalletAlert {
    person: string;
    counterparty: string;
    amount: number;
    date: string;
    description?: string;
    riskLevel?: string;
    riskReason?: string;
    alertType?: string;
    riskScore?: number;
    confidence?: number;
    ruleCode?: string;
    evidenceSummary?: string;
}

export interface AmlAlert {
    name?: string;
    personId?: string;
    person_id?: string;
    alertType?: string;
    alert_type?: string;
    paymentAccountCount?: number;
    payment_account_count?: number;
    paymentTransactionCount?: number;
    payment_transaction_count?: number;
    suspiciousTransactionCount?: number;
    suspicious_transaction_count?: number;
    largeTransactionCount?: number;
    large_transaction_count?: number;
    source?: string;
    riskLevel?: string;
    riskReason?: string;
}

export interface CreditAlert {
    name?: string;
    alertType?: string;
    alert_type?: string;
    count?: number;
    source?: string;
    riskLevel?: string;
    riskReason?: string;
}

export interface TimeSeriesAlert {
    name?: string;
    person?: string;
    entity?: string;
    counterparty?: string;
    date?: string;
    timestamp?: string;
    amount?: number | null;
    description?: string;
    alertType?: string;
    alert_type?: string;
    riskLevel?: string;
    risk_level?: string;
    riskReason?: string;
    risk_reason?: string;
    anomalyType?: string;
    anomaly_type?: string;
}

export interface Suspicions {
    directTransfers: SuspiciousTransaction[];
    cashCollisions: CashCollision[];
    hiddenAssets: Record<string, unknown>;
    fixedFrequency: Record<string, unknown>;
    cashTimingPatterns: unknown[];
    holidayTransactions: Record<string, unknown>;
    amountPatterns: Record<string, unknown>;
    amlAlerts: AmlAlert[];
    creditAlerts: CreditAlert[];
    timeSeriesAlerts: TimeSeriesAlert[];
    walletAlerts: WalletAlert[];
}

export interface AnalysisResults {
    persons: string[];
    companies: string[];
    profiles: Record<string, Profile>;
    suspicions: Suspicions;
    analysisResults: Record<string, unknown>;
    reportPackage?: ReportPackage | null;
    walletData?: Record<string, unknown>;
}

export interface ReportSemanticHighlight {
    title: string;
    summary?: string;
}

export interface ReportSemanticSection {
    headline?: string;
    badges?: string[];
    highlights?: ReportSemanticHighlight[];
    issueCount?: number;
    highRiskIssueCount?: number;
    topPriorityEntities?: string[];
    appendixCount?: number;
    failCount?: number;
    warnCount?: number;
    passCount?: number;
    totalCount?: number;
    familyCount?: number;
    personCount?: number;
    companyCount?: number;
}

export interface ReportSemanticOverview {
    mainReport?: ReportSemanticSection;
    appendices?: ReportSemanticSection;
    qa?: ReportSemanticSection;
    dossiers?: ReportSemanticSection;
}

export interface Report {
    name: string;
    path?: string;
    size: number;
    modified: string;
    filename?: string;
    type?: string;
    extension?: string;
    groupKey?: string;
    groupLabel?: string;
    groupOrder?: number;
    isPreviewable?: boolean;
    semanticTitle?: string;
    semanticSummary?: string;
    semanticBadges?: string[];
    semanticRank?: number;
}

export interface ReportGroup {
    key: string;
    label: string;
    description: string;
    order: number;
    count: number;
    items: Report[];
    semanticHeadline?: string;
    semanticBadges?: string[];
    semanticHighlights?: ReportSemanticHighlight[];
}

export interface ReportManifestResponse {
    success: boolean;
    reports: Report[];
    groups: ReportGroup[];
    semanticOverview?: ReportSemanticOverview;
    totals: {
        reportCount: number;
        groupCount: number;
    };
    message?: string;
    error?: string;
}

export interface LogEntry {
    time: string;
    level: 'INFO' | 'WARN' | 'ERROR';
    msg: string;
}

export interface WebSocketMessage {
    type: 'log' | 'status' | 'complete';
    data: LogEntry | AnalysisStatus;
}

export interface AnalysisLogHistoryResponse {
    message: string;
    data: {
        logs: LogEntry[];
        stats: {
            info: number;
            warn: number;
            error: number;
        };
        path: string;
        source: string;
    };
}

// ==================== HTTP API ====================

class ApiService {
    private baseUrl: string;
    private timeout: number = 60000; // 60秒超时
    private maxRetries: number = 3;
    private retryDelay: number = 1000; // 1秒

    constructor(baseUrl: string = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    public get baseURL(): string {
        return this.baseUrl;
    }

    /**
     * 检查网络连接状态
     */
    isOnline(): boolean {
        return navigator.onLine;
    }

    /**
     * 带超时的 fetch 请求
     */
    private async fetchWithTimeout(
        url: string,
        options: RequestInit = {},
        timeout: number = this.timeout
    ): Promise<Response> {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
            });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error instanceof Error && error.name === 'AbortError') {
                throw new Error('请求超时,请检查网络连接或稍后重试');
            }
            throw error;
        }
    }

    /**
     * 带重试机制的请求
     */
    private async requestWithRetry<T>(
        endpoint: string,
        options: RequestInit = {},
        retries: number = this.maxRetries
    ): Promise<T> {
        // 检查网络连接
        if (!this.isOnline()) {
            throw new Error('网络连接已断开,请检查网络设置');
        }

        const url = `${this.baseUrl}${endpoint}`;

        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const response = await this.fetchWithTimeout(url, {
                    ...options,
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers,
                    },
                });

                if (!response.ok) {
                    // 对于 4xx 错误,不重试
                    if (response.status >= 400 && response.status < 500) {
                        const error = await response.json().catch(() => ({ detail: '请求失败' }));
                        throw new Error(this.getErrorMessage(response.status, error.detail));
                    }

                    // 对于 5xx 错误,可以重试
                    if (attempt < retries) {
                        await this.delay(this.retryDelay * Math.pow(2, attempt));
                        continue;
                    }

                    const error = await response.json().catch(() => ({ detail: '服务器错误' }));
                    throw new Error(this.getErrorMessage(response.status, error.detail));
                }

                return response.json();
            } catch (error) {
                // 如果是最后一次尝试,抛出错误
                if (attempt === retries) {
                    if (error instanceof Error) {
                        throw error;
                    }
                    throw new Error('网络请求失败,请稍后重试');
                }

                // 否则等待后重试
                await this.delay(this.retryDelay * Math.pow(2, attempt));
            }
        }

        throw new Error('请求失败,已达到最大重试次数');
    }

    /**
     * 延迟函数
     */
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * 获取用户友好的错误消息
     */
    private getErrorMessage(status: number, detail: string): string {
        switch (status) {
            case 400:
                return `请求参数错误: ${detail}`;
            case 401:
                return '未授权,请重新登录';
            case 403:
                return '没有权限访问此资源';
            case 404:
                return '请求的资源不存在';
            case 409:
                return `操作冲突: ${detail}`;
            case 500:
                return '服务器内部错误,请稍后重试';
            case 502:
                return '网关错误,服务暂时不可用';
            case 503:
                return '服务暂时不可用,请稍后重试';
            default:
                return detail || `请求失败 (HTTP ${status})`;
        }
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        return this.requestWithRetry<T>(endpoint, options);
    }

    /**
     * 获取 API 健康状态
     */
    async getHealth(): Promise<{ message: string; status: string }> {
        return this.request('/');
    }

    /**
     * 获取分析状态
     */
    async getStatus(): Promise<AnalysisStatus> {
        return this.request('/api/status');
    }

    /**
     * 启动分析
     */
    async startAnalysis(config: AnalysisConfig): Promise<{ message: string; status: string }> {
        return this.request('/api/analysis/start', {
            method: 'POST',
            body: JSON.stringify(config),
        });
    }

    /**
     * 停止分析
     */
    async stopAnalysis(): Promise<{ message: string; status: string }> {
        return this.request('/api/analysis/stop', {
            method: 'POST',
        });
    }

    /**
     * 获取分析结果
     */
    async getResults(): Promise<{ message: string; data: AnalysisResults | null }> {
        return this.request('/api/results');
    }

    /**
     * 获取最近一次分析的历史日志，用于恢复日志控制台
     */
    async getAnalysisLogHistory(limit: number = 200): Promise<AnalysisLogHistoryResponse> {
        return this.request(`/api/analysis/log-history?limit=${encodeURIComponent(String(limit))}`);
    }

    /**
     * 获取报告列表
     */
    async getReports(): Promise<{ reports: Report[] }> {
        return this.request('/api/reports');
    }

    /**
     * 获取报告中心分组清单
     */
    async getReportManifest(): Promise<ReportManifestResponse> {
        return this.request('/api/reports/manifest');
    }

    /**
     * 下载报告
     */
    async downloadReport(filename: string): Promise<Blob> {
        const url = `${this.baseUrl}/api/reports/download/${encodeURIComponent(filename)}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`下载失败: ${response.status}`);
        }

        return response.blob();
    }

    /**
     * 预览报告（txt/html文件）
     */
    async previewReport(filename: string): Promise<{ success: boolean; filename: string; type?: string; content?: string }> {
        const url = `${this.baseUrl}/api/reports/preview/${encodeURIComponent(filename)}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`预览失败: ${response.status}`);
        }

        const contentType = response.headers.get('content-type') || '';

        if (contentType.includes('text/html')) {
            const content = await response.text();
            return {
                success: true,
                filename,
                type: 'html',
                content,
            };
        }

        return response.json();
    }

    /**
     * 获取缓存信息
     */
    async getCacheInfo(): Promise<{
        success: boolean;
        data?: {
            cacheDir: string;
            cacheVersion: string;
            files: Record<string, {
                exists: boolean;
                size?: number;
                modified?: string;
                valid?: boolean;
            }>;
        };
        error?: string;
    }> {
        return this.request('/api/cache/info');
    }

    /**
     * 清除缓存（主动触发重新分析前调用）
     */
    async invalidateCache(): Promise<{ message: string; status: string }> {
        return this.request('/api/cache/invalidate', {
            method: 'POST',
        });
    }

    /**
     * 清空所有缓存（内存+目录）
     * 用于用户想彻底清空数据重新开始
     */
    async clearCache(): Promise<{ success: boolean; message?: string; error?: string }> {
        return this.request('/api/cache/clear', {
            method: 'POST',
        });
    }


    /**
     * 获取默认路径配置
     */
    async getDefaultPaths(): Promise<{
        success: boolean;
        data?: {
            inputDirectory: string;
            outputDirectory: string;
            projectRoot: string;
        };
        error?: string;
    }> {
        return this.request('/api/default-paths');
    }

    /**
     * 同步当前活动输入/输出目录，并尝试恢复该输出目录下的缓存结果
     */
    async syncActivePaths(dataSources: Partial<Pick<AnalysisConfig, 'inputDirectory' | 'outputDirectory'>>): Promise<{
        success: boolean;
        data?: {
            inputDirectory: string;
            outputDirectory: string;
            cacheRestored: boolean;
            status: AnalysisStatus['status'];
        };
    }> {
        return this.request('/api/active-paths', {
            method: 'POST',
            body: JSON.stringify(dataSources),
        });
    }

    /**
     * 弹出目录选择对话框
     */
    async selectDirectory(type: 'input' | 'output', currentPath?: string): Promise<{
        success: boolean;
        path?: string;
        error?: string;
    }> {
        return this.request('/api/select-directory', {
            method: 'POST',
            body: JSON.stringify({
                type,
                current_path: currentPath,
            }),
        });
    }
}

// ==================== WebSocket Service ====================

type WebSocketCallback = (message: WebSocketMessage) => void;

class WebSocketService {
    private ws: WebSocket | null = null;
    private url: string;
    private callbacks: Set<WebSocketCallback> = new Set();
    private statusCallbacks: Set<(status: 'connecting' | 'connected' | 'disconnected' | 'error') => void> = new Set();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 3000; // 3秒基础延迟
    private _status: 'connecting' | 'connected' | 'disconnected' | 'error' = 'disconnected';

    constructor(url: string = WS_URL) {
        this.url = url;
    }

    /**
     * 获取当前连接状态
     */
    get status(): 'connecting' | 'connected' | 'disconnected' | 'error' {
        return this._status;
    }

    /**
     * 更新状态并通知订阅者
     */
    private setStatus(status: 'connecting' | 'connected' | 'disconnected' | 'error'): void {
        this._status = status;
        this.statusCallbacks.forEach(cb => cb(status));
    }

    /**
     * 订阅连接状态变化
     */
    subscribeStatus(callback: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void): () => void {
        this.statusCallbacks.add(callback);
        // 立即通知当前状态
        callback(this._status);
        return () => this.statusCallbacks.delete(callback);
    }

    /**
     * 连接 WebSocket
     */
    connect(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            return;
        }

        this.setStatus('connecting');

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('[WS] Connected');
                this.reconnectAttempts = 0;
                this.setStatus('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data);
                    this.callbacks.forEach(cb => cb(message));
                } catch (e) {
                    console.error('[WS] Parse error:', e);
                }
            };

            this.ws.onclose = () => {
                console.log('[WS] Disconnected');
                this.setStatus('disconnected');
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[WS] Error:', error);
                this.setStatus('error');
            };
        } catch (error) {
            console.error('[WS] Connection failed:', error);
            this.setStatus('error');
            this.attemptReconnect();
        }
    }

    /**
     * 断开连接
     */
    disconnect(): void {
        this.reconnectAttempts = this.maxReconnectAttempts; // 阻止自动重连
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.setStatus('disconnected');
    }

    /**
     * 手动重连
     */
    reconnect(): void {
        this.reconnectAttempts = 0;
        this.disconnect();
        setTimeout(() => this.connect(), 100);
    }

    /**
     * 订阅消息
     */
    subscribe(callback: WebSocketCallback): () => void {
        this.callbacks.add(callback);
        return () => this.callbacks.delete(callback);
    }

    /**
     * 发送消息
     */
    send(message: string): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(message);
        }
    }

    /**
     * 尝试重连 (指数退避，3秒起始，最多5次)
     */
    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WS] Max reconnect attempts reached');
            this.setStatus('error');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.setStatus('connecting');

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * 检查连接状态
     */
    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}

// ==================== 导出单例 ====================

export const api = new ApiService();
export const ws = new WebSocketService();

export default api;
