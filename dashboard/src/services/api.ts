/**
 * API 服务 - 与 FastAPI 后端通信
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

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
    startTime: string | null;
    endTime: string | null;
}

export interface Profile {
    entityName: string;
    totalIncome: number;
    totalExpense: number;
    transactionCount: number;
}

export interface SuspiciousTransaction {
    from: string;
    to: string;
    amount: number;
    date: string;
}

export interface CashCollision {
    person1: string;
    person2: string;
    time1: string;
    time2: string;
    amount1: number;
    amount2: number;
}

export interface Suspicions {
    directTransfers: SuspiciousTransaction[];
    cashCollisions: CashCollision[];
    hiddenAssets: Record<string, unknown>;
    fixedFrequency: Record<string, unknown>;
    cashTimingPatterns: unknown[];
    holidayTransactions: Record<string, unknown>;
    amountPatterns: Record<string, unknown>;
}

export interface AnalysisResults {
    persons: string[];
    companies: string[];
    profiles: Record<string, Profile>;
    suspicions: Suspicions;
    analysisResults: Record<string, unknown>;
}

export interface Report {
    name: string;
    path: string;
    size: number;
    modified: string;
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

// ==================== HTTP API ====================

class ApiService {
    private baseUrl: string;

    constructor(baseUrl: string = API_BASE_URL) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;

        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return response.json();
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
     * 获取报告列表
     */
    async getReports(): Promise<{ reports: Report[] }> {
        return this.request('/api/reports');
    }

    /**
     * 下载报告
     */
    async downloadReport(filename: string): Promise<Blob> {
        const url = `${this.baseUrl}/api/reports/${encodeURIComponent(filename)}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`下载失败: ${response.status}`);
        }

        return response.blob();
    }
}

// ==================== WebSocket Service ====================

type WebSocketCallback = (message: WebSocketMessage) => void;

class WebSocketService {
    private ws: WebSocket | null = null;
    private url: string;
    private callbacks: Set<WebSocketCallback> = new Set();
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;

    constructor(url: string = WS_URL) {
        this.url = url;
    }

    /**
     * 连接 WebSocket
     */
    connect(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            return;
        }

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('[WS] Connected');
                this.reconnectAttempts = 0;
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
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[WS] Error:', error);
            };
        } catch (error) {
            console.error('[WS] Connection failed:', error);
            this.attemptReconnect();
        }
    }

    /**
     * 断开连接
     */
    disconnect(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
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
     * 尝试重连
     */
    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('[WS] Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

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
