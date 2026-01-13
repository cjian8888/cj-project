import React, { useRef, useEffect } from 'react';
import { Server, X } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import type { LogConsoleProps } from '../types';

export function LogConsole() {
    const { logs, clearLogs } = useApp();
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when logs change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="glass-panel rounded-xl flex flex-col h-72 overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-slate-400" />
                    <h3 className="text-sm font-medium text-slate-300 font-mono">实时分析日志</h3>
                </div>
                <div className="flex items-center gap-3">
                    {/* Status indicators */}
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/20 border border-yellow-500/50"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-green-500/20 border border-green-500/50"></div>
                    </div>
                    {/* Clear button */}
                    <button
                        onClick={clearLogs}
                        className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
                        title="清除日志"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Log Content */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-1 bg-[#0a0f18] scrollbar-thin"
            >
                {logs.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-slate-500">
                        暂无日志
                    </div>
                ) : (
                    logs.map((log, idx) => (
                        <LogEntry key={idx} log={log} />
                    ))
                )}
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
}

function LogEntry({ log }: LogEntryProps) {
    const levelClass = {
        INFO: 'text-blue-500',
        WARN: 'text-yellow-500',
        ERROR: 'text-red-500',
    }[log.level];

    const levelText = {
        INFO: '信息',
        WARN: '警告',
        ERROR: '错误',
    }[log.level];

    return (
        <div className="flex gap-4 hover:bg-slate-800/30 py-0.5 px-2 rounded cursor-default border-l-2 border-transparent hover:border-slate-700 transition-colors">
            <span className="text-slate-500 select-none min-w-[60px]">{log.time}</span>
            <span className={`font-bold w-[45px] ${levelClass}`}>{levelText}</span>
            <span className="text-slate-300">{log.msg}</span>
        </div>
    );
}
