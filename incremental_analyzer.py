#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增量分析模块 - 支持只分析新增数据
避免重复处理已分析过的历史数据，提高效率
"""

import os
import json
import hashlib
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import utils

logger = utils.setup_logger(__name__)


class IncrementalAnalyzer:
    """增量分析管理器"""
    
    def __init__(self, checkpoint_dir: str = 'output/.checkpoints'):
        """
        初始化增量分析器
        
        Args:
            checkpoint_dir: 检查点存储目录
        """
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
        self.checkpoint_file = os.path.join(checkpoint_dir, 'analysis_checkpoint.json')
        self.checkpoints = self._load_checkpoints()
    
    def _load_checkpoints(self) -> Dict:
        """加载检查点"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"加载检查点失败: {e}")
                return {}
        return {}
    
    def _save_checkpoints(self):
        """保存检查点"""
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoints, f, ensure_ascii=False, indent=2, default=str)
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)  # 读取前64KB
            hasher.update(buf)
        # 同时考虑文件大小和修改时间
        stat = os.stat(file_path)
        hasher.update(str(stat.st_size).encode())
        hasher.update(str(stat.st_mtime).encode())
        return hasher.hexdigest()
    
    def check_file_changed(self, file_path: str) -> bool:
        """
        检查文件是否有变化
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果文件有变化或是新文件
        """
        if not os.path.exists(file_path):
            return False
        
        current_hash = self._calculate_file_hash(file_path)
        stored_hash = self.checkpoints.get('files', {}).get(file_path, {}).get('hash')
        
        return current_hash != stored_hash
    
    def update_file_checkpoint(self, file_path: str, record_count: int = 0):
        """
        更新文件检查点
        
        Args:
            file_path: 文件路径
            record_count: 处理的记录数
        """
        if 'files' not in self.checkpoints:
            self.checkpoints['files'] = {}
        
        self.checkpoints['files'][file_path] = {
            'hash': self._calculate_file_hash(file_path),
            'last_analyzed': datetime.now().isoformat(),
            'record_count': record_count
        }
        self._save_checkpoints()
    
    def get_changed_files(self, file_list: List[str]) -> List[str]:
        """
        获取有变化的文件列表
        
        Args:
            file_list: 待检查的文件列表
            
        Returns:
            有变化的文件列表
        """
        changed = []
        for file_path in file_list:
            if self.check_file_changed(file_path):
                changed.append(file_path)
                logger.debug(f"文件有变化: {file_path}")
            else:
                logger.debug(f"文件无变化，跳过: {file_path}")
        
        return changed
    
    def get_new_transactions(
        self, 
        df: pd.DataFrame, 
        entity_name: str,
        date_column: str = 'date'
    ) -> pd.DataFrame:
        """
        获取新增的交易记录
        
        Args:
            df: 完整的交易DataFrame
            entity_name: 实体名称
            date_column: 日期列名
            
        Returns:
            只包含新记录的DataFrame
        """
        entity_key = f"entity_{entity_name}"
        last_date = self.checkpoints.get('entities', {}).get(entity_key, {}).get('last_date')
        
        if last_date:
            try:
                last_date = pd.to_datetime(last_date)
                # 返回比上次分析日期更新的记录
                new_df = df[df[date_column] > last_date]
                logger.info(f"{entity_name}: 发现 {len(new_df)} 条新记录 (上次分析至 {last_date.strftime('%Y-%m-%d')})")
                return new_df
            except (ValueError, KeyError) as e:
                logger.debug(f"解析上次分析日期失败: {e}")
        
        logger.info(f"{entity_name}: 首次分析，处理全部 {len(df)} 条记录")
        return df
    
    def update_entity_checkpoint(self, entity_name: str, df: pd.DataFrame, date_column: str = 'date'):
        """
        更新实体分析检查点
        
        Args:
            entity_name: 实体名称
            df: 分析后的DataFrame
            date_column: 日期列名
        """
        if 'entities' not in self.checkpoints:
            self.checkpoints['entities'] = {}
        
        entity_key = f"entity_{entity_name}"
        
        self.checkpoints['entities'][entity_key] = {
            'last_date': df[date_column].max().isoformat() if not df.empty else None,
            'last_analyzed': datetime.now().isoformat(),
            'total_records': len(df)
        }
        self._save_checkpoints()
    
    def should_reanalyze(self, entity_name: str, force: bool = False) -> bool:
        """
        判断是否需要重新分析
        
        Args:
            entity_name: 实体名称
            force: 是否强制重新分析
            
        Returns:
            True 如果需要重新分析
        """
        if force:
            return True
        
        entity_key = f"entity_{entity_name}"
        entity_info = self.checkpoints.get('entities', {}).get(entity_key)
        
        if not entity_info:
            return True  # 首次分析
        
        # 检查是否超过7天未更新
        last_analyzed = entity_info.get('last_analyzed')
        if last_analyzed:
            try:
                last_dt = datetime.fromisoformat(last_analyzed)
                days_since = (datetime.now() - last_dt).days
                if days_since > 7:
                    logger.info(f"{entity_name}: 距上次分析已过{days_since}天，建议重新分析")
                    return True
            except ValueError as e:
                logger.debug(f"解析分析日期失败: {e}")
        
        return False
    
    def get_analysis_summary(self) -> Dict:
        """获取分析摘要"""
        entities = self.checkpoints.get('entities', {})
        files = self.checkpoints.get('files', {})
        
        return {
            'total_entities': len(entities),
            'total_files': len(files),
            'entities': {
                k.replace('entity_', ''): {
                    'last_analyzed': v.get('last_analyzed'),
                    'records': v.get('total_records', 0)
                }
                for k, v in entities.items()
            },
            'last_full_analysis': self.checkpoints.get('last_full_analysis')
        }
    
    def mark_full_analysis_complete(self):
        """标记完整分析完成"""
        self.checkpoints['last_full_analysis'] = datetime.now().isoformat()
        self._save_checkpoints()
    
    def reset(self):
        """重置所有检查点"""
        self.checkpoints = {}
        self._save_checkpoints()
        logger.info("检查点已重置，下次将进行完整分析")


def run_incremental_analysis(
    data_directory: str,
    output_directory: str,
    force_full: bool = False
) -> Tuple[Dict, bool]:
    """
    运行增量分析
    
    Args:
        data_directory: 数据目录
        output_directory: 输出目录
        force_full: 是否强制完整分析
        
    Returns:
        (分析结果, 是否为增量分析)
    """
    analyzer = IncrementalAnalyzer(os.path.join(output_directory, '.checkpoints'))
    
    if force_full:
        logger.info("强制完整分析模式")
        analyzer.reset()
        is_incremental = False
    else:
        summary = analyzer.get_analysis_summary()
        if summary['total_entities'] == 0:
            logger.info("首次运行，执行完整分析")
            is_incremental = False
        else:
            logger.info(f"增量分析模式 - 已有 {summary['total_entities']} 个实体的历史记录")
            is_incremental = True
    
    # 实际的分析逻辑应该在main.py中调用这个模块
    # 这里只提供检查点管理功能
    
    return {'analyzer': analyzer, 'is_incremental': is_incremental}, is_incremental


if __name__ == '__main__':
    # 测试代码
    analyzer = IncrementalAnalyzer()
    
    print("分析摘要:")
    print(json.dumps(analyzer.get_analysis_summary(), indent=2, ensure_ascii=False))
