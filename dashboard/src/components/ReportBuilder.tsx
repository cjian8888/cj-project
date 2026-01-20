import { useState, useCallback, useEffect } from 'react';
import { Download, Users, Settings, FileText, ChevronDown, ChevronUp } from 'lucide-react';

interface ReportSection {
    id: string;
    name: string;
    description: string;
    checked: boolean;
    subItems?: { id: string; name: string; checked: boolean }[];
}

interface Subject {
    name: string;
    type: 'person' | 'company';
    transactionCount: number;
    totalIncome: number;
    salaryRatio?: number;
}

interface ReportBuilderProps {
    className?: string;
}

const API_BASE_URL = 'http://localhost:8000';

export function ReportBuilder({ className }: ReportBuilderProps) {
    // 嫌疑人选择
    const [subjects, setSubjects] = useState<Subject[]>([]);
    const [selectedSubjects, setSelectedSubjects] = useState<string[]>([]);
    const [loadingSubjects, setLoadingSubjects] = useState(false);
    
    // 阈值配置
    const [thresholds, setThresholds] = useState({
        largeTransfer: 50000,
        largeCash: 50000
    });
    const [showThresholds, setShowThresholds] = useState(false);
    
    // 报告模块
    const [sections, setSections] = useState<ReportSection[]>([
        { 
            id: 'summary', 
            name: '资金概览', 
            description: '核心统计指标汇总', 
            checked: true 
        },
        { 
            id: 'assets', 
            name: '个人资产', 
            description: '房产、车辆、银行余额', 
            checked: true,
            subItems: [
                { id: 'property', name: '房产列表', checked: true },
                { id: 'vehicle', name: '车辆信息', checked: true },
                { id: 'balance', name: '银行卡余额表', checked: true }
            ]
        },
        { 
            id: 'risks', 
            name: '可疑交易', 
            description: '疑点交易、资金闭环、现金伴随', 
            checked: true 
        },
    ]);

    const [caseName, setCaseName] = useState('初查报告');
    const [docNumber, setDocNumber] = useState('');
    const [format, setFormat] = useState<'html' | 'json'>('html');
    const [isGenerating, setIsGenerating] = useState(false);
    const [previewHtml, setPreviewHtml] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // 加载可选嫌疑人列表
    useEffect(() => {
        const fetchSubjects = async () => {
            setLoadingSubjects(true);
            try {
                const response = await fetch(`${API_BASE_URL}/api/reports/subjects`);
                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.subjects) {
                        setSubjects(data.subjects);
                        // 默认全选
                        setSelectedSubjects(data.subjects.map((s: Subject) => s.name));
                    }
                }
            } catch (err) {
                console.error('获取嫌疑人列表失败:', err);
            } finally {
                setLoadingSubjects(false);
            }
        };
        fetchSubjects();
    }, []);

    const toggleSubject = (name: string) => {
        setSelectedSubjects(prev => 
            prev.includes(name) 
                ? prev.filter(n => n !== name)
                : [...prev, name]
        );
    };

    const selectAllSubjects = () => {
        setSelectedSubjects(subjects.map(s => s.name));
    };

    const clearAllSubjects = () => {
        setSelectedSubjects([]);
    };

    const toggleSection = (id: string) => {
        setSections(prev =>
            prev.map(s => s.id === id ? { ...s, checked: !s.checked } : s)
        );
    };

    const generateReport = useCallback(async () => {
        if (selectedSubjects.length === 0) {
            setError('请至少选择一个核查对象');
            return;
        }

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
                    subjects: selectedSubjects,
                    doc_number: docNumber || null,
                    thresholds: {
                        large_transfer: thresholds.largeTransfer,
                        large_cash: thresholds.largeCash
                    }
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
                setPreviewHtml(`<pre style="white-space: pre-wrap; font-family: monospace; padding: 20px; color: #333;">${JSON.stringify(data, null, 2)}</pre>`);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '未知错误');
        } finally {
            setIsGenerating(false);
        }
    }, [sections, format, caseName, selectedSubjects, docNumber, thresholds]);

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
            {/* 左侧配置栏 */}
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

                {/* 文号 */}
                <div style={styles.formGroup}>
                    <label style={styles.label}>文号（可选）</label>
                    <input
                        type="text"
                        value={docNumber}
                        onChange={(e) => setDocNumber(e.target.value)}
                        style={styles.input}
                        placeholder="如：国监查 [2026] 第 12345 号"
                    />
                </div>

                {/* 核查对象选择 */}
                <div style={styles.formGroup}>
                    <label style={styles.label}>
                        <Users size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                        核查对象
                        <span style={styles.subLabel}>
                            （已选 {selectedSubjects.length}/{subjects.length}）
                        </span>
                    </label>
                    {loadingSubjects ? (
                        <div style={styles.loading}>加载中...</div>
                    ) : (
                        <>
                            <div style={styles.selectButtons}>
                                <button onClick={selectAllSubjects} style={styles.miniButton}>全选</button>
                                <button onClick={clearAllSubjects} style={styles.miniButton}>清空</button>
                            </div>
                            <div style={styles.subjectList}>
                                {subjects.map(subject => (
                                    <div
                                        key={subject.name}
                                        style={{
                                            ...styles.subjectItem,
                                            ...(selectedSubjects.includes(subject.name) ? styles.subjectItemChecked : {})
                                        }}
                                        onClick={() => toggleSubject(subject.name)}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={selectedSubjects.includes(subject.name)}
                                            onChange={() => { }}
                                            style={styles.checkbox}
                                        />
                                        <div style={styles.subjectInfo}>
                                            <span style={styles.subjectName}>{subject.name}</span>
                                            <span style={styles.subjectType}>
                                                {subject.type === 'person' ? '👤' : '🏢'}
                                            </span>
                                        </div>
                                        {subject.salaryRatio !== undefined && subject.salaryRatio < 0.5 && (
                                            <span style={styles.warningBadge}>⚠</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>

                {/* 阈值微调 */}
                <div style={styles.formGroup}>
                    <div 
                        style={styles.collapseHeader} 
                        onClick={() => setShowThresholds(!showThresholds)}
                    >
                        <Settings size={14} style={{ marginRight: 4 }} />
                        阈值参数
                        {showThresholds ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                    {showThresholds && (
                        <div style={styles.thresholdPanel}>
                            <div style={styles.thresholdItem}>
                                <label style={styles.thresholdLabel}>大额转账标准</label>
                                <div style={styles.amountInput}>
                                    <span style={styles.currencySymbol}>¥</span>
                                    <input
                                        type="number"
                                        value={thresholds.largeTransfer}
                                        onChange={(e) => setThresholds(prev => ({
                                            ...prev,
                                            largeTransfer: parseInt(e.target.value) || 0
                                        }))}
                                        style={styles.numberInput}
                                    />
                                </div>
                            </div>
                            <div style={styles.thresholdItem}>
                                <label style={styles.thresholdLabel}>大额现金标准</label>
                                <div style={styles.amountInput}>
                                    <span style={styles.currencySymbol}>¥</span>
                                    <input
                                        type="number"
                                        value={thresholds.largeCash}
                                        onChange={(e) => setThresholds(prev => ({
                                            ...prev,
                                            largeCash: parseInt(e.target.value) || 0
                                        }))}
                                        style={styles.numberInput}
                                    />
                                </div>
                            </div>
                        </div>
                    )}
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
                                ...(format === 'html' ? styles.formatButtonActive : styles.formatButtonInactive)
                            }}
                        >
                            HTML 报告
                        </button>
                        <button
                            onClick={() => setFormat('json')}
                            style={{
                                ...styles.formatButton,
                                ...(format === 'json' ? styles.formatButtonActive : styles.formatButtonInactive)
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
                        <Download size={16} style={{ marginRight: '6px' }} />
                        下载报告
                    </button>
                )}

                {/* 错误提示 */}
                {error && (
                    <div style={styles.error}>
                        ❌ {error}
                    </div>
                )}
            </div>

            {/* 右侧预览区 - A4仿真，使用 iframe 隔离样式 */}
            <div style={styles.rightPanel}>
                <h2 style={styles.panelTitle}>👁️ 报告预览</h2>
                <div style={styles.previewContainer}>
                    {previewHtml ? (
                        <div style={styles.a4Wrapper}>
                            {/* 使用 iframe 隔离样式，防止污染主页面 */}
                            <iframe
                                srcDoc={previewHtml}
                                style={styles.previewIframe}
                                title="报告预览"
                                sandbox="allow-same-origin"
                            />
                        </div>
                    ) : (
                        <div style={styles.previewPlaceholder}>
                            <FileText size={48} style={{ color: '#ccc', marginBottom: 16 }} />
                            <p style={styles.placeholderText}>选择核查对象和模块</p>
                            <p style={styles.placeholderText}>点击"生成报告"预览</p>
                            <p style={styles.placeholderSubtext}>
                                报告将使用公文格式生成，支持在线编辑
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
        height: '600px',
        gap: '16px',
        padding: '0',
        backgroundColor: 'transparent',
    },
    leftPanel: {
        width: '320px',
        backgroundColor: '#1e293b',
        borderRadius: '12px',
        padding: '16px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        overflow: 'auto',
        border: '1px solid rgba(255,255,255,0.1)',
    },
    rightPanel: {
        flex: 1,
        backgroundColor: '#1e293b',
        borderRadius: '12px',
        padding: '16px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid rgba(255,255,255,0.1)',
    },
    panelTitle: {
        fontSize: '16px',
        fontWeight: 600,
        marginBottom: '16px',
        color: '#fff',
    },
    formGroup: {
        marginBottom: '14px',
    },
    label: {
        display: 'block',
        fontSize: '13px',
        fontWeight: 500,
        color: '#94a3b8',
        marginBottom: '6px',
    },
    subLabel: {
        fontSize: '11px',
        fontWeight: 400,
        color: '#64748b',
        marginLeft: '6px',
    },
    input: {
        width: '100%',
        padding: '10px 12px',
        border: '1px solid #334155',
        borderRadius: '6px',
        fontSize: '14px',
        outline: 'none',
        boxSizing: 'border-box' as const,
        backgroundColor: '#0f172a',
        color: '#f1f5f9',
    },
    loading: {
        padding: '16px',
        textAlign: 'center' as const,
        color: '#64748b',
    },
    selectButtons: {
        display: 'flex',
        gap: '6px',
        marginBottom: '6px',
    },
    miniButton: {
        padding: '4px 10px',
        fontSize: '11px',
        border: '1px solid #334155',
        borderRadius: '4px',
        backgroundColor: '#0f172a',
        color: '#94a3b8',
        cursor: 'pointer',
    },
    subjectList: {
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        maxHeight: '160px',
        overflow: 'auto',
    },
    subjectItem: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 10px',
        border: '1px solid #334155',
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '13px',
        backgroundColor: '#0f172a',
    },
    subjectItemChecked: {
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.15)',
    },
    subjectInfo: {
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
    },
    subjectName: {
        fontWeight: 500,
        color: '#f1f5f9',
    },
    subjectType: {
        fontSize: '12px',
    },
    warningBadge: {
        fontSize: '12px',
        color: '#fbbf24',
    },
    collapseHeader: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 0',
        cursor: 'pointer',
        fontSize: '13px',
        fontWeight: 500,
        color: '#94a3b8',
    },
    thresholdPanel: {
        padding: '12px',
        border: '1px solid #334155',
        borderRadius: '6px',
        backgroundColor: '#0f172a',
    },
    thresholdItem: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
        fontSize: '12px',
    },
    thresholdLabel: {
        color: '#94a3b8',
    },
    amountInput: {
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
    },
    currencySymbol: {
        color: '#64748b',
    },
    numberInput: {
        width: '90px',
        padding: '6px 8px',
        border: '1px solid #334155',
        borderRadius: '4px',
        fontSize: '12px',
        textAlign: 'right' as const,
        backgroundColor: '#1e293b',
        color: '#f1f5f9',
    },
    sectionList: {
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
    },
    sectionItem: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '8px',
        padding: '10px',
        border: '1px solid #334155',
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        backgroundColor: '#0f172a',
    },
    sectionItemChecked: {
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.15)',
    },
    checkbox: {
        marginTop: '2px',
        cursor: 'pointer',
        accentColor: '#3b82f6',
    },
    sectionName: {
        fontSize: '13px',
        fontWeight: 500,
        color: '#f1f5f9',
    },
    sectionDesc: {
        fontSize: '11px',
        color: '#64748b',
        marginTop: '2px',
    },
    formatButtons: {
        display: 'flex',
        gap: '8px',
    },
    formatButton: {
        flex: 1,
        padding: '10px',
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '12px',
        fontWeight: 500,
        transition: 'all 0.2s',
    },
    formatButtonActive: {
        border: '1px solid #3b82f6',
        backgroundColor: '#3b82f6',
        color: '#fff',
    },
    formatButtonInactive: {
        border: '1px solid #334155',
        backgroundColor: '#0f172a',
        color: '#94a3b8',
    },
    generateButton: {
        width: '100%',
        padding: '12px',
        backgroundColor: '#3b82f6',
        color: '#fff',
        border: 'none',
        borderRadius: '8px',
        fontSize: '14px',
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'all 0.2s',
        marginTop: '8px',
    },
    generateButtonDisabled: {
        backgroundColor: '#475569',
        cursor: 'not-allowed',
    },
    downloadButton: {
        width: '100%',
        padding: '10px',
        backgroundColor: 'transparent',
        color: '#22c55e',
        border: '1px solid #22c55e',
        borderRadius: '8px',
        fontSize: '13px',
        cursor: 'pointer',
        marginTop: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.2s',
    },
    error: {
        marginTop: '12px',
        padding: '10px',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderRadius: '6px',
        color: '#ef4444',
        fontSize: '12px',
    },
    previewContainer: {
        flex: 1,
        overflow: 'hidden',
        backgroundColor: '#374151',
        borderRadius: '8px',
    },
    a4Wrapper: {
        height: '100%',
        width: '100%',
        overflow: 'auto',
        padding: '16px',
        boxSizing: 'border-box' as const,
    },
    previewIframe: {
        width: '100%',
        height: '100%',
        minHeight: '500px',
        border: 'none',
        borderRadius: '4px',
        backgroundColor: 'white',
    },
    previewPlaceholder: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: '300px',
        color: '#64748b',
        textAlign: 'center' as const,
    },
    placeholderText: {
        margin: '4px 0',
        color: '#94a3b8',
    },
    placeholderSubtext: {
        fontSize: '11px',
        color: '#64748b',
        marginTop: '12px',
    },
};

export default ReportBuilder;
