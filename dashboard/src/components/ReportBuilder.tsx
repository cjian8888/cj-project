import { useState, useCallback, useEffect } from 'react';
import { Download, Users, Settings, FileText, ChevronDown, ChevronUp, ArrowLeft, ArrowRight, CheckCircle } from 'lucide-react';
import { PrimaryTargetsConfig } from './PrimaryTargetsConfig';
import { API_BASE_URL } from '../services/api';

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

// 归集配置类型定义
interface AnalysisUnitMember {
    name: string;
    relation: string;
    has_data: boolean;
}

interface AnalysisUnit {
    anchor: string;
    members: string[];
    unit_type: 'family' | 'independent';
    member_details?: AnalysisUnitMember[];
    note?: string;
}

interface PrimaryTargetsConfigType {
    version: string;
    employer: string;
    employer_keywords: string[];
    analysis_units: AnalysisUnit[];
    include_companies: string[];
    doc_number: string;
    case_source: string;
    case_notes: string;
    created_at?: string;
    updated_at?: string;
}

interface ReportBuilderProps {
    className?: string;
}

// 步骤定义
type BuilderStep = 'config' | 'generate';

export function ReportBuilder({ className }: ReportBuilderProps) {
    // 步骤控制
    const [currentStep, setCurrentStep] = useState<BuilderStep>('config');
    const [primaryTargetsConfig, setPrimaryTargetsConfig] = useState<PrimaryTargetsConfigType | null>(null);
    
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
        setIsGenerating(true);
        setError(null);
        setPreviewHtml(null);

        try {
            // 【v5.1 关键修改】调用后端HTML生成API，实现"所见即所得"
            // 后端使用 Jinja2 模板 (templates/report_v3/) 生成正式HTML报告
            const response = await fetch(`${API_BASE_URL}/api/investigation-report/generate-html`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    case_background: caseName,
                    data_scope: sections
                        .filter(section => section.checked)
                        .map(section => section.name)
                        .join('、'),
                    doc_number: docNumber || undefined,
                    selected_subjects: selectedSubjects,
                    thresholds,
                    sections: sections.filter(section => section.checked).map(section => section.id),
                }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || '报告生成失败');
            }

            const data = await response.json();
            if (data.success && data.html) {
                // 直接使用后端返回的HTML（正式报告）
                setPreviewHtml(data.html);

                // 保存HTML到输出目录（预览和保存的是同一份HTML）
                try {
                    const saveResponse = await fetch(`${API_BASE_URL}/api/investigation-report/save-html`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            html: data.html,
                            filename: `${caseName}.html`,
                        }),
                    });
                    if (saveResponse.ok) {
                        const saveData = await saveResponse.json();
                        console.log('HTML已保存到输出目录:', saveData.path);
                    } else {
                        console.error('保存HTML失败');
                    }
                } catch (saveErr) {
                    console.error('保存HTML失败:', saveErr);
                }
            } else {
                throw new Error(data.error || '报告生成失败');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '未知错误');
        } finally {
            setIsGenerating(false);
        }
    }, [caseName, docNumber, selectedSubjects, thresholds, sections]);

    // 【v5.1 删除】前端不再使用独立模板渲染
    // 报告HTML统一由后端 /api/investigation-report/generate-html 生成
    // 使用 Jinja2 模板: templates/report_v3/

    const downloadReport = useCallback(() => {
        if (!previewHtml) return;

        const mimeType = 'text/html';
        const extension = 'html';

        const blob = new Blob([previewHtml], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${caseName}.${extension}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, [previewHtml, caseName]);

    return (
        <div className={`report-builder flex flex-col h-[700px] ${className || ''}`}>
            {/* 步骤导航栏 */}
            <div className="flex items-center justify-center gap-4 mb-4 p-3 theme-bg-muted rounded-xl border theme-border">
                <button
                    onClick={() => setCurrentStep('config')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        currentStep === 'config'
                            ? 'bg-blue-500 text-white'
                            : 'theme-bg-base theme-text-muted hover:theme-bg-hover'
                    }`}
                >
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                        currentStep === 'config' ? 'bg-white/20' : 'bg-gray-600'
                    }`}>1</span>
                    归集配置
                    {primaryTargetsConfig && primaryTargetsConfig.analysis_units.length > 0 && (
                        <CheckCircle size={14} className="text-green-400" />
                    )}
                </button>
                
                <ArrowRight size={16} className="theme-text-dim" />
                
                <button
                    onClick={() => setCurrentStep('generate')}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        currentStep === 'generate'
                            ? 'bg-blue-500 text-white'
                            : 'theme-bg-base theme-text-muted hover:theme-bg-hover'
                    }`}
                >
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                        currentStep === 'generate' ? 'bg-white/20' : 'bg-gray-600'
                    }`}>2</span>
                    报告生成
                </button>
            </div>

            {/* 步骤内容区域 */}
            <div className="flex-1 flex gap-4 min-h-0">
                {currentStep === 'config' ? (
                    /* 步骤1: 归集配置 */
                    <>
                        <div className="w-[400px] theme-bg-muted rounded-xl p-4 shadow-lg overflow-auto border theme-border">
                            <PrimaryTargetsConfig 
                                onConfigChange={setPrimaryTargetsConfig}
                            />
                        </div>
                        
                        <div className="flex-1 theme-bg-muted rounded-xl p-4 shadow-lg flex flex-col border theme-border">
                            <h2 className="text-base font-semibold mb-4 theme-text">📊 配置预览</h2>
                            <div className="flex-1 overflow-auto theme-bg-surface rounded-lg p-4">
                                {primaryTargetsConfig ? (
                                    <div className="space-y-4">
                                        {/* 分析单元预览 */}
                                        <div>
                                            <h3 className="text-sm font-medium theme-text-muted mb-2">分析单元 ({primaryTargetsConfig.analysis_units.length})</h3>
                                            <div className="space-y-2">
                                                {primaryTargetsConfig.analysis_units.map((unit, idx) => (
                                                    <div key={idx} className={`p-3 rounded-lg border ${
                                                        unit.unit_type === 'family' 
                                                            ? 'bg-blue-500/10 border-blue-500/30' 
                                                            : 'bg-purple-500/10 border-purple-500/30'
                                                    }`}>
                                                        <div className="flex items-center gap-2 mb-2">
                                                            <span className={`px-2 py-0.5 text-xs rounded ${
                                                                unit.unit_type === 'family'
                                                                    ? 'bg-blue-500/30 text-blue-300'
                                                                    : 'bg-purple-500/30 text-purple-300'
                                                            }`}>
                                                                {unit.unit_type === 'family' ? '核心家庭' : '独立单元'}
                                                            </span>
                                                            <span className="text-sm font-medium theme-text">{unit.anchor || '(未设置锚点)'}</span>
                                                        </div>
                                                        <div className="flex flex-wrap gap-1">
                                                            {unit.member_details?.map(member => (
                                                                <span key={member.name} className={`px-2 py-0.5 text-xs rounded ${
                                                                    member.has_data 
                                                                        ? 'bg-green-500/20 text-green-400' 
                                                                        : 'bg-gray-500/20 text-gray-400'
                                                                }`}>
                                                                    {member.name} ({member.relation})
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ))}
                                                {primaryTargetsConfig.analysis_units.length === 0 && (
                                                    <div className="text-center py-8 theme-text-dim">
                                                        <Users size={32} className="mx-auto mb-2 opacity-40" />
                                                        <p>请在左侧添加分析单元</p>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* 涉案公司预览 */}
                                        {primaryTargetsConfig.include_companies.length > 0 && (
                                            <div>
                                                <h3 className="text-sm font-medium theme-text-muted mb-2">涉案公司 ({primaryTargetsConfig.include_companies.length})</h3>
                                                <div className="flex flex-wrap gap-1">
                                                    {primaryTargetsConfig.include_companies.map(company => (
                                                        <span key={company} className="px-2 py-1 text-xs bg-orange-500/20 text-orange-400 rounded">
                                                            {company}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        
                                        {/* 下一步按钮 */}
                                        <div className="pt-4 border-t border-white/10">
                                            <button
                                                onClick={() => setCurrentStep('generate')}
                                                disabled={!primaryTargetsConfig || primaryTargetsConfig.analysis_units.length === 0}
                                                className={`w-full py-3 rounded-lg text-sm font-medium flex items-center justify-center gap-2 ${
                                                    primaryTargetsConfig && primaryTargetsConfig.analysis_units.length > 0
                                                        ? 'bg-blue-500 text-white hover:bg-blue-600'
                                                        : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                                }`}
                                            >
                                                下一步：生成报告
                                                <ArrowRight size={16} />
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-full theme-text-dim">
                                        <FileText size={48} className="mb-4 opacity-40" />
                                        <p>加载配置中...</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                ) : (
                    /* 步骤2: 报告生成 */
                    <>
                        {/* 左侧配置栏 */}
                        <div className="w-80 theme-bg-muted rounded-xl p-4 shadow-lg overflow-auto border theme-border">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-base font-semibold theme-text">📋 报告配置</h2>
                                <button
                                    onClick={() => setCurrentStep('config')}
                                    className="flex items-center gap-1 px-2 py-1 text-xs theme-text-muted hover:theme-bg-hover rounded"
                                >
                                    <ArrowLeft size={12} />
                                    返回归集
                                </button>
                            </div>

                            {/* 案件名称 */}
                            <div className="mb-3.5">
                                <label className="block text-sm font-medium theme-text-muted mb-1.5">案件名称</label>
                                <input
                                    type="text"
                                    value={caseName}
                                    onChange={(e) => setCaseName(e.target.value)}
                                    className="w-full px-3 py-2.5 border theme-border rounded-md text-sm outline-none theme-bg-base theme-text"
                                    placeholder="输入案件名称"
                                />
                            </div>

                            {/* 文号 */}
                            <div className="mb-3.5">
                                <label className="block text-sm font-medium theme-text-muted mb-1.5">文号（可选）</label>
                                <input
                                    type="text"
                                    value={docNumber}
                                    onChange={(e) => setDocNumber(e.target.value)}
                                    className="w-full px-3 py-2.5 border theme-border rounded-md text-sm outline-none theme-bg-base theme-text"
                                    placeholder="如：国监查 [2026] 第 12345 号"
                                />
                            </div>

                            {/* 核查对象选择 */}
                            <div className="mb-3.5">
                                <label className="block text-sm font-medium theme-text-muted mb-1.5">
                                    <Users size={14} className="inline mr-1 align-middle" />
                                    核查对象
                                    <span className="text-xs font-normal theme-text-dim ml-1.5">
                                        （已选 {selectedSubjects.length}/{subjects.length}）
                                    </span>
                                </label>
                                {loadingSubjects ? (
                                    <div className="p-4 text-center theme-text-dim">加载中...</div>
                                ) : (
                                    <>
                                        <div className="flex gap-1.5 mb-1.5">
                                            <button onClick={selectAllSubjects} className="px-2.5 py-1 text-xs border theme-border rounded theme-bg-base theme-text-muted hover:theme-bg-hover">全选</button>
                                            <button onClick={clearAllSubjects} className="px-2.5 py-1 text-xs border theme-border rounded theme-bg-base theme-text-muted hover:theme-bg-hover">清空</button>
                                        </div>
                                        <div className="flex flex-col gap-1 max-h-40 overflow-auto">
                                            {subjects.map(subject => (
                                                <div
                                                    key={subject.name}
                                                    className={`flex items-center gap-2 px-2.5 py-2 border rounded-md cursor-pointer text-sm transition-colors
                                                        ${selectedSubjects.includes(subject.name) 
                                                            ? 'border-blue-500 bg-blue-500/15' 
                                                            : 'theme-border theme-bg-base hover:theme-bg-hover'}`}
                                                    onClick={() => toggleSubject(subject.name)}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedSubjects.includes(subject.name)}
                                                        onChange={() => { }}
                                                        className="mt-0.5 cursor-pointer accent-blue-500"
                                                    />
                                                    <div className="flex-1 flex items-center gap-1.5">
                                                        <span className="font-medium theme-text">{subject.name}</span>
                                                        <span className="text-xs">
                                                            {subject.type === 'person' ? '👤' : '🏢'}
                                                        </span>
                                                    </div>
                                                    {subject.salaryRatio !== undefined && subject.salaryRatio < 0.5 && (
                                                        <span className="text-xs text-yellow-500">⚠</span>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* 阈值微调 */}
                            <div className="mb-3.5">
                                <div 
                                    className="flex items-center justify-between py-2 cursor-pointer text-sm font-medium theme-text-muted"
                                    onClick={() => setShowThresholds(!showThresholds)}
                                >
                                    <span className="flex items-center gap-1">
                                        <Settings size={14} />
                                        阈值参数
                                    </span>
                                    {showThresholds ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                </div>
                                {showThresholds && (
                                    <div className="p-3 border theme-border rounded-md theme-bg-base">
                                        <div className="flex justify-between items-center mb-2 text-xs">
                                            <label className="theme-text-muted">大额转账标准</label>
                                            <div className="flex items-center gap-1">
                                                <span className="theme-text-dim">¥</span>
                                                <input
                                                    type="number"
                                                    value={thresholds.largeTransfer}
                                                    onChange={(e) => setThresholds(prev => ({
                                                        ...prev,
                                                        largeTransfer: parseInt(e.target.value) || 0
                                                    }))}
                                                    className="w-24 px-2 py-1.5 border theme-border rounded text-xs text-right theme-bg-muted theme-text"
                                                />
                                            </div>
                                        </div>
                                        <div className="flex justify-between items-center text-xs">
                                            <label className="theme-text-muted">大额现金标准</label>
                                            <div className="flex items-center gap-1">
                                                <span className="theme-text-dim">¥</span>
                                                <input
                                                    type="number"
                                                    value={thresholds.largeCash}
                                                    onChange={(e) => setThresholds(prev => ({
                                                        ...prev,
                                                        largeCash: parseInt(e.target.value) || 0
                                                    }))}
                                                    className="w-24 px-2 py-1.5 border theme-border rounded text-xs text-right theme-bg-muted theme-text"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* 模块选择 */}
                            <div className="mb-3.5">
                                <label className="block text-sm font-medium theme-text-muted mb-1.5">选择报告模块</label>
                                <div className="flex flex-col gap-1.5">
                                    {sections.map(section => (
                                        <div
                                            key={section.id}
                                            className={`flex items-start gap-2 p-2.5 border rounded-lg cursor-pointer transition-colors
                                                ${section.checked 
                                                    ? 'border-blue-500 bg-blue-500/15' 
                                                    : 'theme-border theme-bg-base hover:theme-bg-hover'}`}
                                            onClick={() => toggleSection(section.id)}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={section.checked}
                                                onChange={() => { }}
                                                className="mt-0.5 cursor-pointer accent-blue-500"
                                            />
                                            <div>
                                                <div className="text-sm font-medium theme-text">{section.name}</div>
                                                <div className="text-xs theme-text-dim mt-0.5">{section.description}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                             </div>
 
                            {/* 生成按钮 */}
                            <button
                                onClick={generateReport}
                                disabled={isGenerating}
                                className={`w-full py-3 rounded-lg text-sm font-medium transition-colors mt-2
                                    ${isGenerating 
                                        ? 'bg-gray-500 cursor-not-allowed text-gray-300' 
                                        : 'bg-blue-500 hover:bg-blue-600 text-white cursor-pointer'}`}
                            >
                                {isGenerating ? '⏳ 生成中...' : '🚀 生成报告'}
                            </button>

                            {/* 下载按钮 */}
                            {previewHtml && (
                                <button 
                                    onClick={downloadReport} 
                                    className="w-full py-2.5 mt-2 rounded-lg text-sm border border-green-500 text-green-500 hover:bg-green-500/10 flex items-center justify-center gap-1.5 transition-colors"
                                >
                                    <Download size={16} />
                                    下载报告
                                </button>
                            )}

                            {/* 错误提示 */}
                            {error && (
                                <div className="mt-3 p-2.5 bg-red-500/10 border border-red-500/30 rounded-md text-red-500 text-xs">
                                    ❌ {error}
                                </div>
                            )}
                        </div>

                        {/* 右侧预览区 */}
                        <div className="flex-1 theme-bg-muted rounded-xl p-4 shadow-lg flex flex-col border theme-border">
                            <h2 className="text-base font-semibold mb-4 theme-text">👁️ 报告预览</h2>
                            <div className="flex-1 overflow-hidden theme-bg-surface rounded-lg">
                                {previewHtml ? (
                                    <div className="h-full w-full overflow-auto p-4 box-border">
                                        <iframe
                                            srcDoc={previewHtml}
                                            className="w-full h-full min-h-[500px] border-none rounded bg-white"
                                            title="报告预览"
                                            sandbox="allow-same-origin"
                                        />
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center h-full min-h-[300px] theme-text-dim text-center">
                                        <FileText size={48} className="mb-4 opacity-40" />
                                        <p className="theme-text-muted mb-1">选择核查对象和模块</p>
                                        <p className="theme-text-muted">点击"生成报告"预览</p>
                                        <p className="text-xs theme-text-dim mt-3">
                                            报告将按归集配置组织章节结构
                                        </p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}
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
