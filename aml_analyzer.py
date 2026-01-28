"""
人民银行反洗钱数据解析模块

解析 中国人民银行反洗钱（定向查询） 目录下的xlsx文件
提取可疑交易记录、大额交易报告、支付机构账户信息等

作者: AI Assistant
创建时间: 2026-01-20
Phase: 6.2
"""

import os
import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
AML_DIR_NAME = "中国人民银行反洗钱（定向查询）"


def extract_aml_data(data_dir: str) -> Dict[str, Dict]:
    """
    从反洗钱数据目录提取所有反洗钱相关信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的反洗钱数据
        {
            "310102XXXXXXXXXXXX": {
                "name": "甲某某",
                "id_number": "310102XXXXXXXXXXXX",
                "has_result": True,
                "payment_accounts": [...],  # 支付机构账户
                "payment_transactions": [...],  # 支付机构交易明细
                "suspicious_transactions": [...],  # 可疑交易
                "large_transactions": [...]  # 大额交易报告
            }
        }
    """
    result = {}
    
    # 查找反洗钱数据目录
    aml_dir = _find_aml_dir(data_dir)
    if not aml_dir:
        logger.warning(f"未找到反洗钱数据目录: {AML_DIR_NAME}")
        return result
    
    logger.info(f"开始解析反洗钱数据: {aml_dir}")
    
    # 遍历目录下的所有xlsx文件
    xlsx_files = list(Path(aml_dir).glob("*.xlsx"))
    logger.info(f"找到 {len(xlsx_files)} 个xlsx文件")
    
    for file_path in xlsx_files:
        try:
            # 解析文件
            data = parse_aml_file(str(file_path))
            
            if data:
                # 按身份证号合并
                for person_id, person_data in data.items():
                    try:
                        if person_id not in result:
                            result[person_id] = person_data
                        else:
                            # 合并账户和交易数据
                            existing = result[person_id]
                            for key in ["payment_accounts", "payment_transactions",
                                       "suspicious_transactions", "large_transactions"]:
                                if key in person_data:
                                    if key not in existing:
                                        existing[key] = []
                                    # 确保extend的参数是列表
                                    value_to_extend = person_data.get(key, [])
                                    if not isinstance(value_to_extend, list):
                                        logger.warning(f"数据类型错误，期望列表，实际 {type(value_to_extend)}: {key}")
                                        value_to_extend = []
                                    existing[key].extend(value_to_extend)
                    except Exception as e:
                        logger.error(f"合并数据失败 {person_id}: {e}")
                        continue

                logger.info(f"成功解析 {file_path.name}")
                
        except Exception as e:
            logger.error(f"解析文件失败 {file_path}: {e}")
            continue
    
    # 统计
    logger.info(f"反洗钱数据解析完成: {len(result)} 人")
    
    return result


def parse_aml_file(file_path: str) -> Dict[str, Dict]:
    """
    解析单个反洗钱xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的数据
    """
    result = {}
    source_file = os.path.basename(file_path)
    
    # 验证文件
    if not _validate_excel_file(file_path):
        logger.warning(f"Excel文件验证失败，跳过: {source_file}")
        return result
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 解析查询摘要获取人员列表
        persons = _parse_query_summary(xls, source_file)
        
        # 初始化结果
        for person in persons:
            person_id = person.get("id_number")
            if person_id:
                result[person_id] = {
                    "name": person.get("name"),
                    "id_number": person_id,
                    "has_result": person.get("has_result", False),
                    "payment_accounts": [],
                    "payment_transactions": [],
                    "suspicious_transactions": [],
                    "large_transactions": [],
                    "source_file": source_file
                }
        
        # 解析支付机构账户信息
        payment_accounts = _parse_payment_accounts(xls, source_file)
        for acc in payment_accounts:
            person_id = acc.get("id_number")
            if person_id and person_id in result:
                result[person_id]["payment_accounts"].append(acc)
        
        # 解析支付机构交易明细
        payment_transactions = _parse_payment_transactions(xls, source_file)
        for tx in payment_transactions:
            person_id = tx.get("id_number")
            if person_id and person_id in result:
                result[person_id]["payment_transactions"].append(tx)
        
    except Exception as e:
        logger.error(f"解析反洗钱文件失败 {file_path}: {e}")
        logger.exception("详细错误信息:")
        # 不要重新抛出异常，跳过该文件继续处理
    
    return result


def _parse_query_summary(xls: pd.ExcelFile, source_file: str) -> List[Dict]:
    """解析查询摘要sheet"""
    persons = []
    
    for sheet_name in xls.sheet_names:
        if "查询摘要" in sheet_name or "摘要" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                # 检查是否为空
                if df.empty:
                    logger.warning(f"查询摘要sheet为空: {sheet_name}")
                    continue
                
                # 检查必需列是否存在
                required_columns = ["姓名", "证件号码"]
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    logger.warning(f"查询摘要sheet缺少必需列 {missing_columns}: {sheet_name}")
                    continue
                
                for idx, row in df.iterrows():
                    name = row.get("姓名")
                    id_number = row.get("证件号码")
                    result_status = row.get("查询结果", "")
                    
                    if name and id_number:
                        persons.append({
                            "name": str(name),
                            "id_number": str(id_number),
                            "has_result": result_status == "有",
                            "source_file": source_file
                        })
            except Exception as e:
                logger.warning(f"解析查询摘要失败 {sheet_name}: {e}")
                continue
    
    return persons


def _parse_payment_accounts(xls: pd.ExcelFile, source_file: str) -> List[Dict]:
    """解析支付机构账户信息"""
    accounts = []
    
    for sheet_name in xls.sheet_names:
        if "支付机构账户" in sheet_name:
            try:
                # 读取数据，跳过标题行
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                
                if df.empty:
                    logger.debug(f"支付机构账户sheet为空: {sheet_name}")
                    continue
                
                if df.shape[0] < 2:  # 至少需要2行（表头+数据）
                    logger.debug(f"支付机构账户sheet数据不足: {sheet_name}")
                    continue
                
                # 解析格式：第一行可能是人员标识如"(一)甲某某"
                current_person = None
                current_id = None
                header_row = None
                
                for idx, row in df.iterrows():
                    first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                    
                    # 检查是否是人员标识行
                    name_match = re.match(r'[\(（][一二三四五六七八九十]+[\)）](.+)', first_cell)
                    if name_match:
                        current_person = name_match.group(1).strip()
                        continue
                    
                    # 检查是否是表头行
                    if "账户号" in first_cell or "支付机构名称" in first_cell:
                        header_row = idx
                        headers = [str(c) if pd.notna(c) else "" for c in row]
                        continue
                    
                    # 如果有表头且是数据行
                    if header_row is not None and idx > header_row:
                        # 检查是否是空行或分隔行
                        if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == "":
                            continue
                        
                        account = {
                            "holder_name": current_person,
                            "id_number": current_id,
                            "source_file": source_file
                        }
                        
                        # 根据列位置提取数据
                        if len(row) > 0:
                            account["payment_institution"] = _safe_str(row.iloc[0])
                        if len(row) > 1:
                            account["account_number"] = _safe_str(row.iloc[1])
                        if len(row) > 2:
                            account["account_type"] = _safe_str(row.iloc[2])
                        if len(row) > 3:
                            account["open_date"] = _safe_date(row.iloc[3])
                        if len(row) > 4:
                            account["close_date"] = _safe_date(row.iloc[4])
                        if len(row) > 5:
                            account["balance"] = _safe_float(row.iloc[5])
                        
                        if account.get("account_number"):
                            accounts.append(account)
                            
            except Exception as e:
                logger.warning(f"解析支付机构账户失败: {e}")
    
    return accounts


def _parse_payment_transactions(xls: pd.ExcelFile, source_file: str) -> List[Dict]:
    """解析支付机构交易明细"""
    transactions = []
    
    for sheet_name in xls.sheet_names:
        if "支付机构交易" in sheet_name or "交易明细" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                
                if df.empty:
                    logger.debug(f"支付机构交易明细sheet为空: {sheet_name}")
                    continue
                
                if df.shape[0] < 2:  # 至少需要2行（表头+数据）
                    logger.debug(f"支付机构交易明细sheet数据不足: {sheet_name}")
                    continue
                
                current_person = None
                header_row = None
                
                for idx, row in df.iterrows():
                    first_cell = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                    
                    # 检查人员标识
                    name_match = re.match(r'[\(（][一二三四五六七八九十]+[\)）](.+)', first_cell)
                    if name_match:
                        current_person = name_match.group(1).strip()
                        header_row = None
                        continue
                    
                    # 检查表头
                    if "交易日期" in first_cell or "交易时间" in first_cell:
                        header_row = idx
                        continue
                    
                    # 数据行
                    if header_row is not None and idx > header_row:
                        if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == "":
                            continue
                        
                        tx = {
                            "holder_name": current_person,
                            "source_file": source_file
                        }
                        
                        # 提取各字段
                        if len(row) > 0:
                            tx["transaction_date"] = _safe_date(row.iloc[0])
                        if len(row) > 1:
                            tx["transaction_type"] = _safe_str(row.iloc[1])
                        if len(row) > 2:
                            tx["amount"] = _safe_float(row.iloc[2])
                        if len(row) > 3:
                            tx["counterparty"] = _safe_str(row.iloc[3])
                        if len(row) > 4:
                            tx["description"] = _safe_str(row.iloc[4])
                        
                        if tx.get("amount"):
                            transactions.append(tx)
                            
            except Exception as e:
                logger.warning(f"解析支付机构交易明细失败: {e}")
    
    return transactions


def _validate_excel_file(file_path: str) -> bool:
    """
    验证Excel文件是否有效
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        bool: 文件有效返回True，否则返回False
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False
    
    # 检查文件大小（空文件或过小文件可能损坏）
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        logger.warning(f"文件为空: {file_path}")
        return False
    
    # 检查文件扩展名
    if not file_path.lower().endswith(('.xlsx', '.xls')):
        logger.warning(f"文件格式不支持: {file_path}")
        return False
    
    # 尝试打开文件验证格式
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            # xlsx文件应该以PK开头（ZIP格式）
            if not header.startswith(b'PK'):
                logger.warning(f"文件格式不正确（非xlsx格式）: {file_path}")
                return False
    except Exception as e:
        logger.error(f"读取文件头失败 {file_path}: {e}")
        return False
    
    # 尝试用pandas打开验证
    try:
        xls = pd.ExcelFile(file_path)
        # 检查是否有sheet
        if not xls.sheet_names:
            logger.warning(f"Excel文件没有sheet: {file_path}")
            return False
        xls.close()
    except Exception as e:
        logger.error(f"Excel文件打开失败 {file_path}: {e}")
        return False
    
    return True


def _find_aml_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找反洗钱数据目录"""
    data_path = Path(data_dir)
    
    # 直接查找
    direct_path = data_path / AML_DIR_NAME
    if direct_path.exists():
        return str(direct_path)
    
    # 递归查找（最多2层）
    for depth in range(1, 3):
        pattern = "/".join(["*"] * depth) + f"/{AML_DIR_NAME}"
        matches = list(data_path.glob(pattern))
        if matches:
            return str(matches[0])
    
    return None


def _safe_str(value) -> Optional[str]:
    """安全转换为字符串"""
    if pd.isna(value):
        return None
    return str(value).strip()


def _safe_float(value) -> Optional[float]:
    """安全转换为浮点数"""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_date(value) -> Optional[str]:
    """安全转换为日期字符串"""
    if pd.isna(value):
        return None
    try:
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, str):
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        return str(value)
    except:
        return None


# 便捷函数
def get_person_aml_data(data_dir: str, person_id: str) -> Optional[Dict]:
    """
    获取指定人员的反洗钱数据
    
    Args:
        data_dir: 数据目录
        person_id: 身份证号
        
    Returns:
        Dict: 反洗钱数据，未找到返回None
    """
    result = extract_aml_data(data_dir)
    return result.get(person_id)


def get_aml_alerts(data_dir: str) -> List[Dict]:
    """
    获取所有反洗钱预警信息
    
    Args:
        data_dir: 数据目录
        
    Returns:
        List[Dict]: 预警列表
    """
    alerts = []
    
    aml_data = extract_aml_data(data_dir)
    
    for person_id, data in aml_data.items():
        if data.get("has_result"):
            alert = {
                "person_id": person_id,
                "name": data.get("name"),
                "alert_type": "反洗钱查询有结果",
                "payment_account_count": len(data.get("payment_accounts", [])),
                "payment_transaction_count": len(data.get("payment_transactions", [])),
                "suspicious_transaction_count": len(data.get("suspicious_transactions", [])),
                "large_transaction_count": len(data.get("large_transactions", [])),
                "source": data.get("source_file")
            }
            alerts.append(alert)
    
    return alerts


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    aml_data = extract_aml_data(test_dir)
    
    for person_id, data in aml_data.items():
        print(f"\n=== {data.get('name')} ({person_id}) ===")
        print(f"  有结果: {data.get('has_result')}")
        print(f"  支付账户数: {len(data.get('payment_accounts', []))}")
        print(f"  交易记录数: {len(data.get('payment_transactions', []))}")
    
    # 测试预警
    alerts = get_aml_alerts(test_dir)
    print(f"\n=== 反洗钱预警 ({len(alerts)} 条) ===")
    for alert in alerts:
        print(f"  {alert.get('name')}: {alert.get('alert_type')}")
