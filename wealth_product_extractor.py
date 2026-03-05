"""
银行理财产品解析模块

解析两个数据源:
- 银行业金融机构金融理财（定向查询）/*.xlsx
- 理财产品（定向查询）/*.xlsx

提取理财产品信息、持有金额等

作者: AI Assistant
创建时间: 2026-01-20
Phase: 7.2
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils
from utils.safe_types import (
    safe_str,
    safe_float,
    safe_int,
    safe_date,
    safe_datetime,
)

logger = utils.setup_logger(__name__)


# 数据源目录名称
WEALTH_DIR_NAMES = [
    "银行业金融机构金融理财（定向查询）",
    "理财产品（定向查询）"
]


def extract_wealth_product_data(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从理财产品数据目录提取所有理财信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号分组的理财数据
        {
            "310102196504096017": {
                "products": [...],           # 所有时点的产品记录（用于追踪变化）
                "latest_products": [...],    # 最新时点的产品（用于资产统计）
                "accounts": [...],
                "summary": {                 # 基于最新时点计算
                    "total_amount": float,
                    "product_count": int
                },
                "query_dates": [...]         # 所有查询时点
            }
        }
    """
    result = {}
    
    for dir_name in WEALTH_DIR_NAMES:
        # 查找所有匹配的目录（可能有多个时点）
        wealth_dirs = _find_all_wealth_dirs(data_dir, dir_name)
        
        for wealth_dir in wealth_dirs:
            logger.info(f"开始解析理财数据: {wealth_dir}")
            
            # 遍历所有xlsx文件
            wealth_path = Path(wealth_dir)
            xlsx_files = [f for f in wealth_path.glob("*.xlsx") if not f.name.startswith("~$")]
            
            for file_path in xlsx_files:
                try:
                    # 从文件名提取身份证号或统一社会信用代码
                    file_id = _extract_id_from_filename(file_path.name)
                    
                    # 如果指定了person_id，只处理匹配的文件
                    if person_id and file_id != person_id:
                        continue
                    
                    # 解析文件
                    data = parse_wealth_file(str(file_path))
                    
                    if file_id and data:
                        if file_id not in result:
                            result[file_id] = {
                                "products": [],
                                "latest_products": [],
                                "accounts": [],
                                "summary": {"total_amount": 0, "product_count": 0},
                                "query_dates": set(),
                                "_holdings": []  # 【新增】存储持有信息
                            }
                        
                        result[file_id]["products"].extend(data.get("products", []))
                        result[file_id]["accounts"].extend(data.get("accounts", []))
                        result[file_id]["_holdings"].extend(data.get("_holdings", []))  # 【新增】
                        
                        # 收集查询时点
                        for p in data.get("products", []):
                            if p.get("feedback_date"):
                                result[file_id]["query_dates"].add(p["feedback_date"])
                        # 【新增】从持有信息收集时点
                        for h in data.get("_holdings", []):
                            if h.get("holding_date"):
                                result[file_id]["query_dates"].add(h["holding_date"])
                except Exception as e:
                    logger.error(f"解析理财文件失败 {file_path}: {e}")
                    continue
    
    # 处理结果：保留所有记录，但提取最新时点用于统计
    for pid in result:
        # 转换set为sorted list
        result[pid]["query_dates"] = sorted(list(result[pid]["query_dates"]), reverse=True)
        
        # 账户去重
        result[pid]["accounts"] = _deduplicate_accounts(result[pid]["accounts"])
        
        # 【修复】使用持有信息补充产品金额（针对理财产品格式）
        holdings_map = {}
        for h in result[pid].get("_holdings", []):
            code = h.get("product_code", "")
            if code and code not in holdings_map:
                # 取最新日期的持有金额
                holdings_map[code] = h.get("amount", 0)
        
        # 补充产品金额
        for product in result[pid]["products"]:
            if product.get("amount", 0) == 0 and product.get("product_code"):
                code = product["product_code"]
                if code in holdings_map:
                    product["amount"] = holdings_map[code]
                    product["available_amount"] = holdings_map[code]
        
        # 提取最新时点的产品（用于资产统计）
        result[pid]["latest_products"] = _get_latest_products(result[pid]["products"])
        
        # 基于最新时点计算汇总
        result[pid]["summary"] = _calculate_summary(result[pid]["latest_products"])
        result[pid]["summary"]["all_records_count"] = len(result[pid]["products"])
        result[pid]["summary"]["query_count"] = len(result[pid]["query_dates"])
        
        # 清理临时数据
        if "_holdings" in result[pid]:
            del result[pid]["_holdings"]
    
    logger.info(f"理财产品解析完成，共 {len(result)} 个主体")
    return result


def parse_wealth_file(file_path: str) -> Dict:
    """
    解析单个理财产品xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict: 包含products和accounts的字典
    """
    result = {"products": [], "accounts": [], "_holdings": []}
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 【修复】第一遍遍历：先解析持有信息（用于补充产品金额）
        holdings_data = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if df.empty:
                continue
            
            if "持有信息" in sheet_name:
                # 【新增】解析理财产品持有信息（用于补充金额数据）
                holdings = _parse_holdings_sheet(df, filename)
                holdings_data.extend(holdings)
        
        # 【修复】第二遍遍历：解析产品和账户信息
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            if df.empty:
                continue
            
            # 【修复】支持两种数据源格式：银行理财（金融理财信息）和 理财产品（产品信息）
            if "理财信息" in sheet_name or "金融理财信息" in sheet_name or "产品信息" in sheet_name:
                # 解析理财产品信息，传入持有信息用于补充金额
                products = _parse_products_sheet(df, filename, holdings_data)
                result["products"].extend(products)
                
            elif "持有信息" in sheet_name:
                # 持有信息已在上一步处理，这里跳过
                result["_holdings"].extend(holdings_data)
                
            elif "账户" in sheet_name:
                # 解析理财账户信息
                accounts = _parse_accounts_sheet(df, filename)
                result["accounts"].extend(accounts)
    except Exception as e:
        logger.error(f"读取理财文件失败 {file_path}: {e}")
    
    return result


def _parse_products_sheet(df: pd.DataFrame, source_file: str, holdings_data: List[Dict] = None) -> List[Dict]:
    """解析理财产品信息sheet
    
    【修复】支持两种数据源格式：
    1. 银行业金融机构金融理财：列名包含"金融理财名称"、"反馈单位"等
    2. 理财产品（定向查询）：列名包含"产品名称"、"发行机构"等
    """
    products = []
    total_rows = len(df)
    processed = 0
    log_interval = max(1, total_rows // 10) if total_rows > 0 else 1
    
    # 【修复】检测数据源类型
    has_financial_cols = "金融理财名称" in df.columns
    has_product_cols = "产品名称" in df.columns
    
    if not has_financial_cols and not has_product_cols:
        logger.warning(f"[理财解析] 无法识别列名格式，列: {df.columns.tolist()}")
        return products
    
    # 【修复】构建持有信息查找表（product_code -> amount）
    holdings_map = {}
    if holdings_data:
        for h in holdings_data:
            code = h.get("product_code", "")
            if code:
                holdings_map[code] = h.get("amount", 0)

    for _, row in df.iterrows():
        try:
            if has_financial_cols:
                # 格式1：银行业金融机构金融理财（原始逻辑）
                product = {
                    "bank": safe_str(row.get("反馈单位", "")),
                    "product_name": safe_str(row.get("金融理财名称", "")),
                    "product_type": safe_str(row.get("金融理财类型", "")),
                    "product_code": safe_str(row.get("金融产品编号", "")),
                    "amount": safe_float(row.get("资产总数额", 0)),
                    "available_amount": safe_float(row.get("可控资产总数额", 0)),
                    "shares": safe_float(row.get("数量/份额/金额", 0)),
                    "unit_price": safe_float(row.get("资产单位价格", 0)),
                    "currency": safe_str(row.get("币种", "人民币")),
                    "status": safe_str(row.get("产品状态", "")),
                    "sales_type": safe_str(row.get("产品销售种类", "")),
                    "asset_manager": safe_str(row.get("资产管理人", "")),
                    "custodian": safe_str(row.get("托管人", "")),
                    "start_date": safe_date(row.get("成立日")),
                    "end_date": safe_date(row.get("赎回日")),
                    "feedback_date": safe_date(row.get("反馈日期")),
                    "source_file": source_file
                }
            else:
                # 格式2：理财产品（定向查询）（新增逻辑）
                product_code = safe_str(row.get("产品登记编码", ""))
                
                # 从持有信息补充金额（如果存在）
                amount = holdings_map.get(product_code, 0) if holdings_map else 0
                
                product = {
                    "bank": safe_str(row.get("发行机构", "")),
                    "product_name": safe_str(row.get("产品名称", "")),
                    "product_type": safe_str(row.get("产品运作模式", "")),
                    "product_code": product_code,
                    "amount": amount,  # 从持有信息获取
                    "available_amount": amount,  # 默认可用金额等于持有金额
                    "shares": 0,  # 理财产品格式无此字段
                    "unit_price": 0,  # 理财产品格式无此字段
                    "currency": safe_str(row.get("币种", "人民币")),
                    "status": safe_str(row.get("产品状态", "")),
                    "sales_type": "",  # 理财产品格式无此字段
                    "asset_manager": safe_str(row.get("产品管理人", "")),
                    "custodian": safe_str(row.get("产品托管人", "")),
                    "start_date": safe_date(row.get("产品起始日")),
                    "end_date": safe_date(row.get("产品终止日")),
                    "feedback_date": None,  # 理财产品格式无此列，使用持有信息的日期
                    "source_file": source_file
                }

            # 只保留有产品名称的记录
            if product["product_name"]:
                products.append(product)

            processed += 1
            # 每10%输出进度
            if log_interval > 0 and (processed % log_interval == 0 or processed == total_rows):
                progress = (processed / total_rows * 100) if total_rows > 0 else 0
                logger.info(f"理财产品解析进度: {progress:.1f}% ({processed}/{total_rows} 行)")

        except Exception as e:
            logger.debug(f"解析理财产品行失败: {e}")
            continue

    logger.info(f"理财产品解析完成: 共解析 {len(products)} 条有效记录")
    return products


def _parse_accounts_sheet(df: pd.DataFrame, source_file: str) -> List[Dict]:
    """解析理财账户信息sheet"""
    accounts = []
    
    for _, row in df.iterrows():
        try:
            account = {
                "bank": safe_str(row.get("反馈单位", "")),
                "account_number": safe_str(row.get("理财账号", row.get("理财卡号", ""))),
                "account_type": safe_str(row.get("账户类别", "")),
                "account_status": safe_str(row.get("账户状态", "")),
                "open_date": safe_date(row.get("开户日期")),
                "open_branch": safe_str(row.get("开户网点", "")),
                "balance": safe_float(row.get("账户余额", 0)),
                "available_balance": safe_float(row.get("可用余额", 0)),
                "currency": safe_str(row.get("币种", "人民币")),
                "last_transaction_time": safe_str(row.get("最后交易时间", "")),
                "source_file": source_file
            }
            
            if account["account_number"] or account["bank"]:
                accounts.append(account)
                
        except Exception as e:
            logger.debug(f"解析理财账户行失败: {e}")
            continue
    
    return accounts
def _parse_holdings_sheet(df: pd.DataFrame, source_file: str) -> List[Dict]:
    """解析理财产品持有信息sheet（用于理财产品定向查询格式）
    
    【新增】从持有信息sheet提取产品持有金额
    列名：产品登记编码、持有日期、币种、持有金额、理财收益率
    """
    holdings = []
    
    for _, row in df.iterrows():
        try:
            holding = {
                "product_code": safe_str(row.get("产品登记编码", "")),
                "holding_date": safe_date(row.get("持有日期")),
                "currency": safe_str(row.get("币种", "人民币")),
                "amount": safe_float(row.get("持有金额", 0)),
                "yield_rate": safe_float(row.get("理财收益率（%）", 0)),
                "source_file": source_file
            }
            
            if holding["product_code"]:
                holdings.append(holding)
                
        except Exception as e:
            logger.debug(f"解析持有信息行失败: {e}")
            continue
    
    logger.info(f"持有信息解析完成: 共解析 {len(holdings)} 条记录")
    return holdings

def _find_all_wealth_dirs(data_dir: str, target_name: str) -> List[str]:
    """
    在数据目录中查找所有匹配的理财数据目录（支持多时点查询）
    
    Args:
        data_dir: 数据根目录
        target_name: 目标目录名
        
    Returns:
        List[str]: 所有匹配目录的路径列表
    """
    data_path = Path(data_dir)
    found_dirs = []
    
    for path in data_path.rglob("*"):
        if path.is_dir() and target_name in path.name:
            found_dirs.append(str(path))
    
    return found_dirs


def _get_latest_products(products: List[Dict]) -> List[Dict]:
    """
    从所有时点的产品记录中，提取最新时点的产品
    
    逻辑：按(product_code, bank, product_name)分组，保留feedback_date最新的记录
    
    Args:
        products: 所有时点的产品列表
        
    Returns:
        List[Dict]: 最新时点的产品列表
    """
    if not products:
        return []
    
    # 按产品唯一键分组
    product_groups = {}
    
    for p in products:
        key = (p.get("product_code", ""), p.get("bank", ""), p.get("product_name", ""))
        feedback_date = p.get("feedback_date", "")
        
        if key not in product_groups:
            product_groups[key] = p
        else:
            # 比较日期，保留最新的
            existing_date = product_groups[key].get("feedback_date", "")
            if feedback_date > existing_date:
                product_groups[key] = p
    
    return list(product_groups.values())


def _find_wealth_dir(data_dir: str, target_name: str) -> Optional[str]:
    """在数据目录中查找理财数据目录（兼容旧接口）"""
    dirs = _find_all_wealth_dirs(data_dir, target_name)
    return dirs[0] if dirs else None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号或统一社会信用代码"""
    # 匹配18位身份证号
    id_pattern = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(id_pattern, filename)
    if match:
        return match.group().upper()
    
    # 匹配统一社会信用代码 (18位)
    credit_pattern = r'[0-9A-Z]{18}'
    match = re.search(credit_pattern, filename)
    if match:
        return match.group()
    
    return None


def _deduplicate_products(products: List[Dict]) -> List[Dict]:
    """按产品编号和银行去重"""
    seen = set()
    unique = []
    
    for p in products:
        key = (p.get("product_code", ""), p.get("bank", ""), p.get("product_name", ""))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    return unique


def _deduplicate_accounts(accounts: List[Dict]) -> List[Dict]:
    """按账号去重"""
    seen = set()
    unique = []
    
    for a in accounts:
        key = a.get("account_number", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
    
    return unique


def _calculate_summary(products: List[Dict]) -> Dict:
    """计算理财产品汇总"""
    total = sum(p.get("amount", 0) for p in products)
    available = sum(p.get("available_amount", 0) for p in products)
    
    return {
        "total_amount": round(total, 2),
        "total_available": round(available, 2),
        "product_count": len(products)
    }


def get_wealth_summary(data_dir: str) -> Dict:
    """获取理财产品汇总统计"""
    all_data = extract_wealth_product_data(data_dir)
    
    total_persons = len(all_data)
    total_products = sum(len(d["products"]) for d in all_data.values())
    total_amount = sum(d["summary"].get("total_amount", 0) for d in all_data.values())
    
    # 统计银行分布
    banks = {}
    for data in all_data.values():
        for p in data["products"]:
            bank = p.get("bank", "未知")
            banks[bank] = banks.get(bank, 0) + 1
    
    return {
        "total_persons": total_persons,
        "total_products": total_products,
        "total_amount": round(total_amount, 2),
        "bank_distribution": banks
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    all_data = extract_wealth_product_data(test_dir)
    print(f"\n=== 理财产品数据 ({len(all_data)} 个主体) ===")
    
    for person_id, data in all_data.items():
        print(f"\n身份证号: {person_id}")
        print(f"  产品数量: {len(data['products'])}")
        print(f"  账户数量: {len(data['accounts'])}")
        print(f"  总金额: {data['summary'].get('total_amount', 0):,.2f}")
        
        for p in data["products"][:3]:  # 只显示前3个
            print(f"  - {p.get('product_name')[:30]}... ({p.get('bank')})")
    
    # 测试汇总
    summary = get_wealth_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总人数: {summary['total_persons']}")
    print(f"总产品数: {summary['total_products']}")
    print(f"总金额: {summary['total_amount']:,.2f}")
