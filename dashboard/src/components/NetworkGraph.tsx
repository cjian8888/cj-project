import { useEffect, useRef, useState } from 'react';
import { Network, DataSet } from 'vis-network/standalone';
import type { Data, Node, Edge, Options } from 'vis-network/standalone';
import { API_BASE_URL } from '../services/api';
import {
  AlertTriangle,
  CreditCard,
  Banknote,
  Landmark,
  Info
} from 'lucide-react';

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
      loan_amount: number;
      repay_amount: number;
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
    }>;
    online_loans: Array<{
      platform: string;
      amount: number;
    }>;
  };
}

function NetworkGraph({ onLog }: NetworkGraphProps) {
  const networkRef = useRef<HTMLDivElement>(null);
  const networkInstance = useRef<Network | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<{ label: string; group: string } | null>(null);

  // 获取图谱数据
  const fetchGraphData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Add 10s timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

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
          label: node.label,
          value: nodeSize,
          size: nodeSize,
          group: node.group,
          title: `【${node.label}】\n${getGroupLabel(node.group || 'other')}`
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
    <div className="h-full w-full flex bg-gradient-to-br from-gray-900 to-slate-900 text-white" style={{ minHeight: '700px' }}>
      {/* 左侧统计面板 */}
      <div className="w-80 flex-shrink-0 bg-white/5 backdrop-blur-sm border-r border-white/10 flex flex-col">
        <div className="p-4 border-b border-white/10">
          <h3 className="text-cyan-400 font-bold text-lg mb-2">📊 数据概览</h3>
          {graphData && (
            <p className="text-xs text-gray-400">
              生成时间: {new Date().toLocaleString('zh-CN')}
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* 空状态提示 */}
          {!graphData && !loading && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                <Info className="w-8 h-8 text-gray-500" />
              </div>
              <h4 className="text-gray-400 font-medium mb-2">暂无图谱数据</h4>
              <p className="text-xs text-gray-500 leading-relaxed max-w-[200px]">
                请先在侧边栏点击"启动引擎"运行分析，完成后数据将自动加载
              </p>
            </div>
          )}

          {/* 加载状态 */}
          {loading && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-10 h-10 border-3 border-white/20 border-t-cyan-400 rounded-full animate-spin mb-4"></div>
              <p className="text-sm text-gray-400">正在加载图谱数据...</p>
            </div>
          )}

          {/* 核心人员 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg p-4 hover:translate-x-1 transition-transform cursor-default">
              <h4 className="text-white text-sm font-medium mb-2">核心人员</h4>
              <div className="value text-2xl font-bold text-cyan-400 mb-1">
                {graphData.stats.corePersonCount}
              </div>
              <div className="desc text-xs text-gray-400 leading-relaxed">
                {graphData.stats.corePersonNames.join(', ')}
              </div>
            </div>
          )}

          {/* 高风险项目 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg p-4 border-l-4 border-red-500 hover:translate-x-1 transition-transform cursor-default">
              <h4 className="text-white text-sm font-medium mb-2">🔴 高风险项目</h4>
              <div className="value text-2xl font-bold text-cyan-400 mb-1">
                {graphData.stats.highRiskCount}
              </div>
              <div className="desc text-xs text-gray-400">建议优先核查</div>
            </div>
          )}

          {/* 中风险项目 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg p-4 border-l-4 border-yellow-500 hover:translate-x-1 transition-transform cursor-default">
              <h4 className="text-white text-sm font-medium mb-2">🟡 中风险项目</h4>
              <div className="value text-2xl font-bold text-cyan-400 mb-1">
                {graphData.stats.mediumRiskCount}
              </div>
              <div className="desc text-xs text-gray-400">需酌情关注</div>
            </div>
          )}

          {/* 借贷配对 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg p-4 hover:translate-x-1 transition-transform cursor-default">
              <h4 className="text-white text-sm font-medium mb-2">借贷配对</h4>
              <div className="value text-2xl font-bold text-cyan-400">
                {graphData.stats.loanPairCount}
              </div>
            </div>
          )}

          {/* 涉案公司 */}
          {graphData && (
            <div className="stat-card bg-white/10 rounded-lg p-4 border-l-4 border-orange-500 hover:translate-x-1 transition-transform cursor-default">
              <h4 className="text-white text-sm font-medium mb-2">涉案公司</h4>
              <div className="value text-2xl font-bold text-cyan-400 mb-1">
                {graphData.stats.involvedCompanyCount}
              </div>
              <div className="desc text-xs text-gray-400 leading-relaxed">
                重点监控企业
              </div>
            </div>
          )}

          {/* 资金流向统计 */}
          {graphData && (
            <div className="mt-6">
              <h3 className="text-cyan-400 font-bold text-sm mb-3 pb-2 border-b border-white/10">
                📊 资金流向统计
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed space-y-1">
                <div>• 核心人员间: <span className="text-cyan-400">{graphData.stats.coreEdgeCount}笔</span></div>
                <div>• 公司间交易: <span className="text-cyan-400">{graphData.stats.companyEdgeCount}笔</span></div>
                <div>• 核心-外部: <span className="text-cyan-400">{graphData.stats.otherEdgeCount}笔</span></div>
                <div className="pt-2 text-gray-500 italic">• 线条越粗金额越大</div>
              </p>
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
              <p className="text-xs text-gray-400 leading-relaxed space-y-1">
                <div>• 拖拽节点可调整位置</div>
                <div>• 滚轮缩放视图</div>
                <div>• 悬停查看交易详情</div>
                <div>• 导航按钮在右下角</div>
              </p>
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
      <div className="flex-1 flex flex-col overflow-y-auto h-full">
        {/* 顶部标题栏 */}
        <div className="h-16 flex-shrink-0 flex items-center justify-between px-6 bg-white/5 backdrop-blur-sm border-b border-white/10 sticky top-0 z-20">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              💰 资金流向可视化分析
            </h2>
            {graphData && (
              <div className="text-sm text-gray-400">
                共 <span className="text-cyan-400">{graphData.stats.nodeCount}</span> 个节点,
                <span className="text-cyan-400"> {graphData.stats.edgeCount}</span> 条资金流向
              </div>
            )}
          </div>
          {selectedNode && (
            <div className="text-sm text-cyan-400">
              选中: {selectedNode.label} ({selectedNode.group})
            </div>
          )}
        </div>

        {/* 图表区域 (固定高度) */}
        <div className="h-[600px] flex-shrink-0 relative border-b border-white/10 bg-gray-900/50">
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
            </div>
          )}

          {!graphData && !loading && !error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 z-10">
              <div className="text-gray-400 mb-4 text-lg">暂无图谱数据</div>
              <button
                onClick={fetchGraphData}
                className="px-6 py-2 bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white rounded-lg font-medium transition-all shadow-lg shadow-cyan-500/20"
              >
                加载数据
              </button>
            </div>
          )}

          <div ref={networkRef} className="w-full h-full" />
        </div>

        {/* 采样提示信息 */}
        {graphData && graphData.sampling && (
          <div className="px-6 py-3 bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-b border-white/10">
            <div className="flex items-center gap-2 text-sm">
              <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <p className="text-gray-300">
                {graphData.sampling.message}
                <span className="text-amber-300 ml-2">
                  (展示 {graphData.sampling.sampledNodes}/{graphData.sampling.totalNodes} 节点,
                  {graphData.sampling.sampledEdges}/{graphData.sampling.totalEdges} 连线)
                </span>
              </p>
            </div>
          </div>
        )}

        {/* 详细核查报告区域 */}
        {graphData && graphData.report && (
          <div className="p-8 space-y-8 bg-gradient-to-b from-gray-900 to-slate-900">
            <div className="flex items-center gap-2 mb-6 border-b border-white/10 pb-4">
              <Banknote className="w-6 h-6 text-cyan-400" />
              <h3 className="text-xl font-bold text-white">详细核查报告</h3>
              <span className="px-2 py-0.5 rounded text-xs bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">AI 分析生成</span>
            </div>

            {/* 1. 借贷关系图 */}
            <div className="report-section">
              <h4 className="flex items-center gap-2 text-lg font-semibold text-white mb-4">
                <CreditCard className="w-5 h-5 text-blue-400" />
                借贷关系分析
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                  <div className="px-4 py-3 border-b border-white/10 bg-white/5 font-medium text-blue-300">
                    疑似借贷配对 (借入/还款)
                  </div>
                  {graphData.report.loan_pairs.length > 0 ? (
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 bg-black/20 text-xs">
                        <tr>
                          <th className="px-4 py-2 text-left">借款人</th>
                          <th className="px-4 py-2 text-left">出借人</th>
                          <th className="px-4 py-2 text-right">借入金额</th>
                          <th className="px-4 py-2 text-right">还款金额</th>
                          <th className="px-4 py-2 text-center">还款率</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {graphData.report.loan_pairs.map((item, idx) => {
                          const repayRate = item.loan_amount > 0
                            ? Math.round((item.repay_amount / item.loan_amount) * 100)
                            : 0;
                          const rateColor = repayRate >= 100 ? 'text-green-400' :
                            repayRate >= 50 ? 'text-amber-400' : 'text-red-400';
                          const rateBg = repayRate >= 100 ? 'bg-green-500/20' :
                            repayRate >= 50 ? 'bg-amber-500/20' : 'bg-red-500/20';
                          return (
                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                              <td className="px-4 py-3 text-gray-300">{item.person}</td>
                              <td className="px-4 py-3 text-gray-300">{item.counterparty}</td>
                              <td className="px-4 py-3 text-right text-green-400 font-mono">
                                ¥{item.loan_amount >= 10000 ? (item.loan_amount / 10000).toFixed(1) + '万' : item.loan_amount.toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-right text-red-400 font-mono">
                                ¥{item.repay_amount >= 10000 ? (item.repay_amount / 10000).toFixed(1) + '万' : item.repay_amount.toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${rateBg} ${rateColor}`}>
                                  {repayRate}%
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  ) : (
                    <div className="p-6 text-center text-gray-500 text-sm">暂无借贷配对记录</div>
                  )}
                </div>

                <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                  <div className="px-4 py-3 border-b border-white/10 bg-white/5 font-medium text-orange-400 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    无还款大额借贷 (疑似利益输送)
                  </div>
                  {graphData.report.no_repayment_loans.length > 0 ? (
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 bg-black/20 text-xs">
                        <tr>
                          <th className="px-4 py-2 text-left">借款人</th>
                          <th className="px-4 py-2 text-left">出借人</th>
                          <th className="px-4 py-2 text-right">金额</th>
                          <th className="px-4 py-2 text-right">未还天数</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {graphData.report.no_repayment_loans.map((item, idx) => (
                          <tr key={idx} className="hover:bg-white/5 transition-colors">
                            <td className="px-4 py-3 text-gray-300">{item.person}</td>
                            <td className="px-4 py-3 text-gray-300">{item.counterparty}</td>
                            <td className="px-4 py-3 text-right text-orange-400 font-bold font-mono">¥{(item.income_amount / 10000).toFixed(1)}万</td>
                            <td className={`px-4 py-3 text-right font-semibold ${item.days_since >= 180 ? 'text-red-400' :
                              item.days_since >= 90 ? 'text-amber-400' : 'text-green-400'
                              }`}>
                              {item.days_since}天
                              {item.days_since >= 180 && <span className="ml-1 text-[10px]">⚠️</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="p-6 text-center text-gray-500 text-sm">暂无无还款记录</div>
                  )}
                </div>
              </div>
            </div>

            {/* 2. 异常收入与网贷 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 高风险收入 */}
              <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                <div className="px-4 py-3 border-b border-white/10 bg-white/5 font-medium text-red-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  高风险异常收入来源
                </div>
                {graphData.report.high_risk_income.length > 0 ? (
                  <div className="max-h-60 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 bg-black/20 text-xs sticky top-0 backdrop-blur-md">
                        <tr>
                          <th className="px-4 py-2 text-left">收款人</th>
                          <th className="px-4 py-2 text-left">来源方</th>
                          <th className="px-4 py-2 text-right">金额</th>
                          <th className="px-4 py-2 text-center">风险</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {graphData.report.high_risk_income.map((item, idx) => {
                          const riskLevel = item.risk_level || 'high';
                          const riskConfig = {
                            high: { bg: 'bg-red-500/20', text: 'text-red-400', label: '高' },
                            medium: { bg: 'bg-amber-500/20', text: 'text-amber-400', label: '中' },
                            low: { bg: 'bg-green-500/20', text: 'text-green-400', label: '低' }
                          }[riskLevel] || { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '?' };
                          return (
                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                              <td className="px-4 py-3 text-gray-300">{item.person}</td>
                              <td className="px-4 py-3 text-gray-300">{item.counterparty}</td>
                              <td className="px-4 py-3 text-right text-red-400 font-bold font-mono">
                                ¥{item.amount >= 10000 ? (item.amount / 10000).toFixed(1) + '万' : item.amount.toFixed(0)}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${riskConfig.bg} ${riskConfig.text}`}>
                                  {riskConfig.label}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-6 text-center text-gray-500 text-sm">暂无高风险收入记录</div>
                )}
              </div>

              {/* 网贷统计 */}
              <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                <div className="px-4 py-3 border-b border-white/10 bg-white/5 font-medium text-violet-400 flex items-center gap-2">
                  <Landmark className="w-4 h-4" />
                  网贷平台互动统计
                </div>
                {graphData.report.online_loans.length > 0 ? (
                  <div className="max-h-60 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="text-gray-400 bg-black/20 text-xs sticky top-0 backdrop-blur-md">
                        <tr>
                          <th className="px-4 py-2 text-left">平台/机构</th>
                          <th className="px-4 py-2 text-right">涉及金额</th>
                          <th className="px-4 py-2 text-center">笔数</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {/* 聚合统计：金额+笔数 */}
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
                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                              <td className="px-4 py-3 text-gray-300">{platform}</td>
                              <td className="px-4 py-3 text-right text-violet-400 font-mono">
                                ¥{stats.amount >= 10000 ? (stats.amount / 10000).toFixed(1) + '万' : stats.amount.toLocaleString()}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${stats.count >= 5 ? 'bg-amber-500/20 text-amber-400' : 'text-gray-400'
                                  }`}>
                                  {stats.count}笔
                                </span>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-6 text-center text-gray-500 text-sm">无网贷平台记录</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default NetworkGraph;
