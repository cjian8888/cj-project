import React from 'react';
import { Header } from './Header';
import { KPICards } from './KPICards';
import { TabContent } from './TabContent';
import { LogConsole } from './LogConsole';
import { useApp } from '../contexts/AppContext';

export function MainContent() {
    const { analysis } = useApp();

    return (
        <main className="flex-1 flex flex-col h-screen overflow-hidden relative z-10">
            {/* Top Accent Line */}
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-60" />

            {/* Header */}
            <Header />

            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-y-auto p-6 lg:p-8 scrollbar-thin">
                {/* Progress Bar - Only visible during analysis */}
                {analysis.isRunning && (
                    <div className="mb-6 animate-fade-in">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-gray-300">{analysis.currentPhase}</span>
                            <span className="text-sm font-mono text-blue-400">{analysis.progress}%</span>
                        </div>
                        <div className="progress-bar">
                            <div
                                className="progress-bar-fill animate-pulse-glow"
                                style={{ width: `${analysis.progress}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* KPI Cards */}
                <section className="mb-8 animate-slide-up" style={{ animationDelay: '0.1s' }}>
                    <KPICards />
                </section>

                {/* Tab Content */}
                <section className="mb-8 animate-slide-up" style={{ animationDelay: '0.2s' }}>
                    <TabContent />
                </section>

                {/* Log Console */}
                <section className="animate-slide-up" style={{ animationDelay: '0.3s' }}>
                    <LogConsole />
                </section>
            </div>
        </main>
    );
}
