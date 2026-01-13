import React, { useEffect } from 'react';
import { AppProvider } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar';
import { KPICards } from './components/KPICards';
import { TabContent } from './components/TabContent';
import { LogConsole } from './components/LogConsole';
import { useApp } from './contexts/AppContext';

// ==================== Main Content Component ====================

function MainContent() {
  const { logs, addLog } = useApp();

  // Simulate incoming logs (for demo purposes)
  useEffect(() => {
    const interval = setInterval(() => {
      const actions = [
        { level: 'INFO' as const, msgs: ['正在扫描节点 84...', '验证交易哈希中...', '更新关系图谱...', '同步审计记录...', '实体索引完成，共 1,248 个节点'] },
        { level: 'WARN' as const, msgs: ['检测到异常高频交易 ID-992', '跨境资金阈值即将超限', '数据扇区4发现差异', '关联交易模式异常'] },
        { level: 'ERROR' as const, msgs: ['API-2 连接超时', '签名验证失败', '数据库写入失败'] }
      ];

      const r = Math.random();
      const type = r > 0.95 ? actions[2] : r > 0.8 ? actions[1] : actions[0];
      const msg = type.msgs[Math.floor(Math.random() * type.msgs.length)];

      const now = new Date();
      const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

      addLog({ time: timeStr, level: type.level, msg });
    }, 3000);

    return () => clearInterval(interval);
  }, [addLog]);

  return (
    <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
      {/* Top Ambient Glow */}
      <div className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 via-cyan-500 to-blue-600 z-50 opacity-80"></div>
      <div className="absolute top-0 right-0 p-8 w-1/3 h-1/3 bg-blue-500/5 blur-[100px] pointer-events-none rounded-full"></div>

      {/* Header */}
      <header className="px-8 py-6 border-b border-slate-800/50 shrink-0">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">指挥中心</h2>
            <p className="text-slate-400 text-sm">实时金融监控与异常检测平台</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-slate-500">上次同步: 24秒前</span>
          </div>
        </div>
      </header>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto p-8 z-10 scrollbar-thin">
        {/* KPI Cards */}
        <div className="mb-8">
          <KPICards />
        </div>

        {/* Tab Content */}
        <div className="mb-8">
          <TabContent />
        </div>

        {/* Log Console */}
        <div>
          <LogConsole />
        </div>
      </div>
    </main>
  );
}

// ==================== Root App Component ====================

export default function App() {
  return (
    <AppProvider>
      <div className="flex h-screen bg-slate-950 text-slate-50 selection:bg-blue-500/30">
        <Sidebar />
        <MainContent />
      </div>
    </AppProvider>
  );
}
