"""
人民银行银行账户解析模块

解析 中国人民银行银行账户（定向查询） 目录下的xlsx文件
提取官方银行账户信息，包括账户状态、开销户时间等

作者: AI Assistant
创建时间: 2026-01-20
Phase: 6.1
"""

import os
import re
import logging
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
PBOC_ACCOUNT_DIR_NAME = "中国人民银行银行账户（定向查询）"


def extract_pboc_accounts(data_dir: str, person_id: str = None) -> Dict[str, List[Dict]]:
    """
    从人民银行账户数据目录提取所有账户信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号，仅提取该人员的账户
        
    Returns:
        Dict[str, List[Dict]]: 按身份证号分组的账户列表
        {
            "310102196504096017": [
                {
                    "bank_name": "中国工商银行",
                    "account_number": "6222370251700890",
                    "account_type": "贷记卡",
                    "status": "正常",
                    "open_date": "2018-01-01",
                    "close_date": None,
                    "holder_name": "甲某某",
                    "id_number": "310102XXXXXXXXXXXX",
                    "source_file": "甲某某_310102XXXXXXXXXXXX_xxx.xlsx"
                },
                ...
            ]
        }
    """
    result = {}
    
    # 查找人民银行账户目录
    pboc_dir = _find_pboc_account_dir(data_dir)
    if not pboc_dir:
        logger.warning(f"未找到人民银行账户数据目录: {PBOC_ACCOUNT_DIR_NAME}")
        return result
    
    logger.info(f"开始解析人民银行账户数据: {pboc_dir}")
    
    # 遍历目录下的所有xlsx文件
    xlsx_files = [f for f in Path(pboc_dir).glob("*.xlsx") if not f.name.startswith("~$")]
    logger.info(f"找到 {len(xlsx_files)} 个xlsx文件")
    
    for file_path in xlsx_files:
        try:
            # 从文件名提取身份证号
            file_id_number = _extract_id_from_filename(file_path.name)
            
            # 如果指定了person_id，只处理匹配的文件
            if person_id and file_id_number != person_id:
                continue
            
            # 解析文件
            accounts = parse_pboc_account_file(str(file_path))
            
            if accounts:
                # 按身份证号分组
                for account in accounts:
                    id_num = account.get("id_number", file_id_number)
                    if id_num:
                        if id_num not in result:
                            result[id_num] = []
                        result[id_num].append(account)
                        
                logger.info(f"成功解析 {file_path.name}: {len(accounts)} 个账户")
                
        except Exception as e:
            logger.error(f"解析文件失败 {file_path}: {e}")
            continue
    
    # 统计
    total_accounts = sum(len(accounts) for accounts in result.values())
    logger.info(f"人民银行账户解析完成: {len(result)} 人, 共 {total_accounts} 个账户")
    
    return result


def parse_pboc_account_file(file_path: str) -> List[Dict]:
    """
    解析单个人民银行账户xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        List[Dict]: 账户列表
    """
    accounts = []
    
    try:
        # 读取Excel文件
        xls = pd.ExcelFile(file_path)
        
        # 查找开户信息sheet
        target_sheet = None
        for sheet_name in xls.sheet_names:
            if "开户" in sheet_name or "账户" in sheet_name:
                target_sheet = sheet_name
                break
        
        if not target_sheet:
            # 默认使用第一个sheet
            target_sheet = xls.sheet_names[0] if xls.sheet_names else None
        
        if not target_sheet:
            logger.warning(f"文件无有效sheet: {file_path}")
            return accounts
        
        # 读取数据
        df = pd.read_excel(xls, sheet_name=target_sheet)
        
        if df.empty:
            return accounts
        
        # 字段映射
        column_mapping = {
            "开户银行名称": "bank_name",
            "帐号": "account_number",
            "账号": "account_number",  # 备用
            "账户性质": "account_type",
            "账户状态": "status",
            "开户时间": "open_date",
            "销户时间": "close_date",
            "名称": "holder_name",
            "证件号码": "id_number",
            "账户名称": "account_name",
            "银行机构代码": "bank_code",
        }
        
        # 获取文件名作为来源
        source_file = os.path.basename(file_path)
        
        # 遍历每行数据
        for idx, row in df.iterrows():
            account = {"source_file": source_file}
            
            for src_col, dst_col in column_mapping.items():
                if src_col in df.columns:
                    value = row.get(src_col)
                    # 处理NaN和日期格式
                    if pd.isna(value):
                        value = None
                    elif isinstance(value, pd.Timestamp):
                        value = value.strftime("%Y-%m-%d")
                    elif dst_col in ["open_date", "close_date"] and value:
                        # 尝试转换日期字符串
                        try:
                            if isinstance(value, str):
                                value = pd.to_datetime(value).strftime("%Y-%m-%d")
                        except:
                            pass
                    
                    account[dst_col] = value
            
            # 跳过没有账号的记录
            if not account.get("account_number"):
                continue
            
            # 标准化账户类型
            account["account_type"] = _normalize_account_type(account.get("account_type"))
            
            accounts.append(account)
        
    except Exception as e:
        logger.error(f"解析人民银行账户文件失败 {file_path}: {e}")
        raise
    
    return accounts


def _find_pboc_account_dir(data_dir: str) -> Optional[str]:
    """
    在数据目录中查找人民银行账户目录
    
    Args:
        data_dir: 数据根目录
        
    Returns:
        str: 找到的目录路径，未找到返回None
    """
    data_path = Path(data_dir)
    
    # 直接查找
    direct_path = data_path / PBOC_ACCOUNT_DIR_NAME
    if direct_path.exists():
        return str(direct_path)
    
    # 递归查找（最多2层）
    for depth in range(1, 3):
        pattern = "/".join(["*"] * depth) + f"/{PBOC_ACCOUNT_DIR_NAME}"
        matches = list(data_path.glob(pattern))
        if matches:
            return str(matches[0])
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """
    从文件名中提取身份证号
    
    文件名格式示例: 甲某某_310102XXXXXXXXXXXX_国监查【XXXX】第XXXXXX号_人民银行账户信息.xlsx
    
    Args:
        filename: 文件名
        
    Returns:
        str: 身份证号，未找到返回None
    """
    # 身份证号正则：18位数字或17位数字+X
    id_pattern = r'(\d{17}[\dXx])'
    match = re.search(id_pattern, filename)
    if match:
        return match.group(1).upper()
    
    # 备用：统一社会信用代码（18位）
    uscc_pattern = r'([0-9A-Z]{18})'
    match = re.search(uscc_pattern, filename)
    if match:
        return match.group(1)
    
    return None


def _normalize_account_type(account_type: Optional[str]) -> str:
    """
    标准化账户类型
    
    Args:
        account_type: 原始账户类型
        
    Returns:
        str: 标准化后的账户类型
    """
    if not account_type:
        return "未知"
    
    account_type = str(account_type).strip()
    
    # 类型映射
    type_mapping = {
        "贷记卡": "信用卡",
        "借记卡": "借记卡",
        "其它": "其他",
        "其他": "其他",
        "活期": "活期账户",
        "定期": "定期账户",
        "对公": "对公账户",
    }
    
    for key, value in type_mapping.items():
        if key in account_type:
            return value
    
    return account_type


# 便捷函数：获取单个人员的账户列表
def get_person_pboc_accounts(data_dir: str, person_id: str) -> List[Dict]:
    """
    获取指定人员的人民银行账户列表
    
    Args:
        data_dir: 数据目录
        person_id: 身份证号
        
    Returns:
        List[Dict]: 账户列表
    """
    result = extract_pboc_accounts(data_dir, person_id)
    return result.get(person_id, [])


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    accounts = extract_pboc_accounts(test_dir)
    
    for person_id, person_accounts in accounts.items():
        print(f"\n=== {person_id} ===")
        for acc in person_accounts[:3]:  # 只显示前3个
            print(f"  银行: {acc.get('bank_name')}")
            print(f"  账号: {acc.get('account_number')}")
            print(f"  类型: {acc.get('account_type')}")
            print(f"  状态: {acc.get('status')}")
            print(f"  ---")
