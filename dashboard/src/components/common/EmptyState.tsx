import { FileText, AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react';

interface EmptyStateProps {
  type?: 'data' | 'error' | 'loading' | 'success' | 'safe';
  message?: string;
  onAction?: () => void;
  actionText?: string;
}

/**
 * 空状态组件
 * 用于显示暂无数据、错误、加载中或安全确认的友好提示
 */
export function EmptyState({
  type = 'data',
  message,
  onAction,
  actionText
}: EmptyStateProps) {
  const getIcon = () => {
    switch (type) {
      case 'error':
        return <AlertCircle className="w-12 h-12 text-red-400" />;
      case 'loading':
        return <RefreshCw className="w-12 h-12 text-cyan-400 animate-spin" />;
      case 'success':
      case 'safe':
        return <ShieldCheck className="w-12 h-12 text-green-400" />;
      default:
        return <FileText className="w-12 h-12 theme-text-dim" />;
    }
  };

  const getMessage = () => {
    if (message) return message;
    switch (type) {
      case 'error':
        return '加载失败，请重试';
      case 'loading':
        return '加载中...';
      case 'success':
      case 'safe':
        return '系统运行正常，未监测到异常资金流动';
      default:
        return '暂无数据，请先运行分析';
    }
  };

  // 安全类型使用绿色渐变背景
  const isSafeType = type === 'success' || type === 'safe';
  const bgClass = isSafeType ? 'bg-gradient-to-br from-green-500/5 to-emerald-500/5 rounded-xl' : '';

  return (
    <div className={`flex flex-col items-center justify-center py-16 px-4 ${bgClass}`}>
      <div className={`mb-4 ${isSafeType ? 'p-4 rounded-full bg-green-500/10' : ''}`}>
        {getIcon()}
      </div>
      <p className={`text-sm mb-6 ${isSafeType ? 'text-green-400 font-medium' : 'theme-text-muted'}`}>
        {getMessage()}
      </p>
      {isSafeType && (
        <p className="text-xs theme-text-dim text-center max-w-xs">
          所有监测指标正常，暂未发现需要关注的可疑交易
        </p>
      )}
      {onAction && (
        <button
          onClick={onAction}
          className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-lg text-sm font-medium transition-all"
        >
          {actionText || '加载数据'}
        </button>
      )}
    </div>
  );
}
