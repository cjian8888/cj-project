import { AppProvider } from './contexts/AppContext';
import { Sidebar } from './components/Sidebar';
import { MainContent } from './components/MainContent';

// ==================== Root App Component ====================

export default function App() {
  return (
    <AppProvider>
      <div className="flex h-screen theme-bg-base theme-text selection:bg-blue-500/30 overflow-hidden">
        {/* Background Effects */}
        <div className="grid-bg" />
        <div className="scan-line opacity-30" />

        {/* Ambient Orbs */}
        <div className="orb orb-blue w-[600px] h-[600px] -top-[200px] -left-[200px] opacity-40" />
        <div className="orb orb-cyan w-[500px] h-[500px] top-[40%] right-[-150px] opacity-30" />
        <div className="orb orb-purple w-[400px] h-[400px] bottom-[-100px] left-[30%] opacity-25" />

        {/* Main Layout */}
        <Sidebar />
        <MainContent />
      </div>
    </AppProvider>
  );
}
