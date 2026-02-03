import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null,
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('ErrorBoundary caught an error:', error, errorInfo);
        this.setState({ errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="p-4 m-4 rounded-lg bg-red-500/10 border border-red-500/30">
                    <h2 className="text-lg font-bold text-red-400 mb-2">⚠️ 组件渲染错误</h2>
                    <p className="text-sm text-red-300 mb-2">
                        <strong>错误信息：</strong> {this.state.error?.message}
                    </p>
                    <details className="text-xs text-gray-400">
                        <summary className="cursor-pointer hover:text-gray-300">点击查看错误堆栈</summary>
                        <pre className="mt-2 p-2 bg-black/30 rounded overflow-auto max-h-64">
                            {this.state.error?.stack}
                        </pre>
                        {this.state.errorInfo && (
                            <pre className="mt-2 p-2 bg-black/30 rounded overflow-auto max-h-64">
                                {this.state.errorInfo.componentStack}
                            </pre>
                        )}
                    </details>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                        className="mt-4 px-3 py-1 text-sm bg-red-500/20 text-red-400 rounded hover:bg-red-500/30"
                    >
                        重试
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
