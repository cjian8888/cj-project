import { useState, useCallback } from 'react';

interface ReportSection {
    id: string;
    name: string;
    description: string;
    checked: boolean;
}

interface ReportBuilderProps {
    className?: string;
}

const API_BASE_URL = 'http://localhost:8000';

export function ReportBuilder({ className }: ReportBuilderProps) {
    const [sections, setSections] = useState<ReportSection[]>([
        { id: 'summary', name: '资金概览', description: '核心统计指标汇总', checked: true },
        { id: 'assets', name: '个人资产', description: '各人员资产情况表', checked: false },
        { id: 'risks', name: '可疑交易', description: '疑点交易、资金闭环、现金伴随', checked: true },
    ]);

    const [caseName, setCaseName] = useState('审计报告');
    const [format, setFormat] = useState<'html' | 'json'>('html');
    const [isGenerating, setIsGenerating] = useState(false);
    const [previewHtml, setPreviewHtml] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const toggleSection = (id: string) => {
        setSections(prev =>
            prev.map(s => s.id === id ? { ...s, checked: !s.checked } : s)
        );
    };

    const generateReport = useCallback(async () => {
        const selectedSections = sections.filter(s => s.checked).map(s => s.id);

        if (selectedSections.length === 0) {
            setError('请至少选择一个报告模块');
            return;
        }

        setIsGenerating(true);
        setError(null);
        setPreviewHtml(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/reports/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sections: selectedSections,
                    format: format,
                    case_name: caseName,
                }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || '报告生成失败');
            }

            if (format === 'html') {
                const html = await response.text();
                setPreviewHtml(html);
            } else {
                const data = await response.json();
                setPreviewHtml(`<pre style="white-space: pre-wrap; font-family: monospace; padding: 20px;">${JSON.stringify(data, null, 2)}</pre>`);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '未知错误');
        } finally {
            setIsGenerating(false);
        }
    }, [sections, format, caseName]);

    const downloadReport = useCallback(() => {
        if (!previewHtml) return;

        const blob = new Blob([previewHtml], { type: format === 'html' ? 'text/html' : 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${caseName}.${format === 'html' ? 'html' : 'json'}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [previewHtml, format, caseName]);

    return (
        <div className={`report-builder ${className || ''}`} style={styles.container}>
            <div style={styles.leftPanel}>
                <h2 style={styles.panelTitle}>📋 报告配置</h2>

                {/* 案件名称 */}
                <div style={styles.formGroup}>
                    <label style={styles.label}>案件名称</label>
                    <input
                        type="text"
                        value={caseName}
                        onChange={(e) => setCaseName(e.target.value)}
                        style={styles.input}
                        placeholder="输入案件名称"
                    />
                </div>

                {/* 模块选择 */}
                <div style={styles.formGroup}>
                    <label style={styles.label}>选择报告模块</label>
                    <div style={styles.sectionList}>
                        {sections.map(section => (
                            <div
                                key={section.id}
                                style={{
                                    ...styles.sectionItem,
                                    ...(section.checked ? styles.sectionItemChecked : {})
                                }}
                                onClick={() => toggleSection(section.id)}
                            >
                                <input
                                    type="checkbox"
                                    checked={section.checked}
                                    onChange={() => { }}
                                    style={styles.checkbox}
                                />
                                <div>
                                    <div style={styles.sectionName}>{section.name}</div>
                                    <div style={styles.sectionDesc}>{section.description}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* 格式选择 */}
                <div style={styles.formGroup}>
                    <label style={styles.label}>输出格式</label>
                    <div style={styles.formatButtons}>
                        <button
                            onClick={() => setFormat('html')}
                            style={{
                                ...styles.formatButton,
                                ...(format === 'html' ? styles.formatButtonActive : {})
                            }}
                        >
                            HTML 报告
                        </button>
                        <button
                            onClick={() => setFormat('json')}
                            style={{
                                ...styles.formatButton,
                                ...(format === 'json' ? styles.formatButtonActive : {})
                            }}
                        >
                            JSON 数据
                        </button>
                    </div>
                </div>

                {/* 生成按钮 */}
                <button
                    onClick={generateReport}
                    disabled={isGenerating}
                    style={{
                        ...styles.generateButton,
                        ...(isGenerating ? styles.generateButtonDisabled : {})
                    }}
                >
                    {isGenerating ? '⏳ 生成中...' : '🚀 生成报告'}
                </button>

                {/* 下载按钮 */}
                {previewHtml && (
                    <button onClick={downloadReport} style={styles.downloadButton}>
                        ⬇️ 下载报告
                    </button>
                )}

                {/* 错误提示 */}
                {error && (
                    <div style={styles.error}>
                        ❌ {error}
                    </div>
                )}
            </div>

            {/* 预览区域 */}
            <div style={styles.rightPanel}>
                <h2 style={styles.panelTitle}>👁️ 报告预览</h2>
                <div style={styles.previewContainer}>
                    {previewHtml ? (
                        <iframe
                            srcDoc={previewHtml}
                            style={styles.previewFrame}
                            title="报告预览"
                            sandbox="allow-same-origin"
                        />
                    ) : (
                        <div style={styles.previewPlaceholder}>
                            <span style={{ fontSize: '48px' }}>📄</span>
                            <p>选择模块并点击"生成报告"</p>
                            <p style={{ fontSize: '14px', color: '#999' }}>
                                报告将使用官方公文格式生成
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

const styles: Record<string, React.CSSProperties> = {
    container: {
        display: 'flex',
        height: '100%',
        gap: '20px',
        padding: '20px',
        backgroundColor: '#f5f5f5',
    },
    leftPanel: {
        width: '320px',
        backgroundColor: '#fff',
        borderRadius: '12px',
        padding: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        overflow: 'auto',
    },
    rightPanel: {
        flex: 1,
        backgroundColor: '#fff',
        borderRadius: '12px',
        padding: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        display: 'flex',
        flexDirection: 'column',
    },
    panelTitle: {
        fontSize: '18px',
        fontWeight: 600,
        marginBottom: '20px',
        color: '#333',
    },
    formGroup: {
        marginBottom: '20px',
    },
    label: {
        display: 'block',
        fontSize: '14px',
        fontWeight: 500,
        color: '#666',
        marginBottom: '8px',
    },
    input: {
        width: '100%',
        padding: '10px 12px',
        border: '1px solid #ddd',
        borderRadius: '6px',
        fontSize: '14px',
        outline: 'none',
        boxSizing: 'border-box' as const,
    },
    sectionList: {
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
    },
    sectionItem: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '12px',
        border: '1px solid #eee',
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s',
    },
    sectionItemChecked: {
        borderColor: '#1890ff',
        backgroundColor: '#e6f7ff',
    },
    checkbox: {
        marginTop: '2px',
        cursor: 'pointer',
    },
    sectionName: {
        fontSize: '14px',
        fontWeight: 500,
        color: '#333',
    },
    sectionDesc: {
        fontSize: '12px',
        color: '#999',
        marginTop: '2px',
    },
    formatButtons: {
        display: 'flex',
        gap: '8px',
    },
    formatButton: {
        flex: 1,
        padding: '10px',
        border: '1px solid #ddd',
        borderRadius: '6px',
        backgroundColor: '#fff',
        cursor: 'pointer',
        fontSize: '13px',
        transition: 'all 0.2s',
    },
    formatButtonActive: {
        borderColor: '#1890ff',
        backgroundColor: '#1890ff',
        color: '#fff',
    },
    generateButton: {
        width: '100%',
        padding: '14px',
        backgroundColor: '#1890ff',
        color: '#fff',
        border: 'none',
        borderRadius: '8px',
        fontSize: '15px',
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'all 0.2s',
    },
    generateButtonDisabled: {
        backgroundColor: '#ccc',
        cursor: 'not-allowed',
    },
    downloadButton: {
        width: '100%',
        padding: '12px',
        backgroundColor: '#52c41a',
        color: '#fff',
        border: 'none',
        borderRadius: '8px',
        fontSize: '14px',
        cursor: 'pointer',
        marginTop: '10px',
    },
    error: {
        marginTop: '15px',
        padding: '12px',
        backgroundColor: '#fff1f0',
        border: '1px solid #ffa39e',
        borderRadius: '6px',
        color: '#cf1322',
        fontSize: '13px',
    },
    previewContainer: {
        flex: 1,
        border: '1px solid #eee',
        borderRadius: '8px',
        overflow: 'hidden',
        backgroundColor: '#fafafa',
    },
    previewFrame: {
        width: '100%',
        height: '100%',
        border: 'none',
    },
    previewPlaceholder: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: '#999',
        textAlign: 'center' as const,
    },
};

export default ReportBuilder;
