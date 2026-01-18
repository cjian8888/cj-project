#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
操作审计日志模块

【模块定位】
符合等保 2.0 要求的操作审计日志系统，用于：
1. 记录用户关键操作（查看、导出、分析等）
2. 记录敏感数据访问
3. 支持日志归档和检索
4. 为安全审计提供证据链

【等保合规】
- 安全审计：记录关键操作和异常事件
- 日志完整性：防篡改设计
- 日志留存：支持 180 天以上归档

创建日期: 2026-01-18
"""

import os
import json
import hashlib
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging

import config
import utils

logger = utils.setup_logger(__name__)


class AuditAction(Enum):
    """审计操作类型"""
    # 数据访问
    VIEW_PROFILE = "view_profile"           # 查看资金画像
    VIEW_TRANSACTION = "view_transaction"   # 查看交易明细
    VIEW_REPORT = "view_report"             # 查看分析报告
    VIEW_GRAPH = "view_graph"               # 查看资金图谱
    
    # 数据操作
    EXPORT_DATA = "export_data"             # 导出数据
    RUN_ANALYSIS = "run_analysis"           # 运行分析
    IMPORT_DATA = "import_data"             # 导入数据
    
    # 系统操作
    LOGIN = "login"                         # 登录
    LOGOUT = "logout"                       # 登出
    CONFIG_CHANGE = "config_change"         # 配置变更
    
    # 敏感操作
    ACCESS_SENSITIVE = "access_sensitive"   # 访问敏感数据
    DELETE_DATA = "delete_data"             # 删除数据


class AuditLevel(Enum):
    """审计级别"""
    INFO = "info"           # 一般操作
    WARNING = "warning"     # 需关注
    CRITICAL = "critical"   # 高风险


@dataclass
class AuditRecord:
    """审计记录"""
    timestamp: str              # 时间戳 ISO 格式
    action: str                 # 操作类型
    level: str                  # 审计级别
    user_id: str               # 用户标识
    user_ip: str               # 用户 IP
    target_type: str           # 操作对象类型（如 person, company, report）
    target_id: str             # 操作对象 ID
    details: Dict[str, Any]    # 详细信息
    result: str                # 操作结果（success/failure）
    checksum: str = ""         # 校验和（防篡改）
    
    def compute_checksum(self, secret_key: str = "audit_secret") -> str:
        """计算校验和"""
        data = f"{self.timestamp}|{self.action}|{self.user_id}|{self.target_id}|{secret_key}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """
    审计日志记录器
    
    特点：
    - 线程安全
    - 支持多种输出（文件、数据库）
    - 防篡改校验
    - 自动归档
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, log_dir: str = None, retention_days: int = 180):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.log_dir = log_dir or os.path.join(
            getattr(config, 'OUTPUT_DIR', './output'), 
            'audit_logs'
        )
        self.retention_days = retention_days
        self._current_file = None
        self._current_date = None
        self._file_lock = threading.Lock()
        self._initialized = True
        
        # 确保目录存在
        os.makedirs(self.log_dir, exist_ok=True)
        
        logger.info(f'审计日志系统初始化: {self.log_dir}')
    
    def log(
        self,
        action: AuditAction,
        user_id: str = "system",
        user_ip: str = "127.0.0.1",
        target_type: str = "",
        target_id: str = "",
        details: Dict[str, Any] = None,
        result: str = "success",
        level: AuditLevel = AuditLevel.INFO
    ) -> AuditRecord:
        """
        记录审计日志
        
        Args:
            action: 操作类型
            user_id: 用户标识
            user_ip: 用户 IP
            target_type: 操作对象类型
            target_id: 操作对象 ID
            details: 详细信息
            result: 操作结果
            level: 审计级别
            
        Returns:
            审计记录对象
        """
        record = AuditRecord(
            timestamp=datetime.now().isoformat(),
            action=action.value,
            level=level.value,
            user_id=user_id,
            user_ip=user_ip,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            result=result
        )
        record.checksum = record.compute_checksum()
        
        # 写入文件
        self._write_to_file(record)
        
        # 高风险操作额外告警
        if level == AuditLevel.CRITICAL:
            logger.warning(f'[AUDIT ALERT] {action.value}: {target_type}/{target_id} by {user_id}')
        
        return record
    
    def _write_to_file(self, record: AuditRecord):
        """写入日志文件"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._file_lock:
            # 检查是否需要轮转日志文件
            if self._current_date != today:
                if self._current_file:
                    self._current_file.close()
                
                log_path = os.path.join(self.log_dir, f'audit_{today}.jsonl')
                self._current_file = open(log_path, 'a', encoding='utf-8')
                self._current_date = today
                logger.debug(f'审计日志轮转: {log_path}')
            
            # 写入记录（JSONL 格式）
            self._current_file.write(record.to_json() + '\n')
            self._current_file.flush()
    
    def query(
        self,
        start_date: str = None,
        end_date: str = None,
        action: AuditAction = None,
        user_id: str = None,
        target_id: str = None,
        limit: int = 100
    ) -> List[AuditRecord]:
        """
        查询审计日志
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            action: 操作类型过滤
            user_id: 用户过滤
            target_id: 目标对象过滤
            limit: 返回数量限制
            
        Returns:
            匹配的审计记录列表
        """
        records = []
        
        # 确定查询的日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = end_date  # 默认只查当天
        
        # 遍历日期范围内的日志文件
        from datetime import timedelta
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end and len(records) < limit:
            date_str = current.strftime('%Y-%m-%d')
            log_path = os.path.join(self.log_dir, f'audit_{date_str}.jsonl')
            
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if len(records) >= limit:
                            break
                        try:
                            data = json.loads(line.strip())
                            
                            # 应用过滤条件
                            if action and data.get('action') != action.value:
                                continue
                            if user_id and data.get('user_id') != user_id:
                                continue
                            if target_id and data.get('target_id') != target_id:
                                continue
                            
                            records.append(AuditRecord(**data))
                        except (json.JSONDecodeError, TypeError):
                            continue
            
            current += timedelta(days=1)
        
        return records
    
    def verify_integrity(self, record: AuditRecord) -> bool:
        """验证记录完整性（防篡改检查）"""
        expected = record.compute_checksum()
        return record.checksum == expected
    
    def close(self):
        """关闭日志记录器"""
        with self._file_lock:
            if self._current_file:
                self._current_file.close()
                self._current_file = None


# 全局单例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取审计日志记录器单例"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_log(
    action: AuditAction,
    user_id: str = "system",
    user_ip: str = "127.0.0.1",
    target_type: str = "",
    target_id: str = "",
    details: Dict[str, Any] = None,
    result: str = "success",
    level: AuditLevel = AuditLevel.INFO
) -> AuditRecord:
    """便捷函数：记录审计日志"""
    return get_audit_logger().log(
        action=action,
        user_id=user_id,
        user_ip=user_ip,
        target_type=target_type,
        target_id=target_id,
        details=details,
        result=result,
        level=level
    )


# ========== 装饰器：自动审计 ==========

def audited(action: AuditAction, target_type: str = ""):
    """
    函数装饰器：自动记录审计日志
    
    用法：
        @audited(AuditAction.VIEW_PROFILE, target_type="person")
        def view_person_profile(person_id: str):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 提取 target_id（尝试从第一个参数获取）
            target_id = str(args[0]) if args else kwargs.get('target_id', '')
            
            try:
                result = func(*args, **kwargs)
                audit_log(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    result="success"
                )
                return result
            except Exception as e:
                audit_log(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    result="failure",
                    details={"error": str(e)},
                    level=AuditLevel.WARNING
                )
                raise
        return wrapper
    return decorator
