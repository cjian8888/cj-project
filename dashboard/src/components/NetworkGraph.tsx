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
  const [viewMode, setViewMode] = useState<'graph' | 'report'>('graph');
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  // P0-1: 交易详情 Modal 状态
  const [transactionDetail, setTransactionDetail] = useState<TransactionDetail | null>(null);
  // 导出快照引用（保留用于未来功能）
  const exportRef = useRef<HTMLDivElement>(null);
  // 左侧菜单展开状态
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  
  // 切换展开/折叠状态
  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
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
      const processedEdges = graphData.edges.map(edge => ({
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
          }
        } else {
          setSelectedNode(null);
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
