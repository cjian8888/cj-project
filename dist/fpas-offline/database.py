#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块 - SQLite 数据持久化

【模块定位】
数据库持久化模块，用于：
1. 交易数据的存储和查询
2. 分析结果的缓存和检索
3. 历史数据的管理
4. 增量数据更新支持

【审计价值】
- 提高数据查询效率
- 支持历史数据对比分析
- 便于数据追溯和审计
- 支持增量分析，提高处理效率

【技术实现】
- SQLite 数据库
- ORM 风格的数据访问
- 支持批量操作
- 支持事务处理
"""

import sqlite3
import pandas as pd
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import os

import config
import utils

logger = utils.setup_logger(__name__)


def _normalize_required_amount(value: Any) -> float:
    """归一化必填金额字段，无法解析时回退为0。"""
    return utils.format_amount(value)


def _normalize_optional_amount(value: Any) -> Optional[float]:
    """归一化可选金额字段，空值和脏值保留为None。"""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", "--"}:
        return None
    if not any(ch.isdigit() for ch in text):
        return None
    return utils.format_amount(value)


def _normalize_transaction_date(value: Any) -> str:
    """统一交易日期文本，兼容 Excel 序列值和脏日期。"""
    parsed = utils.parse_date(value)
    if parsed is None:
        return str(value or "").strip()
    if parsed.hour or parsed.minute or parsed.second:
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    return parsed.strftime("%Y-%m-%d")


class DatabaseManager:
    """
    数据库管理器
    
    功能：
    1. 数据库初始化和表结构管理
    2. 数据的增删改查
    3. 批量操作支持
    4. 事务管理
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，默认为 ./data/audit_system.db
        """
        if db_path is None:
            db_path = os.path.join(config.OUTPUT_DIR, 'data', 'audit_system.db')
        
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 支持字典式访问
        return conn
    
    def transaction(self):
        """
        事务上下文管理器
        
        用法:
            with db.transaction():
                # 多个数据库操作
                db.insert_transactions(...)
                db.upsert_profile(...)
                # 如果发生异常，自动回滚
                # 否则自动提交
        """
        class TransactionContext:
            def __init__(self, db_manager):
                self.db_manager = db_manager
                self.conn = None
                self.cursor = None
            
            def __enter__(self):
                self.conn = self.db_manager._get_connection()
                self.cursor = self.conn.cursor()
                # 开始事务（SQLite默认是自动提交模式，需要显式关闭）
                self.conn.execute('BEGIN')
                return self.conn, self.cursor
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    # 没有异常，提交事务
                    self.conn.commit()
                    logger.debug('事务提交成功')
                else:
                    # 有异常，回滚事务
                    self.conn.rollback()
                    logger.warning(f'事务回滚: {exc_type.__name__}: {exc_val}')
                self.conn.close()
                # 返回False表示不抑制异常
                return False
        
        return TransactionContext(self)
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 实体表（人员/公司）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,  -- 'person' or 'company'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. 交易表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    income REAL DEFAULT 0,
                    expense REAL DEFAULT 0,
                    balance REAL,
                    counterparty TEXT,
                    description TEXT,
                    account TEXT,
                    transaction_type TEXT,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 3. 资金画像表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL UNIQUE,
                    total_income REAL DEFAULT 0,
                    total_expense REAL DEFAULT 0,
                    net_income REAL DEFAULT 0,
                    transaction_count INTEGER DEFAULT 0,
                    income_sources INTEGER DEFAULT 0,
                    expense_targets INTEGER DEFAULT 0,
                    profile_data TEXT,  -- JSON 格式存储完整画像数据
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 4. 疑点表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS suspicions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    suspicion_type TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    description TEXT,
                    details TEXT,  -- JSON 格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 5. 分析结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER,
                    analysis_type TEXT NOT NULL,
                    result_data TEXT,  -- JSON 格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 6. 资产表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    asset_type TEXT NOT NULL,  -- 'property', 'vehicle', etc.
                    asset_name TEXT,
                    asset_value REAL,
                    location TEXT,
                    details TEXT,  -- JSON 格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 7. 关联关系表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id INTEGER NOT NULL,
                    related_entity_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL,
                    transaction_count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0,
                    details TEXT,  -- JSON 格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entity_id) REFERENCES entities(id),
                    FOREIGN KEY (related_entity_id) REFERENCES entities(id)
                )
            ''')
            
            # 8. 分析历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_type TEXT NOT NULL,
                    entity_count INTEGER DEFAULT 0,
                    transaction_count INTEGER DEFAULT 0,
                    suspicion_count INTEGER DEFAULT 0,
                    duration_seconds REAL,
                    status TEXT,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            # 创建索引
            # entities 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)')
            
            # transactions 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_entity ON transactions(entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_income ON transactions(income)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_expense ON transactions(expense)')
            
            # profiles 表索引（entity_id 有 UNIQUE 约束，自动创建索引）
            
            # suspicions 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_suspicions_entity ON suspicions(entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_suspicions_risk ON suspicions(risk_level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_suspicions_created_at ON suspicions(created_at)')
            
            # analysis_results 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_results_entity ON analysis_results(entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_results_type ON analysis_results(analysis_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_results_created_at ON analysis_results(created_at)')
            
            # assets 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_entity ON assets(entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type)')
            
            # relationships 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationships_entity ON relationships(entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationships_related_entity ON relationships(related_entity_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type)')
            
            # analysis_history 表索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_history_type ON analysis_history(analysis_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_analysis_history_started_at ON analysis_history(started_at)')
            
            conn.commit()
            logger.info(f'数据库初始化完成: {self.db_path}')
    
    # ==================== 实体管理 ====================
    
    def upsert_entity(self, name: str, entity_type: str) -> int:
        """
        插入或更新实体
        
        Args:
            name: 实体名称
            entity_type: 实体类型 ('person' or 'company')
            
        Returns:
            实体ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO entities (name, type, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (name, entity_type))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_entity_id(self, name: str) -> Optional[int]:
        """获取实体ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM entities WHERE name = ?', (name,))
            row = cursor.fetchone()
            return row['id'] if row else None
    
    def get_all_entities(self, entity_type: Optional[str] = None) -> List[Dict]:
        """获取所有实体"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if entity_type:
                cursor.execute('SELECT * FROM entities WHERE type = ?', (entity_type,))
            else:
                cursor.execute('SELECT * FROM entities')
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 交易数据管理 ====================
    
    def insert_transactions(self, entity_name: str, df: pd.DataFrame, 
                          entity_type: str = 'person') -> int:
        """
        批量插入交易数据
        
        Args:
            entity_name: 实体名称
            df: 交易数据DataFrame
            entity_type: 实体类型
            
        Returns:
            插入的记录数
        """
        if df.empty:
            return 0
        
        # 获取或创建实体ID
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            entity_id = self.upsert_entity(entity_name, entity_type)
        
        # 准备数据
        records = []
        for _, row in df.iterrows():
            record = {
                'entity_id': entity_id,
                'date': _normalize_transaction_date(row.get('date', '')),
                'income': _normalize_required_amount(row.get('income', 0)),
                'expense': _normalize_required_amount(row.get('expense', 0)),
                'balance': _normalize_optional_amount(row.get('balance')),
                'counterparty': str(row.get('counterparty', '')),
                'description': str(row.get('description', '')),
                'account': str(row.get('account', '')),
                'transaction_type': str(row.get('transaction_type', '')),
                'source_file': str(row.get('source_file', ''))
            }
            records.append(record)
        
        # 批量插入
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO transactions 
                (entity_id, date, income, expense, balance, counterparty, 
                 description, account, transaction_type, source_file)
                VALUES 
                (:entity_id, :date, :income, :expense, :balance, :counterparty,
                 :description, :account, :transaction_type, :source_file)
            ''', records)
            
            conn.commit()
            return cursor.rowcount
    
    def get_transactions(self, entity_name: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       min_amount: Optional[float] = None) -> pd.DataFrame:
        """
        查询交易数据
        
        Args:
            entity_name: 实体名称（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            min_amount: 最小金额（可选）
            
        Returns:
            交易数据DataFrame
        """
        query = '''
            SELECT t.*, e.name as entity_name, e.type as entity_type
            FROM transactions t
            JOIN entities e ON t.entity_id = e.id
            WHERE 1=1
        '''
        params = []
        
        if entity_name:
            query += ' AND e.name = ?'
            params.append(entity_name)
        
        if start_date:
            query += ' AND t.date >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND t.date <= ?'
            params.append(end_date)
        
        if min_amount:
            query += ' AND (t.income >= ? OR t.expense >= ?)'
            params.extend([min_amount, min_amount])
        
        query += ' ORDER BY t.date DESC'
        
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df
    
    def get_transaction_summary(self, entity_name: str) -> Dict:
        """获取交易汇总信息"""
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            return {}
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as transaction_count,
                    SUM(income) as total_income,
                    SUM(expense) as total_expense,
                    MIN(date) as first_date,
                    MAX(date) as last_date
                FROM transactions
                WHERE entity_id = ?
            ''', (entity_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    # ==================== 资金画像管理 ====================
    
    def upsert_profile(self, entity_name: str, profile: Dict) -> int:
        """
        插入或更新资金画像
        
        Args:
            entity_name: 实体名称
            profile: 资金画像数据
            
        Returns:
            记录ID
        """
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            entity_id = self.upsert_entity(entity_name, 'person')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO profiles 
                (entity_id, total_income, total_expense, net_income, 
                 transaction_count, income_sources, expense_targets, 
                 profile_data, updated_at)
                VALUES 
                (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                entity_id,
                profile.get('total_income', 0),
                profile.get('total_expense', 0),
                profile.get('net_income', 0),
                profile.get('transaction_count', 0),
                profile.get('income_sources', 0),
                profile.get('expense_targets', 0),
                json.dumps(profile, ensure_ascii=False)
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_profile(self, entity_name: str) -> Optional[Dict]:
        """获取资金画像"""
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM profiles WHERE entity_id = ?', (entity_id,))
            row = cursor.fetchone()
            
            if row:
                profile = dict(row)
                if profile.get('profile_data'):
                    profile['full_data'] = json.loads(profile['profile_data'])
                return profile
            return None
    
    # ==================== 疑点管理 ====================
    
    def insert_suspicion(self, entity_name: str, suspicion_type: str,
                       risk_level: str, description: str, 
                       details: Optional[Dict] = None) -> int:
        """
        插入疑点记录
        
        Args:
            entity_name: 实体名称
            suspicion_type: 疑点类型
            risk_level: 风险等级
            description: 描述
            details: 详细信息（JSON）
            
        Returns:
            记录ID
        """
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            entity_id = self.upsert_entity(entity_name, 'person')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO suspicions 
                (entity_id, suspicion_type, risk_level, description, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entity_id,
                suspicion_type,
                risk_level,
                description,
                json.dumps(details, ensure_ascii=False) if details else None
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_suspicions(self, entity_name: Optional[str] = None,
                      risk_level: Optional[str] = None) -> List[Dict]:
        """查询疑点记录"""
        query = '''
            SELECT s.*, e.name as entity_name
            FROM suspicions s
            JOIN entities e ON s.entity_id = e.id
            WHERE 1=1
        '''
        params = []
        
        if entity_name:
            query += ' AND e.name = ?'
            params.append(entity_name)
        
        if risk_level:
            query += ' AND s.risk_level = ?'
            params.append(risk_level)
        
        query += ' ORDER BY s.created_at DESC'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('details'):
                    result['details'] = json.loads(result['details'])
                results.append(result)
            
            return results
    
    # ==================== 分析结果管理 ====================
    
    def insert_analysis_result(self, analysis_type: str, result_data: Dict,
                            entity_name: Optional[str] = None) -> int:
        """
        插入分析结果
        
        Args:
            analysis_type: 分析类型
            result_data: 结果数据
            entity_name: 实体名称（可选）
            
        Returns:
            记录ID
        """
        entity_id = None
        if entity_name:
            entity_id = self.get_entity_id(entity_name)
            if entity_id is None:
                entity_id = self.upsert_entity(entity_name, 'person')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO analysis_results 
                (entity_id, analysis_type, result_data)
                VALUES (?, ?, ?)
            ''', (
                entity_id,
                analysis_type,
                json.dumps(result_data, ensure_ascii=False)
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_analysis_results(self, analysis_type: Optional[str] = None,
                          entity_name: Optional[str] = None) -> List[Dict]:
        """查询分析结果"""
        query = '''
            SELECT ar.*, e.name as entity_name
            FROM analysis_results ar
            LEFT JOIN entities e ON ar.entity_id = e.id
            WHERE 1=1
        '''
        params = []
        
        if analysis_type:
            query += ' AND ar.analysis_type = ?'
            params.append(analysis_type)
        
        if entity_name:
            query += ' AND e.name = ?'
            params.append(entity_name)
        
        query += ' ORDER BY ar.created_at DESC'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('result_data'):
                    result['result_data'] = json.loads(result['result_data'])
                results.append(result)
            
            return results
    
    # ==================== 资产管理 ====================
    
    def insert_asset(self, entity_name: str, asset_type: str, asset_name: str,
                   asset_value: float, location: Optional[str] = None,
                   details: Optional[Dict] = None) -> int:
        """
        插入资产记录
        
        Args:
            entity_name: 实体名称
            asset_type: 资产类型
            asset_name: 资产名称
            asset_value: 资产价值
            location: 位置
            details: 详细信息
            
        Returns:
            记录ID
        """
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            entity_id = self.upsert_entity(entity_name, 'person')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO assets 
                (entity_id, asset_type, asset_name, asset_value, location, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entity_id,
                asset_type,
                asset_name,
                asset_value,
                location,
                json.dumps(details, ensure_ascii=False) if details else None
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_assets(self, entity_name: Optional[str] = None,
                 asset_type: Optional[str] = None) -> List[Dict]:
        """查询资产记录"""
        query = '''
            SELECT a.*, e.name as entity_name
            FROM assets a
            JOIN entities e ON a.entity_id = e.id
            WHERE 1=1
        '''
        params = []
        
        if entity_name:
            query += ' AND e.name = ?'
            params.append(entity_name)
        
        if asset_type:
            query += ' AND a.asset_type = ?'
            params.append(asset_type)
        
        query += ' ORDER BY a.asset_value DESC'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('details'):
                    result['details'] = json.loads(result['details'])
                results.append(result)
            
            return results
    
    # ==================== 关联关系管理 ====================
    
    def upsert_relationship(self, entity_name: str, related_entity_name: str,
                          relationship_type: str, transaction_count: int = 0,
                          total_amount: float = 0, details: Optional[Dict] = None) -> int:
        """
        插入或更新关联关系
        
        Args:
            entity_name: 实体名称
            related_entity_name: 关联实体名称
            relationship_type: 关系类型
            transaction_count: 交易次数
            total_amount: 总金额
            details: 详细信息
            
        Returns:
            记录ID
        """
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            entity_id = self.upsert_entity(entity_name, 'person')
        
        related_entity_id = self.get_entity_id(related_entity_name)
        if related_entity_id is None:
            related_entity_id = self.upsert_entity(related_entity_name, 'person')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO relationships 
                (entity_id, related_entity_id, relationship_type, 
                 transaction_count, total_amount, details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entity_id,
                related_entity_id,
                relationship_type,
                transaction_count,
                total_amount,
                json.dumps(details, ensure_ascii=False) if details else None
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_relationships(self, entity_name: Optional[str] = None,
                        relationship_type: Optional[str] = None) -> List[Dict]:
        """查询关联关系"""
        query = '''
            SELECT r.*, 
                   e1.name as entity_name,
                   e2.name as related_entity_name
            FROM relationships r
            JOIN entities e1 ON r.entity_id = e1.id
            JOIN entities e2 ON r.related_entity_id = e2.id
            WHERE 1=1
        '''
        params = []
        
        if entity_name:
            query += ' AND e1.name = ?'
            params.append(entity_name)
        
        if relationship_type:
            query += ' AND r.relationship_type = ?'
            params.append(relationship_type)
        
        query += ' ORDER BY r.total_amount DESC'
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result.get('details'):
                    result['details'] = json.loads(result['details'])
                results.append(result)
            
            return results
    
    # ==================== 分析历史管理 ====================
    
    def start_analysis_history(self, analysis_type: str) -> int:
        """开始分析历史记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO analysis_history 
                (analysis_type, started_at, status)
                VALUES (?, CURRENT_TIMESTAMP, 'running')
            ''', (analysis_type,))
            
            conn.commit()
            return cursor.lastrowid
    
    def complete_analysis_history(self, history_id: int, entity_count: int,
                                transaction_count: int, suspicion_count: int,
                                duration_seconds: float, status: str = 'completed',
                                error_message: Optional[str] = None):
        """完成分析历史记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE analysis_history
                SET entity_count = ?,
                    transaction_count = ?,
                    suspicion_count = ?,
                    duration_seconds = ?,
                    status = ?,
                    error_message = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                entity_count,
                transaction_count,
                suspicion_count,
                duration_seconds,
                status,
                error_message,
                history_id
            ))
            
            conn.commit()
    
    def get_analysis_history(self, analysis_type: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
        """查询分析历史"""
        query = 'SELECT * FROM analysis_history WHERE 1=1'
        params = []
        
        if analysis_type:
            query += ' AND analysis_type = ?'
            params.append(analysis_type)
        
        query += ' ORDER BY started_at DESC LIMIT ?'
        params.append(limit)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 数据清理 ====================
    
    def clear_entity_data(self, entity_name: str):
        """清除指定实体的所有数据"""
        entity_id = self.get_entity_id(entity_name)
        if entity_id is None:
            return
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 删除关联数据
            cursor.execute('DELETE FROM transactions WHERE entity_id = ?', (entity_id,))
            cursor.execute('DELETE FROM profiles WHERE entity_id = ?', (entity_id,))
            cursor.execute('DELETE FROM suspicions WHERE entity_id = ?', (entity_id,))
            cursor.execute('DELETE FROM assets WHERE entity_id = ?', (entity_id,))
            cursor.execute('DELETE FROM relationships WHERE entity_id = ? OR related_entity_id = ?', 
                         (entity_id, entity_id))
            
            conn.commit()
            logger.info(f'已清除实体 {entity_name} 的所有数据')
    
    def clear_all_data(self):
        """清除所有数据（慎用）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM transactions')
            cursor.execute('DELETE FROM profiles')
            cursor.execute('DELETE FROM suspicions')
            cursor.execute('DELETE FROM analysis_results')
            cursor.execute('DELETE FROM assets')
            cursor.execute('DELETE FROM relationships')
            cursor.execute('DELETE FROM entities')
            cursor.execute('DELETE FROM analysis_history')
            
            conn.commit()
            logger.warning('已清除所有数据库数据')
    
    def get_database_stats(self) -> Dict:
        """获取数据库统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # 表记录数
            tables = ['entities', 'transactions', 'profiles', 'suspicions', 
                     'analysis_results', 'assets', 'relationships', 'analysis_history']
            
            for table in tables:
                cursor.execute(f'SELECT COUNT(*) as count FROM {table}')
                stats[f'{table}_count'] = cursor.fetchone()['count']
            
            # 数据库文件大小
            if os.path.exists(self.db_path):
                stats['db_size_bytes'] = os.path.getsize(self.db_path)
                stats['db_size_mb'] = stats['db_size_bytes'] / (1024 * 1024)
            
            return stats


# 全局单例实例
_db_manager = None


def get_db_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager


def save_to_database(cleaned_data: Dict[str, pd.DataFrame],
                    profiles: Dict,
                    suspicions: Dict,
                    all_persons: List[str],
                    all_companies: List[str]) -> Dict:
    """
    将分析结果保存到数据库（使用事务保证原子性）
    
    Args:
        cleaned_data: 清洗后的交易数据
        profiles: 资金画像
        suspicions: 疑点检测结果
        all_persons: 所有人员
        all_companies: 所有公司
        
    Returns:
        保存统计信息
        
    Raises:
        Exception: 保存过程中任何错误都会导致事务回滚
    """
    logger.info('='*60)
    logger.info('开始保存数据到数据库（事务模式）')
    logger.info('='*60)
    
    db = get_db_manager()
    stats = {
        'entities': 0,
        'transactions': 0,
        'profiles': 0,
        'suspicions': 0
    }
    
    try:
        # 使用事务上下文管理器
        with db.transaction() as (conn, cursor):
            # 1. 保存实体和交易数据
            for entity_name, df in cleaned_data.items():
                entity_type = 'person' if entity_name in all_persons else 'company'
                
                # 获取或创建实体ID
                cursor.execute('SELECT id FROM entities WHERE name = ?', (entity_name,))
                row = cursor.fetchone()
                if row:
                    entity_id = row['id']
                else:
                    cursor.execute('''
                        INSERT INTO entities (name, type, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (entity_name, entity_type))
                    entity_id = cursor.lastrowid
                
                # 准备交易数据
                if not df.empty:
                    records = []
                    for _, row_data in df.iterrows():
                        record = (
                            entity_id,
                            _normalize_transaction_date(row_data.get('date', '')),
                            _normalize_required_amount(row_data.get('income', 0)),
                            _normalize_required_amount(row_data.get('expense', 0)),
                            _normalize_optional_amount(row_data.get('balance')),
                            str(row_data.get('counterparty', '')),
                            str(row_data.get('description', '')),
                            str(row_data.get('account', '')),
                            str(row_data.get('transaction_type', '')),
                            str(row_data.get('source_file', ''))
                        )
                        records.append(record)
                    
                    # 批量插入交易数据
                    cursor.executemany('''
                        INSERT INTO transactions
                        (entity_id, date, income, expense, balance, counterparty,
                         description, account, transaction_type, source_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', records)
                    
                    count = cursor.rowcount
                    stats['transactions'] += count
                    stats['entities'] += 1
                    logger.info(f'保存 {entity_name}: {count} 条交易记录')
            
            # 2. 保存资金画像
            for entity_name, profile in profiles.items():
                # 获取实体ID
                cursor.execute('SELECT id FROM entities WHERE name = ?', (entity_name,))
                row = cursor.fetchone()
                if row:
                    entity_id = row['id']
                else:
                    # 如果实体不存在，创建它
                    cursor.execute('''
                        INSERT INTO entities (name, type, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (entity_name, 'person'))
                    entity_id = cursor.lastrowid
                
                # 插入或更新画像
                cursor.execute('''
                    INSERT OR REPLACE INTO profiles
                    (entity_id, total_income, total_expense, net_income,
                     transaction_count, income_sources, expense_targets,
                     profile_data, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    entity_id,
                    profile.get('total_income', 0),
                    profile.get('total_expense', 0),
                    profile.get('net_income', 0),
                    profile.get('transaction_count', 0),
                    profile.get('income_sources', 0),
                    profile.get('expense_targets', 0),
                    json.dumps(profile, ensure_ascii=False)
                ))
                
                stats['profiles'] += 1
            
            # 3. 保存疑点
            for entity_name, entity_suspicions in suspicions.items():
                # 获取实体ID
                cursor.execute('SELECT id FROM entities WHERE name = ?', (entity_name,))
                row = cursor.fetchone()
                if row:
                    entity_id = row['id']
                else:
                    # 如果实体不存在，创建它
                    cursor.execute('''
                        INSERT INTO entities (name, type, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (entity_name, 'person'))
                    entity_id = cursor.lastrowid
                
                # 插入疑点
                for suspicion_type, suspicion_list in entity_suspicions.items():
                    if isinstance(suspicion_list, list):
                        for suspicion in suspicion_list:
                            cursor.execute('''
                                INSERT INTO suspicions
                                (entity_id, suspicion_type, risk_level, description, details)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (
                                entity_id,
                                suspicion_type,
                                suspicion.get('risk_level', 'medium'),
                                suspicion.get('description', ''),
                                json.dumps(suspicion, ensure_ascii=False) if suspicion else None
                            ))
                            stats['suspicions'] += 1
        
        # 事务成功提交
        logger.info(f'数据库保存完成（事务已提交）:')
        logger.info(f'  实体数: {stats["entities"]}')
        logger.info(f'  交易记录: {stats["transactions"]}')
        logger.info(f'  资金画像: {stats["profiles"]}')
        logger.info(f'  疑点记录: {stats["suspicions"]}')
        
    except Exception as e:
        # 事务会自动回滚
        logger.error(f'数据库保存失败，事务已回滚: {e}')
        raise
    
    return stats
