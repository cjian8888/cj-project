"""
银行业金融机构账户信息解析模块

解析 银行业金融机构账户信息（定向查询） 目录下的xlsx文件
提取商业银行账户详情，补充人民银行账户数据

作者: AI Assistant
创建时间: 2026-01-20
Phase: 6.5
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils
from utils.safe_types import (
    safe_str,
    safe_float,
    safe_amount,
    safe_int,
    safe_date,
    safe_datetime,
)

logger = utils.setup_logger(__name__)


# 数据源目录名称
BANK_ACCOUNT_INFO_DIR_NAME = "银行业金融机构账户信息（定向查询）"


def _safe_money(value) -> Optional[float]:
    """账户余额统一按元解析，兼容显式单位和脏字符串。"""
    return safe_amount(value, source_unit="yuan", target_unit="yuan")


def extract_bank_account_info(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从银行账户信息目录提取所有账户信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的账户信息
        {
            "310102196504096017": {
                "name": "施灵",
                "id_number": "310102196504096017",
                "accounts": [
                    {
                        "account_number": "621...",
                        "card_number": "621...",
                        "bank_name": "工商银行",
                        "account_type": "储蓄账户",
                        "status": "正常",
                        "balance": 10000.00,
                        "open_date": "2020-01-01",
                        "close_date": None,
                        "source_file": "xxx.xlsx"
                    },
                    ...
                ]
            }
        }
    """
    info_dir = _find_bank_account_info_dir(data_dir)
    if not info_dir:
        logger.warning(f"未找到银行账户信息目录: {BANK_ACCOUNT_INFO_DIR_NAME}")
        return {}
    
    results = {}
    info_path = Path(info_dir)
    
    # 遍历所有xlsx文件
    xlsx_files = [f for f in info_path.glob("*.xlsx") if not f.name.startswith("~$")]
    logger.info(f"找到 {len(xlsx_files)} 个银行账户信息文件")
    
    for xlsx_file in xlsx_files:
        # 如果指定了person_id，只处理对应文件
        if person_id:
            if person_id not in xlsx_file.name:
                continue
        
        try:
            file_data = parse_bank_account_info_file(str(xlsx_file))
            for id_key, data in file_data.items():
                if id_key in results:
                    # 合并账户列表
                    results[id_key]["accounts"].extend(data.get("accounts", []))
                else:
                    results[id_key] = data
        except Exception as e:
            logger.error(f"解析银行账户信息文件失败 {xlsx_file.name}: {e}")
    
    logger.info(f"成功解析 {len(results)} 个主体的银行账户信息")
    return results


def parse_bank_account_info_file(file_path: str) -> Dict[str, Dict]:
    """
    解析单个银行账户信息xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的账户信息
    """
    filename = Path(file_path).name
    results = {}
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 解析账号基本信息sheet
        if "账号基本信息" in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name="账号基本信息")
            
            for _, row in df.iterrows():
                id_number = safe_str(row.get("证件号码"))
                if not id_number:
                    continue
                
                name = safe_str(row.get("名称"))
                
                if id_number not in results:
                    results[id_number] = {
                        "name": name,
                        "id_number": id_number,
                        "accounts": []
                    }
                
                account = {
                    "account_number": safe_str(row.get("账号")),
                    "card_number": safe_str(row.get("卡号")),
                    "bank_name": safe_str(row.get("反馈单位")),
                    "account_type": safe_str(row.get("账户类别")),
                    "status": safe_str(row.get("账户状态")),
                    "balance": _safe_money(row.get("账户余额")),
                    "available_balance": _safe_money(row.get("可用余额")),
                    "open_date": safe_date(row.get("开户日期")),
                    "close_date": safe_date(row.get("销户日期")),
                    "branch": safe_str(row.get("开户网点")),
                    "currency": safe_str(row.get("币种")),
                    "last_transaction": safe_datetime(row.get("最后交易时间")),
                    "source_file": filename
                }
                
                # 去重：检查是否已存在相同账号
                existing_accounts = [a.get("account_number") for a in results[id_number]["accounts"]]
                if account["account_number"] not in existing_accounts:
                    results[id_number]["accounts"].append(account)
        
    except Exception as e:
        logger.error(f"解析银行账户信息文件出错 {filename}: {e}")
    
    return results


def _find_bank_account_info_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找银行账户信息目录"""
    data_path = Path(data_dir)
    
    # 直接查找
    direct_path = data_path / BANK_ACCOUNT_INFO_DIR_NAME
    if direct_path.exists():
        return str(direct_path)
    
    # 递归查找
    for subdir in data_path.rglob(BANK_ACCOUNT_INFO_DIR_NAME):
        if subdir.is_dir():
            return str(subdir)
    
    return None


def get_account_summary(data_dir: str) -> Dict:
    """
    获取账户汇总信息
    
    Args:
        data_dir: 数据目录
        
    Returns:
        Dict: 汇总信息
    """
    all_data = extract_bank_account_info(data_dir)
    
    summary = {
        "total_persons": len(all_data),
        "total_accounts": 0,
        "total_balance": 0.0,
        "by_bank": {},
        "by_status": {}
    }
    
    for id_number, info in all_data.items():
        for account in info.get("accounts", []):
            summary["total_accounts"] += 1
            balance = account.get("balance") or 0
            summary["total_balance"] += balance
            
            # 按银行统计
            bank = account.get("bank_name") or "未知"
            if bank not in summary["by_bank"]:
                summary["by_bank"][bank] = {"count": 0, "balance": 0}
            summary["by_bank"][bank]["count"] += 1
            summary["by_bank"][bank]["balance"] += balance
            
            # 按状态统计
            status = account.get("status") or "未知"
            if status not in summary["by_status"]:
                summary["by_status"][status] = 0
            summary["by_status"][status] += 1
    
    return summary


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    bank_data = extract_bank_account_info(test_dir)
    print(f"\n=== 银行账户信息 ({len(bank_data)} 人) ===")
    
    for id_number, info in bank_data.items():
        accounts = info.get("accounts", [])
        print(f"\n{info.get('name')} ({id_number}): {len(accounts)} 个账户")
        for acc in accounts[:3]:
            print(f"  - {acc.get('bank_name')}: {acc.get('account_number')} ({acc.get('status')}) 余额: {acc.get('balance', 0):.2f}")
    
    # 测试汇总
    summary = get_account_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总账户数: {summary['total_accounts']}")
    print(f"总余额: {summary['total_balance']:.2f}")
