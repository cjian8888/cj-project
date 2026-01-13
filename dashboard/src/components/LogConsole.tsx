import React, { useRef, useEffect, useState } from 'react';
import { Terminal, X, Maximize2, Minimize2, Copy, CheckCircle2 } from 'lucide-react';
import { useApp } from '../contexts/AppContext';

export function LogConsole() {
    const { logs, clearLogs, addLog } = useApp();
    const scrollRef = useRef<HTMLDivElement>(null);
    const [isExpanded, setIsExpanded] = useState(false);
    const [copied, setCopied] = useState(false);

    // Auto-scroll to bottom when logs change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    // Simulate real-time logs (demo purposes - remove in production)
    useEffect(() => {
        const interval = setInterval(() => {
            const demoLogs = [
                { level: 'INFO' as const, msgs: ['扫描数据节点...', '验证交易签名...', '更新关系图谱...', '索引实体记录...', '同步审计日志...'] },
                { level: 'WARN' as const, msgs: ['检测到异常高频交易', '跨境资金阈值预警', '数据一致性校验差异'] },
                { level: 'ERROR' as const, msgs: ['数据源连接超时', '签名验证失败'] }
            ];

            const random = Math.random();
            const type = random > 0.95 ? demoLogs[2] : random > 0.85 ? demoLogs[1] : demoLogs[0];
            const msg = type.msgs[Math.floor(Math.random() * type.msgs.length)];

            const now = new Date();
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

            addLog({ time: timeStr, level: type.level, msg });
        }, 4000);

        return () => clearInterval(interval);
    }, [addLog]);

    const copyLogs = () => {
        const logText = logs.map(log => `[${log.time}] ${log.level}: ${log.msg}`).join('\n');
        navigator.clipboard.writeText(logText);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className={`
      terminal transition-all duration-300
      ${isExpanded ? 'fixed inset-4 z-50' : 'relative'}
    `}>
            {/* Terminal Header */}
            <div className="terminal-header">
                <div className="flex items-center gap-3">
                    {/* macOS Style Window Buttons */}
                    <div className="flex gap-2">
                        <button
                            onClick={clearLogs}
                            className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400 transition-colors"
                            title="清除日志"
                        />
                        <button
                            className="w-3 h-3 rounded-full bg-yellow-500 hover:bg-yellow-400 transition-colors"
                            title="最小化"
                        />
                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="w-3 h-3 rounded-full bg-green-500 hover:bg-green-400 transition-colors"
                            title={isExpanded ? '收起' : '展开'}
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-gray-400" />
                        <span className="text-sm font-medium text-gray-300 font-mono">实时分析日志</span>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Log Stats */}
                    <div className="hidden sm:flex items-center gap-3 mr-3 text-xs">
                        <span className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-blue-500" />
                            <span className="text-gray-500">{logs.filter(l => l.level === 'INFO').length}</span>
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-yellow-500" />
                            <span className="text-gray-500">{logs.filter(l => l.level === 'WARN').length}</span>
                        </span>
                        <span className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-red-500" />
                            <span className="text-gray-500">{logs.filter(l => l.level === 'ERROR').length}</span>
                        </span>
                    </div>

                    {/* Action Buttons */}
                    <button
                        onClick={copyLogs}
                        className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors rounded-md hover:bg-gray-800"
                        title="复制日志"
                    >
                        {copied ? <CheckCircle2 className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors rounded-md hover:bg-gray-800"
                        title={isExpanded ? '收起' : '全屏'}
                    >
                        {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={clearLogs}
                        className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors rounded-md hover:bg-gray-800"
                        title="清除"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Terminal Content */}
            <div
                ref={scrollRef}
                className={`
          terminal-content scrollbar-thin
          ${isExpanded ? 'h-[calc(100%-48px)]' : 'h-56'}
        `}
            >
                {logs.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-gray-600 font-mono">
                        <span className="animate-pulse">等待日志输出...</span>
                    </div>
                ) : (
                    <div className="space-y-0.5">
                        {logs.map((log, idx) => (
                            <LogEntry key={idx} log={log} isNew={idx === logs.length - 1} />
                        ))}
                    </div>
                )}
            </div>

            {/* Command Input (decorative) */}
            <div className="px-4 py-2 border-t border-gray-800/50 bg-[#080c14] flex items-center gap-2">
                <span className="text-green-400 font-mono text-sm">❯</span>
                <input
                    type="text"
                    placeholder="输入命令..."
                    className="flex-1 bg-transparent text-sm text-gray-300 font-mono placeholder:text-gray-600 focus:outline-none"
                    readOnly
                />
            </div>
        </div>
    );
}

// ==================== Log Entry Component ====================

interface LogEntryProps {
    log: {
        time: string;
        level: 'INFO' | 'WARN' | 'ERROR';
        msg: string;
    };
    isNew?: boolean;
}

function LogEntry({ log, isNew }: LogEntryProps) {
    const levelConfig = {
        INFO: { color: 'text-blue-400', label: '信息', bgHover: 'hover:bg-blue-500/5' },
        WARN: { color: 'text-yellow-400', label: '警告', bgHover: 'hover:bg-yellow-500/5' },
        ERROR: { color: 'text-red-400', label: '错误', bgHover: 'hover:bg-red-500/5' },
    };

    const config = levelConfig[log.level];

    return (
        <div className={`
      log-entry py-1 px-2 -mx-2 rounded
      ${config.bgHover}
      ${isNew ? 'animate-slide-in-right' : ''}
      transition-colors cursor-default
    `}>
            <span className="log-time">{log.time}</span>
            <span className={`log-level ${config.color}`}>
                [{config.label}]
            </span>
            <span className="log-msg">{log.msg}</span>
        </div>
    );
}
