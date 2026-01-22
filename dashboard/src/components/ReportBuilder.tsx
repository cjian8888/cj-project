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
    const [format, setFormat] = useState<'html' | 'json' | 'v3'>('v3');  // 默认使用 v3 格式
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
        if (selectedSections.length === 0 && format !== 'v3') {
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
                    },
                    // v3.0 特有参数
                    primary_person: selectedSubjects[0] || null,
                    case_background: caseName,
                }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || '报告生成失败');
            }

            if (format === 'html') {
                const html = await response.text();
                setPreviewHtml(html);
            } else if (format === 'v3') {
                // v3.0 格式返回 JSON，转换为专业的 HTML 预览
                const data = await response.json();
                if (data.success && data.report) {
                    const v3Html = renderV3ReportToHtml(data.report);
                    setPreviewHtml(v3Html);
                } else {
                    throw new Error(data.error || 'v3.0 报告生成失败');
                }
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

    // v3.0 报告转 HTML 预览
    const renderV3ReportToHtml = (report: any): string => {
        const meta = report.meta || {};
        const family = report.family || {};
        const memberDetails = report.member_details || [];
        const companies = report.companies || [];
        const conclusion = report.conclusion || {};
        
        // 格式化金额（分转万元）
        const formatWan = (amount: number) => ((amount || 0) / 10000).toFixed(2);
        const formatCurrency = (amount: number) => (amount || 0).toLocaleString('zh-CN');
        
        // 计算家庭总银行卡数
        const totalBankAccounts = memberDetails.reduce((sum: number, m: any) => 
            sum + (m.assets?.bank_account_count || m.assets?.bank_accounts?.length || 0), 0);

        return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${meta.doc_number || '初查报告'}</title>
    <style>
        body { font-family: 'SimSun', 'Microsoft YaHei', serif; margin: 40px; line-height: 1.8; color: #333; background: #fff; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 22px; margin-bottom: 10px; }
        .header .doc-number { color: #666; font-size: 14px; }
        .section { margin: 30px 0; }
        .section h2 { font-size: 16px; border-bottom: 2px solid #333; padding-bottom: 8px; margin-bottom: 20px; }
        .section h3 { font-size: 14px; margin: 20px 0 10px 0; color: #444; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 13px; }
        th { background: #f5f5f5; font-weight: bold; }
        .highlight { background: #fff3cd; padding: 2px 6px; border-radius: 3px; }
        .warning { color: #dc3545; font-weight: bold; }
        .amount { text-align: right; font-family: 'Consolas', monospace; }
        .summary-box { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .issue-item { padding: 10px; border-left: 4px solid #dc3545; background: #fff5f5; margin: 10px 0; }
        .issue-high { border-left-color: #dc3545; }
        .issue-medium { border-left-color: #ffc107; background: #fffbeb; }
    </style>
</head>
<body>
    <div class="header">
        <h1>资金穿透核查初查报告</h1>
        <div class="doc-number">${meta.doc_number || ''}</div>
        <div style="font-size: 12px; color: #888; margin-top: 10px;">
            数据范围：${meta.data_scope || '见数据源'} | 生成时间：${meta.generated_at ? new Date(meta.generated_at).toLocaleDateString('zh-CN') : new Date().toLocaleDateString('zh-CN')}
        </div>
    </div>

    <div class="section">
        <h2>一、案源及核查背景</h2>
        <p>${meta.case_background || '根据相关线索，对被核查人进行资金流水穿透分析。'}</p>
    </div>

    <div class="section">
        <h2>二、家庭单元概览</h2>
        <h3>2.1 核心关系人</h3>
        <table>
            <tr><th>关系</th><th>姓名</th><th>数据状态</th></tr>
            ${(family.members || []).map((m: any) => `
                <tr>
                    <td>${m.relation || '成员'}</td>
                    <td>${m.name || '-'}</td>
                    <td>${m.has_data ? '✅ 有数据' : '❌ 无数据'}</td>
                </tr>
            `).join('')}
        </table>
        
        <div class="summary-box">
            <strong>家庭资产汇总</strong><br>
            房产 ${family.summary?.assets?.real_estate_count || 0} 套 | 
            车辆 ${family.summary?.assets?.vehicle_count || 0} 辆 | 
            银行卡 ${totalBankAccounts} 张 | 
            资金总流入 ¥${formatWan(family.summary?.total_income || 0)} 万元 |
            资金总流出 ¥${formatWan(family.summary?.total_expense || 0)} 万元
        </div>
    </div>

    ${memberDetails.map((member: any, idx: number) => `
    <div class="section">
        <h2>三、${member.name || '成员'}（${member.relation || '成员'}）资金分析</h2>
        
        <h3>3.1 资金载体</h3>
        <table>
            <tr><th>银行</th><th>卡号</th><th>类型</th><th>余额</th></tr>
            ${(member.assets?.bank_accounts || []).slice(0, 10).map((acc: any) => `
                <tr>
                    <td>${acc.bank_name || acc.bank || '-'}</td>
                    <td>${acc.account_number || '-'}</td>
                    <td>${acc.account_type || acc.type || '-'}</td>
                    <td class="amount">¥${formatCurrency(acc.balance || 0)}</td>
                </tr>
            `).join('')}
        </table>
        ${(member.assets?.bank_accounts || []).length > 10 ? `<p style="color: #888; font-size: 12px;">（仅显示前10条，共${member.assets?.bank_accounts?.length}张卡）</p>` : ''}
        
        <h3>3.2 收支概况</h3>
        <table>
            <tr><th>指标</th><th>数值</th><th>备注</th></tr>
            <tr>
                <td>资金流入总额</td>
                <td class="amount">¥${formatWan(member.total_income || member.analysis?.inflow_analysis?.total_inflow || 0)} 万元</td>
                <td>-</td>
            </tr>
            <tr>
                <td>资金流出总额</td>
                <td class="amount">¥${formatWan(member.total_expense || member.analysis?.outflow_analysis?.total_outflow || 0)} 万元</td>
                <td>-</td>
            </tr>
            <tr>
                <td>交易笔数</td>
                <td class="amount">${(member.transaction_count || 0).toLocaleString()} 笔</td>
                <td>-</td>
            </tr>
            <tr>
                <td>工资收入总额</td>
                <td class="amount">¥${formatWan(member.assets?.salary_total || 0)} 万元</td>
                <td>-</td>
            </tr>
            <tr>
                <td>工资收入占比</td>
                <td class="amount">${(member.analysis?.income_gap?.ratio || 0).toFixed(1)}%</td>
                <td>${(member.analysis?.income_gap?.ratio || 0) < 50 ? '<span class="warning">低于50%，需核实</span>' : '正常'}</td>
            </tr>
            <tr>
                <td>来源不明收入</td>
                <td class="amount">¥${formatWan(member.analysis?.inflow_analysis?.unknown_source_amount || 0)} 万元</td>
                <td>${(member.analysis?.inflow_analysis?.unknown_source_ratio || 0) > 0.3 ? '<span class="warning">占比较高</span>' : '-'}</td>
            </tr>
        </table>
        
        ${(member.analysis?.income_gap?.ratio || 0) < 50 ? `
        <div class="issue-item issue-medium">
            ⚠ ${member.analysis?.income_gap?.verdict || '工资收入占比不足，需核实其他收入来源'}
        </div>
        ` : ''}
        
        ${(member.analysis?.large_transfers?.transactions || []).length > 0 ? `
        <h3>3.3 大额转账明细（前10笔）</h3>
        <table>
            <tr><th>日期</th><th>金额</th><th>方向</th><th>交易对手</th><th>摘要</th></tr>
            ${(member.analysis?.large_transfers?.transactions || []).slice(0, 10).map((tx: any) => `
                <tr>
                    <td>${tx.date ? tx.date.substring(0, 10) : '-'}</td>
                    <td class="amount">¥${formatCurrency(tx.amount || 0)}</td>
                    <td>${tx.direction === 'income' ? '收入' : '支出'}</td>
                    <td>${tx.counterparty || '-'}</td>
                    <td>${(tx.description || '-').substring(0, 20)}</td>
                </tr>
            `).join('')}
        </table>
        ` : ''}
    </div>
    `).join('')}

    ${companies.length > 0 ? `
    <div class="section">
        <h2>四、涉案公司分析</h2>
        ${companies.map((company: any) => `
        <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
            <h3 style="margin-top: 0;">${company.name || '未知公司'}</h3>
            <table>
                <tr><th>指标</th><th>数值</th></tr>
                <tr><td>资金规模</td><td class="amount">¥${formatWan(company.fund_scale?.total_income || 0)} 万元</td></tr>
                <tr><td>交易笔数</td><td class="amount">${(company.fund_scale?.transaction_count || 0).toLocaleString()} 笔</td></tr>
                <tr><td>与核心人员往来</td><td class="amount">¥${formatWan(company.related_person_transfers?.total_amount || 0)} 万元</td></tr>
            </table>
        </div>
        `).join('')}
    </div>
    ` : ''}

    <div class="section">
        <h2>五、综合研判与建议</h2>
        
        <div class="summary-box">
            <strong>研判结论</strong><br>
            ${conclusion.summary_text || '经分析，详见各模块具体内容。'}
        </div>
        
        <h3>5.1 问题清单</h3>
        ${(conclusion.issues || []).length > 0 ? `
        <table>
            <tr><th>人员</th><th>问题类型</th><th>说明</th><th>金额(万元)</th><th>风险等级</th></tr>
            ${(conclusion.issues || []).map((issue: any) => `
                <tr>
                    <td>${issue.person || '-'}</td>
                    <td>${issue.issue_type || '-'}</td>
                    <td>${issue.description || '-'}</td>
                    <td class="amount">${formatWan(issue.amount || 0)}</td>
                    <td><span class="${issue.severity === 'high' ? 'warning' : ''}">${issue.severity === 'high' ? '高' : issue.severity === 'medium' ? '中' : '低'}</span></td>
                </tr>
            `).join('')}
        </table>
        ` : '<p>未发现明显异常问题。</p>'}
        
        <h3>5.2 下一步工作建议</h3>
        <ol>
            ${(conclusion.next_steps || ['对相关人员进行进一步核实', '调取工商登记信息核实公司关系', '进一步核实大额资金来源']).map((step: string) => `<li>${step}</li>`).join('')}
        </ol>
    </div>

    <div style="margin-top: 60px; text-align: center; color: #888; font-size: 12px;">
        本报告由资金穿透审计系统自动生成，仅供参考
    </div>
</body>
</html>
        `;
    };

    const downloadReport = useCallback(() => {
        if (!previewHtml) return;

        const mimeType = format === 'html' || format === 'v3' ? 'text/html' : 'application/json';
        const extension = format === 'json' ? 'json' : 'html';
        
        const blob = new Blob([previewHtml], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${caseName}.${extension}`;
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
                            onClick={() => setFormat('v3')}
                            style={{
                                ...styles.formatButton,
                                ...(format === 'v3' ? styles.formatButtonActive : styles.formatButtonInactive)
                            }}
                        >
                            📋 v3.0 初查报告
                        </button>
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
