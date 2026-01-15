import { FileText, AlertCircle, RefreshCw } from 'lucide-react';

interface EmptyStateProps {
  type?: 'data' | 'error' | 'loading';
  message?: string;
  onAction?: () => void;
  actionText?: string;
}

/**
 * 空状态组件
 * 用于显示暂无数据、错误或加载中的友好提示
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
      default:
        return <FileText className="w-12 h-12 text-gray-500" />;
    }
  };

  const getMessage = () => {
    if (message) return message;
    switch (type) {
      case 'error':
        return '加载失败，请重试';
      case 'loading':
        return '加载中...';
      default:
        return '暂无数据，请先运行分析';
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="mb-4">
        {getIcon()}
      </div>
      <p className="text-gray-400 text-sm mb-6">{getMessage()}</p>
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
