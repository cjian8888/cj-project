# 数据备份机制改进方案

本文档提供了数据库备份机制的改进方案。

## 当前问题分析

### 1. 缺少自动备份机制
- 没有定期自动备份数据库
- 没有在关键操作前自动备份

### 2. 缺少备份恢复机制
- 没有从备份恢复数据的功能
- 没有备份版本管理

### 3. 缺少备份验证
- 没有验证备份完整性的机制
- 没有备份损坏检测

### 4. 缺少备份清理
- 没有自动清理旧备份的机制
- 没有备份保留策略

## 改进方案

### 方案一：创建备份管理模块

```python
# database_backup.py
import os
import shutil
import sqlite3
import json
import gzip
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 备份配置
BACKUP_DIR = './backups/database'
MAX_BACKUP_COUNT = 10  # 最多保留10个备份
BACKUP_BEFORE_CRITICAL = True  # 关键操作前自动备份
BACKUP_ON_STARTUP = True  # 启动时自动备份
BACKUP_COMPRESSION = True  # 使用压缩减少空间


class DatabaseBackupManager:
    """数据库备份管理器"""
    
    def __init__(self, db_path: str, backup_dir: str = BACKUP_DIR):
        """
        初始化备份管理器
        
        Args:
            db_path: 数据库文件路径
            backup_dir: 备份目录
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建备份元数据文件
        self.metadata_file = self.backup_dir / 'backup_metadata.json'
        self._load_metadata()
    
    def _load_metadata(self):
        """加载备份元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                'backups': [],
                'last_backup': None,
                'last_restore': None
            }
    
    def _save_metadata(self):
        """保存备份元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def create_backup(self, description: str = '') -> str:
        """
        创建数据库备份
        
        Args:
            description: 备份描述
            
        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name
        
        # 如果启用压缩，使用 .db.gz 扩展名
        if BACKUP_COMPRESSION:
            backup_name = f"backup_{timestamp}.db.gz"
            backup_path = self.backup_dir / backup_name
            
            # 使用 gzip 压缩
            with open(self.db_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy2(self.db_path, backup_path)
        
        # 计算文件大小
        file_size = backup_path.stat().st_size
        
        # 更新元数据
        backup_info = {
            'filename': backup_name,
            'path': str(backup_path),
            'timestamp': datetime.now().isoformat(),
            'description': description,
            'size': file_size,
            'compressed': BACKUP_COMPRESSION
        }
        
        self.metadata['backups'].insert(0, backup_info)
        self.metadata['last_backup'] = backup_info['timestamp']
        self._save_metadata()
        
        # 清理旧备份
        self._cleanup_old_backups()
        
        logger.info(f"创建备份: {backup_name}, 大小: {file_size} bytes")
        
        return str(backup_path)
    
    def restore_backup(self, backup_filename: str) -> bool:
        """
        从备份恢复数据库
        
        Args:
            backup_filename: 备份文件名
            
        Returns:
            是否恢复成功
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False
        
        # 验证备份完整性
        if not self._validate_backup(backup_path):
            logger.error(f"备份文件验证失败: {backup_path}")
            return False
        
        # 创建当前数据库的备份（以防恢复失败）
        safety_backup = self.create_backup('恢复前安全备份')
        
        try:
            # 如果是压缩备份，先解压
            if backup_filename.endswith('.gz'):
                temp_path = self.backup_dir / f"temp_{backup_filename}"
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                restore_path = temp_path
            else:
                restore_path = backup_path
            
            # 关闭数据库连接
            self._close_database_connections()
            
            # 恢复备份
            shutil.copy2(restore_path, self.db_path)
            
            # 更新元数据
            self.metadata['last_restore'] = datetime.now().isoformat()
            self._save_metadata()
            
            logger.info(f"从备份恢复: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"恢复备份失败: {str(e)}")
            # 尝试恢复安全备份
            try:
                shutil.copy2(safety_backup, self.db_path)
            except:
                pass
            return False
    
    def _validate_backup(self, backup_path: Path) -> bool:
        """
        验证备份完整性
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            是否有效
        """
        try:
            # 检查文件大小
            if backup_path.stat().st_size == 0:
                return False
            
            # 如果是压缩文件，尝试解压验证
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f:
                    # 尝试读取前几个字节
                    f.read(1024)
            else:
                # 尝试打开数据库验证
                conn = sqlite3.connect(str(backup_path))
                conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                conn.close()
            
            return True
            
        except Exception as e:
            logger.warning(f"备份验证失败: {str(e)}")
            return False
    
    def _cleanup_old_backups(self):
        """清理旧备份，保留最新的 MAX_BACKUP_COUNT 个"""
        backups = self.metadata.get('backups', [])
        
        if len(backups) > MAX_BACKUP_COUNT:
            # 删除最旧的备份
            backups_to_delete = backups[MAX_BACKUP_COUNT:]
            
            for backup_info in backups_to_delete:
                backup_path = Path(backup_info['path'])
                if backup_path.exists():
                    backup_path.unlink()
                    logger.info(f"删除旧备份: {backup_info['filename']}")
            
            # 更新元数据
            self.metadata['backups'] = backups[:MAX_BACKUP_COUNT]
            self._save_metadata()
    
    def list_backups(self) -> List[dict]:
        """
        列出所有备份
        
        Returns:
            备份信息列表
        """
        return self.metadata.get('backups', [])
    
    def get_latest_backup(self) -> Optional[dict]:
        """
        获取最新的备份
        
        Returns:
            最新备份信息，如果没有则返回None
        """
        backups = self.metadata.get('backups', [])
        return backups[0] if backups else None
    
    def delete_backup(self, backup_filename: str) -> bool:
        """
        删除指定备份
        
        Args:
            backup_filename: 备份文件名
            
        Returns:
            是否删除成功
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False
        
        try:
            backup_path.unlink()
            
            # 更新元数据
            self.metadata['backups'] = [
                b for b in self.metadata['backups']
                if b['filename'] != backup_filename
            ]
            self._save_metadata()
            
            logger.info(f"删除备份: {backup_filename}")
            return True
            
        except Exception as e:
            logger.error(f"删除备份失败: {str(e)}")
            return False
    
    def _close_database_connections(self):
        """关闭所有数据库连接"""
        # 这里需要根据实际的数据库连接管理方式实现
        pass


# 全局备份管理器实例
_backup_manager: Optional[DatabaseBackupManager] = None


def get_backup_manager(db_path: str = './audit_system.db') -> DatabaseBackupManager:
    """
    获取备份管理器实例（单例模式）
    
    Args:
        db_path: 数据库文件路径
        
    Returns:
        备份管理器实例
    """
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = DatabaseBackupManager(db_path)
    return _backup_manager


def auto_backup_before_operation(description: str = ''):
    """
    在关键操作前自动备份
    
    Args:
        description: 操作描述
    """
    if BACKUP_BEFORE_CRITICAL:
        manager = get_backup_manager()
        manager.create_backup(f"操作前备份: {description}")


def auto_backup_on_startup():
    """启动时自动备份"""
    if BACKUP_ON_STARTUP:
        manager = get_backup_manager()
        manager.create_backup('启动时自动备份')
```

### 方案二：集成到 database.py

```python
# database.py 中添加备份功能
from database_backup import get_backup_manager, auto_backup_before_operation

# 在关键操作前自动备份
def save_to_database(data: Dict, table_name: str) -> bool:
    """保存数据到数据库（带备份）"""
    # 操作前自动备份
    auto_backup_before_operation(f"保存数据到 {table_name}")
    
    # 原有的保存逻辑
    ...

# 添加备份管理 API
def create_manual_backup(description: str = '') -> str:
    """创建手动备份"""
    manager = get_backup_manager()
    return manager.create_backup(description)

def restore_from_backup(backup_filename: str) -> bool:
    """从备份恢复"""
    manager = get_backup_manager()
    return manager.restore_backup(backup_filename)

def list_backups() -> List[dict]:
    """列出所有备份"""
    manager = get_backup_manager()
    return manager.list_backups()

def delete_backup(backup_filename: str) -> bool:
    """删除备份"""
    manager = get_backup_manager()
    return manager.delete_backup(backup_filename)
```

### 方案三：添加 API 端点

```python
# api_server.py 中添加备份管理端点

from database import create_manual_backup, restore_from_backup, list_backups, delete_backup

@app.get("/api/backups")
async def list_backups_api():
    """列出所有备份"""
    backups = list_backups()
    return {"status": "success", "data": backups}

@app.post("/api/backups/create")
async def create_backup_api(request: dict):
    """创建备份"""
    description = request.get('description', '手动备份')
    backup_path = create_manual_backup(description)
    return {"status": "success", "data": {"backup_path": backup_path}}

@app.post("/api/backups/restore")
async def restore_backup_api(request: dict):
    """恢复备份"""
    backup_filename = request.get('filename')
    success = restore_from_backup(backup_filename)
    if success:
        return {"status": "success", "message": "备份恢复成功"}
    else:
        return {"status": "error", "message": "备份恢复失败"}

@app.delete("/api/backups/{filename}")
async def delete_backup_api(filename: str):
    """删除备份"""
    success = delete_backup(filename)
    if success:
        return {"status": "success", "message": "备份删除成功"}
    else:
        return {"status": "error", "message": "备份删除失败"}
```

## 实施步骤

### 阶段一：创建备份模块
1. 创建 `database_backup.py` 模块
2. 实现 `DatabaseBackupManager` 类
3. 实现备份、恢复、验证、清理功能
4. 添加配置选项

### 阶段二：集成到 database.py
1. 导入备份管理器
2. 在关键操作前添加自动备份
3. 添加备份管理 API 函数

### 阶段三：添加 API 端点
1. 添加备份列表端点
2. 添加创建备份端点
3. 添加恢复备份端点
4. 添加删除备份端点

### 阶段四：测试
1. 测试备份创建
2. 测试备份恢复
3. 测试备份验证
4. 测试备份清理

## 配置选项

```yaml
# config/backup_config.yaml
backup:
  enabled: true
  directory: './backups/database'
  max_count: 10
  compression: true
  auto_before_critical: true
  auto_on_startup: true
  schedule:
    enabled: false
    interval_hours: 24
```

## 最佳实践

1. **定期备份**：设置自动备份计划（如每天一次）
2. **操作前备份**：关键操作前自动备份
3. **验证完整性**：每次备份后验证文件完整性
4. **保留策略**：保留一定数量的备份，自动清理旧备份
5. **压缩存储**：使用压缩减少存储空间
6. **异地备份**：重要数据应考虑异地备份
7. **备份加密**：敏感数据应考虑加密备份
