import { useEffect, useRef, useState } from 'react';
import { Network, DataSet } from 'vis-network/standalone';
import type { Data, Node, Edge, Options } from 'vis-network/standalone';
import { API_BASE_URL } from '../services/api';
import {
  AlertTriangle,
  CreditCard,
  Landmark,
  Info,
  X,
  ExternalLink,
  FileText,
  ChevronDown,
  ChevronUp,
  Users,
  Building2
} from 'lucide-react';
import { formatPartyName, formatRiskLevel, getRiskLevelBadgeStyle } from '../utils/formatters';

// 交易详情接口
interface TransactionDetail {
  type: 'loan_pair' | 'no_repayment' | 'high_risk_income' | 'online_loan';
  person: string;
  counterparty: string;
  amount: number;
  repayAmount?: number;
  daysSince?: number;
  riskLevel?: string;
  platform?: string;
  // 扩展字段（从后端获取）
  date?: string;
  description?: string;
  bank?: string;
  sourceFile?: string;
  sourceRow?: number;
  detail?: string;  // 原始交易详细信息
  incomeType?: string; // 收入类型
}

interface TransactionRef {
  date?: string;
  amount?: number;
  source_file?: string;
  source_row_index?: number;
  description?: string;
  direction?: string;
  counterparty_raw?: string;
}

interface BasePathExplainability {
  path_type?: string;
  summary?: string;
  inspection_points?: string[];
  path?: string;
  nodes?: string[];
  evidence_template?: {
    headline?: string;
    summary?: string;
    key_points?: string[];
    metrics?: Array<{ label?: string; value?: string }>;
    supporting_refs?: {
      kind?: string;
      returned?: number;
      total?: number;
      truncated?: boolean;
      notice?: string;
    };
  };
}

interface CycleEdgeSegment {
  index?: number;
  from?: string;
  to?: string;
  amount?: number;
  transaction_count?: number;
  transaction_refs_total?: number;
  transaction_ref_sample_count?: number;
  transaction_refs_returned?: number;
  transaction_refs_truncated?: boolean;
  transaction_refs_limit?: number;
  transaction_refs?: TransactionRef[];
}

interface CyclePathExplainability extends BasePathExplainability {
  edge_segments?: CycleEdgeSegment[];
  bottleneck_edge?: {
    from?: string;
    to?: string;
    amount?: number;
  };
}

interface RelayTimeAxisEvent {
  step?: number;
  event_type?: string;
  time?: string;
  label?: string;
  amount?: number;
  source_file?: string;
  source_row_index?: number;
}

interface RelayPathExplainability extends BasePathExplainability {
  time_axis?: RelayTimeAxisEvent[];
  time_axis_total?: number;
  time_axis_sample_count?: number;
  time_axis_truncated?: boolean;
  sequence_summary?: string;
}

interface DirectFlowPathExplainability extends BasePathExplainability {
  amount?: number;
  direction?: string;
  transaction_refs?: TransactionRef[];
  transaction_refs_total?: number;
  transaction_ref_sample_count?: number;
  transaction_refs_truncated?: boolean;
}

type RepresentativePathExplainability =
  | CyclePathExplainability
  | RelayPathExplainability
  | DirectFlowPathExplainability
  | BasePathExplainability;

interface RelationshipRepresentativePath {
  path_type?: string;
  path?: string;
  nodes?: string[];
  amount?: number;
  risk_score?: number;
  confidence?: number;
  priority_score?: number;
  priority_reason?: string;
  summary?: string;
  inspection_points?: string[];
  path_explainability?: RepresentativePathExplainability;
  evidence_template?: BasePathExplainability['evidence_template'];
}

interface RelationshipClusterPathExplainability extends BasePathExplainability {
  representative_path_count?: number;
  representative_paths?: RelationshipRepresentativePath[];
}

interface LinkedSelection {
  id: string;
  type: 'fund_cycle' | 'third_party_relay' | 'relationship_cluster' | 'cluster_representative_path';
  label: string;
  path?: string;
  nodes: string[];
  riskScore?: number;
  sectionKeys: string[];
}

interface NetworkGraphProps {
  onLog?: (message: string) => void;
}

interface GraphData {
  nodes: Node[];
  edges: Edge[];
  sampling: {
    totalNodes: number;
    totalEdges: number;
    sampledNodes: number;
    sampledEdges: number;
    message: string;
  };
  stats: {
    nodeCount: number;
    edgeCount: number;
    corePersonCount: number;
    corePersonNames: string[];
    involvedCompanyCount: number;
    highRiskCount: number;
    mediumRiskCount: number;
    loanPairCount: number;
    noRepayCount: number;
    discoveredNodeCount: number;
    relationshipClusterCount: number;
    coreEdgeCount: number;
    companyEdgeCount: number;
    otherEdgeCount: number;
  };
  report: {
    loan_pairs: Array<{
      person: string;
      counterparty: string;
      income_total: number;  // 借入总额
      expense_total: number; // 还款总额
      income_count?: number;
      expense_count?: number;
      loan_type?: string;
      ratio?: number;
      risk_level?: string;
    }>;
    no_repayment_loans: Array<{
      person: string;
      counterparty: string;
      income_amount: number;
      days_since: number;
    }>;
    high_risk_income: Array<{
      person: string;
      counterparty: string;
      amount: number;
      risk_level?: string;
      type?: string;  // 收入类型
      detail?: string; // 原始交易详情
      source_file?: string; // 来源文件
      source_row?: number;  // 行号
    }>;
    online_loans: Array<{
      platform: string;
      amount: number;
    }>;
    third_party_relays: Array<{
      from: string;
      relay: string;
      to: string;
      outflow_amount?: number;
      inflow_amount?: number;
      amount_diff?: number;
      time_diff_hours?: number;
      risk_score?: number;
      risk_level?: string;
      confidence?: number;
      evidence?: string[];
      path_explainability?: RelayPathExplainability;
    }>;
    focus_entities: Array<{
      name: string;
      risk_score: number;
      risk_level?: string;
      risk_confidence?: number;
      high_priority_clue_count?: number;
      top_evidence_score?: number;
      summary?: string;
      top_clues?: string[];
      in_graph?: boolean;
      graph_node_id?: string | number;
      graph_group?: string;
    }>;
    aggregation_summary?: {
      极高风险实体数?: number;
      高风险实体数?: number;
      中风险实体数?: number;
      高优先线索实体数?: number;
    };
    aggregation_metadata?: Record<string, unknown>;
    discovered_nodes: Array<{
      name: string;
      node_type?: string;
      occurrences?: number;
      relation_types?: string[];
      linked_cores?: string[];
      total_amount?: number;
      risk_score?: number;
      risk_level?: string;
      confidence?: number;
      evidence?: string[];
      path_explainability?: RelayPathExplainability;
    }>;
    relationship_clusters: Array<{
      cluster_id: string;
      core_members: string[];
      external_members: string[];
      all_nodes?: string[];
      relation_types?: string[];
      direct_flow_count?: number;
      relay_count?: number;
      loop_count?: number;
      total_amount?: number;
      risk_score?: number;
      risk_level?: string;
      confidence?: number;
      evidence?: string[];
      path_explainability?: RelationshipClusterPathExplainability;
    }>;
    fund_cycles: Array<{
      path?: string;
      nodes?: string[];
      participants?: string[];
      length?: number;
      total_amount?: number;
      risk_score?: number;
      risk_level?: string;
      confidence?: number;
      evidence?: string[];
      path_explainability?: CyclePathExplainability;
    }>;
    fund_cycle_meta?: {
      truncated?: boolean;
      timed_out?: boolean;
      truncated_reasons?: string[];
      timeout_seconds?: number;
      requested_start_nodes?: number;
      searched_start_nodes?: number;
      returned_count?: number;
    };
  };
}

function NetworkGraph({ onLog }: NetworkGraphProps) {
  const htmlReportName = '资金流向可视化.html';
  const excelReportName = '资金核查底稿.xlsx';
  const htmlReportUrl = `${API_BASE_URL}/api/reports/preview/${encodeURIComponent(htmlReportName)}`;
  const excelReportUrl = `${API_BASE_URL}/api/reports/download/${encodeURIComponent(excelReportName)}`;
  const networkRef = useRef<HTMLDivElement>(null);
  const networkInstance = useRef<Network | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ label: string; group: string } | null>(null);
  const [activeSelection, setActiveSelection] = useState<LinkedSelection | null>(null);
  const [viewMode, setViewMode] = useState<'graph' | 'report'>('graph');
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  // P0-1: 交易详情 Modal 状态
  const [transactionDetail, setTransactionDetail] = useState<TransactionDetail | null>(null);
  // 导出快照引用（保留用于未来功能）
  const exportRef = useRef<HTMLDivElement>(null);
  // 左侧菜单展开状态
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const discoveredNodes = graphData?.report.discovered_nodes || [];
  const relationshipClusters = graphData?.report.relationship_clusters || [];
  const fundCycles = graphData?.report.fund_cycles || [];
  const thirdPartyRelays = graphData?.report.third_party_relays || [];
  const focusEntities = graphData?.report.focus_entities || [];
  const aggregationSummary = graphData?.report.aggregation_summary || {};
  
  // 切换展开/折叠状态
  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const expandSections = (sections: string[]) => {
    if (sections.length === 0) {
      return;
    }
    setExpandedSections(prev => {
      const next = { ...prev };
      sections.forEach(section => {
        next[section] = true;
      });
      return next;
    });
  };

  // 格式化金额显示 - 统一使用万元单位（P2: 金额单位统一）
  const formatAmount = (amount: number) => {
    // 统一使用万元单位，保留2位小数
    const wan = amount / 10000;
    if (wan >= 0.01) {
      return `¥${wan.toFixed(2)}万`;
    }
    // 不足0.01万（100元）的显示原值
    return `¥${amount.toFixed(2)}`;
  };

  // 格式化对手方名称 - 标注未知来源（P1: 未知对手方问题）
  const formatCounterpartyWithWarning = (name: string) => {
    if (!name || name === '未知' || name === '(未知)' || name === 'nan' || name.length < 2) {
      return <span className="text-orange-400 font-medium">⚠ 来源不明</span>;
    }
    return formatPartyName(name);
  };

  const relationTypeLabels: Record<string, string> = {
    direct_flow: '直接往来',
    third_party_relay: '第三方中转',
    fund_loop: '资金闭环',
    fund_cycle: '资金闭环',
    relationship_cluster: '关系簇',
  };
  const fundCycleMeta = graphData?.report.fund_cycle_meta || {};

  const formatRelationTypes = (relationTypes?: string[]) => {
    if (!relationTypes || relationTypes.length === 0) {
      return '关系类型待补充';
    }
    return relationTypes.map(type => relationTypeLabels[type] || type).join(' / ');
  };

  const formatOptionalAmount = (amount?: number) => {
    if (!amount || amount <= 0) {
      return '金额待估';
    }
    return formatAmount(amount);
  };

  const formatConfidence = (confidence?: number) => {
    if (confidence === undefined || confidence === null) {
      return '置信度待估';
    }
    return `置信度 ${(confidence * 100).toFixed(0)}%`;
  };

  const formatEvidence = (evidence?: string[], limit = 2) => {
    if (!evidence || evidence.length === 0) {
      return '';
    }
    return evidence.slice(0, limit).join('；');
  };

  const formatPathSummary = (payload?: { summary?: string }) => {
    const summary = payload?.summary?.trim();
    return summary || '';
  };

  const formatInspectionPoints = (
    payload?: { inspection_points?: string[] },
    limit = 2,
  ) => {
    if (!payload?.inspection_points || payload.inspection_points.length === 0) {
      return '';
    }
    return payload.inspection_points
      .slice(0, limit)
      .map(point => point.trim())
      .filter(Boolean)
      .join('；');
  };

  const formatCycleEdgeSegments = (
    payload?: CyclePathExplainability,
  ) => {
    if (!payload?.edge_segments || payload.edge_segments.length === 0) {
      return '';
    }
    const lines = payload.edge_segments
      .slice(0, 3)
      .map(segment => {
        const amount = Number(segment.amount || 0);
        return `第${segment.index || 0}跳 ${segment.from || '未知'} -> ${segment.to || '未知'} ${formatOptionalAmount(amount)}`;
      });
    if (payload.bottleneck_edge?.from && payload.bottleneck_edge?.to) {
      const amount = Number(payload.bottleneck_edge.amount || 0);
      lines.push(`瓶颈边 ${payload.bottleneck_edge.from} -> ${payload.bottleneck_edge.to} ${formatOptionalAmount(amount)}`);
    }
    return lines.join('；');
  };

  const formatRelayTimeAxis = (
    payload?: RelayPathExplainability,
  ) => {
    const parts: string[] = [];
    if (payload?.sequence_summary?.trim()) {
      parts.push(payload.sequence_summary.trim());
    }
    if (payload?.time_axis && payload.time_axis.length > 0) {
      parts.push(
        payload.time_axis
          .slice(0, 2)
          .map(event => {
            const file = event.source_file
              ? ` ${event.source_file}${event.source_row_index !== undefined && event.source_row_index !== null ? ` 第${event.source_row_index}行` : ''}`
              : '';
            return `${event.time || '未知时间'} ${event.label || '未知事件'} ${formatOptionalAmount(Number(event.amount || 0))}${file}`;
          })
          .join('；'),
      );
    }
    return parts.join('；');
  };

  const getSegmentTransactionTotal = (segment?: CycleEdgeSegment) => {
    if (!segment) {
      return 0;
    }
    const refs = segment.transaction_refs || [];
    return Math.max(
      Number(segment.transaction_refs_total || segment.transaction_count || 0),
      refs.length,
    );
  };

  const getSegmentReturnedCount = (segment?: CycleEdgeSegment) => {
    if (!segment) {
      return 0;
    }
    const refs = segment.transaction_refs || [];
    return Math.max(Number(segment.transaction_refs_returned || 0), refs.length);
  };

  const getTimeAxisTotal = (payload?: RelayPathExplainability) => {
    if (!payload) {
      return 0;
    }
    const events = payload.time_axis || [];
    return Math.max(Number(payload.time_axis_total || 0), events.length);
  };

  const getRepresentativePathPayload = (
    representativePath?: RelationshipRepresentativePath,
  ): RepresentativePathExplainability | undefined => {
    if (!representativePath) {
      return undefined;
    }
    if (representativePath.path_explainability) {
      return representativePath.path_explainability;
    }
    if (representativePath.path || representativePath.summary || representativePath.inspection_points) {
      return {
        path_type: representativePath.path_type,
        path: representativePath.path,
        nodes: representativePath.nodes,
        summary: representativePath.summary,
        inspection_points: representativePath.inspection_points,
      };
    }
    return undefined;
  };

  const getRepresentativePathNodes = (
    representativePath?: RelationshipRepresentativePath,
  ) => {
    const payload = getRepresentativePathPayload(representativePath);
    const payloadNodes = payload?.nodes || [];
    if (payloadNodes.length > 0) {
      return payloadNodes.filter(Boolean);
    }
    const nodes = representativePath?.nodes || [];
    if (nodes.length > 0) {
      return nodes.filter(Boolean);
    }
    const rawPath = String(representativePath?.path || '').trim();
    if (!rawPath) {
      return [];
    }
    return rawPath
      .split('→')
      .map(node => node.trim())
      .filter(Boolean);
  };

  const getDirectFlowRefTotal = (payload?: DirectFlowPathExplainability) => {
    if (!payload) {
      return 0;
    }
    const refs = payload.transaction_refs || [];
    return Math.max(Number(payload.transaction_refs_total || 0), refs.length);
  };

  const findGraphNodesByNames = (names: string[]) => {
    if (!graphData) {
      return [];
    }
    const normalizedNames = new Set(
      names
        .map(name => String(name || '').trim())
        .filter(Boolean),
    );
    return graphData.nodes.filter(node => {
      const nodeId = String(node.id || '').trim();
      const nodeLabel = String(node.label || '').trim();
      return normalizedNames.has(nodeId) || normalizedNames.has(nodeLabel);
    });
  };

  const resolveGraphNodeNameById = (nodeId: string | number) => {
    const matchedNode = graphData?.nodes.find(node => String(node.id) === String(nodeId));
    return String(matchedNode?.label || matchedNode?.id || nodeId).trim();
  };

  const focusGraphNodes = (names: string[], label: string) => {
    if (!networkInstance.current) {
      return;
    }
    const matchedNodes = findGraphNodesByNames(names);
    if (matchedNodes.length === 0) {
      onLog?.(`${label} 未在当前采样图中展示`);
      return;
    }

    const nodeIds = matchedNodes.map(node => node.id);
    networkInstance.current.selectNodes(nodeIds);
    networkInstance.current.fit({
      nodes: nodeIds,
      animation: {
        duration: 500,
        easingFunction: 'easeInOutQuad',
      },
    });

    const firstNode = matchedNodes[0];
    setSelectedNode({
      label: formatPartyName(String(firstNode.label || firstNode.id || label)),
      group: String(firstNode.group || 'other'),
    });
    onLog?.(`图谱已定位 ${label}: ${matchedNodes.map(node => String(node.label || node.id)).join('、')}`);
  };

  const getCycleNodes = (cycle: GraphData['report']['fund_cycles'][number]) => {
    const nodes = cycle.path_explainability?.nodes || cycle.nodes || cycle.participants || [];
    return nodes.map(node => String(node || '').trim()).filter(Boolean);
  };

  const getRelayNodes = (relay: GraphData['report']['third_party_relays'][number]) => {
    return (
      relay.path_explainability?.nodes ||
      [relay.from, relay.relay, relay.to]
    )
      .map(node => String(node || '').trim())
      .filter(Boolean);
  };

  const getClusterNodes = (cluster: GraphData['report']['relationship_clusters'][number]) => {
    return (
      cluster.all_nodes ||
      [...(cluster.core_members || []), ...(cluster.external_members || [])]
    )
      .map(node => String(node || '').trim())
      .filter(Boolean);
  };

  const getSelectionEdges = (selection: LinkedSelection) => {
    const edges: Array<[string, string]> = [];
    const nodes = selection.nodes || [];
    if (nodes.length < 2) {
      return edges;
    }
    for (let idx = 0; idx < nodes.length - 1; idx += 1) {
      edges.push([nodes[idx], nodes[idx + 1]]);
    }
    if (selection.type === 'fund_cycle' && nodes.length > 2) {
      edges.push([nodes[nodes.length - 1], nodes[0]]);
    }
    return edges;
  };

  const buildLinkedSelections = (): LinkedSelection[] => {
    if (!graphData) {
      return [];
    }

    const selections: LinkedSelection[] = [];

    fundCycles.forEach((cycle, idx) => {
      selections.push({
        id: `fund_cycle:${idx}`,
        type: 'fund_cycle',
        label: `资金闭环 ${idx + 1}`,
        path: getCyclePath(cycle),
        nodes: getCycleNodes(cycle),
        riskScore: cycle.risk_score,
        sectionKeys: ['fundCycles', `fundCycle:${idx}:details`],
      });
    });

    thirdPartyRelays.forEach((relay, idx) => {
      selections.push({
        id: `third_party_relay:${idx}`,
        type: 'third_party_relay',
        label: `第三方中转 ${idx + 1}`,
        path: relay.path_explainability?.path || `${relay.from} → ${relay.relay} → ${relay.to}`,
        nodes: getRelayNodes(relay),
        riskScore: relay.risk_score,
        sectionKeys: ['thirdPartyRelays', `relay:${idx}:details`],
      });
    });

    relationshipClusters.forEach((cluster, idx) => {
      selections.push({
        id: `relationship_cluster:${idx}`,
        type: 'relationship_cluster',
        label: `关系簇 ${cluster.cluster_id || idx + 1}`,
        path: cluster.path_explainability?.path || cluster.cluster_id,
        nodes: getClusterNodes(cluster),
        riskScore: cluster.risk_score,
        sectionKeys: ['relationshipClusters'],
      });

      (cluster.path_explainability?.representative_paths || []).forEach((representativePath, pathIdx) => {
        selections.push({
          id: `cluster_representative_path:${idx}:${pathIdx}`,
          type: 'cluster_representative_path',
          label: `关系簇代表路径 ${idx + 1}-${pathIdx + 1}`,
          path: representativePath.path || representativePath.path_explainability?.path,
          nodes: getRepresentativePathNodes(representativePath),
          riskScore: representativePath.risk_score,
          sectionKeys: ['relationshipClusters', `cluster:${idx}:paths`, `cluster:${idx}:path:${pathIdx}`],
        });
      });
    });

    return selections.filter(selection => selection.nodes.length > 0);
  };

  const getSelectionTypePriority = (selectionType: LinkedSelection['type']) => {
    switch (selectionType) {
      case 'fund_cycle':
        return 50;
      case 'third_party_relay':
        return 45;
      case 'cluster_representative_path':
        return 40;
      case 'relationship_cluster':
        return 10;
      default:
        return 0;
    }
  };

  const activateSelection = (
    selection: LinkedSelection,
    options?: { focusGraph?: boolean; logMessage?: boolean },
  ) => {
    setActiveSelection(selection);
    expandSections(selection.sectionKeys);

    if (options?.focusGraph !== false) {
      focusGraphNodes(selection.nodes, selection.path || selection.label);
    } else if (options?.logMessage !== false) {
      onLog?.(`右侧已联动到 ${selection.label}: ${selection.path || selection.nodes.join(' → ')}`);
    }
  };

  const syncPanelToGraphSelection = (params: { nodeNames: string[]; edgePair?: [string, string] | null }) => {
    const linkedSelections = buildLinkedSelections();
    if (linkedSelections.length === 0) {
      return;
    }

    const clickedNodeSet = new Set(
      params.nodeNames
        .map(node => String(node || '').trim())
        .filter(Boolean),
    );
    if (clickedNodeSet.size === 0 && !params.edgePair) {
      return;
    }

    const scored = linkedSelections
      .map(selection => {
        const selectionNodeSet = new Set(selection.nodes);
        const overlapCount = Array.from(clickedNodeSet).filter(node => selectionNodeSet.has(node)).length;
        const hasEdgeMatch = Boolean(params.edgePair) && getSelectionEdges(selection).some(
          ([from, to]) => (
            (from === params.edgePair?.[0] && to === params.edgePair?.[1]) ||
            (from === params.edgePair?.[1] && to === params.edgePair?.[0])
          ),
        );
        if (overlapCount === 0 && !hasEdgeMatch) {
          return null;
        }
        let score = overlapCount * 100 + getSelectionTypePriority(selection.type) + Number(selection.riskScore || 0);
        if (hasEdgeMatch) {
          score += 500;
        }
        score -= selection.nodes.length;
        return { selection, score };
      })
      .filter((item): item is { selection: LinkedSelection; score: number } => Boolean(item))
      .sort((a, b) => b.score - a.score);

    if (scored.length === 0) {
      return;
    }

    activateSelection(scored[0].selection, { focusGraph: false, logMessage: false });
  };

  const isActiveSelection = (selectionId: string) => activeSelection?.id === selectionId;

  const getCyclePath = (cycle: GraphData['report']['fund_cycles'][number]) => {
    if (cycle.path) {
      return cycle.path;
    }
    const nodes = cycle.nodes || cycle.participants || [];
    if (nodes.length === 0) {
      return '未知路径';
    }
    return [...nodes, nodes[0]].join(' → ');
  };

  const focusEntityInGraph = (entity: GraphData['report']['focus_entities'][number]) => {
    if (!graphData) {
      return null;
    }
    return graphData.nodes.find(node =>
      node.id === entity.graph_node_id ||
      node.id === entity.name ||
      node.label === entity.name
    ) || null;
  };

  const focusGraphEntity = (entity: GraphData['report']['focus_entities'][number]) => {
    focusGraphNodes([entity.name], `重点对象 ${entity.name}`);
  };

  useEffect(() => {
    // Check if report exists (only run once on mount)
    fetch(htmlReportUrl, { method: 'HEAD' })
      .then(res => {
        if (res.ok) {
          setReportUrl(htmlReportUrl);
          // Always keep graph view as default, don't auto-switch to report
        }
      })
      .catch(() => { });
  }, [htmlReportUrl]); // Empty deps except derived URL

  // 获取图谱数据
  const fetchGraphData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Add 180s timeout (graph-data API needs time to process large datasets)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000);

      const response = await fetch(`${API_BASE_URL}/api/analysis/graph-data`, {
        signal: controller.signal
      }).catch(err => {
        throw new Error(err.name === 'AbortError' ? '请求超时，请检查后端服务' : '网络请求失败');
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `加载失败 (${response.status})`);
      }

      const result = await response.json();

      if (result.message === 'success' && result.data) {
        setGraphData(result.data);
        setActiveSelection(null);
        setSelectedNode(null);
        onLog?.(`图谱数据加载成功: ${result.data.stats.nodeCount} 个节点`);
      } else {
        throw new Error('返回数据格式错误');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '未知错误';
      setError(errorMessage);
      onLog?.(`加载图谱数据失败: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  // 自动加载数据
  useEffect(() => {
    fetchGraphData();
  }, []);

  // 初始化图表
  useEffect(() => {
    if (!networkRef.current || !graphData) return;

    // 调试日志
    console.log('[NetworkGraph] 初始化图表:', {
      nodeCount: graphData.nodes?.length || 0,
      edgeCount: graphData.edges?.length || 0,
      containerExists: !!networkRef.current,
      containerSize: networkRef.current ? {
        width: networkRef.current.offsetWidth,
        height: networkRef.current.offsetHeight
      } : null
    });

    // 如果没有节点数据，不初始化
    if (!graphData.nodes || graphData.nodes.length === 0) {
      console.warn('[NetworkGraph] 没有节点数据，跳过初始化');
      return;
    }

    try {
      // Clean up previous instance
      if (networkInstance.current) {
        networkInstance.current.destroy();
        networkInstance.current = null;
      }

      // 配置 Dark Sci-Fi 样式（完美复刻 HTML 版本）
      const options: Options = {
        // 物理引擎配置（与 HTML 完全一致）
        physics: {
          stabilization: {
            iterations: 300,
            fit: true
          },
          barnesHut: {
            gravitationalConstant: -5000,
            springLength: 200,
            springConstant: 0.01,
            centralGravity: 0.3
          }
        },

        // 交互配置
        interaction: {
          hover: true,
          tooltipDelay: 100,
          navigationButtons: true,
          keyboard: true
        },

        // 节点样式
        nodes: {
          shape: 'dot',
          borderWidth: 2,
          shadow: true,
          scaling: {
            min: 15,
            max: 50,
            label: {
              enabled: true,
              min: 10,
              max: 18
            }
          },
          font: {
            color: '#fff',
            size: 14,
            face: 'Microsoft YaHei'
          }
        },

        // 边样式
        edges: {
          width: 2,
          shadow: true,
          scaling: {
            min: 1,
            max: 8
          },
          smooth: {
            enabled: true,
            type: 'curvedCW',
            roundness: 0.2
          }
        },

        // 分组样式（与 HTML 完全一致）
        groups: {
          core: {
            color: {
              background: '#ff6b6b',
              border: '#c0392b',
              highlight: {
                background: '#e74c3c',
                border: '#c0392b'
              }
            },
            font: { color: '#ffffff' },
            size: 35
          },
          company: {
            color: {
              background: '#9b59b6',
              border: '#8e44ad',
              highlight: {
                background: '#8e44ad',
                border: '#7d3c98'
              }
            },
            font: { color: '#ffffff' },
            shape: 'box',
            size: 25
          },
          involved_company: {
            color: {
              background: '#ff9800',
              border: '#e65100',
              highlight: {
                background: '#ffa726',
                border: '#fb8c00'
              }
            },
            font: { color: '#ffffff', size: 14 },
            shape: 'box',
            shadow: {
              enabled: true,
              color: 'rgba(255,152,0,0.5)',
              size: 10
            },
            borderWidth: 3,
            size: 40
          },
          other: {
            color: {
              background: '#4ecdc4',
              border: '#1abc9c',
              highlight: {
                background: '#1abc9c',
                border: '#16a085'
              }
            },
            size: 18
          }
        },

        // 背景和整体样式
        configure: {
          enabled: false
        },

        // 自动适配
        autoResize: true,
        height: '100%',
        width: '100%'
      };

      // 准备节点数据
      const getGroupLabel = (group: string) => {
        switch (group) {
          case 'core': return '🔴 核心人员';
          case 'company': return '🏢 关联企业';
          case 'involved_company': return '⚠️ 涉案企业';
          case 'other': return '🔵 其他关联方';
          default: return group;
        }
      };

      // 处理节点数据，确保 size/value 正确
      const processedNodes = graphData.nodes.map(node => {
        // 根据 group 设置默认大小
        let nodeSize = node.size || 20;
        if (node.group === 'core') nodeSize = Math.max(nodeSize, 35);
        else if (node.group === 'involved_company') nodeSize = Math.max(nodeSize, 40);
        else if (node.group === 'company') nodeSize = Math.max(nodeSize, 25);
        else nodeSize = Math.max(nodeSize, 18);

        return {
          id: node.id,
          label: formatPartyName(node.label),
          value: nodeSize,
          size: nodeSize,
          group: node.group,
          title: `【${formatPartyName(node.label)}】\n${getGroupLabel(node.group || 'other')}`
        };
      });

      const nodes = new DataSet<Node>(processedNodes);

      // 处理边数据
      const processedEdges = graphData.edges.map((edge, edgeIdx) => ({
        id: `${edge.from}->${edge.to}->${edgeIdx}`,
        from: edge.from,
        to: edge.to,
        value: edge.value || 1,
        title: edge.title || `${edge.from} → ${edge.to}`,
        arrows: 'to',
        color: { color: '#00d2ff', opacity: 0.8 },
        smooth: { enabled: true, type: 'curvedCW', roundness: 0.2 }
      }));

      const edges = new DataSet<Edge>(processedEdges);

      const data: Data = { nodes, edges };

      console.log('[NetworkGraph] 创建网络实例，节点:', processedNodes.length, '边:', processedEdges.length);

      // 创建网络实例
      networkInstance.current = new Network(networkRef.current, data, options);

      // 稳定化完成后日志
      networkInstance.current.on('stabilizationIterationsDone', () => {
        console.log('[NetworkGraph] 网络稳定化完成');
        onLog?.('网络图谱渲染完成');
      });

      // 事件监听
      networkInstance.current.on('click', (params) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const nodeData = nodes.get(nodeId);
          if (nodeData && !Array.isArray(nodeData)) {
            const n = nodeData as any;
            setSelectedNode({ label: n.label, group: n.group });
            onLog?.(`选中节点: ${n.label}`);
            syncPanelToGraphSelection({
              nodeNames: [resolveGraphNodeNameById(nodeId)],
            });
          }
        } else if (params.edges.length > 0) {
          const edgeId = params.edges[0];
          const edgeData = edges.get(edgeId);
          if (edgeData && !Array.isArray(edgeData)) {
            const rawEdge = edgeData as any;
            const fromNode = resolveGraphNodeNameById(rawEdge.from);
            const toNode = resolveGraphNodeNameById(rawEdge.to);
            onLog?.(`选中边: ${fromNode} → ${toNode}`);
            syncPanelToGraphSelection({
              nodeNames: [fromNode, toNode],
              edgePair: [fromNode, toNode],
            });
          }
        } else {
          setSelectedNode(null);
          setActiveSelection(null);
        }
      });

      // 调试：打印创建成功
      console.log('[NetworkGraph] 网络实例创建成功');

    } catch (err) {
      console.error('[NetworkGraph] 初始化失败:', err);
      setError('图表初始化失败: ' + (err instanceof Error ? err.message : String(err)));
    }

    return () => {
      if (networkInstance.current) {
        networkInstance.current.destroy();
        networkInstance.current = null;
      }
    };
  }, [graphData]);

  return (
    <div className="h-full w-full flex bg-gradient-to-br from-theme-bg-base to-theme-bg-elevated text-white" style={{ minHeight: '700px' }}>
      {/* P0-1: 交易详情 Modal */}
      {transactionDetail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setTransactionDetail(null)}
        >
          <div
            className="theme-bg-base border border-cyan-500/30 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10 bg-gradient-to-r from-cyan-500/10 to-blue-500/10">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-cyan-500/20">
                  <FileText className="w-5 h-5 text-cyan-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white">交易详情穿透</h3>
                  <p className="text-xs theme-text-muted">
                    {transactionDetail.type === 'loan_pair' ? '借贷配对' :
                      transactionDetail.type === 'no_repayment' ? '无还款借贷' :
                        transactionDetail.type === 'high_risk_income' ? '高风险收入' : '网贷交易'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setTransactionDetail(null)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 theme-text-muted" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-5 space-y-4">
              {/* 交易双方信息（P1修复: 明确标注方向） */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs theme-text-dim mb-1">付款方</div>
                  <div className="text-white font-medium">
                    {transactionDetail.counterparty &&
                     transactionDetail.counterparty !== '未知' &&
                     transactionDetail.counterparty !== '(未知)' &&
                     transactionDetail.counterparty !== 'nan' ?
                      formatPartyName(transactionDetail.counterparty) :
                      <span className="text-orange-400">⚠ 来源不明</span>
                    }
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs theme-text-dim mb-1">收款方</div>
                  <div className="text-cyan-400 font-medium">{transactionDetail.person}</div>
                </div>
              </div>

              {/* 资金方向指示 */}
              <div className="flex items-center justify-center theme-text-dim text-sm">
                <span className="theme-text-muted">{formatPartyName(transactionDetail.counterparty || '付款方')}</span>
                <span className="mx-2 text-cyan-400">→</span>
                <span className="text-cyan-400">{transactionDetail.person}</span>
              </div>

              {/* 金额信息 */}
              <div className="bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-lg p-4 border border-cyan-500/20">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs theme-text-muted mb-1">交易金额</div>
                    <div className="text-2xl font-bold text-cyan-400">
                      ¥{transactionDetail.amount >= 10000
                        ? (transactionDetail.amount / 10000).toFixed(2) + '万'
                        : transactionDetail.amount.toLocaleString()}
                    </div>
                  </div>
                  {transactionDetail.repayAmount !== undefined && (
                    <div className="text-right">
                      <div className="text-xs theme-text-muted mb-1">还款金额</div>
                      <div className="text-xl font-bold text-orange-400">
                        ¥{transactionDetail.repayAmount >= 10000
                          ? (transactionDetail.repayAmount / 10000).toFixed(2) + '万'
                          : transactionDetail.repayAmount.toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>
                {transactionDetail.daysSince !== undefined && (
                  <div className="mt-2 pt-2 border-t border-white/10 text-sm theme-text-muted">
                    未还款天数: <span className={transactionDetail.daysSince >= 180 ? 'text-red-400 font-bold' : 'text-amber-400'}>{transactionDetail.daysSince}天</span>
                    {transactionDetail.daysSince >= 180 && <span className="ml-2">⚠️ 超过180天</span>}
                  </div>
                )}
              </div>

              {/* 风险等级 */}
              {transactionDetail.riskLevel && (
                <div className="flex items-center gap-2">
                  <span className="text-xs theme-text-dim">风险等级:</span>
                  <span className={getRiskLevelBadgeStyle(transactionDetail.riskLevel)}>
                    {formatRiskLevel(transactionDetail.riskLevel)}
                  </span>
                </div>
              )}

              {/* 收入类型（如果有） */}
              {transactionDetail.incomeType && (
                <div className="flex items-center gap-2">
                  <span className="text-xs theme-text-dim">收入类型:</span>
                  <span className="text-xs text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded">
                    {transactionDetail.incomeType}
                  </span>
                </div>
              )}

              {/* 交易详情（如果有） */}
              {transactionDetail.detail && (
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="text-xs theme-text-dim mb-1">交易详情</div>
                  <div className="text-sm theme-text-secondary font-mono whitespace-pre-line">
                    {transactionDetail.detail}
                  </div>
                </div>
              )}

              {/* 数据溯源信息 */}
              {transactionDetail.sourceFile ? (
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
                  <div className="flex items-center gap-2 text-green-400 font-medium text-sm mb-2">
                    <Info className="w-4 h-4" />
                    📍 精确溯源信息
                  </div>
                  <div className="space-y-1 text-xs">
                    <div className="flex items-start gap-2">
                      <span className="theme-text-dim w-16 flex-shrink-0">来源文件:</span>
                      <span className="text-green-300 font-mono break-all">
                        {transactionDetail.sourceFile.split('/').pop()}
                      </span>
                    </div>
                    {transactionDetail.sourceRow && (
                      <div className="flex items-center gap-2">
                        <span className="theme-text-dim w-16">原始行号:</span>
                        <span className="text-green-400 font-mono font-bold">
                          第 {transactionDetail.sourceRow} 行
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="mt-2 pt-2 border-t border-green-500/20 text-xs text-green-400/70">
                    💡 可直接在 cleaned_data 目录定位该文件核对原始记录
                  </div>
                </div>
              ) : (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-sm text-amber-300 flex items-start gap-2">
                  <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium mb-1">数据溯源提示</div>
                    <div className="text-xs text-amber-400/80">
                      完整原始流水请查阅 Excel 报告中的"清洗后流水"工作表，或在 cleaned_data 目录查看对应实体的合并流水文件。
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-white/10 bg-white/5 flex justify-end gap-3">
              <button
                onClick={() => setTransactionDetail(null)}
                className="px-4 py-2 theme-text-muted hover:text-white text-sm transition-colors"
              >
                关闭
              </button>
              <a
                href={excelReportUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 text-sm rounded-lg transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                下载 Excel 报告
              </a>
            </div>
          </div>
        </div>
      )}

      {/* 左侧统计面板 */}
      <div className="w-80 flex-shrink-0 bg-white/5 backdrop-blur-sm border-r border-white/10 flex flex-col">
        <div className="p-4 border-b border-white/10">
          <h3 className="text-cyan-400 font-bold text-lg mb-2">📊 数据概览</h3>
          {graphData && (
            <p className="text-xs theme-text-muted">
              生成时间: {new Date().toLocaleString('zh-CN')}
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* 空状态提示 */}
          {!graphData && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                <Info className="w-8 h-8 theme-text-dim" />
              </div>
              <h4 className="theme-text-muted font-medium mb-2">暂无图谱数据</h4>
              <p className="text-xs theme-text-dim leading-relaxed max-w-[200px] mb-4">
                请先在侧边栏点击"启动引擎"运行分析，完成后数据将自动加载
              </p>
              {reportUrl && (
                <button
                  onClick={() => setViewMode('report')}
                  className="text-cyan-400 text-xs underline hover:text-cyan-300"
                >
                  尝试查看静态报告
                </button>
              )}
            </div>
          )}

          {/* 加载状态 */}
          {loading && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-10 h-10 border-3 border-white/20 border-t-cyan-400 rounded-full animate-spin mb-4"></div>
              <p className="text-sm theme-text-muted">正在加载图谱数据...</p>
            </div>
          )}

          {/* 核心人员 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden">
              <button 
                onClick={() => toggleSection('corePersons')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Users className="w-5 h-5 text-cyan-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">核心人员</h4>
                    <div className="text-2xl font-bold text-cyan-400">
                      {graphData.stats.corePersonCount}
                    </div>
                  </div>
                </div>
                {expandedSections['corePersons'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['corePersons'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3">
                  <div className="space-y-2">
                    {graphData.stats.corePersonNames.map((name, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm theme-text-secondary">
                        <div className="w-2 h-2 rounded-full bg-red-500"></div>
                        {name}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 重点核查对象 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-rose-500">
              <button
                onClick={() => toggleSection('focusEntities')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div>
                  <h4 className="text-white text-sm font-medium mb-1">🎯 重点核查对象</h4>
                  <div className="text-2xl font-bold text-rose-400">
                    {focusEntities.length}
                  </div>
                  <div className="text-xs theme-text-muted">
                    与正式报告统一的聚合排序口径
                  </div>
                </div>
                {expandedSections['focusEntities'] ?
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> :
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['focusEntities'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-72 overflow-y-auto">
                  {(aggregationSummary.极高风险实体数 || aggregationSummary.高风险实体数 || aggregationSummary.高优先线索实体数) ? (
                    <div className="mb-3 rounded-lg bg-white/5 p-3 text-xs theme-text-secondary">
                      极高风险 {aggregationSummary.极高风险实体数 || 0} 个，
                      高风险 {aggregationSummary.高风险实体数 || 0} 个，
                      高优先线索实体 {aggregationSummary.高优先线索实体数 || 0} 个
                    </div>
                  ) : null}
                  {focusEntities.length > 0 ? (
                    <div className="space-y-3">
                      {focusEntities.map((entity, idx) => {
                        const inGraph = entity.in_graph || Boolean(focusEntityInGraph(entity));
                        return (
                          <button
                            key={`${entity.name}-${idx}`}
                            onClick={() => focusGraphEntity(entity)}
                            className="w-full rounded-lg bg-white/5 p-3 text-left hover:bg-white/10 transition-colors"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-mono text-rose-300">#{idx + 1}</span>
                                  <span className="text-sm font-medium text-white">{formatPartyName(entity.name)}</span>
                                </div>
                                <div className="mt-1 text-xs theme-text-muted">
                                  {inGraph ? '可在当前图谱中定位' : '当前采样图未展示该对象'}
                                </div>
                              </div>
                              <span className={getRiskLevelBadgeStyle(entity.risk_level || 'medium')}>
                                {formatRiskLevel(entity.risk_level || 'medium')}
                              </span>
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs theme-text-secondary">
                              <span>评分 {entity.risk_score.toFixed(1)}</span>
                              {entity.risk_confidence !== undefined && (
                                <span>{formatConfidence(entity.risk_confidence)}</span>
                              )}
                              {entity.high_priority_clue_count !== undefined && (
                                <span>高优先线索 {entity.high_priority_clue_count}</span>
                              )}
                            </div>
                            {entity.summary && (
                              <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                                {entity.summary}
                              </div>
                            )}
                            {entity.top_clues && entity.top_clues.length > 0 && (
                              <div className="mt-2 text-xs text-amber-200 leading-relaxed">
                                {entity.top_clues.slice(0, 1).join('；')}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-sm theme-text-dim">当前未形成稳定的重点核查对象排序</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 资金闭环 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-fuchsia-500">
              <button
                onClick={() => toggleSection('fundCycles')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-fuchsia-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">资金闭环</h4>
                    <div className="text-2xl font-bold text-fuchsia-400">
                      {fundCycles.length}
                    </div>
                    <div className="text-xs theme-text-muted">优先展示强版闭环路径</div>
                  </div>
                </div>
                {expandedSections['fundCycles'] ?
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> :
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['fundCycles'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-56 overflow-y-auto">
                  {fundCycleMeta.truncated && (
                    <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
                      本次闭环搜索存在截断:
                      {' '}
                      {(fundCycleMeta.truncated_reasons || ['search_truncated']).join(' / ')}
                      {fundCycleMeta.timeout_seconds ? `，超时阈值 ${fundCycleMeta.timeout_seconds} 秒` : ''}
                    </div>
                  )}
                  {fundCycles.length > 0 ? (
                    <div className="space-y-3">
                      {fundCycles.map((cycle, idx) => {
                        const selectionId = `fund_cycle:${idx}`;
                        return (
                        <div
                          key={idx}
                          className={`rounded-lg p-3 transition-colors ${
                            isActiveSelection(selectionId)
                              ? 'bg-fuchsia-500/10 ring-1 ring-fuchsia-400/40'
                              : 'bg-white/5'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="text-sm text-white leading-relaxed break-all">
                              {getCyclePath(cycle)}
                            </div>
                            <span className={getRiskLevelBadgeStyle(cycle.risk_level || 'medium')}>
                              {formatRiskLevel(cycle.risk_level || 'medium')}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs theme-text-muted">
                            <span>节点数 {cycle.length || (cycle.nodes || cycle.participants || []).length || 0}</span>
                            <span>{formatOptionalAmount(cycle.total_amount)}</span>
                            {cycle.risk_score !== undefined && <span>评分 {cycle.risk_score.toFixed(1)}</span>}
                            <span>{formatConfidence(cycle.confidence)}</span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              onClick={() => activateSelection({
                                id: selectionId,
                                type: 'fund_cycle',
                                label: `资金闭环 ${idx + 1}`,
                                path: getCyclePath(cycle),
                                nodes: getCycleNodes(cycle),
                                riskScore: cycle.risk_score,
                                sectionKeys: ['fundCycles', `fundCycle:${idx}:details`],
                              })}
                              className="rounded border border-fuchsia-400/30 px-2 py-1 text-[11px] text-fuchsia-200 hover:bg-fuchsia-500/10"
                            >
                              {isActiveSelection(selectionId) ? '已联动路径' : '定位路径'}
                            </button>
                          </div>
                          {formatPathSummary(cycle.path_explainability) && (
                            <div className="mt-2 text-xs text-amber-200 leading-relaxed">
                              {formatPathSummary(cycle.path_explainability)}
                            </div>
                          )}
                          {formatInspectionPoints(cycle.path_explainability) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatInspectionPoints(cycle.path_explainability)}
                            </div>
                          )}
                          {formatCycleEdgeSegments(cycle.path_explainability) && (
                            <div className="mt-2 text-xs text-cyan-200 leading-relaxed">
                              {formatCycleEdgeSegments(cycle.path_explainability)}
                            </div>
                          )}
                          {cycle.path_explainability?.edge_segments && cycle.path_explainability.edge_segments.length > 0 && (
                            <div className="mt-3 rounded-lg border border-fuchsia-500/20 bg-fuchsia-500/5 p-2">
                              <button
                                onClick={() => toggleSection(`fundCycle:${idx}:details`)}
                                className="flex w-full items-center justify-between gap-3 text-left"
                              >
                                <div>
                                  <div className="text-xs font-medium text-fuchsia-200">逐跳支撑流水</div>
                                  <div className="mt-1 text-[11px] theme-text-muted">
                                    共 {cycle.path_explainability.edge_segments.length} 跳，点击展开查看每一跳的原始流水样本
                                  </div>
                                </div>
                                {expandedSections[`fundCycle:${idx}:details`] ? (
                                  <ChevronUp className="h-4 w-4 theme-text-muted" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 theme-text-muted" />
                                )}
                              </button>
                              {expandedSections[`fundCycle:${idx}:details`] && (
                                <div className="mt-3 space-y-2">
                                  {cycle.path_explainability.edge_segments.map((segment, segmentIdx) => {
                                    const segmentKey = `fundCycle:${idx}:hop:${segment.index || segmentIdx + 1}`;
                                    const refs = segment.transaction_refs || [];
                                    const totalRefs = getSegmentTransactionTotal(segment);
                                    return (
                                      <div
                                        key={segmentKey}
                                        className="rounded-lg border border-white/10 bg-black/10 p-2"
                                      >
                                        <button
                                          onClick={() => toggleSection(segmentKey)}
                                          className="flex w-full items-center justify-between gap-3 text-left"
                                        >
                                          <div>
                                            <div className="text-xs text-white">
                                              第{segment.index || segmentIdx + 1}跳 {segment.from || '未知'} → {segment.to || '未知'}
                                            </div>
                                            <div className="mt-1 text-[11px] theme-text-muted">
                                              {formatOptionalAmount(segment.amount)} · 支撑流水 {totalRefs} 笔
                                              {refs.length > 0 ? ` · 当前返回 ${getSegmentReturnedCount(segment)} 条` : ''}
                                            </div>
                                          </div>
                                          {expandedSections[segmentKey] ? (
                                            <ChevronUp className="h-4 w-4 theme-text-muted" />
                                          ) : (
                                            <ChevronDown className="h-4 w-4 theme-text-muted" />
                                          )}
                                        </button>
                                        {expandedSections[segmentKey] && (
                                          <div className="mt-2 space-y-2">
                                            {refs.length > 0 ? (
                                              refs.map((ref, refIdx) => (
                                                <div
                                                  key={`${segmentKey}:ref:${refIdx}`}
                                                  className="rounded-md bg-white/5 p-2 text-[11px] leading-relaxed"
                                                >
                                                  <div className="text-cyan-100">
                                                    {ref.date || '未知时间'} · {formatOptionalAmount(Number(ref.amount || 0))}
                                                  </div>
                                                  <div className="mt-1 theme-text-secondary">
                                                    {(ref.source_file || '未知文件')}
                                                    {ref.source_row_index !== undefined && ref.source_row_index !== null
                                                      ? ` 第${ref.source_row_index}行`
                                                      : ''}
                                                  </div>
                                                  {ref.description && (
                                                    <div className="mt-1 theme-text-muted break-all">
                                                      摘要: {ref.description}
                                                    </div>
                                                  )}
                                                </div>
                                              ))
                                            ) : (
                                              <div className="text-[11px] theme-text-dim">
                                                当前未返回可展示的原始流水样本
                                              </div>
                                            )}
                                            {totalRefs > refs.length && (
                                              <div className="text-[11px] text-amber-200">
                                                当前仅回传前 {getSegmentReturnedCount(segment)} 条，实际共 {totalRefs} 条支撑流水。
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}
                          {formatEvidence(cycle.evidence) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatEvidence(cycle.evidence)}
                            </div>
                          )}
                        </div>
                      )})}
                    </div>
                  ) : (
                    <div className="text-sm theme-text-dim">未发现闭环路径</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 第三方中转 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-amber-500">
              <button
                onClick={() => toggleSection('thirdPartyRelays')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Landmark className="w-5 h-5 text-amber-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">第三方中转</h4>
                    <div className="text-2xl font-bold text-amber-400">
                      {thirdPartyRelays.length}
                    </div>
                    <div className="text-xs theme-text-muted">多跳中转链 explainability</div>
                  </div>
                </div>
                {expandedSections['thirdPartyRelays'] ?
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> :
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['thirdPartyRelays'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-72 overflow-y-auto">
                  {thirdPartyRelays.length > 0 ? (
                    <div className="space-y-3">
                      {thirdPartyRelays.map((relay, idx) => {
                        const selectionId = `third_party_relay:${idx}`;
                        return (
                        <div
                          key={`${relay.from}-${relay.relay}-${relay.to}-${idx}`}
                          className={`rounded-lg p-3 transition-colors ${
                            isActiveSelection(selectionId)
                              ? 'bg-amber-500/10 ring-1 ring-amber-400/40'
                              : 'bg-white/5'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="text-sm text-white leading-relaxed break-all">
                              {relay.path_explainability?.path || `${relay.from} → ${relay.relay} → ${relay.to}`}
                            </div>
                            <span className={getRiskLevelBadgeStyle(relay.risk_level || 'medium')}>
                              {formatRiskLevel(relay.risk_level || 'medium')}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs theme-text-muted">
                            <span>{formatOptionalAmount(relay.outflow_amount)}</span>
                            {relay.risk_score !== undefined && <span>评分 {relay.risk_score.toFixed(1)}</span>}
                            {relay.time_diff_hours !== undefined && <span>时差 {relay.time_diff_hours.toFixed(1)} 小时</span>}
                            <span>{formatConfidence(relay.confidence)}</span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              onClick={() => activateSelection({
                                id: selectionId,
                                type: 'third_party_relay',
                                label: `第三方中转 ${idx + 1}`,
                                path: relay.path_explainability?.path || `${relay.from} → ${relay.relay} → ${relay.to}`,
                                nodes: getRelayNodes(relay),
                                riskScore: relay.risk_score,
                                sectionKeys: ['thirdPartyRelays', `relay:${idx}:details`],
                              })}
                              className="rounded border border-amber-400/30 px-2 py-1 text-[11px] text-amber-200 hover:bg-amber-500/10"
                            >
                              {isActiveSelection(selectionId) ? '已联动路径' : '定位路径'}
                            </button>
                          </div>
                          {formatPathSummary(relay.path_explainability) && (
                            <div className="mt-2 text-xs text-amber-200 leading-relaxed">
                              {formatPathSummary(relay.path_explainability)}
                            </div>
                          )}
                          {formatInspectionPoints(relay.path_explainability) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatInspectionPoints(relay.path_explainability)}
                            </div>
                          )}
                          {formatRelayTimeAxis(relay.path_explainability) && (
                            <div className="mt-2 text-xs text-cyan-200 leading-relaxed">
                              {formatRelayTimeAxis(relay.path_explainability)}
                            </div>
                          )}
                          {relay.path_explainability?.time_axis && relay.path_explainability.time_axis.length > 0 && (
                            <div className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-2">
                              <button
                                onClick={() => toggleSection(`relay:${idx}:details`)}
                                className="flex w-full items-center justify-between gap-3 text-left"
                              >
                                <div>
                                  <div className="text-xs font-medium text-amber-200">时序明细</div>
                                  <div className="mt-1 text-[11px] theme-text-muted">
                                    当前返回 {relay.path_explainability.time_axis.length} 步，
                                    实际共 {getTimeAxisTotal(relay.path_explainability)} 步
                                  </div>
                                </div>
                                {expandedSections[`relay:${idx}:details`] ? (
                                  <ChevronUp className="h-4 w-4 theme-text-muted" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 theme-text-muted" />
                                )}
                              </button>
                              {expandedSections[`relay:${idx}:details`] && (
                                <div className="mt-3 space-y-2">
                                  {relay.path_explainability.time_axis.map((event, eventIdx) => (
                                    <div
                                      key={`relay:${idx}:event:${eventIdx}`}
                                      className="rounded-lg border border-white/10 bg-black/10 p-2 text-[11px] leading-relaxed"
                                    >
                                      <div className="text-amber-100">
                                        第{event.step || eventIdx + 1}步 {event.time || '未知时间'}
                                      </div>
                                      <div className="mt-1 text-white">
                                        {event.label || '未知事件'} · {formatOptionalAmount(Number(event.amount || 0))}
                                      </div>
                                      <div className="mt-1 theme-text-secondary">
                                        {(event.source_file || '未知文件')}
                                        {event.source_row_index !== undefined && event.source_row_index !== null
                                          ? ` 第${event.source_row_index}行`
                                          : ''}
                                      </div>
                                    </div>
                                  ))}
                                  {getTimeAxisTotal(relay.path_explainability) > relay.path_explainability.time_axis.length && (
                                    <div className="text-[11px] text-amber-200">
                                      当前仅回传前 {relay.path_explainability.time_axis.length} 步样本，
                                      实际共 {getTimeAxisTotal(relay.path_explainability)} 步。
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                          {formatEvidence(relay.evidence) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatEvidence(relay.evidence)}
                            </div>
                          )}
                        </div>
                      )})}
                    </div>
                  ) : (
                    <div className="text-sm theme-text-dim">当前未识别出稳定的第三方中转链</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 外围节点 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-emerald-500">
              <button
                onClick={() => toggleSection('discoveredNodes')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Users className="w-5 h-5 text-emerald-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">外围节点</h4>
                    <div className="text-2xl font-bold text-emerald-400">
                      {discoveredNodes.length}
                    </div>
                    <div className="text-xs theme-text-muted">从中转与闭环中扩展发现</div>
                  </div>
                </div>
                {expandedSections['discoveredNodes'] ?
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> :
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['discoveredNodes'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-64 overflow-y-auto">
                  {discoveredNodes.length > 0 ? (
                    <div className="space-y-2">
                      {discoveredNodes.map((node, idx) => (
                        <div key={`${node.name}-${idx}`} className="rounded-lg bg-white/5 p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="text-sm text-white font-medium">{formatPartyName(node.name)}</div>
                              <div className="mt-1 text-xs theme-text-muted">
                                关联核心对象: {(node.linked_cores || []).join('、') || '未标注'}
                              </div>
                            </div>
                            <span className={getRiskLevelBadgeStyle(node.risk_level || 'medium')}>
                              {formatRiskLevel(node.risk_level || 'medium')}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs theme-text-secondary">
                            <span>{formatRelationTypes(node.relation_types)}</span>
                            <span>出现 {node.occurrences || 0} 次</span>
                            <span>{formatOptionalAmount(node.total_amount)}</span>
                            {node.risk_score !== undefined && <span>评分 {node.risk_score.toFixed(1)}</span>}
                            <span>{formatConfidence(node.confidence)}</span>
                          </div>
                          {formatPathSummary(node.path_explainability) && (
                            <div className="mt-2 text-xs text-amber-200 leading-relaxed">
                              {formatPathSummary(node.path_explainability)}
                            </div>
                          )}
                          {formatInspectionPoints(node.path_explainability) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatInspectionPoints(node.path_explainability)}
                            </div>
                          )}
                          {formatEvidence(node.evidence) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatEvidence(node.evidence)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm theme-text-dim">当前图谱未扩展出新的外围节点</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 关系簇 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-cyan-500">
              <button
                onClick={() => toggleSection('relationshipClusters')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Building2 className="w-5 h-5 text-cyan-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">关系簇</h4>
                    <div className="text-2xl font-bold text-cyan-400">
                      {relationshipClusters.length}
                    </div>
                    <div className="text-xs theme-text-muted">核心对象与外围节点的联通组件</div>
                  </div>
                </div>
                {expandedSections['relationshipClusters'] ?
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> :
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['relationshipClusters'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-72 overflow-y-auto">
                  {relationshipClusters.length > 0 ? (
                    <div className="space-y-3">
                      {relationshipClusters.map((cluster, idx) => {
                        const clusterSelectionId = `relationship_cluster:${idx}`;
                        const clusterHasActivePath = Boolean(
                          activeSelection?.id === clusterSelectionId ||
                          activeSelection?.id.startsWith(`cluster_representative_path:${idx}:`)
                        );
                        return (
                        <div
                          key={cluster.cluster_id || idx}
                          className={`rounded-lg p-3 transition-colors ${
                            clusterHasActivePath
                              ? 'bg-sky-500/10 ring-1 ring-sky-400/40'
                              : 'bg-white/5'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="text-sm text-white font-medium">
                                {(cluster.cluster_id || `cluster_${idx + 1}`).replace('_', ' ').toUpperCase()}
                              </div>
                              <div className="mt-1 text-xs theme-text-muted">
                                核心成员: {(cluster.core_members || []).join('、') || '未标注'}
                              </div>
                              <div className="mt-1 text-xs theme-text-muted">
                                外围成员: {(cluster.external_members || []).join('、') || '无'}
                              </div>
                            </div>
                            <span className={getRiskLevelBadgeStyle(cluster.risk_level || 'medium')}>
                              {formatRiskLevel(cluster.risk_level || 'medium')}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs theme-text-secondary">
                            <span>{formatRelationTypes(cluster.relation_types)}</span>
                            <span>直接 {cluster.direct_flow_count || 0}</span>
                            <span>中转 {cluster.relay_count || 0}</span>
                            <span>闭环 {cluster.loop_count || 0}</span>
                            <span>{formatOptionalAmount(cluster.total_amount)}</span>
                            {cluster.risk_score !== undefined && <span>评分 {cluster.risk_score.toFixed(1)}</span>}
                            <span>{formatConfidence(cluster.confidence)}</span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              onClick={() => activateSelection({
                                id: clusterSelectionId,
                                type: 'relationship_cluster',
                                label: `关系簇 ${cluster.cluster_id || idx + 1}`,
                                path: cluster.cluster_id,
                                nodes: getClusterNodes(cluster),
                                riskScore: cluster.risk_score,
                                sectionKeys: ['relationshipClusters'],
                              })}
                              className="rounded border border-cyan-400/30 px-2 py-1 text-[11px] text-cyan-200 hover:bg-cyan-500/10"
                            >
                              {isActiveSelection(clusterSelectionId) ? '已联动关系簇' : '定位关系簇'}
                            </button>
                          </div>
                          {formatPathSummary(cluster.path_explainability) && (
                            <div className="mt-2 text-xs text-amber-200 leading-relaxed">
                              {formatPathSummary(cluster.path_explainability)}
                            </div>
                          )}
                          {formatInspectionPoints(cluster.path_explainability) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatInspectionPoints(cluster.path_explainability)}
                            </div>
                          )}
                          {cluster.path_explainability?.representative_paths && cluster.path_explainability.representative_paths.length > 0 && (
                            <div className="mt-3 rounded-lg border border-sky-500/20 bg-sky-500/5 p-2">
                              <button
                                onClick={() => toggleSection(`cluster:${idx}:paths`)}
                                className="flex w-full items-center justify-between gap-3 text-left"
                              >
                                <div>
                                  <div className="text-xs font-medium text-sky-200">代表路径</div>
                                  <div className="mt-1 text-[11px] theme-text-muted">
                                    已提炼 {cluster.path_explainability.representative_paths.length} 条优先核查链路
                                  </div>
                                </div>
                                {expandedSections[`cluster:${idx}:paths`] ? (
                                  <ChevronUp className="h-4 w-4 theme-text-muted" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 theme-text-muted" />
                                )}
                              </button>
                              {expandedSections[`cluster:${idx}:paths`] && (
                                <div className="mt-3 space-y-2">
                                  {cluster.path_explainability.representative_paths.map((representativePath, pathIdx) => {
                                    const payload = getRepresentativePathPayload(representativePath);
                                    const pathNodes = getRepresentativePathNodes(representativePath);
                                    const cyclePayload = payload as CyclePathExplainability | undefined;
                                    const relayPayload = payload as RelayPathExplainability | undefined;
                                    const directPayload = payload as DirectFlowPathExplainability | undefined;
                                    const pathKey = `cluster:${idx}:path:${pathIdx}`;
                                    const selectionId = `cluster_representative_path:${idx}:${pathIdx}`;

                                    return (
                                      <div
                                        key={`${cluster.cluster_id || idx}:rep:${pathIdx}`}
                                        className={`rounded-lg border p-2 transition-colors ${
                                          isActiveSelection(selectionId)
                                            ? 'border-sky-400/40 bg-sky-500/10'
                                            : 'border-white/10 bg-black/10'
                                        }`}
                                      >
                                        <div className="flex items-start justify-between gap-3">
                                          <div>
                                            <div className="text-xs text-white">
                                              [{relationTypeLabels[representativePath.path_type || ''] || representativePath.path_type || '代表路径'}]
                                              {' '}
                                              {representativePath.path || payload?.path || '未知路径'}
                                            </div>
                                            <div className="mt-1 flex flex-wrap items-center gap-3 text-[11px] theme-text-muted">
                                              {representativePath.amount !== undefined && representativePath.amount > 0 && (
                                                <span>{formatOptionalAmount(representativePath.amount)}</span>
                                              )}
                                              {representativePath.risk_score !== undefined && (
                                                <span>评分 {representativePath.risk_score.toFixed(1)}</span>
                                              )}
                                              {representativePath.priority_score !== undefined && (
                                                <span>优先级 {representativePath.priority_score.toFixed(1)}</span>
                                              )}
                                              {representativePath.confidence !== undefined && (
                                                <span>{formatConfidence(representativePath.confidence)}</span>
                                              )}
                                            </div>
                                          </div>
                                          <div className="flex items-center gap-2">
                                            <button
                                              onClick={() => activateSelection({
                                                id: selectionId,
                                                type: 'cluster_representative_path',
                                                label: `关系簇代表路径 ${idx + 1}-${pathIdx + 1}`,
                                                path: representativePath.path || payload?.path,
                                                nodes: pathNodes,
                                                riskScore: representativePath.risk_score,
                                                sectionKeys: ['relationshipClusters', `cluster:${idx}:paths`, `cluster:${idx}:path:${pathIdx}`],
                                              })}
                                              className="rounded border border-cyan-400/30 px-2 py-1 text-[11px] text-cyan-200 hover:bg-cyan-500/10"
                                            >
                                              {isActiveSelection(selectionId) ? '已联动路径' : '定位路径'}
                                            </button>
                                            <button
                                              onClick={() => toggleSection(pathKey)}
                                              className="rounded border border-white/10 px-2 py-1 text-[11px] theme-text-secondary hover:bg-white/5"
                                            >
                                              {expandedSections[pathKey] ? '收起细节' : '展开细节'}
                                            </button>
                                          </div>
                                        </div>
                                        {formatPathSummary(payload) && (
                                          <div className="mt-2 text-[11px] text-amber-200 leading-relaxed">
                                            {formatPathSummary(payload)}
                                          </div>
                                        )}
                                        {formatInspectionPoints(payload, 1) && (
                                          <div className="mt-2 text-[11px] theme-text-secondary leading-relaxed">
                                            {formatInspectionPoints(payload, 1)}
                                          </div>
                                        )}
                                        {representativePath.priority_reason && (
                                          <div className="mt-2 text-[11px] theme-text-muted leading-relaxed">
                                            排序依据: {representativePath.priority_reason}
                                          </div>
                                        )}
                                        {payload?.evidence_template?.supporting_refs?.notice && (
                                          <div className="mt-2 text-[11px] text-cyan-200 leading-relaxed">
                                            {payload.evidence_template.supporting_refs.notice}
                                          </div>
                                        )}
                                        {expandedSections[pathKey] && (
                                          <div className="mt-3 space-y-2">
                                            {cyclePayload?.edge_segments && cyclePayload.edge_segments.length > 0 && (
                                              <div className="rounded-md border border-fuchsia-500/20 bg-fuchsia-500/5 p-2">
                                                <div className="text-[11px] text-fuchsia-200">
                                                  {formatCycleEdgeSegments(cyclePayload)}
                                                </div>
                                                <div className="mt-2 space-y-2">
                                                  {cyclePayload.edge_segments.map((segment, segmentIdx) => {
                                                    const segmentRefs = segment.transaction_refs || [];
                                                    const totalRefs = getSegmentTransactionTotal(segment);
                                                    return (
                                                      <div
                                                        key={`${pathKey}:segment:${segmentIdx}`}
                                                        className="rounded-md bg-white/5 p-2 text-[11px] leading-relaxed"
                                                      >
                                                        <div className="text-white">
                                                          第{segment.index || segmentIdx + 1}跳 {segment.from || '未知'} → {segment.to || '未知'}
                                                          {' '}
                                                          · {formatOptionalAmount(segment.amount)}
                                                        </div>
                                                        {segmentRefs.map((ref, refIdx) => (
                                                          <div
                                                            key={`${pathKey}:segment:${segmentIdx}:ref:${refIdx}`}
                                                            className="mt-1 theme-text-secondary"
                                                          >
                                                            {ref.date || '未知时间'} · {formatOptionalAmount(Number(ref.amount || 0))}
                                                            {' '}
                                                            {(ref.source_file || '未知文件')}
                                                            {ref.source_row_index !== undefined && ref.source_row_index !== null
                                                              ? ` 第${ref.source_row_index}行`
                                                              : ''}
                                                          </div>
                                                        ))}
                                                        {totalRefs > segmentRefs.length && (
                                                          <div className="mt-1 text-amber-200">
                                                            当前仅回传前 {segmentRefs.length} 条样本，实际共 {totalRefs} 条。
                                                          </div>
                                                        )}
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              </div>
                                            )}
                                            {relayPayload?.time_axis && relayPayload.time_axis.length > 0 && (
                                              <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-2">
                                                <div className="text-[11px] text-amber-200">
                                                  {formatRelayTimeAxis(relayPayload)}
                                                </div>
                                                <div className="mt-2 space-y-2">
                                                  {relayPayload.time_axis.map((event, eventIdx) => (
                                                    <div
                                                      key={`${pathKey}:event:${eventIdx}`}
                                                      className="rounded-md bg-white/5 p-2 text-[11px] leading-relaxed"
                                                    >
                                                      <div className="text-white">
                                                        第{event.step || eventIdx + 1}步 {event.time || '未知时间'}
                                                      </div>
                                                      <div className="mt-1 theme-text-secondary">
                                                        {event.label || '未知事件'} · {formatOptionalAmount(Number(event.amount || 0))}
                                                      </div>
                                                      <div className="mt-1 theme-text-muted">
                                                        {(event.source_file || '未知文件')}
                                                        {event.source_row_index !== undefined && event.source_row_index !== null
                                                          ? ` 第${event.source_row_index}行`
                                                          : ''}
                                                      </div>
                                                    </div>
                                                  ))}
                                                </div>
                                              </div>
                                            )}
                                            {directPayload?.transaction_refs && directPayload.transaction_refs.length > 0 && (
                                              <div className="rounded-md border border-emerald-500/20 bg-emerald-500/5 p-2">
                                                <div className="text-[11px] text-emerald-200">
                                                  直接往来样本
                                                </div>
                                                <div className="mt-2 space-y-2">
                                                  {directPayload.transaction_refs.map((ref, refIdx) => (
                                                    <div
                                                      key={`${pathKey}:direct:${refIdx}`}
                                                      className="rounded-md bg-white/5 p-2 text-[11px] leading-relaxed"
                                                    >
                                                      <div className="text-white">
                                                        {ref.date || '未知时间'} · {formatOptionalAmount(Number(ref.amount || 0))}
                                                      </div>
                                                      <div className="mt-1 theme-text-secondary">
                                                        {(ref.source_file || '未知文件')}
                                                        {ref.source_row_index !== undefined && ref.source_row_index !== null
                                                          ? ` 第${ref.source_row_index}行`
                                                          : ''}
                                                      </div>
                                                      {ref.description && (
                                                        <div className="mt-1 theme-text-muted break-all">
                                                          摘要: {ref.description}
                                                        </div>
                                                      )}
                                                    </div>
                                                  ))}
                                                  {getDirectFlowRefTotal(directPayload) > directPayload.transaction_refs.length && (
                                                    <div className="text-[11px] text-amber-200">
                                                      当前仅回传前 {directPayload.transaction_refs.length} 条样本，
                                                      实际共 {getDirectFlowRefTotal(directPayload)} 条。
                                                    </div>
                                                  )}
                                                </div>
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}
                          {formatEvidence(cluster.evidence) && (
                            <div className="mt-2 text-xs theme-text-secondary leading-relaxed">
                              {formatEvidence(cluster.evidence)}
                            </div>
                          )}
                        </div>
                      )})}
                    </div>
                  ) : (
                    <div className="text-sm theme-text-dim">当前未形成可展示的关系簇</div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 高风险项目 - 可折叠（P0修复: 使用实际数据长度） */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-red-500">
              <button 
                onClick={() => toggleSection('highRisk')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div>
                  <h4 className="text-white text-sm font-medium mb-1">🔴 高风险项目</h4>
                  <div className="text-2xl font-bold text-red-400">
                    {/* P0修复: 使用实际数据长度，而非可能不一致的 stats */}
                    {graphData.report.high_risk_income.length}
                  </div>
                  <div className="text-xs theme-text-muted">建议优先核查</div>
                </div>
                {expandedSections['highRisk'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['highRisk'] && graphData.report.high_risk_income.length > 0 && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-48 overflow-y-auto">
                  <div className="space-y-2">
                    {graphData.report.high_risk_income.map((item, idx) => (
                      <button 
                        key={idx} 
                        onClick={() => setTransactionDetail({
                          type: 'high_risk_income',
                          person: item.person,
                          counterparty: item.counterparty,
                          amount: item.amount,
                          riskLevel: item.risk_level || 'high',
                          // 新增: 溯源信息
                          sourceFile: item.source_file,
                          sourceRow: item.source_row,
                          detail: item.detail,
                          incomeType: item.type
                        })}
                        className="w-full text-left p-2 rounded bg-white/5 hover:bg-white/10 transition-colors"
                      >
                        {/* P1修复: 明确标注付款方→收款方方向 */}
                        <div className="flex justify-between items-center text-sm">
                          <div className="flex items-center gap-1">
                            <span className="theme-text-muted">{formatCounterpartyWithWarning(item.counterparty)}</span>
                            <span className="theme-text-dim">→</span>
                            <span className="text-cyan-400">{item.person}</span>
                          </div>
                          <span className="text-red-400 font-mono">{formatAmount(item.amount)}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 借贷配对 - 可折叠 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-blue-500">
              <button 
                onClick={() => toggleSection('loanPairs')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <CreditCard className="w-5 h-5 text-blue-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">借贷配对</h4>
                    <div className="text-2xl font-bold text-blue-400">
                      {/* P0修复: 使用实际数据长度 */}
                      {graphData.report.loan_pairs.length}
                    </div>
                    <div className="text-xs theme-text-muted">双向资金往来</div>
                  </div>
                </div>
                {expandedSections['loanPairs'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['loanPairs'] && graphData.report.loan_pairs.length > 0 && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-48 overflow-y-auto">
                  <div className="space-y-2">
                    {graphData.report.loan_pairs.map((item, idx) => {
                      // 使用 income_total/expense_total 字段（bidirectional_flows 格式）
                      const loanAmount = item.income_total || 0;
                      const repayAmount = item.expense_total || 0;
                      const repayRate = loanAmount > 0
                        ? Math.round((repayAmount / loanAmount) * 100)
                        : 0;
                      return (
                        <button 
                          key={idx} 
                          onClick={() => setTransactionDetail({
                            type: 'loan_pair',
                            person: item.person,
                            counterparty: item.counterparty,
                            amount: loanAmount,
                            repayAmount: repayAmount
                          })}
                          className="w-full text-left p-2 rounded bg-white/5 hover:bg-white/10 transition-colors"
                        >
                          <div className="flex justify-between items-center text-sm">
                            <span className="theme-text-secondary">{item.person} ↔ {formatPartyName(item.counterparty)}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded ${repayRate >= 100 ? 'bg-green-500/20 text-green-400' : repayRate >= 50 ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'}`}>
                              {repayRate}%
                            </span>
                          </div>
                          <div className="flex justify-between text-xs mt-1">
                            <span className="text-green-400">借: {formatAmount(loanAmount)}</span>
                            <span className="text-red-400">还: {formatAmount(repayAmount)}</span>
                          </div>
                          {item.loan_type && (
                            <div className="text-xs theme-text-dim mt-1">{item.loan_type}</div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 无还款借贷 - 可折叠（P0修复: 使用实际数据长度） */}
          {graphData && graphData.report.no_repayment_loans.length > 0 && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-orange-500">
              <button 
                onClick={() => toggleSection('noRepayment')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-orange-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">无还款借贷</h4>
                    <div className="text-2xl font-bold text-orange-400">
                      {/* P0修复: 使用实际数据长度 */}
                      {graphData.report.no_repayment_loans.length}
                    </div>
                    <div className="text-xs theme-text-muted">疑似利益输送</div>
                  </div>
                </div>
                {expandedSections['noRepayment'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['noRepayment'] && graphData.report.no_repayment_loans.length > 0 && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-48 overflow-y-auto">
                  <div className="space-y-2">
                    {graphData.report.no_repayment_loans.map((item, idx) => (
                      <button 
                        key={idx} 
                        onClick={() => setTransactionDetail({
                          type: 'no_repayment',
                          person: item.person,
                          counterparty: item.counterparty,
                          amount: item.income_amount,
                          daysSince: item.days_since
                        })}
                        className="w-full text-left p-2 rounded bg-white/5 hover:bg-white/10 transition-colors"
                      >
                        {/* P1修复: 明确付款方→收款方 */}
                        <div className="flex justify-between items-center text-sm">
                          <div className="flex items-center gap-1">
                            <span className="theme-text-muted">{formatCounterpartyWithWarning(item.counterparty)}</span>
                            <span className="theme-text-dim">→</span>
                            <span className="text-cyan-400">{item.person}</span>
                          </div>
                          <span className="text-orange-400 font-mono">{formatAmount(item.income_amount)}</span>
                        </div>
                        <div className="flex justify-end text-xs mt-1">
                          <span className={item.days_since >= 180 ? 'text-red-400' : 'text-amber-400'}>
                            {item.days_since}天未还 {item.days_since >= 180 && '⚠️'}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 涉案公司 - 可折叠 */}
          {graphData && graphData.stats.involvedCompanyCount > 0 && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-purple-500">
              <button 
                onClick={() => toggleSection('companies')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Building2 className="w-5 h-5 text-purple-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">涉案公司</h4>
                    <div className="text-2xl font-bold text-cyan-400">
                      {graphData.stats.involvedCompanyCount}
                    </div>
                    <div className="text-xs theme-text-muted">重点监控企业</div>
                  </div>
                </div>
                {expandedSections['companies'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['companies'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3">
                  <div className="space-y-2">
                    {graphData.nodes
                      .filter(node => node.group === 'involved_company')
                      .map((node, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm theme-text-secondary p-2 rounded bg-white/5">
                          <div className="w-3 h-3 rounded bg-orange-500"></div>
                          {formatPartyName(String(node.label))}
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 网贷平台 - 可折叠 */}
          {graphData && graphData.report.online_loans.length > 0 && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden border-l-4 border-violet-500">
              <button 
                onClick={() => toggleSection('onlineLoans')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <Landmark className="w-5 h-5 text-violet-400" />
                  <div>
                    <h4 className="text-white text-sm font-medium">网贷平台</h4>
                    <div className="text-2xl font-bold text-violet-400">
                      {Object.keys(graphData.report.online_loans.reduce((acc, curr) => {
                        acc[curr.platform] = true;
                        return acc;
                      }, {} as Record<string, boolean>)).length}
                    </div>
                    <div className="text-xs theme-text-muted">涉及平台数</div>
                  </div>
                </div>
                {expandedSections['onlineLoans'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['onlineLoans'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3 max-h-48 overflow-y-auto">
                  <div className="space-y-2">
                    {Object.entries(
                      graphData.report.online_loans.reduce((acc, curr) => {
                        if (!acc[curr.platform]) {
                          acc[curr.platform] = { amount: 0, count: 0 };
                        }
                        acc[curr.platform].amount += curr.amount;
                        acc[curr.platform].count += 1;
                        return acc;
                      }, {} as Record<string, { amount: number; count: number }>)
                    )
                      .sort(([, a], [, b]) => b.amount - a.amount)
                      .map(([platform, stats], idx) => (
                        <div key={idx} className="p-2 rounded bg-white/5 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="theme-text-secondary">{platform}</span>
                            <span className="text-violet-400 font-mono">{formatAmount(stats.amount)}</span>
                          </div>
                          <div className="text-xs theme-text-dim mt-1">{stats.count}笔交易</div>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 资金流向统计 - 可展开（P2修复: 添加穿透能力） */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg overflow-hidden mt-6">
              <button 
                onClick={() => toggleSection('flowStats')}
                className="w-full p-4 hover:bg-white/5 transition-colors text-left flex items-center justify-between"
              >
                <div>
                  <h3 className="text-cyan-400 font-bold text-sm">📊 资金流向统计</h3>
                  <div className="text-xs theme-text-muted mt-1">
                    共 {graphData.stats.coreEdgeCount + graphData.stats.companyEdgeCount + graphData.stats.otherEdgeCount} 条资金流向
                  </div>
                </div>
                {expandedSections['flowStats'] ? 
                  <ChevronUp className="w-5 h-5 theme-text-muted" /> : 
                  <ChevronDown className="w-5 h-5 theme-text-muted" />
                }
              </button>
              {expandedSections['flowStats'] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-3">
                  <div className="space-y-3">
                    {/* 核心人员间 */}
                    <div className="bg-red-500/10 rounded p-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-red-400 font-medium">🔴 核心人员间</span>
                        <span className="text-sm text-cyan-400">{graphData.stats.coreEdgeCount} 条</span>
                      </div>
                      <div className="text-xs theme-text-dim mt-1">核心审查对象之间的直接资金往来</div>
                    </div>
                    {/* 公司间交易 */}
                    <div className="bg-orange-500/10 rounded p-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-orange-400 font-medium">🏢 公司间交易</span>
                        <span className="text-sm text-cyan-400">{graphData.stats.companyEdgeCount} 条</span>
                      </div>
                      <div className="text-xs theme-text-dim mt-1">涉案公司的业务往来</div>
                    </div>
                    {/* 核心-外部 */}
                    <div className="bg-teal-500/10 rounded p-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-teal-400 font-medium">🔵 核心-外部</span>
                        <span className="text-sm text-cyan-400">{graphData.stats.otherEdgeCount} 条</span>
                      </div>
                      <div className="text-xs theme-text-dim mt-1">核心人员与外部实体的资金流动</div>
                    </div>
                  </div>
                  <div className="mt-3 pt-2 border-t border-white/10 text-xs theme-text-dim italic">
                    💡 图中线条越粗，累计金额越大
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 图例说明 */}
          {graphData && (
            <div className="mt-6">
              <h3 className="text-cyan-400 font-bold text-sm mb-3 pb-2 border-b border-white/10">
                🎨 图例说明
              </h3>
              <div className="space-y-2 text-xs">
                <div className="legend-item flex items-center space-x-2">
                  <div className="legend-color w-5 h-5 rounded-full bg-red-500"></div>
                  <span>🔴 核心人员</span>
                </div>
                <div className="legend-item flex items-center space-x-2">
                  <div className="legend-color w-5 h-5 rounded bg-orange-500"></div>
                  <span>🏢 涉案公司（重点）</span>
                </div>
                <div className="legend-item flex items-center space-x-2">
                  <div className="legend-color w-5 h-5 rounded-full bg-teal-500"></div>
                  <span>🔵 其他关联方</span>
                </div>
              </div>
            </div>
          )}

          {/* 操作提示 */}
          {graphData && (
            <div className="mt-6">
              <h3 className="text-cyan-400 font-bold text-sm mb-3 pb-2 border-b border-white/10">
                💡 操作提示
              </h3>
              <div className="text-xs theme-text-muted leading-relaxed space-y-1">
                <div>• 拖拽节点可调整位置</div>
                <div>• 滚轮缩放视图</div>
                <div>• 悬停查看交易详情</div>
                <div>• 点击图中节点/边会自动联动到右侧最相关路径</div>
                <div>• 导航按钮在右下角</div>
              </div>
            </div>
          )}
        </div>

        {/* 底部刷新按钮 */}
        <div className="p-4 border-t border-white/10">
          <button
            onClick={fetchGraphData}
            disabled={loading}
            className="w-full py-2 px-4 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded font-medium text-sm transition-all disabled:from-gray-600 disabled:to-gray-600 disabled:cursor-not-allowed"
          >
            {loading ? '加载中...' : '🔄 刷新数据'}
          </button>
        </div>
      </div>

      {/* 右侧主区域 (改为可滚动) */}
      <div ref={exportRef} className="flex-1 flex flex-col overflow-y-auto h-full">
        {/* 顶部标题栏 */}
        <div className="h-16 flex-shrink-0 flex items-center justify-between px-6 bg-white/5 backdrop-blur-sm border-b border-white/10 sticky top-0 z-20">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              {viewMode === 'graph' ? '💰 资金流向可视化分析' : '📑 完整资金流向报告'}
            </h2>
            {viewMode === 'graph' && graphData && (
              <div className="text-sm theme-text-muted">
                共 <span className="text-cyan-400">{graphData.stats.nodeCount}</span> 个节点,
                <span className="text-cyan-400"> {graphData.stats.edgeCount}</span> 条资金流向
              </div>
            )}
          </div>
          <div className="flex items-center gap-4">
            {activeSelection && (
              <div className="max-w-[520px] rounded-lg border border-cyan-400/20 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-200">
                联动路径: {activeSelection.path || activeSelection.label}
              </div>
            )}
            {selectedNode && (
              <div className="text-sm text-cyan-400">
                选中: {selectedNode.label} ({selectedNode.group})
              </div>
            )}
          </div>
        </div>

        {/* 图表区域 (固定高度) */}
        <div className="h-[600px] flex-shrink-0 relative border-b border-white/10 theme-bg-base/50">
          {viewMode === 'report' && reportUrl ? (
            <iframe
              src={reportUrl}
              className="w-full h-full border-none bg-white"
              title="Funds Flow Report"
            />
          ) : (
            <>
              {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10 transition-opacity duration-300">
                  <div className="text-center">
                    <div className="loading-spinner w-10 h-10 border-3 border-white/20 border-t-cyan-400 rounded-full animate-spin mx-auto mb-3"></div>
                    <div className="text-cyan-400 font-medium">数据分析中...</div>
                  </div>
                </div>
              )}

              {error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 z-10">
                  <div className="text-red-400 mb-4 text-lg font-medium">{error}</div>
                  <button
                    onClick={fetchGraphData}
                    className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-lg font-medium transition-all shadow-lg shadow-cyan-500/20"
                  >
                    重新加载
                  </button>
                  {reportUrl && (
                    <button
                      onClick={() => setViewMode('report')}
                      className="mt-4 theme-text-muted text-sm hover:text-white underline"
                    >
                      查看静态报告
                    </button>
                  )}
                </div>
              )}

              {!graphData && !loading && !error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 z-10">
                  <div className="theme-text-muted mb-4 text-lg">暂无图谱数据</div>
                  <button
                    onClick={fetchGraphData}
                    className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-lg font-medium transition-all shadow-lg shadow-cyan-500/20"
                  >
                    加载数据
                  </button>
                </div>
              )}

              <div ref={networkRef} className="w-full" style={{ height: '580px' }} />
            </>
          )}
        </div>

        {/* 采样提示信息 */}
        {graphData && graphData.sampling && (
          <div className="px-6 py-3 bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-b border-white/10">
            <div className="flex items-center gap-2 text-sm">
              <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <p className="theme-text-secondary">
                {graphData.sampling.message}
                <span className="text-amber-300 ml-2">
                  (展示 {graphData.sampling.sampledNodes}/{graphData.sampling.totalNodes} 节点,
                  {graphData.sampling.sampledEdges}/{graphData.sampling.totalEdges} 连线)
                </span>
              </p>
            </div>
          </div>
        )}

        {/* 底部报告区域已移除，详情通过左侧二级菜单展开查看 */}
      </div>
    </div>
  );
};

export default NetworkGraph;
