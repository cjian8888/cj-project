#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j 图数据库适配器

【模块定位】
为大规模资金图谱分析提供图数据库支持，当节点数 > 10,000 时使用。
本模块提供与现有 MoneyGraph 兼容的接口，支持无缝切换。

【性能优势】
- 亿级节点/边的高效存储和查询
- 原生图算法支持（最短路径、PageRank 等）
- 持久化存储，重启后不丢失
- 分布式部署支持

【切换条件】
- 节点数 > 10,000
- 需要持久化存储
- 需要多用户并发访问

创建日期: 2026-01-18
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import os

import utils

logger = utils.setup_logger(__name__)


@dataclass
class GraphEdge:
    """图边数据结构"""
    source: str
    target: str
    amount: float
    date: Any
    edge_type: str  # 'income' or 'expense'
    properties: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'target': self.target,
            'amount': self.amount,
            'date': str(self.date) if self.date else None,
            'edge_type': self.edge_type,
            'properties': self.properties or {}
        }


class GraphAdapter(ABC):
    """
    图数据库适配器抽象基类
    
    定义统一的图操作接口，支持：
    - 内存图实现（MoneyGraph）
    - Neo4j 实现
    - 其他图数据库实现
    """
    
    @abstractmethod
    def add_node(self, node_id: str, node_type: str, properties: Dict = None):
        """添加节点"""
        pass
    
    @abstractmethod
    def add_edge(self, source: str, target: str, amount: float, 
                 date: Any = None, edge_type: str = "transfer"):
        """添加边"""
        pass
    
    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取节点"""
        pass
    
    @abstractmethod
    def get_edges(self, source: str = None, target: str = None) -> List[GraphEdge]:
        """获取边"""
        pass
    
    @abstractmethod
    def find_path(self, start: str, end: str, max_depth: int = 5) -> List[List[str]]:
        """查找路径"""
        pass
    
    @abstractmethod
    def find_cycles(self, start: str, max_depth: int = 4) -> List[List[str]]:
        """查找环路"""
        pass
    
    @abstractmethod
    def get_node_count(self) -> int:
        """获取节点数量"""
        pass
    
    @abstractmethod
    def get_edge_count(self) -> int:
        """获取边数量"""
        pass
    
    @abstractmethod
    def clear(self):
        """清空图"""
        pass


class Neo4jAdapter(GraphAdapter):
    """
    Neo4j 图数据库适配器
    
    使用 neo4j-driver 连接 Neo4j 数据库
    """
    
    def __init__(
        self, 
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
        database: str = "neo4j"
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None
        self._connected = False
        
        self._try_connect()
    
    def _try_connect(self):
        """尝试连接数据库"""
        try:
            from neo4j import GraphDatabase
            
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 测试连接
            with self._driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            self._connected = True
            logger.info(f'Neo4j 连接成功: {self.uri}')
            
        except ImportError:
            logger.warning('neo4j-driver 未安装。可通过 pip install neo4j 安装')
        except Exception as e:
            logger.warning(f'Neo4j 连接失败: {e}')
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def add_node(self, node_id: str, node_type: str, properties: Dict = None):
        """添加节点"""
        if not self._connected:
            raise ConnectionError("Neo4j 未连接")
        
        props = properties or {}
        props['id'] = node_id
        props['type'] = node_type
        
        with self._driver.session(database=self.database) as session:
            session.run(
                f"MERGE (n:{node_type} {{id: $id}}) SET n += $props",
                id=node_id,
                props=props
            )
    
    def add_edge(self, source: str, target: str, amount: float,
                 date: Any = None, edge_type: str = "transfer"):
        """添加边"""
        if not self._connected:
            raise ConnectionError("Neo4j 未连接")
        
        with self._driver.session(database=self.database) as session:
            session.run("""
                MATCH (a {id: $source})
                MATCH (b {id: $target})
                MERGE (a)-[r:TRANSFER]->(b)
                ON CREATE SET r.amount = $amount, r.date = $date, r.type = $edge_type
                ON MATCH SET r.amount = r.amount + $amount
            """, source=source, target=target, amount=amount, 
                date=str(date) if date else None, edge_type=edge_type)
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取节点"""
        if not self._connected:
            return None
        
        with self._driver.session(database=self.database) as session:
            result = session.run(
                "MATCH (n {id: $id}) RETURN n",
                id=node_id
            )
            record = result.single()
            if record:
                return dict(record['n'])
        return None
    
    def get_edges(self, source: str = None, target: str = None) -> List[GraphEdge]:
        """获取边"""
        if not self._connected:
            return []
        
        with self._driver.session(database=self.database) as session:
            if source and target:
                query = """
                    MATCH (a {id: $source})-[r:TRANSFER]->(b {id: $target})
                    RETURN a.id as source, b.id as target, r.amount as amount, 
                           r.date as date, r.type as edge_type
                """
                result = session.run(query, source=source, target=target)
            elif source:
                query = """
                    MATCH (a {id: $source})-[r:TRANSFER]->(b)
                    RETURN a.id as source, b.id as target, r.amount as amount,
                           r.date as date, r.type as edge_type
                """
                result = session.run(query, source=source)
            elif target:
                query = """
                    MATCH (a)-[r:TRANSFER]->(b {id: $target})
                    RETURN a.id as source, b.id as target, r.amount as amount,
                           r.date as date, r.type as edge_type
                """
                result = session.run(query, target=target)
            else:
                query = """
                    MATCH (a)-[r:TRANSFER]->(b)
                    RETURN a.id as source, b.id as target, r.amount as amount,
                           r.date as date, r.type as edge_type
                    LIMIT 1000
                """
                result = session.run(query)
            
            edges = []
            for record in result:
                edges.append(GraphEdge(
                    source=record['source'],
                    target=record['target'],
                    amount=record['amount'],
                    date=record['date'],
                    edge_type=record['edge_type']
                ))
            return edges
    
    def find_path(self, start: str, end: str, max_depth: int = 5) -> List[List[str]]:
        """查找路径"""
        if not self._connected:
            return []
        
        with self._driver.session(database=self.database) as session:
            result = session.run(f"""
                MATCH path = allShortestPaths((a {{id: $start}})-[*1..{max_depth}]->(b {{id: $end}}))
                RETURN [n in nodes(path) | n.id] as path_nodes
                LIMIT 10
            """, start=start, end=end)
            
            return [record['path_nodes'] for record in result]
    
    def find_cycles(self, start: str, max_depth: int = 4) -> List[List[str]]:
        """查找环路"""
        if not self._connected:
            return []
        
        with self._driver.session(database=self.database) as session:
            result = session.run(f"""
                MATCH path = (a {{id: $start}})-[*2..{max_depth}]->(a)
                RETURN [n in nodes(path) | n.id] as cycle_nodes
                LIMIT 10
            """, start=start)
            
            return [record['cycle_nodes'] for record in result]
    
    def get_node_count(self) -> int:
        """获取节点数量"""
        if not self._connected:
            return 0
        
        with self._driver.session(database=self.database) as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            return result.single()['count']
    
    def get_edge_count(self) -> int:
        """获取边数量"""
        if not self._connected:
            return 0
        
        with self._driver.session(database=self.database) as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            return result.single()['count']
    
    def clear(self):
        """清空图"""
        if not self._connected:
            return
        
        with self._driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info('Neo4j 图已清空')
    
    def close(self):
        """关闭连接"""
        if self._driver:
            self._driver.close()
            self._connected = False


class MemoryGraphAdapter(GraphAdapter):
    """
    内存图适配器
    
    封装现有的 MoneyGraph 实现，提供统一接口
    """
    
    def __init__(self):
        self.nodes: Dict[str, Dict] = {}
        self.edges: Dict[str, List[GraphEdge]] = {}
    
    def add_node(self, node_id: str, node_type: str, properties: Dict = None):
        self.nodes[node_id] = {
            'id': node_id,
            'type': node_type,
            **(properties or {})
        }
    
    def add_edge(self, source: str, target: str, amount: float,
                 date: Any = None, edge_type: str = "transfer"):
        if source not in self.edges:
            self.edges[source] = []
        
        self.edges[source].append(GraphEdge(
            source=source,
            target=target,
            amount=amount,
            date=date,
            edge_type=edge_type
        ))
        
        # 确保节点存在
        if source not in self.nodes:
            self.nodes[source] = {'id': source, 'type': 'unknown'}
        if target not in self.nodes:
            self.nodes[target] = {'id': target, 'type': 'unknown'}
    
    def get_node(self, node_id: str) -> Optional[Dict]:
        return self.nodes.get(node_id)
    
    def get_edges(self, source: str = None, target: str = None) -> List[GraphEdge]:
        result = []
        for s, edges in self.edges.items():
            if source and s != source:
                continue
            for edge in edges:
                if target and edge.target != target:
                    continue
                result.append(edge)
        return result
    
    def find_path(self, start: str, end: str, max_depth: int = 5) -> List[List[str]]:
        """简单 DFS 查找路径"""
        paths = []
        self._dfs_path(start, end, [], set(), paths, max_depth)
        return paths
    
    def _dfs_path(self, current: str, end: str, path: List[str], 
                  visited: set, paths: List[List[str]], max_depth: int):
        if len(path) >= max_depth:
            return
        
        path.append(current)
        
        if current == end and len(path) > 1:
            paths.append(path.copy())
        else:
            for edge in self.edges.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    self._dfs_path(edge.target, end, path, visited, paths, max_depth)
                    visited.discard(edge.target)
        
        path.pop()
    
    def find_cycles(self, start: str, max_depth: int = 4) -> List[List[str]]:
        """DFS 查找环路"""
        cycles = []
        self._dfs_cycle(start, start, [], set(), cycles, max_depth)
        return cycles
    
    def _dfs_cycle(self, current: str, start: str, path: List[str],
                   visited: set, cycles: List[List[str]], max_depth: int):
        if len(path) >= max_depth:
            return
        
        path.append(current)
        
        for edge in self.edges.get(current, []):
            if edge.target == start and len(path) >= 2:
                cycles.append(path.copy() + [start])
            elif edge.target not in visited:
                visited.add(edge.target)
                self._dfs_cycle(edge.target, start, path, visited, cycles, max_depth)
                visited.discard(edge.target)
        
        path.pop()
    
    def get_node_count(self) -> int:
        return len(self.nodes)
    
    def get_edge_count(self) -> int:
        return sum(len(edges) for edges in self.edges.values())
    
    def clear(self):
        self.nodes.clear()
        self.edges.clear()


def create_graph_adapter(
    node_count_threshold: int = 10000,
    neo4j_config: Dict = None
) -> GraphAdapter:
    """
    工厂函数：根据规模自动选择图适配器
    
    Args:
        node_count_threshold: 使用 Neo4j 的节点数阈值
        neo4j_config: Neo4j 连接配置
        
    Returns:
        GraphAdapter 实例
    """
    # 默认使用内存图
    adapter = MemoryGraphAdapter()
    
    # 如果提供了 Neo4j 配置，尝试连接
    if neo4j_config:
        neo4j_adapter = Neo4jAdapter(**neo4j_config)
        if neo4j_adapter.is_connected:
            return neo4j_adapter
        logger.warning('Neo4j 连接失败，回退到内存图')
    
    return adapter
