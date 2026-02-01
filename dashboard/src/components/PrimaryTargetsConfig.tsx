/**
 * 家庭归集配置组件
 *
 * 功能：
 * 1. 从 analysis_cache 读取家庭成员和公司列表
 * 2. 展示家庭单元，让用户调整主归集人和成员
 * 3. 支持创建/编辑家庭单元
 * 4. 保存配置到 primary_targets.json
 *
 * 家庭识别规则：
 * - 不同户籍地 = 不同家庭
 * - 同一户籍地 = 同一家庭
 * - 主归集人：默认为户主，用户可调整
 */

import { useState, useEffect, useCallback } from 'react';
import {
    Users, Building2, Plus, Trash2, Save, RefreshCw,
    ChevronDown, ChevronUp, Check, AlertTriangle, Info
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

// 类型定义
interface EntityInfo {
    name: string;
    has_data: boolean;
}

interface AnalysisUnitMember {
    name: string;
    relation: string;
    has_data: boolean;
}

interface AnalysisUnit {
    anchor: string;              // 主归集人（默认户主，可调整）
    members: string[];           // 家庭成员列表
    member_details?: AnalysisUnitMember[];
    address?: string;            // 家庭地址
    note?: string;
}

interface PrimaryTargetsConfig {
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

interface EntitiesResponse {
    persons: EntityInfo[];
    companies: EntityInfo[];
    family_summary?: {
        family_members?: string[];
        family_core?: string[];
    };
}

// 关系选项
const RELATION_OPTIONS = [
    '本人', '配偶', '子女', '父亲', '母亲', '兄弟', '姐妹', '其他亲属', '待确认'
];

interface PrimaryTargetsConfigProps {
    onConfigChange?: (config: PrimaryTargetsConfig | null) => void;
    className?: string;
}

export function PrimaryTargetsConfig({ onConfigChange, className }: PrimaryTargetsConfigProps) {
    // 状态
    const [config, setConfig] = useState<PrimaryTargetsConfig | null>(null);
    const [entities, setEntities] = useState<EntitiesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [isNew, setIsNew] = useState(false);
    const [expandedUnits, setExpandedUnits] = useState<Set<number>>(new Set([0]));
    const [showCompanies, setShowCompanies] = useState(true);

    // 加载配置和实体列表
    useEffect(() => {
        loadData();
    }, []);

    // 配置变化时通知父组件
    useEffect(() => {
        if (onConfigChange) {
            onConfigChange(config);
        }
    }, [config, onConfigChange]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            // 并行加载配置和实体列表
            const [configRes, entitiesRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/primary-targets`),
                fetch(`${API_BASE_URL}/api/primary-targets/entities`)
            ]);

            if (configRes.ok) {
                const configData = await configRes.json();
                if (configData.success) {
                    setConfig(configData.config);
                    setIsNew(configData.is_new || false);
                }
            }

            if (entitiesRes.ok) {
                const entitiesData = await entitiesRes.json();
                if (entitiesData.success) {
                    // 后端直接返回 persons 和 companies，不是包装在 data 对象中
                    setEntities({
                        persons: entitiesData.persons || [],
                        companies: entitiesData.companies || [],
                        family_summary: entitiesData.family_summary
                    });
                }
            }
        } catch (err) {
            console.error('加载归集配置失败:', err);
            setError('加载配置失败，请确保后端服务已启动');
        } finally {
            setLoading(false);
        }
    };

    // 保存配置
    const saveConfig = async () => {
        if (!config) return;

        setSaving(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/primary-targets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (data.success) {
                setSuccessMessage('配置已保存');
                setIsNew(false);
                setTimeout(() => setSuccessMessage(null), 3000);
            } else {
                setError(data.error || '保存失败');
            }
        } catch (err) {
            console.error('保存归集配置失败:', err);
            setError('保存失败，请检查网络连接');
        } finally {
            setSaving(false);
        }
    };

    // 重新生成默认配置
    const regenerateDefault = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/api/primary-targets/generate-default`, {
                method: 'POST'
            });
            const data = await response.json();
            if (data.success) {
                setConfig(data.config);
                setIsNew(true);
                setSuccessMessage('已重新生成默认配置');
                setTimeout(() => setSuccessMessage(null), 3000);
            } else {
                setError(data.error || '生成失败');
            }
        } catch (err) {
            setError('生成默认配置失败');
        } finally {
            setLoading(false);
        }
    };

    // 添加分析单元（只有家庭类型）
    const addUnit = () => {
        if (!config) return;

        const newUnit: AnalysisUnit = {
            anchor: '',
            members: [],
            member_details: [],
            note: '家庭单元'
        };

        const newConfig = {
            ...config,
            analysis_units: [...config.analysis_units, newUnit]
        };
        setConfig(newConfig);

        // 展开新添加的单元
        setExpandedUnits(prev => new Set([...prev, config.analysis_units.length]));
    };

    // 删除分析单元
    const removeUnit = (index: number) => {
        if (!config) return;

        const newUnits = config.analysis_units.filter((_, i) => i !== index);
        setConfig({ ...config, analysis_units: newUnits });
    };

    // 更新分析单元
    const updateUnit = (index: number, updates: Partial<AnalysisUnit>) => {
        if (!config) return;

        const newUnits = [...config.analysis_units];
        newUnits[index] = { ...newUnits[index], ...updates };
        setConfig({ ...config, analysis_units: newUnits });
    };

    // 添加成员到单元
    const addMemberToUnit = (unitIndex: number, personName: string) => {
        if (!config) return;

        const unit = config.analysis_units[unitIndex];
        if (unit.members.includes(personName)) return;

        const personInfo = entities?.persons.find(p => p.name === personName);

        const newMember: AnalysisUnitMember = {
            name: personName,
            relation: unit.members.length === 0 ? '本人' : '待确认',
            has_data: personInfo?.has_data ?? false
        };

        const newMembers = [...unit.members, personName];
        const newMemberDetails = [...(unit.member_details || []), newMember];

        // 如果是第一个成员，设置为锚点
        const anchor = newMembers.length === 1 ? personName : unit.anchor;

        updateUnit(unitIndex, {
            anchor,
            members: newMembers,
            member_details: newMemberDetails
        });
    };

    // 从单元移除成员
    const removeMemberFromUnit = (unitIndex: number, personName: string) => {
        if (!config) return;

        const unit = config.analysis_units[unitIndex];
        const newMembers = unit.members.filter(m => m !== personName);
        const newMemberDetails = (unit.member_details || []).filter(m => m.name !== personName);

        // 如果移除的是锚点，选择第一个成员作为新锚点
        const anchor = personName === unit.anchor && newMembers.length > 0
            ? newMembers[0]
            : (newMembers.includes(unit.anchor) ? unit.anchor : '');

        updateUnit(unitIndex, {
            anchor,
            members: newMembers,
            member_details: newMemberDetails
        });
    };

    // 更新成员关系
    const updateMemberRelation = (unitIndex: number, personName: string, relation: string) => {
        if (!config) return;

        const unit = config.analysis_units[unitIndex];
        const newMemberDetails = (unit.member_details || []).map(m =>
            m.name === personName ? { ...m, relation } : m
        );

        updateUnit(unitIndex, { member_details: newMemberDetails });
    };

    // 设置锚点（主核查对象）
    const setAnchor = (unitIndex: number, personName: string) => {
        updateUnit(unitIndex, { anchor: personName });
    };

    // 切换公司选择
    const toggleCompany = (companyName: string) => {
        if (!config) return;

        const included = config.include_companies.includes(companyName);
        const newCompanies = included
            ? config.include_companies.filter(c => c !== companyName)
            : [...config.include_companies, companyName];

        setConfig({ ...config, include_companies: newCompanies });
    };

    // 切换单元展开/折叠
    const toggleUnitExpand = (index: number) => {
        setExpandedUnits(prev => {
            const newSet = new Set(prev);
            if (newSet.has(index)) {
                newSet.delete(index);
            } else {
                newSet.add(index);
            }
            return newSet;
        });
    };

    // 检查成员关系是否违反铁律（已移除，不再有此限制）
    // 不同住址的家庭会自动识别为独立家庭

    // 获取可选的人员（未被分配到任何单元的人员）
    const getAvailablePersons = useCallback((excludeUnitIndex?: number) => {
        if (!entities || !config) {
            console.log('[getAvailablePersons] entities or config missing', { entities, config });
            return [];
        }

        const assignedPersons = new Set<string>();
        config.analysis_units.forEach((unit, idx) => {
            if (idx !== excludeUnitIndex) {
                unit.members.forEach(m => assignedPersons.add(m));
            }
        });

        const available = entities.persons.filter(p => !assignedPersons.has(p.name));
        console.log('[getAvailablePersons] excludeUnitIndex:', excludeUnitIndex,
            'assignedPersons:', Array.from(assignedPersons),
            'entities.persons:', entities.persons.map(p => p.name),
            'available:', available.map(p => p.name));

        return available;
    }, [entities, config]);

    if (loading) {
        return (
            <div className={`primary-targets-config p-4 theme-bg-muted rounded-xl ${className || ''}`}>
                <div className="flex items-center justify-center h-40 theme-text-dim">
                    <RefreshCw className="animate-spin mr-2" size={20} />
                    加载归集配置...
                </div>
            </div>
        );
    }

    if (error && !config) {
        return (
            <div className={`primary-targets-config p-4 theme-bg-muted rounded-xl ${className || ''}`}>
                <div className="flex flex-col items-center justify-center h-40 text-red-400">
                    <AlertTriangle size={32} className="mb-2" />
                    <p>{error}</p>
                    <button
                        onClick={loadData}
                        className="mt-3 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600"
                    >
                        重试
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={`primary-targets-config ${className || ''}`}>
            {/* 标题栏 */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Users size={18} className="text-blue-400" />
                    <h3 className="text-base font-semibold theme-text">归集配置</h3>
                    {isNew && (
                        <span className="px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded">
                            未保存
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={regenerateDefault}
                        className="px-3 py-1.5 text-xs border theme-border rounded-md theme-bg-base theme-text-muted hover:theme-bg-hover flex items-center gap-1"
                        title="重新生成默认配置"
                    >
                        <RefreshCw size={12} />
                        重置
                    </button>
                    <button
                        onClick={saveConfig}
                        disabled={saving}
                        className={`px-3 py-1.5 text-xs rounded-md flex items-center gap-1 ${saving
                            ? 'bg-gray-500 text-gray-300 cursor-not-allowed'
                            : 'bg-green-500 text-white hover:bg-green-600'
                            }`}
                    >
                        <Save size={12} />
                        {saving ? '保存中...' : '保存配置'}
                    </button>
                </div>
            </div>

            {/* 提示信息 */}
            {successMessage && (
                <div className="mb-3 p-2 bg-green-500/10 border border-green-500/30 rounded-md text-green-400 text-xs flex items-center gap-2">
                    <Check size={14} />
                    {successMessage}
                </div>
            )}
            {error && (
                <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-md text-red-400 text-xs">
                    ❌ {error}
                </div>
            )}

            {/* 说明文字 */}
            <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs theme-text-muted">
                <div className="flex items-start gap-2">
                    <Info size={14} className="text-blue-400 mt-0.5 flex-shrink-0" />
                    <div>
                        <p className="mb-1"><strong>归集规则：</strong></p>
                        <ul className="list-disc list-inside space-y-0.5 text-xs">
                            <li><strong>家庭识别</strong>：不同户籍地自动识别为不同家庭</li>
                            <li><strong>主归集人</strong>：默认为户主，可根据核查需要调整</li>
                            <li><strong>灵活配置</strong>：支持添加/删除家庭、调整成员、设置主归集人</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* 分析单元列表 */}
            <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium theme-text-muted">分析单元</h4>
                    <div className="flex gap-1">
                        <button
                            onClick={() => addUnit()}
                            className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 flex items-center gap-1"
                        >
                            <Plus size={12} />
                            添加家庭
                        </button>
                    </div>
                </div>

                <div className="space-y-2 max-h-[300px] overflow-auto pr-1">
                    {config?.analysis_units.map((unit, unitIndex) => {
                        const isExpanded = expandedUnits.has(unitIndex);
                        const availablePersons = getAvailablePersons(unitIndex);

                        return (
                            <div
                                key={unitIndex}
                                className="border rounded-lg overflow-hidden border-blue-500/30 bg-blue-500/5"
                            >
                                {/* 单元头部 */}
                                <div
                                    className="flex items-center justify-between p-2 cursor-pointer hover:bg-white/5"
                                    onClick={() => toggleUnitExpand(unitIndex)}
                                >
                                    <div className="flex items-center gap-2">
                                        <span className="px-1.5 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400">
                                            家庭
                                        </span>
                                        <span className="text-sm font-medium theme-text">
                                            {unit.anchor || '(未设置主归集人)'}
                                        </span>
                                        <span className="text-xs theme-text-dim">
                                            ({unit.members.length}人)
                                        </span>
                                        {unit.address && (
                                            <span className="text-xs theme-text-dim">
                                                {unit.address}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removeUnit(unitIndex);
                                            }}
                                            className="p-1 hover:bg-red-500/20 rounded text-red-400"
                                            title="删除单元"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                    </div>
                                </div>

                                {/* 单元详情 */}
                                {isExpanded && (
                                    <div className="p-3 border-t border-white/10">
                                        {/* 成员列表 */}
                                        <div className="mb-3">
                                            <label className="text-xs theme-text-dim mb-1 block">成员列表</label>
                                            <div className="space-y-1">
                                                {unit.member_details?.map((member) => (
                                                    <div
                                                        key={member.name}
                                                        className="flex items-center gap-2 p-1.5 bg-white/5 rounded"
                                                    >
                                                        <button
                                                            onClick={() => setAnchor(unitIndex, member.name)}
                                                            className={`p-0.5 rounded ${
                                                                unit.anchor === member.name
                                                                    ? 'bg-green-500 text-white'
                                                                    : 'bg-gray-600 text-gray-400 hover:bg-gray-500'
                                                            }`}
                                                            title={unit.anchor === member.name ? '主归集人' : '设为主归集人'}
                                                        >
                                                            <Check size={12} />
                                                        </button>
                                                        <span className={`flex-1 text-sm ${member.has_data ? 'theme-text' : 'theme-text-dim'}`}>
                                                            {member.name}
                                                            {!member.has_data && <span className="text-xs text-red-400 ml-1">(无数据)</span>}
                                                        </span>
                                                        <select
                                                            value={member.relation}
                                                            onChange={(e) => updateMemberRelation(unitIndex, member.name, e.target.value)}
                                                            className="px-1.5 py-0.5 text-xs bg-gray-700 border border-gray-600 rounded"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            {RELATION_OPTIONS.map(rel => (
                                                                <option key={rel} value={rel}>{rel}</option>
                                                            ))}
                                                        </select>
                                                        <button
                                                            onClick={() => removeMemberFromUnit(unitIndex, member.name)}
                                                            className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                                                        >
                                                            <Trash2 size={12} />
                                                        </button>
                                                    </div>
                                                ))}
                                                {unit.members.length === 0 && (
                                                    <div className="text-xs theme-text-dim text-center py-2">
                                                        暂无成员，请从下方添加
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* 添加成员 */}
                                        {availablePersons.length > 0 && (
                                            <div>
                                                <label className="text-xs theme-text-dim mb-1 block">添加成员</label>
                                                <div className="flex flex-wrap gap-1">
                                                    {availablePersons.slice(0, 10).map(person => (
                                                        <button
                                                            key={person.name}
                                                            onClick={() => addMemberToUnit(unitIndex, person.name)}
                                                            className={`px-2 py-1 text-xs rounded border ${person.has_data
                                                                ? 'border-green-500/30 bg-green-500/10 text-green-400 hover:bg-green-500/20'
                                                                : 'border-gray-500/30 bg-gray-500/10 text-gray-400 hover:bg-gray-500/20'
                                                                }`}
                                                        >
                                                            + {person.name}
                                                        </button>
                                                    ))}
                                                    {availablePersons.length > 10 && (
                                                        <span className="text-xs theme-text-dim py-1">
                                                            +{availablePersons.length - 10} 更多
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}

                    {config?.analysis_units.length === 0 && (
                        <div className="text-center py-6 theme-text-dim text-sm">
                            暂无分析单元，请点击上方按钮添加
                        </div>
                    )}
                </div>
            </div>

            {/* 涉案公司 */}
            <div className="mb-4">
                <div
                    className="flex items-center justify-between mb-2 cursor-pointer"
                    onClick={() => setShowCompanies(!showCompanies)}
                >
                    <div className="flex items-center gap-2">
                        <Building2 size={14} className="text-orange-400" />
                        <h4 className="text-sm font-medium theme-text-muted">涉案公司</h4>
                        <span className="text-xs theme-text-dim">
                            (已选 {config?.include_companies.length || 0}/{entities?.companies.length || 0})
                        </span>
                    </div>
                    {showCompanies ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>

                {showCompanies && (
                    <div className="flex flex-wrap gap-1.5 max-h-[120px] overflow-auto">
                        {entities?.companies.map(company => {
                            const isSelected = config?.include_companies.includes(company.name);
                            return (
                                <button
                                    key={company.name}
                                    onClick={() => toggleCompany(company.name)}
                                    className={`px-2 py-1 text-xs rounded border transition-colors ${isSelected
                                        ? 'border-orange-500 bg-orange-500/20 text-orange-400'
                                        : 'border-gray-600 bg-gray-700/50 theme-text-dim hover:bg-gray-700'
                                        }`}
                                >
                                    {isSelected && <Check size={10} className="inline mr-1" />}
                                    {company.name}
                                </button>
                            );
                        })}
                        {entities?.companies.length === 0 && (
                            <span className="text-xs theme-text-dim">无涉案公司</span>
                        )}
                    </div>
                )}
            </div>

            {/* 案件信息 */}
            <div className="space-y-3">
                <div>
                    <label className="block text-xs font-medium theme-text-muted mb-1">核查对象所在单位</label>
                    <input
                        type="text"
                        value={config?.employer || ''}
                        onChange={(e) => setConfig(config ? { ...config, employer: e.target.value } : null)}
                        className="w-full px-3 py-2 text-sm border theme-border rounded-md theme-bg-base theme-text"
                        placeholder="如：XX市XX局"
                    />
                </div>
                <div>
                    <label className="block text-xs font-medium theme-text-muted mb-1">案件来源</label>
                    <input
                        type="text"
                        value={config?.case_source || ''}
                        onChange={(e) => setConfig(config ? { ...config, case_source: e.target.value } : null)}
                        className="w-full px-3 py-2 text-sm border theme-border rounded-md theme-bg-base theme-text"
                        placeholder="如：群众举报、巡视发现"
                    />
                </div>
            </div>
        </div>
    );
}

export default PrimaryTargetsConfig;
