"""
证券信息解析模块

解析 证券信息（定向查询） 目录下的xlsx文件
提取证券账户、持仓信息、交易记录

作者: AI Assistant
创建时间: 2026-01-20
Phase: 7.3
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
SECURITIES_DIR_NAME = "证券信息（定向查询）"


def extract_securities_data(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从证券信息数据目录提取所有证券信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的证券数据
        {
            "310230196811100267": {
                "accounts": [...],
                "holdings": [...],              # 所有时点的持仓记录
                "latest_holdings": [...],       # 最新时点的持仓（用于资产统计）
                "transactions": [...],
                "query_dates": [...],           # 所有查询时点
                "summary": {...}                # 基于latest_holdings计算
            }
        }
    """
    result = {}
    
    # 查找所有匹配的目录（可能有多个时点）
    securities_dirs = _find_all_securities_dirs(data_dir)
    if not securities_dirs:
        logger.warning(f"未找到证券信息数据目录: {SECURITIES_DIR_NAME}")
        return result
    
    for securities_dir in securities_dirs:
        logger.info(f"开始解析证券信息数据: {securities_dir}")
        
        # 遍历所有xlsx文件
        securities_path = Path(securities_dir)
        xlsx_files = list(securities_path.glob("*.xlsx"))
        
        for file_path in xlsx_files:
            try:
                # 从文件名提取身份证号
                file_person_id = _extract_id_from_filename(file_path.name)
                
                if person_id and file_person_id != person_id:
                    continue
                
                # 解析文件
                data = parse_securities_file(str(file_path))
                
                if file_person_id and data:
                    if file_person_id not in result:
                        result[file_person_id] = {
                            "accounts": [],
                            "holdings": [],
                            "latest_holdings": [],
                            "transactions": [],
                            "query_dates": set(),
                            "summary": {}
                        }
                    
                    result[file_person_id]["accounts"].extend(data.get("accounts", []))
                    result[file_person_id]["holdings"].extend(data.get("holdings", []))
                    result[file_person_id]["transactions"].extend(data.get("transactions", []))
                    
                    # 从source_file中提取查询时点
                    query_date = _extract_date_from_path(str(file_path))
                    if query_date:
                        result[file_person_id]["query_dates"].add(query_date)
                    
            except Exception as e:
                logger.error(f"解析证券文件失败 {file_path}: {e}")
                continue
    
    # 处理结果：保留所有记录，但提取最新时点用于统计
    for pid in result:
        # 转换set为sorted list
        result[pid]["query_dates"] = sorted(list(result[pid]["query_dates"]), reverse=True)
        
        # 账户去重
        result[pid]["accounts"] = _deduplicate_accounts(result[pid]["accounts"])
        
        # 提取最新时点的持仓（用于资产统计）
        result[pid]["latest_holdings"] = _get_latest_holdings(result[pid]["holdings"])
        
        # 基于最新时点计算汇总
        result[pid]["summary"] = _calculate_summary(result[pid])
        result[pid]["summary"]["all_holdings_count"] = len(result[pid]["holdings"])
        result[pid]["summary"]["query_count"] = len(result[pid]["query_dates"])
    
    logger.info(f"证券信息解析完成，共 {len(result)} 个主体")
    return result



def parse_securities_file(file_path: str) -> Dict:
    """
    解析单个证券信息xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict: 包含accounts, holdings, transactions的字典
    """
    result = {"accounts": [], "holdings": [], "transactions": []}
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if df.empty:
                continue
            
            if "账户" in sheet_name and "变动" not in sheet_name:
                accounts = _parse_accounts_sheet(df, filename)
                result["accounts"].extend(accounts)
                
            elif "持有" in sheet_name and "变动" not in sheet_name:
                holdings = _parse_holdings_sheet(df, filename)
                result["holdings"].extend(holdings)
                
            elif "变动" in sheet_name:
                transactions = _parse_transactions_sheet(df, filename)
                result["transactions"].extend(transactions)
        
    except Exception as e:
        logger.error(f"读取证券文件失败 {file_path}: {e}")
    
    return result


def _parse_accounts_sheet(df: pd.DataFrame, source_file: str) -> List[Dict]:
    """解析证券账户sheet"""
    accounts = []
    
    for _, row in df.iterrows():
        try:
            account = {
                "holder_name": _safe_str(row.get("持有人名称", "")),
                "id_type": _safe_str(row.get("证件类型", "")),
                "id_number": _safe_str(row.get("证件号码", "")),
                "market": _safe_str(row.get("市场类型", "")),
                "account": _safe_str(row.get("证券账户", "")),
                "status": _safe_str(row.get("证券账户状态", "")),
                "open_date": _safe_date(row.get("开户日期")),
                "address": _safe_str(row.get("联系地址", "")),
                "phone": _safe_str(row.get("联系电话", "")),
                "broker": _safe_str(row.get("开户代理机构名称", "")),
                "result_note": _safe_str(row.get("结果说明", "")),
                "source_file": source_file
            }
            
            if account["account"]:
                accounts.append(account)
                
        except Exception as e:
            logger.debug(f"解析证券账户行失败: {e}")
            continue
    
    return accounts


def _parse_holdings_sheet(df: pd.DataFrame, source_file: str) -> List[Dict]:
    """解析证券持有sheet"""
    holdings = []
    
    for _, row in df.iterrows():
        try:
            # 检查是否有持有信息
            result_note = _safe_str(row.get("结果说明", ""))
            if "无持有信息" in result_note:
                continue
            
            quantity = _safe_int(row.get("持有数量", 0))
            price = _safe_float(row.get("当日收牌价", 0))
            
            holding = {
                "market": _safe_str(row.get("市场类型", "")),
                "account": _safe_str(row.get("证券账户", "")),
                "code": _safe_str(row.get("证券代码", "")),
                "name": _safe_str(row.get("证券简称", "")),
                "category": _safe_str(row.get("证券类别", "")),
                "quantity": quantity,
                "price": price,
                "market_value": round(quantity * price, 2),
                "total_shares": _safe_int(row.get("证券总股本数量", 0)),
                "frozen_quantity": _safe_int(row.get("其中冻结数量", 0)),
                "circulation_type": _safe_str(row.get("流通类型", "")),
                "source_file": source_file
            }
            
            if holding["code"] and quantity > 0:
                holdings.append(holding)
                
        except Exception as e:
            logger.debug(f"解析证券持有行失败: {e}")
            continue
    
    return holdings


def _parse_transactions_sheet(df: pd.DataFrame, source_file: str) -> List[Dict]:
    """解析证券持有变动sheet"""
    transactions = []
    
    for _, row in df.iterrows():
        try:
            transaction = {
                "market": _safe_str(row.get("市场类型", "")),
                "account": _safe_str(row.get("证券账户", "")),
                "code": _safe_str(row.get("证券代码", "")),
                "name": _safe_str(row.get("证券简称", "")),
                "category": _safe_str(row.get("证券类别", "")),
                "date": _safe_date(row.get("过户日期")),
                "type": _safe_str(row.get("过户类型", "")),
                "quantity": _safe_int(row.get("过户数量", 0)),
                "broker": _safe_str(row.get("结算人简称", "")),
                "source_file": source_file
            }
            
            if transaction["code"] and transaction["quantity"]:
                transactions.append(transaction)
                
        except Exception as e:
            logger.debug(f"解析证券交易行失败: {e}")
            continue
    
    return transactions


def _find_all_securities_dirs(data_dir: str) -> List[str]:
    """
    在数据目录中查找所有匹配的证券信息目录（支持多时点查询）
    """
    data_path = Path(data_dir)
    found_dirs = []
    
    for path in data_path.rglob("*"):
        if path.is_dir() and SECURITIES_DIR_NAME in path.name:
            found_dirs.append(str(path))
    
    return found_dirs


def _find_securities_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找证券信息目录（兼容旧接口）"""
    dirs = _find_all_securities_dirs(data_dir)
    return dirs[0] if dirs else None


def _extract_date_from_path(file_path: str) -> Optional[str]:
    """从文件路径中提取查询日期（从目录名）"""
    # 匹配格式如：2024年09月29日 或 2024-09-29
    pattern1 = r'(\d{4})年(\d{2})月(\d{2})日'
    pattern2 = r'(\d{4})-(\d{2})-(\d{2})'
    
    match = re.search(pattern1, file_path)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    
    match = re.search(pattern2, file_path)
    if match:
        return match.group(0)
    
    return None


def _get_latest_holdings(holdings: List[Dict]) -> List[Dict]:
    """
    从所有时点的持仓记录中，提取最新时点的持仓
    
    逻辑：按(code, account)分组，保留source_file日期最新的记录
    """
    if not holdings:
        return []
    
    # 按持仓唯一键分组
    holding_groups = {}
    
    for h in holdings:
        key = (h.get("code", ""), h.get("account", ""))
        source_file = h.get("source_file", "")
        
        # 从source_file提取日期
        date = _extract_date_from_path(source_file) or ""
        
        if key not in holding_groups:
            holding_groups[key] = (h, date)
        else:
            existing_date = holding_groups[key][1]
            if date > existing_date:
                holding_groups[key] = (h, date)
    
    return [h for h, _ in holding_groups.values()]


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号"""
    pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern, filename)
    
    if match:
        return match.group().upper()
    
    return None


def _deduplicate_accounts(accounts: List[Dict]) -> List[Dict]:
    """按账户号去重"""
    seen = set()
    unique = []
    
    for a in accounts:
        key = (a.get("account", ""), a.get("market", ""))
        if key not in seen:
            seen.add(key)
            unique.append(a)
    
    return unique


def _deduplicate_holdings(holdings: List[Dict]) -> List[Dict]:
    """按证券代码和账户去重"""
    seen = set()
    unique = []
    
    for h in holdings:
        key = (h.get("code", ""), h.get("account", ""))
        if key not in seen:
            seen.add(key)
            unique.append(h)
    
    return unique


def _calculate_summary(data: Dict) -> Dict:
    """计算证券数据汇总（基于最新时点的持仓）"""
    # 使用latest_holdings而非holdings计算市值
    latest = data.get("latest_holdings", data.get("holdings", []))
    total_market_value = sum(h.get("market_value", 0) for h in latest)
    total_frozen = sum(h.get("frozen_quantity", 0) for h in latest)
    
    return {
        "account_count": len(data.get("accounts", [])),
        "holding_count": len(latest),
        "transaction_count": len(data.get("transactions", [])),
        "total_market_value": round(total_market_value, 2),
        "total_frozen_quantity": total_frozen
    }


def _safe_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_float(value) -> float:
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(value) -> int:
    if pd.isna(value):
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _safe_date(value) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    # 处理YYYYMMDD格式
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10]


# 便捷函数
def get_person_securities(data_dir: str, person_id: str) -> Dict:
    """获取指定人员的证券信息"""
    result = extract_securities_data(data_dir, person_id)
    return result.get(person_id, {"accounts": [], "holdings": [], "transactions": [], "summary": {}})


def get_securities_summary(data_dir: str) -> Dict:
    """获取证券数据汇总统计"""
    all_data = extract_securities_data(data_dir)
    
    total_persons = len(all_data)
    total_accounts = sum(len(d["accounts"]) for d in all_data.values())
    total_holdings = sum(len(d["holdings"]) for d in all_data.values())
    total_value = sum(d["summary"].get("total_market_value", 0) for d in all_data.values())
    
    return {
        "total_persons": total_persons,
        "total_accounts": total_accounts,
        "total_holdings": total_holdings,
        "total_market_value": round(total_value, 2)
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    all_data = extract_securities_data(test_dir)
    print(f"\n=== 证券信息数据 ({len(all_data)} 个主体) ===")
    
    for person_id, data in all_data.items():
        print(f"\n身份证号: {person_id}")
        print(f"  账户数: {len(data['accounts'])}")
        print(f"  持仓数: {len(data['holdings'])}")
        print(f"  交易数: {len(data['transactions'])}")
        print(f"  总市值: {data['summary'].get('total_market_value', 0):,.2f}")
        
        for h in data["holdings"][:3]:
            print(f"  - {h.get('code')} {h.get('name')}: {h.get('quantity')}股")
    
    # 测试汇总
    summary = get_securities_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总账户: {summary['total_accounts']}")
    print(f"总持仓: {summary['total_holdings']}")
