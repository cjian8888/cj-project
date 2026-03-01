"""
市场监管总局企业登记信息解析模块

解析 市场监管总局企业登记信息（定向查询） 目录下的xlsx文件
提取公司名称、注册资本、法人、股东、经营范围等信息

作者: AI Assistant
创建时间: 2026-01-20
Phase: 6.3
"""

import os
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
COMPANY_INFO_DIR_NAME = "市场监管总局企业登记信息（定向查询）"


def extract_company_info(data_dir: str) -> Dict[str, Dict]:
    """
    从市场监管总局数据目录提取所有企业登记信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        Dict[str, Dict]: 按统一社会信用代码分组的企业信息
        {
            "913100006076928753": {
                "company_name": "XX科技有限公司",
                "uscc": "913100006076928753",
                "legal_representative": "甲某某",
                "registered_capital": 3829.6,
                "capital_currency": "人民币",
                "establishment_date": "1993-05-26",
                "business_scope": "...",
                "registration_status": "存续",
                "company_type": "股份有限公司",
                "shareholders": [...],
                "key_persons": [...],
                "related_companies": [...]
            }
        }
    """
    result = {}
    
    # 查找企业登记信息目录
    company_dir = _find_company_info_dir(data_dir)
    if not company_dir:
        logger.warning(f"未找到企业登记信息目录: {COMPANY_INFO_DIR_NAME}")
        return result
    
    logger.info(f"开始解析企业登记信息: {company_dir}")
    
    # 遍历目录下的所有xlsx文件
    xlsx_files = [f for f in Path(company_dir).glob("*.xlsx") if not f.name.startswith("~$")]
    logger.info(f"找到 {len(xlsx_files)} 个xlsx文件")
    
    for file_path in xlsx_files:
        try:
            # 解析文件
            companies = parse_company_info_file(str(file_path))
            
            for uscc, company_data in companies.items():
                if uscc not in result:
                    result[uscc] = company_data
                else:
                    # 合并数据
                    existing = result[uscc]
                    for key in ["shareholders", "key_persons", "related_companies"]:
                        if key in company_data:
                            if key not in existing:
                                existing[key] = []
                            existing[key].extend(company_data.get(key, []))
            
            logger.info(f"成功解析 {file_path.name}: {len(companies)} 家企业")
                
        except Exception as e:
            logger.error(f"解析文件失败 {file_path}: {e}")
            continue
    
    # 统计
    logger.info(f"企业登记信息解析完成: {len(result)} 家企业")
    
    return result


def parse_company_info_file(file_path: str) -> Dict[str, Dict]:
    """
    解析单个企业登记信息xlsx文件
    
    Args:
        file_path: xlsx文件路径
        
    Returns:
        Dict[str, Dict]: 按统一社会信用代码分组的企业信息
    """
    result = {}
    
    try:
        xls = pd.ExcelFile(file_path)
        source_file = os.path.basename(file_path)
        
        # 1. 解析企业基本信息
        basic_info = _parse_basic_info(xls, source_file)
        for uscc, info in basic_info.items():
            result[uscc] = info
        
        # 2. 解析自然人出资信息（股东）
        shareholders = _parse_shareholders(xls, source_file)
        for uscc, sh_list in shareholders.items():
            if uscc in result:
                result[uscc]["shareholders"] = sh_list
        
        # 3. 解析主要人员信息
        key_persons = _parse_key_persons(xls, source_file)
        for uscc, kp_list in key_persons.items():
            if uscc in result:
                result[uscc]["key_persons"] = kp_list
        
        # 4. 解析分支机构信息
        branches = _parse_branches(xls, source_file)
        for uscc, br_list in branches.items():
            if uscc in result:
                result[uscc]["branches"] = br_list
        
    except Exception as e:
        logger.error(f"解析企业登记信息文件失败 {file_path}: {e}")
        raise
    
    return result


def _parse_basic_info(xls: pd.ExcelFile, source_file: str) -> Dict[str, Dict]:
    """解析企业基本信息sheet"""
    result = {}
    
    for sheet_name in xls.sheet_names:
        if "企业基本信息" in sheet_name or "基本信息" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                if df.empty:
                    continue
                
                for idx, row in df.iterrows():
                    uscc = safe_str(row.get("统一社会信用代码"))
                    if not uscc:
                        continue
                    
                    company = {
                        "uscc": uscc,
                        "company_name": safe_str(row.get("企业（机构）名称")),
                        "legal_representative": safe_str(row.get("法定代表人")),
                        "registered_capital": safe_float(row.get("注册资本(金)（万元）")),
                        "capital_currency": safe_str(row.get("注册资本(金)币种", "人民币")),
                        "paid_capital": safe_float(row.get("实收资本")),
                        "establishment_date": safe_date(row.get("成立日期")),
                        "approval_date": safe_date(row.get("核准日期")),
                        "business_scope": safe_str(row.get("经营范围")),
                        "registration_status": safe_str(row.get("登记状态")),
                        "company_type": safe_str(row.get("市场主体类型")),
                        "statistical_type": safe_str(row.get("统计企业类型")),
                        "industry": safe_str(row.get("行业门类")),
                        "industry_code": safe_str(row.get("行业代码")),
                        "registration_authority": safe_str(row.get("登记机关")),
                        "address": safe_str(row.get("住所")),
                        "registration_number": safe_str(row.get("注册号")),
                        "employee_count": safe_int(row.get("从业人员/农专成员总数")),
                        "shareholders": [],
                        "key_persons": [],
                        "branches": [],
                        "related_companies": [],
                        "source_file": source_file
                    }
                    
                    # 只保留主公司（查询对象）
                    query_name = safe_str(row.get("查询名称"))
                    company_name = company["company_name"]
                    
                    if query_name and company_name:
                        if query_name == company_name:
                            company["is_query_target"] = True
                        else:
                            # 关联公司
                            company["is_query_target"] = False
                            company["related_to"] = query_name
                    
                    result[uscc] = company
                    
            except Exception as e:
                logger.warning(f"解析企业基本信息失败: {e}")
    
    return result


def _parse_shareholders(xls: pd.ExcelFile, source_file: str) -> Dict[str, List[Dict]]:
    """解析自然人出资信息（股东）"""
    result = {}
    
    for sheet_name in xls.sheet_names:
        if "自然人出资" in sheet_name or "出资信息" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                if df.empty:
                    continue
                
                for idx, row in df.iterrows():
                    uscc = safe_str(row.get("证件号码"))  # 企业的统一社会信用代码
                    if not uscc:
                        continue
                    
                    shareholder = {
                        "name": safe_str(row.get("自然人姓名")),
                        "id_type": safe_str(row.get("自然人证件类型")),
                        "id_number": safe_str(row.get("自然人证件号码")),
                        "subscribed_capital": safe_float(row.get("认缴出资额（万元）")),
                        "subscribed_ratio": safe_float(row.get("认缴出资比例")),
                        "subscribed_date": safe_date(row.get("认缴出资期限")),
                        "paid_capital": safe_float(row.get("实缴出资额（万元）")),
                        "currency": safe_str(row.get("币种", "人民币")),
                        "source_file": source_file
                    }
                    
                    if shareholder["name"]:
                        if uscc not in result:
                            result[uscc] = []
                        result[uscc].append(shareholder)
                    
            except Exception as e:
                logger.warning(f"解析自然人出资信息失败: {e}")
    
    return result


def _parse_key_persons(xls: pd.ExcelFile, source_file: str) -> Dict[str, List[Dict]]:
    """解析主要人员信息"""
    result = {}
    
    for sheet_name in xls.sheet_names:
        if "主要人员" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                if df.empty:
                    continue
                
                for idx, row in df.iterrows():
                    uscc = safe_str(row.get("证件号码"))  # 企业的统一社会信用代码
                    if not uscc:
                        continue
                    
                    person = {
                        "name": safe_str(row.get("姓名")) or safe_str(row.get("主要人员姓名")),
                        "position": safe_str(row.get("职务")) or safe_str(row.get("职位")),
                        "id_type": safe_str(row.get("证件类型")),
                        "id_number": safe_str(row.get("人员证件号码")),
                        "source_file": source_file
                    }
                    
                    if person["name"]:
                        if uscc not in result:
                            result[uscc] = []
                        result[uscc].append(person)
                    
            except Exception as e:
                logger.warning(f"解析主要人员信息失败: {e}")
    
    return result


def _parse_branches(xls: pd.ExcelFile, source_file: str) -> Dict[str, List[Dict]]:
    """解析分支机构信息"""
    result = {}
    
    for sheet_name in xls.sheet_names:
        if "分支机构" in sheet_name:
            try:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                if df.empty:
                    continue
                
                for idx, row in df.iterrows():
                    uscc = safe_str(row.get("证件号码"))  # 总公司的统一社会信用代码
                    if not uscc:
                        continue
                    
                    branch = {
                        "branch_name": safe_str(row.get("分支机构名称")),
                        "branch_uscc": safe_str(row.get("分支机构统一社会信用代码")),
                        "branch_registration_number": safe_str(row.get("分支机构注册号")),
                        "source_file": source_file
                    }
                    
                    if branch["branch_name"]:
                        if uscc not in result:
                            result[uscc] = []
                        result[uscc].append(branch)
                    
            except Exception as e:
                logger.warning(f"解析分支机构信息失败: {e}")
    
    return result


def _find_company_info_dir(data_dir: str) -> Optional[str]:
    """在数据目录中查找企业登记信息目录"""
    data_path = Path(data_dir)
    
    # 直接查找
    direct_path = data_path / COMPANY_INFO_DIR_NAME
    if direct_path.exists():
        return str(direct_path)
    
    # 递归查找（最多2层）
    for depth in range(1, 3):
        pattern = "/".join(["*"] * depth) + f"/{COMPANY_INFO_DIR_NAME}"
        matches = list(data_path.glob(pattern))
        if matches:
            return str(matches[0])
    
    return None


def get_companies_by_person(data_dir: str, person_id: str) -> List[Dict]:
    """
    根据身份证号查找关联的企业
    
    Args:
        data_dir: 数据目录
        person_id: 身份证号
        
    Returns:
        List[Dict]: 关联企业列表
    """
    companies = []
    all_companies = extract_company_info(data_dir)
    
    for uscc, company in all_companies.items():
        # 检查法定代表人
        # (法定代表人信息中没有身份证号，只能通过股东和主要人员匹配)
        
        # 检查股东
        for shareholder in company.get("shareholders", []):
            if shareholder.get("id_number") == person_id:
                companies.append({
                    "uscc": uscc,
                    "company_name": company.get("company_name"),
                    "role": "股东",
                    "detail": shareholder
                })
                break
        
        # 检查主要人员
        for person in company.get("key_persons", []):
            if person.get("id_number") == person_id:
                companies.append({
                    "uscc": uscc,
                    "company_name": company.get("company_name"),
                    "role": person.get("position", "主要人员"),
                    "detail": person
                })
                break
    
    return companies


def get_all_shareholders(data_dir: str) -> List[Dict]:
    """
    获取所有股东信息
    
    Args:
        data_dir: 数据目录
        
    Returns:
        List[Dict]: 股东列表
    """
    shareholders = []
    all_companies = extract_company_info(data_dir)
    
    for uscc, company in all_companies.items():
        for shareholder in company.get("shareholders", []):
            shareholder_info = shareholder.copy()
            shareholder_info["company_uscc"] = uscc
            shareholder_info["company_name"] = company.get("company_name")
            shareholders.append(shareholder_info)
    
    return shareholders


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    else:
        test_dir = "./data"
    
    print(f"测试目录: {test_dir}")
    
    # 测试提取
    companies = extract_company_info(test_dir)
    
    for uscc, company in companies.items():
        print(f"\n=== {company.get('company_name')} ===")
        print(f"  统一社会信用代码: {uscc}")
        print(f"  法定代表人: {company.get('legal_representative')}")
        print(f"  注册资本: {company.get('registered_capital')} 万元")
        print(f"  成立日期: {company.get('establishment_date')}")
        print(f"  登记状态: {company.get('registration_status')}")
        print(f"  股东数: {len(company.get('shareholders', []))}")
        print(f"  主要人员数: {len(company.get('key_persons', []))}")
        
        # 显示股东
        if company.get("shareholders"):
            print("  股东:")
            for sh in company["shareholders"][:3]:
                print(f"    - {sh.get('name')}: {sh.get('subscribed_capital')}万 ({sh.get('subscribed_ratio')}%)")


# =============================================================================
# 统一社会信用代码解析 (Phase 7.5)
# =============================================================================

CREDIT_CODE_DIR_NAME = "市场监管总局统一社会信用代码（定向查询）"


def extract_credit_code_info(data_dir: str) -> Dict[str, Dict]:
    """
    从统一社会信用代码目录提取企业信息
    
    Args:
        data_dir: 数据根目录路径
        
    Returns:
        Dict[str, Dict]: 按统一社会信用代码分组的企业信息
    """
    result = {}
    
    credit_dir = _find_credit_code_dir(data_dir)
    if not credit_dir:
        logger.warning(f"未找到统一社会信用代码目录: {CREDIT_CODE_DIR_NAME}")
        return result
    
    logger.info(f"开始解析统一社会信用代码数据: {credit_dir}")
    
    xlsx_files = [f for f in Path(credit_dir).glob("*.xlsx") if not f.name.startswith("~$")]
    
    for file_path in xlsx_files:
        try:
            companies = parse_credit_code_file(str(file_path))
            
            for uscc, company_data in companies.items():
                if uscc not in result:
                    result[uscc] = company_data
                else:
                    # 合并数据，保留更完整的信息
                    for key, value in company_data.items():
                        if value and not result[uscc].get(key):
                            result[uscc][key] = value
            
        except Exception as e:
            logger.error(f"解析统一社会信用代码文件失败 {file_path}: {e}")
            continue
    
    logger.info(f"统一社会信用代码解析完成: {len(result)} 家企业")
    return result


def parse_credit_code_file(file_path: str) -> Dict[str, Dict]:
    """解析单个统一社会信用代码xlsx文件"""
    result = {}
    source_file = os.path.basename(file_path)
    
    try:
        xls = pd.ExcelFile(file_path)
        
        sheet_name = None
        for name in xls.sheet_names:
            if "信用代码" in name or "统一社会" in name:
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = xls.sheet_names[0] if xls.sheet_names else None
        
        if not sheet_name:
            return result
        
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        if df.empty:
            return result
        
        for _, row in df.iterrows():
            uscc = safe_str(row.get("统一社会信用代码"))
            if not uscc:
                continue
            
            company = {
                "uscc": uscc,
                "org_code": safe_str(row.get("组织机构代码")),
                "company_name": safe_str(row.get("机构名称")),
                "registration_number": safe_str(row.get("注册号")),
                "company_type": safe_str(row.get("机构类型")),
                "legal_representative": safe_str(row.get("法定代表人")),
                "legal_representative_id": safe_str(row.get("法定代表人证件号码")),
                "legal_representative_phone": safe_str(row.get("法定代表人电话号码")),
                "registered_capital": safe_float(row.get("注册资本")),
                "registered_capital_currency": safe_str(row.get("注册资本币种", "人民币")),
                "paid_capital": safe_float(row.get("实收资本")),
                "establishment_date": safe_date(row.get("成立日期")),
                "business_scope": safe_str(row.get("经营范围")),
                "operation_period_start": safe_date(row.get("经营期限起")),
                "operation_period_end": safe_date(row.get("经营期限止")),
                "operation_status": safe_str(row.get("经营状态")),
                "registration_authority": safe_str(row.get("登记机关")),
                "address": safe_str(row.get("机构地址")),
                "feedback_date": safe_str(row.get("反馈录入时间")),
                "source_file": source_file,
                "data_source": "统一社会信用代码查询"
            }
            
            if uscc not in result:
                result[uscc] = company
        
    except Exception as e:
        logger.error(f"读取统一社会信用代码文件失败 {file_path}: {e}")
    
    return result


def _find_credit_code_dir(data_dir: str) -> Optional[str]:
    """查找统一社会信用代码目录"""
    data_path = Path(data_dir)
    
    for path in data_path.rglob("*"):
        if path.is_dir() and CREDIT_CODE_DIR_NAME in path.name:
            return str(path)
    
    return None


def merge_company_info(company_info: Dict[str, Dict], credit_code_info: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    合并企业登记信息和统一社会信用代码信息
    
    Args:
        company_info: 从企业登记信息提取的数据
        credit_code_info: 从统一社会信用代码提取的数据
        
    Returns:
        Dict[str, Dict]: 合并后的企业信息
    """
    result = company_info.copy()
    
    for uscc, credit_data in credit_code_info.items():
        if uscc in result:
            # 补充缺失字段
            for key, value in credit_data.items():
                if value and not result[uscc].get(key):
                    result[uscc][key] = value
            # 标记已合并
            result[uscc]["merged_credit_code"] = True
        else:
            # 新增企业
            credit_data["merged_credit_code"] = False
            result[uscc] = credit_data
    
    return result

