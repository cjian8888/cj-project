"""
保险信息解析模块

解析 保险信息（定向查询） 目录下的xlsx文件
提取保险保单信息、人员信息、赔案信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 8.1
"""

import re
from typing import List, Dict, Optional
from pathlib import Path

import pandas as pd

import utils

logger = utils.setup_logger(__name__)


# 数据源目录名称
INSURANCE_DIR_NAME = "保险信息（定向查询）"


def extract_insurance_data(data_dir: str, person_id: str = None) -> Dict[str, Dict]:
    """
    从保险信息数据目录提取所有保险信息
    
    Args:
        data_dir: 数据根目录路径
        person_id: 可选，指定人员的身份证号
        
    Returns:
        Dict[str, Dict]: 按身份证号/统一社会信用代码分组的保险数据
        {
            "310102196504096017": {
                "policies": [保单列表],
                "persons": [人员信息列表],
                "claims": [赔案信息列表],
                "summary": {汇总信息}
            }
        }
    """
    result = {}
    
    # 查找保险数据目录
    insurance_dir = _find_insurance_dir(data_dir)
    if not insurance_dir:
        logger.warning(f"未找到保险信息数据目录: {INSURANCE_DIR_NAME}")
        return result
    
    logger.info(f"开始解析保险信息数据: {insurance_dir}")
    
    # 遍历所有xlsx文件
    insurance_path = Path(insurance_dir)
    xlsx_files = [f for f in insurance_path.glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            # 从文件名提取身份证号/统一社会信用代码
            entity_id = _extract_id_from_filename(file_path.name)
            entity_name = _extract_name_from_filename(file_path.name)
            
            # 如果指定了person_id，只处理匹配的文件
            if person_id and entity_id != person_id:
                continue
            
            # 解析文件
            insurance_data = parse_insurance_file(str(file_path))
            
            if entity_id and insurance_data:
                if entity_id not in result:
                    result[entity_id] = {
                        "name": entity_name,
                        "policies": [],
                        "persons": [],
                        "claims": [],
                        "summary": {}
                    }
                
                result[entity_id]["policies"].extend(insurance_data.get("policies", []))
                result[entity_id]["persons"].extend(insurance_data.get("persons", []))
                result[entity_id]["claims"].extend(insurance_data.get("claims", []))
                
                logger.debug(f"从 {file_path.name} 提取了 {len(insurance_data.get('policies', []))} 条保单记录")
                
        except Exception as e:
            logger.error(f"解析保险文件失败 {file_path}: {e}")
            continue
    
    # 计算每个主体的汇总
    for entity_id in result:
        result[entity_id]["summary"] = _calculate_summary(result[entity_id])
    
    logger.info(f"保险信息解析完成，共 {len(result)} 个主体")
    return result


def parse_insurance_file(file_path: str) -> Dict:
    """
    解析单个保险信息xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict: 包含 policies, persons, claims 的字典
    """
    result = {
        "policies": [],
        "persons": [],
        "claims": []
    }
    filename = Path(file_path).name
    
    try:
        xls = pd.ExcelFile(file_path)
        
        # 解析保险保单信息
        for sheet_name in xls.sheet_names:
            if "保单" in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if not df.empty:
                    for _, row in df.iterrows():
                        policy = _parse_policy_row(row, filename)
                        if policy:
                            result["policies"].append(policy)
            
            elif "人员" in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if not df.empty:
                    for _, row in df.iterrows():
                        person = _parse_person_row(row, filename)
                        if person:
                            result["persons"].append(person)
            
            elif "赔案" in sheet_name:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if not df.empty:
                    for _, row in df.iterrows():
                        claim = _parse_claim_row(row, filename)
                        if claim:
                            result["claims"].append(claim)
        
    except Exception as e:
        logger.error(f"读取保险文件失败 {file_path}: {e}")
    
    return result


def _parse_policy_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析保单行数据"""
    try:
        policy = {
            "entity_name": _safe_str(row.get("自然人对象名称") or row.get("机构名称", "")),
            "entity_id": _safe_str(row.get("自然人证件号码") or row.get("统一社会信用代码", "")),
            "product_name": _safe_str(row.get("保险产品名称", "")),
            "policy_number": _safe_str(row.get("保单号", "")),
            "insurance_company": _safe_str(row.get("保险公司名称", "")),
            "premium_paid": _safe_float(row.get("累计缴纳保费")),
            "currency": _safe_str(row.get("币种", "CNY")),
            "insurance_type": _safe_str(row.get("险种名称", "")),
            "policy_nature": _safe_str(row.get("保单团个性质", "")),
            "purchase_date": _safe_date(row.get("购买日期")),
            "effective_date": _safe_date(row.get("保单生效日期")),
            "termination_date": _safe_date(row.get("保单终止日期")),
            "insured_subject": _safe_str(row.get("保险标的名称", "")),
            "account_value": _safe_float(row.get("保险账户价值")),
            "data_date": _safe_date(row.get("数据提取日期")),
            "source_file": source_file
        }
        
        # 只有有效数据才返回
        if policy["policy_number"] or policy["product_name"]:
            return policy
        return None
        
    except Exception as e:
        logger.debug(f"解析保单行失败: {e}")
        return None


def _parse_person_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析人员行数据"""
    try:
        person = {
            "policy_seq": _safe_str(row.get("保单序号", "")),
            "person_type": _safe_str(row.get("人员类别", "")),
            "person_seq": _safe_str(row.get("人员序号", "")),
            "id_type": _safe_str(row.get("人员证件类型", "")),
            "id_number": _safe_str(row.get("人员证件号码", "")),
            "phone": _safe_str(row.get("人员联系电话", "")),
            "address": _safe_str(row.get("人员联系地址", "")),
            "payment_account": _safe_str(row.get("缴费账号", "")),
            "applicant_name": _safe_str(row.get("投保人名称", "")),
            "insured_name": _safe_str(row.get("被保险人名称", "")),
            "beneficiary_name": _safe_str(row.get("受益人名称", "")),
            "source_file": source_file
        }
        
        if person["id_number"] or person["applicant_name"] or person["insured_name"]:
            return person
        return None
        
    except Exception as e:
        logger.debug(f"解析人员行失败: {e}")
        return None


def _parse_claim_row(row: pd.Series, source_file: str) -> Optional[Dict]:
    """解析赔案行数据"""
    try:
        claim = {
            "policy_seq": _safe_str(row.get("保单序号", "")),
            "claim_seq": _safe_str(row.get("赔案序号", "")),
            "reporter_name": _safe_str(row.get("赔案报案人姓名", "")),
            "reporter_phone": _safe_str(row.get("赔案报案人联系电话", "")),
            "claim_number": _safe_str(row.get("赔案号", "")),
            "incident_time": _safe_datetime(row.get("出险时间")),
            "report_time": _safe_datetime(row.get("报案时间")),
            "incident_reason": _safe_str(row.get("出险原因", "")),
            "payment_account": _safe_str(row.get("赔款支付账号", "")),
            "payment_amount": _safe_float(row.get("赔付金额")),
            "payment_date": _safe_date(row.get("赔付日期")),
            "source_file": source_file
        }
        
        if claim["claim_number"] or claim["payment_amount"]:
            return claim
        return None
        
    except Exception as e:
        logger.debug(f"解析赔案行失败: {e}")
        return None


def _calculate_summary(data: Dict) -> Dict:
    """计算保险数据汇总"""
    policies = data.get("policies", [])
    claims = data.get("claims", [])
    
    total_premium = sum(p.get("premium_paid", 0) or 0 for p in policies)
    total_value = sum(p.get("account_value", 0) or 0 for p in policies)
    total_claims = sum(c.get("payment_amount", 0) or 0 for c in claims)
    
    # 统计保险公司分布
    companies = {}
    for p in policies:
        co = p.get("insurance_company", "未知")
        companies[co] = companies.get(co, 0) + 1
    
    # 统计险种分布
    types = {}
    for p in policies:
        t = p.get("insurance_type", "未知")
        types[t] = types.get(t, 0) + 1
    
    return {
        "total_policies": len(policies),
        "total_premium": total_premium,
        "total_account_value": total_value,
        "total_claims_count": len(claims),
        "total_claims_amount": total_claims,
        "company_distribution": companies,
        "type_distribution": types
    }


def _find_insurance_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找保险信息目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and INSURANCE_DIR_NAME in path.name:
            return str(path)
    
    return None


def _extract_id_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取身份证号或统一社会信用代码"""
    # 匹配18位身份证号
    pattern_id = r'[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
    match = re.search(pattern_id, filename)
    if match:
        return match.group().upper()
    
    # 匹配统一社会信用代码 (18位)
    pattern_credit = r'[0-9A-Z]{18}'
    match = re.search(pattern_credit, filename)
    if match:
        return match.group()
    
    return None


def _extract_name_from_filename(filename: str) -> str:
    """从文件名中提取名称"""
    # 格式: 名称_证件号_其他信息.xlsx
    parts = filename.split('_')
    if parts:
        return parts[0]
    return ""


def _safe_str(value) -> str:
    """安全转换为字符串"""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _safe_float(value) -> float:
    """安全转换为浮点数"""
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_date(value) -> str:
    """安全转换为日期字符串"""
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()[:10]


def _safe_datetime(value) -> str:
    """安全转换为日期时间字符串"""
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()[:19]


# 便捷函数
def get_person_insurance(data_dir: str, person_id: str) -> Dict:
    """获取指定人员的保险信息"""
    result = extract_insurance_data(data_dir, person_id)
    return result.get(person_id, {})


def get_insurance_summary(data_dir: str) -> Dict:
    """获取保险数据汇总"""
    all_data = extract_insurance_data(data_dir)
    
    total_entities = len(all_data)
    total_policies = 0
    total_premium = 0.0
    total_claims = 0.0
    
    for entity_id, data in all_data.items():
        summary = data.get("summary", {})
        total_policies += summary.get("total_policies", 0)
        total_premium += summary.get("total_premium", 0)
        total_claims += summary.get("total_claims_amount", 0)
    
    return {
        "total_entities": total_entities,
        "total_policies": total_policies,
        "total_premium": total_premium,
        "total_claims_amount": total_claims
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    all_data = extract_insurance_data(test_dir)
    print(f"\n=== 保险信息数据 ({len(all_data)} 个主体) ===")
    
    for entity_id, data in all_data.items():
        name = data.get("name", "")
        summary = data.get("summary", {})
        print(f"\n{name} ({entity_id}):")
        print(f"  保单数: {summary.get('total_policies', 0)}")
        print(f"  累计保费: {summary.get('total_premium', 0):.2f}")
        print(f"  账户价值: {summary.get('total_account_value', 0):.2f}")
        print(f"  赔案数: {summary.get('total_claims_count', 0)}")
        print(f"  赔付金额: {summary.get('total_claims_amount', 0):.2f}")
    
    # 测试汇总
    summary = get_insurance_summary(test_dir)
    print(f"\n=== 汇总 ===")
    print(f"总主体数: {summary['total_entities']}")
    print(f"总保单数: {summary['total_policies']}")
    print(f"总保费: {summary['total_premium']:.2f}")
    print(f"总赔付: {summary['total_claims_amount']:.2f}")
