#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金画像分析模块 - 资金穿透与关联排查系统
生成个人/公司的资金特征画像
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
import config
import utils

logger = utils.setup_logger(__name__)


def _calculate_stable_cv(amounts: List[float], remove_outliers: bool = True) -> float:
    """
    计算变异系数CV，可选择剔除异常值
    
    Args:
        amounts: 金额列表
        remove_outliers: 是否剔除异常值（使用IQR方法）
    
    Returns:
        变异系数CV
    """
    if len(amounts) == 0:
        return 999
    
    # 如果需要剔除异常值且数据量足够
    if remove_outliers and len(amounts) > 3:
        # 使用IQR方法识别异常值
        sorted_amounts = sorted(amounts)
        n = len(sorted_amounts)
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_amounts[q1_idx]
        q3 = sorted_amounts[q3_idx]
        iqr = q3 - q1
        
        # 定义上下界
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # 过滤异常值
        filtered_amounts = [x for x in amounts if lower_bound <= x <= upper_bound]
        
        # 如果剔除后至少还有一半数据，使用过滤后的数据
        if len(filtered_amounts) >= max(3, len(amounts) * 0.5):
            amounts = filtered_amounts
            logger.debug(f'剔除异常值: 原{len(amounts)}笔 -> 保留{len(filtered_amounts)}笔')
    
    # 计算均值和标准差
    mean_amt = sum(amounts) / len(amounts)
    variance = sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)
    std_amt = variance ** 0.5
    
    # 计算CV
    cv = std_amt / mean_amt if mean_amt > 0 else 999
    
    return cv


def calculate_income_structure(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    计算收支结构（增强版工资识别 - 能够自动识别工资发放单位，并严格剔除理财/投资类回款）
    
    Args:
        df: 交易DataFrame
        entity_name: 核查对象姓名（用于排除同名转账）
        
    Returns:
        收支结构字典
    """
    logger.info('正在计算收支结构...')
    
    # 获取日期范围
    start_date, end_date = utils.calculate_date_range(df['date'].tolist())
    
    # 统计总流入和同名转账
    total_inflow = df['income'].sum()
    total_expense = df['expense'].sum()
    
    # 识别同名转账（本人转入）
    self_transfer_mask = (df['counterparty'] == entity_name) & (df['income'] > 0)
    self_transfer_income = df[self_transfer_mask]['income'].sum()
    
    # 计算外部净收入（排除本人互转）
    external_income = total_inflow - self_transfer_income
    
    # 识别工资性收入（增强版）
    salary_income = 0.0
    non_salary_income = 0.0
    salary_details = []  # 工资明细列表
    
    # 只处理收入记录
    income_df = df[df['income'] > 0].copy()
    
    if not income_df.empty:
        # 为每笔收入标记是否为工资
        income_df['is_salary'] = False
        income_df['salary_reason'] = ''  # 判定依据
        income_df['is_self_transfer'] = False # 是否为本人互转
        income_df['is_reimbursement'] = False # 是否为报销/退款
        
        if entity_name:
             income_df.loc[income_df['counterparty'] == entity_name, 'is_self_transfer'] = True
        
        # 预处理：识别报销/差旅/退款（负面清单）
        immunity_keywords = ['安家费', '年终奖', '绩效', '奖金', '工资', '薪资', '劳务', '骨干奖', '贡献奖']
        
        for idx, row in income_df.iterrows():
            if row['is_self_transfer']: continue
            description = str(row.get('description', ''))
            
            # 检查是否包含排除关键词
            if utils.contains_keywords(description, config.EXCLUDED_REIMBURSEMENT_KEYWORDS):
                if not utils.contains_keywords(description, immunity_keywords):
                    income_df.at[idx, 'is_reimbursement'] = True

        # -------------------------------------------------------------------------
        # 步骤 A: 自动挖掘工资发放单位 (最重要的优化)
        # -------------------------------------------------------------------------
        learned_salary_payers = set(config.KNOWN_SALARY_PAYERS + config.USER_DEFINED_SALARY_PAYERS)
        
        # 1. 强制添加用户指定的红名单单位
        learned_salary_payers.add("上海航天化工应用研究所") 
        
        # 定义由于理财/投资/基金导致的“假性工资发放者”黑名单关键词
        # 凡是名字里带这些的，绝对不是发工资的单位，而是投资回款
        WEALTH_ENTITY_BLACKLIST = [
            '基金', '资产管理', '投资', '信托', '证券', '期货', '保险', 
            '财富', '资本', '经营部', '个体', '直销', '理财', 
            '固收', '定活宝', '增利',
            'Fund', 'Asset', 'Invest', 'Capital', 'Wealth'
        ]
        
        # 2. 扫描数据，寻找那些发过"工资/奖金"的单位
        if not income_df.empty:
            for _, row in income_df.iterrows():
                desc = str(row.get('description', ''))
                cp = str(row.get('counterparty', '')).strip()
                
                # 如果是"代发工资内部户"等，直接认可
                if '代发工资' in cp:
                    learned_salary_payers.add(cp)
                    continue

                if not cp or len(cp) < 4: continue # 忽略太短的
                
                # 安全检查：如果单位名字包含投资/基金/理财特征，绝对不能加入所谓"工资白名单"
                if utils.contains_keywords(cp, WEALTH_ENTITY_BLACKLIST):
                    continue
                
                # 排除银行分行（往往是理财转出）
                if '银行' in cp and not '人力' in cp:
                    continue

                # 如果某笔交易摘要明确说是工资/奖金，那么这个对手方就很可能就是发薪单位
                if utils.contains_keywords(desc, config.SALARY_STRONG_KEYWORDS + ['年终奖', '骨干奖', '绩效', '薪酬', '代发工资']):
                    learned_salary_payers.add(cp)
        
        logger.info(f"已识别的发薪/收入来源白名单: {list(learned_salary_payers)}")


        # -------------------------------------------------------------------------
        # 步骤 B: 多轮次识别
        # -------------------------------------------------------------------------
        
        # 轮次1: 白名单单位的所有打款（除非明确是退款或理财赎回）
        for idx, row in income_df.iterrows():
            if income_df.at[idx, 'is_salary'] or row['is_self_transfer'] or row['is_reimbursement']:
                continue
            
            counterparty = str(row.get('counterparty', ''))
            description = str(row.get('description', ''))
            
            # 双重保险：即使是白名单，如果摘要包含赎回特征，也不算工资
            if utils.contains_keywords(description, ['赎回', '卖出', '本金', '退保', '分红']):
                continue
            
            # 检查对手方是否在白名单中
            is_known_payer = False
            for payer in learned_salary_payers:
                if payer in counterparty: 
                    is_known_payer = True
                    break
            
            if is_known_payer:
                income_df.at[idx, 'is_salary'] = True
                reason = '已知发薪单位'
                if utils.contains_keywords(description, ['奖', '绩效', '年薪']):
                    reason = f'已知单位-{description}'
                income_df.at[idx, 'salary_reason'] = reason

                
        # 轮次2: 强关键词匹配 (需严格区分理财分红和奖金分红)
        for idx, row in income_df.iterrows():
            if income_df.at[idx, 'is_salary'] or row['is_self_transfer'] or row.get('is_reimbursement'):
                continue
            description = str(row.get('description', ''))
            counterparty = str(row.get('counterparty', ''))
            
            # 如果是"分红"，必须确认不是基金/证券公司的分红
            if '分红' in description:
                if utils.contains_keywords(counterparty, WEALTH_ENTITY_BLACKLIST):
                    continue
            
            if utils.contains_keywords(description, config.SALARY_STRONG_KEYWORDS):
                income_df.at[idx, 'is_salary'] = True
                income_df.at[idx, 'salary_reason'] = '摘要含强工资关键词'
                
        # 轮次3: 人力资源公司
        for idx, row in income_df.iterrows():
            if income_df.at[idx, 'is_salary'] or row['is_self_transfer'] or row['is_reimbursement']:
                continue
            counterparty = str(row.get('counterparty', ''))
            if utils.contains_keywords(counterparty, config.HR_COMPANY_KEYWORDS):
                if row['income'] >= 1000:
                    income_df.at[idx, 'is_salary'] = True
                    income_df.at[idx, 'salary_reason'] = '人力资源公司'

        # 轮次4: 高频稳定收入 (严格排除金融机构)
        counterparty_groups = income_df.groupby('counterparty')
        for counterparty, group in counterparty_groups:
            if not counterparty or str(counterparty) == 'nan': continue
            if group['is_salary'].any(): continue 
            if group.iloc[0]['is_self_transfer']: continue
            
            # 排除由于理财和借贷导致的频繁交易
            # 增加对金融机构的排除力度
            if utils.contains_keywords(str(counterparty), 
                config.LOAN_PLATFORM_KEYWORDS + 
                config.THIRD_PARTY_PAYMENT_KEYWORDS + 
                ['银行', '保险', '证券', '基金', '信托', '期货', '资产', '投资', '理财']):
                continue
                
            import re
            if re.match(r'^[\u4e00-\u9fa5]{2,4}$', str(counterparty)): continue
            
            valid_group = group[~group['is_reimbursement'].fillna(False)]
            if len(valid_group) >= 6:
                dates = valid_group['date'].tolist()
                months = set(d.strftime('%Y-%m') for d in dates)
                # 至少5个月，覆盖率0.6
                if len(months) >= 5 and len(valid_group)/len(months) > 0.6:
                    amounts = valid_group['income'].tolist()
                    cv = _calculate_stable_cv(amounts, remove_outliers=True)
                    mean_amount = sum(amounts) / len(amounts)
                    # 进一步检查摘要，排除理财赎回特征
                    is_wealth_like = False
                    wealth_keywords = ['赎回', '到期', '本息', '转存', '理财', '结息', '收益', '分红', '活期宝', '转活', '提现', '银证']
                    
                    # 检查组内是否有过多理财特征
                    wealth_count = 0
                    for d in valid_group['description']:
                        if utils.contains_keywords(str(d), wealth_keywords):
                            wealth_count += 1
                    
                    if wealth_count / len(valid_group) > 0.3: # 如果超过30%看起来像理财
                        continue

                    if 2000 <= mean_amount <= 80000 and cv < 2.0: 
                         for idx, row in valid_group.iterrows():
                            # 单笔再检查一次
                            if utils.contains_keywords(str(row['description']), wealth_keywords):
                                continue
                                
                            income_df.at[idx, 'is_salary'] = True
                            income_df.at[idx, 'salary_reason'] = f'高频稳定收入(连续{len(months)}月)'

        # 统计
        for idx, row in income_df.iterrows():
            if row['is_salary']:
                salary_income += row['income']
                salary_details.append({
                    '日期': row['date'], '金额': row['income'],
                    '对手方': row.get('counterparty', ''),
                    '摘要': row.get('description', ''),
                    '判定依据': row['salary_reason']
                })
            elif not row['is_self_transfer'] and not row['is_reimbursement']:
                non_salary_income += row['income']
    
    # 按年度/月度统计 (保持原样)
    df['year'] = df['date'].dt.year
    yearly_stats = df.groupby('year').agg({'income': 'sum', 'expense': 'sum'}).to_dict('index')
    df['month'] = df['date'].apply(utils.get_month_key)
    monthly_stats = df.groupby('month').agg({'income': 'sum', 'expense': 'sum'}).to_dict('index')
    
    result = {
        'date_range': (start_date, end_date),
        'total_inflow': total_inflow, 
        'total_income': total_inflow, 
        'self_transfer_income': self_transfer_income, 
        'external_income': external_income, 
        'total_expense': total_expense,
        'net_flow': total_inflow - total_expense,
        'salary_income': salary_income,
        'non_salary_income': non_salary_income,
        'salary_ratio': salary_income / total_inflow if total_inflow > 0 else 0,
        'salary_details': salary_details, 
        'yearly_stats': yearly_stats,
        'monthly_stats': monthly_stats,
        'transaction_count': len(df)
    }
    
    logger.info(f'工资性收入: {utils.format_currency(salary_income)}({len(salary_details)}笔)')
    return result


def analyze_fund_flow(df: pd.DataFrame) -> Dict:
    """
    分析资金去向
    
    Args:
        df: 交易DataFrame
        
    Returns:
        资金去向分析字典
    """
    logger.info('正在分析资金去向...')
    
    # 流向第三方支付平台的金额（支出）
    third_party_expense = 0.0
    third_party_expense_transactions = []
    
    # 来自第三方支付平台的金额（收入）
    third_party_income = 0.0
    third_party_income_transactions = []
    
    for _, row in df.iterrows():
        is_third_party = utils.contains_keywords(row['description'], config.THIRD_PARTY_PAYMENT_KEYWORDS) or \
                        utils.contains_keywords(row['counterparty'], config.THIRD_PARTY_PAYMENT_KEYWORDS)
        
        if is_third_party:
            if row['expense'] > 0:
                third_party_expense += row['expense']
                third_party_expense_transactions.append({
                    '日期': row['date'],
                    '金额': row['expense'],
                    '摘要': row.get('description', ''),
                    '对手方': row.get('counterparty', ''),
                    '类型': '支出'
                })
            if row['income'] > 0:
                third_party_income += row['income']
                third_party_income_transactions.append({
                    '日期': row['date'],
                    '金额': row['income'],
                    '摘要': row.get('description', ''),
                    '对手方': row.get('counterparty', ''),
                    '类型': '收入'
                })
    
    # 按对手方统计
    counterparty_stats = {}
    for _, row in df.iterrows():
        if row['counterparty']:
            counterparty = row['counterparty']
            if counterparty not in counterparty_stats:
                counterparty_stats[counterparty] = {
                    'income': 0.0,
                    'expense': 0.0,
                    'count': 0
                }
            counterparty_stats[counterparty]['income'] += row['income']
            counterparty_stats[counterparty]['expense'] += row['expense']
            counterparty_stats[counterparty]['count'] += 1
    
    # 排序找出前10大对手方
    top_counterparties = sorted(
        counterparty_stats.items(),
        key=lambda x: x[1]['expense'] + x[1]['income'],
        reverse=True
    )[:10]
    
    result = {
        # 第三方支付支出
        'third_party_amount': third_party_expense,  # 保持兼容
        'third_party_expense': third_party_expense,
        'third_party_expense_count': len(third_party_expense_transactions),
        'third_party_expense_transactions': third_party_expense_transactions,
        # 第三方支付收入
        'third_party_income': third_party_income,
        'third_party_income_count': len(third_party_income_transactions),
        'third_party_income_transactions': third_party_income_transactions,
        # 合并明细（收入+支出）
        'third_party_transactions': third_party_expense_transactions + third_party_income_transactions,
        'third_party_count': len(third_party_expense_transactions) + len(third_party_income_transactions),
        # 占比
        'third_party_ratio': third_party_expense / df['expense'].sum() if df['expense'].sum() > 0 else 0,
        'counterparty_stats': counterparty_stats,
        'top_counterparties': top_counterparties
    }
    
    logger.info(f'第三方支付: 收入{utils.format_currency(third_party_income)}({len(third_party_income_transactions)}笔), '
                f'支出{utils.format_currency(third_party_expense)}({len(third_party_expense_transactions)}笔)')
    
    return result


def analyze_wealth_management(df: pd.DataFrame, entity_name: str = None) -> Dict:
    """
    分析理财产品交易（增强版 - 深度清洗空转资金）
    
    识别银行卡中的理财产品操作，包括：
    - 银行理财产品购买/赎回
    - 基金申购/赎回
    - 证券转账（银证互转）
    - 定期存款/大额存单
    - 自我转账（账户间划转，含隐形关联账户）
    - 贷款发放/还款（不算作收入/支出）
    - 退款/冲正（不算作收入）
    
    Args:
        df: 交易DataFrame
        entity_name: 实体名称（用于识别自我转账）
        
    Returns:
        理财交易分析字典
    """
    logger.info('正在分析理财产品交易（增强版 - 深度清洗）...')
    
    # 1. 获取该人员名下的所有账号集合（用于识别隐形自我转账）
    import account_analyzer
    my_accounts = set()
    try:
        acct_info = account_analyzer.classify_accounts(df)
        my_accounts.update(acct_info['physical_cards'])
        my_accounts.update(acct_info['virtual_accounts'])
        my_accounts.update(acct_info['wealth_accounts'])
    except Exception as e:
        logger.warning(f"获取账户列表失败: {e}")

    # 理财购买（支出）
    wealth_purchase = 0.0
    wealth_purchase_transactions = []
    
    # 理财赎回（收入）
    wealth_redemption = 0.0
    wealth_redemption_transactions = []
    
    # 自我转账统计
    self_transfer_income = 0.0
    self_transfer_expense = 0.0
    self_transfer_transactions = []
    
    # 理财收益（利息/分红等，区别于本金赎回）
    wealth_income = 0.0
    wealth_income_transactions = []

    # 贷款发放（资金流入，非收入）
    loan_inflow = 0.0
    loan_transactions = []
    
    # 退款/冲正（资金流入，非收入）
    refund_inflow = 0.0
    refund_transactions = []
    
    # 分类统计
    category_stats = {
        '银行理财': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
        '基金': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
        '定期存款': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
        '证券': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
        '其他理财': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
        '疑似理财': {'购入': 0.0, '赎回': 0.0, '笔数': 0},
    }
    
    # 年度统计
    yearly_stats = {}
    
    import re
    # 理财产品代码特征 (如 D3109023..., FSG...)
    product_code_pattern = re.compile(r'[A-Za-z0-9]{8,}') 
    
    for _, row in df.iterrows():
        description = str(row.get('description', ''))
        counterparty = str(row.get('counterparty', '')).strip()
        income = row.get('income', 0) or 0
        expense = row.get('expense', 0) or 0
        year = row['date'].year if pd.notna(row['date']) else 0
        
        # 初始化年度统计
        if year and year not in yearly_stats:
            yearly_stats[year] = {
                '购入': 0.0, '赎回': 0.0, '收益': 0.0,
                '自我转入': 0.0, '自我转出': 0.0
            }
        
        # ----------------------------------------------------
        # 步骤 1: 识别贷款发放和退款 (这些绝对不是收入)
        # ----------------------------------------------------
        if income > 0:
            # 贷款
            if utils.contains_keywords(description, ['放款', '贷款发放', '个贷发放']):
                loan_inflow += income
                loan_transactions.append(row.to_dict())
                continue
            
            # 退款/冲正
            if utils.contains_keywords(description, ['退款', '冲正', '退回', '撤销']):
                refund_inflow += income
                refund_transactions.append(row.to_dict())
                continue

        # ----------------------------------------------------
        # 步骤 2: 深度识别自我转账 (同名 or 账号在名下列表中)
        # ----------------------------------------------------
        is_self_transfer = False
        
        # A. 显式同名
        if entity_name and entity_name in counterparty:
            is_self_transfer = True
        
        # B. 账号匹配 (对手方账号是否在我的账号列表中)
        # 这里需要从对手方/摘要中提取账号，这比较难，但如果我们直接有counterparty_account列最好
        # 目前主要看 counterparty 字段本身是否就是账号
        elif counterparty in my_accounts:
            is_self_transfer = True
            
        # C. 模糊特征 "本人", "户主"
        elif utils.contains_keywords(counterparty + description, ['本人', '户主', '卡卡转账', '自行转账']):
            is_self_transfer_likely = True
            # 二次确认：如果是他人名字叫“本人”... 不太可能，直接算吧
            is_self_transfer = True
            
        if is_self_transfer:
            if income > 0:
                self_transfer_income += income
                if year: yearly_stats[year]['自我转入'] += income
            if expense > 0:
                self_transfer_expense += expense
                if year: yearly_stats[year]['自我转出'] += expense
                
            self_transfer_transactions.append({
                '日期': row['date'], '收入': income, '支出': expense,
                '摘要': description, '对手方': counterparty,
                '备注': '识别为自我转账'
            })
            continue
        
        # ----------------------------------------------------
        # 步骤 3: 深度识别理财/基金 (包含隐蔽赎回)
        # ----------------------------------------------------
        is_wealth = False
        wealth_type = '其他理财'
        confidence = 'low' # low, high
        
        # A. 关键词匹配 (原有逻辑)
        if utils.contains_keywords(description + counterparty, config.WEALTH_MANAGEMENT_KEYWORDS):
            is_wealth = True
            confidence = 'high'
            
        # B. 隐蔽赎回特征 (对手方为空/-，且摘要包含代码)
        if not is_wealth and income > 0:
            if counterparty in ['', '-', 'nan', 'NaN']:
                # 检查摘要是否包含长数字/字母代码 (理财产品编号)
                if product_code_pattern.search(description) or \
                   utils.contains_keywords(description, ['到期', '赎回', '结清', '自动', '归还']):
                    is_wealth = True
                    confidence = 'medium'
                    wealth_type = '定期存款' if '定期' in description else '银行理财'
            
            # C. 账号属性特征 (隐形理财户)
            # 如果本方账号本身就是理财专属账号，且对手方为空，那么这笔进账一定是理财到期
            my_account_num = str(row.get('本方账号', row.get('account_number', '')))
            if not is_wealth and counterparty in ['', '-', 'nan', 'NaN']:
                 if my_account_num in acct_info.get('wealth_accounts', []):
                     is_wealth = True
                     wealth_type = '银行理财'
                     confidence = 'high'
            
            # D. 双空特征 (对手方空 + 摘要空 + 大额) -> 疑似理财
            # 这种情况通常是银行系统自动入账，非人工转账，大概率是理财/利息
            if not is_wealth and income > 10000 and counterparty in ['', '-', 'nan', 'NaN'] and description in ['', 'nan', 'NaN']:
                 is_wealth = True
                 wealth_type = '疑似理财'
                 confidence = 'medium'
                    
        if not is_wealth:
            continue
            
        # 细化类型
        if utils.contains_keywords(description + counterparty, ['基金', '申购', '赎回', '定投']):
            wealth_type = '基金'
        elif utils.contains_keywords(description + counterparty, ['定期', '定存', '大额存单', '存款', '通知存款']):
            wealth_type = '定期存款'
        elif utils.contains_keywords(description + counterparty, ['证券', '银证', '股票']):
            wealth_type = '证券'
        elif utils.contains_keywords(description + counterparty, ['理财', '理财产品', '资管', '资产管理']):
            wealth_type = '银行理财'
        
        # 判断是否为收益（而非本金赎回）
        is_income_yield = utils.contains_keywords(description, ['利息', '结息', '分红', '收益', '红利'])
        
        # 记录
        if expense > 0:
            # 购买
            wealth_purchase += expense
            wealth_purchase_transactions.append({
                '日期': row['date'], '金额': expense,
                '摘要': description, '对手方': counterparty,
                '类型': wealth_type, '判断依据': f'支出+{wealth_type}'
            })
            category_stats[wealth_type]['购入'] += expense
            category_stats[wealth_type]['笔数'] += 1
            if year: yearly_stats[year]['购入'] += expense
                
        elif income > 0:
            if is_income_yield:
                # 纯收益
                wealth_income += income
                wealth_income_transactions.append({
                    '日期': row['date'], '金额': income,
                    '摘要': description, '对手方': counterparty,
                    '类型': '收益'
                })
                if year: yearly_stats[year]['收益'] += income
            else:
                # 赎回本金
                wealth_redemption += income
                wealth_redemption_transactions.append({
                    '日期': row['date'], '金额': income,
                    '摘要': description, '对手方': counterparty,
                    '类型': wealth_type, '判断依据': f'收入+{wealth_type}' if confidence == 'high' else '隐蔽赎回特征'
                })
                category_stats[wealth_type]['赎回'] += income
                category_stats[wealth_type]['笔数'] += 1
                if year: yearly_stats[year]['赎回'] += income
    
    # 计算理财净额
    net_wealth_flow = wealth_purchase - wealth_redemption
    real_wealth_profit = wealth_redemption + wealth_income - wealth_purchase
    
    # 逻辑修正：如果算出巨额正收益（例如投入1000万，赎回4000万），通常是因为数据缺失导致的“无本之利”
    # 在这种情况下，我们不能草率地宣称某人赚了3000万，而应该认为“本金投入记录缺失”
    # 修正策略：如果收益率 > 20% 且 绝对收益 > 10万，则强制修正
    if wealth_purchase > 0:
        yield_rate = real_wealth_profit / wealth_purchase
        if yield_rate > 0.5 and real_wealth_profit > 100000:
            logger.warning(f'检测到异常的理财高收益(投入{wealth_purchase}, 产出{wealth_redemption+wealth_income})，可能是理财购买记录(如自我转账)未被识别')
            # 悲观修正：只计算显式的利息/收益作为盈利，本金赎回部分假设收支平衡
            real_wealth_profit = wealth_income 
    elif wealth_redemption > 100000:
        # 如果根本没有购买记录，却有大额赎回，说明购买记录完全缺失
        real_wealth_profit = wealth_income
    
    result = {
        'wealth_purchase': wealth_purchase,
        'wealth_purchase_count': len(wealth_purchase_transactions),
        'wealth_purchase_transactions': wealth_purchase_transactions,
        'wealth_redemption': wealth_redemption,
        'wealth_redemption_count': len(wealth_redemption_transactions),
        'wealth_redemption_transactions': wealth_redemption_transactions,
        'wealth_income': wealth_income,
        'wealth_income_count': len(wealth_income_transactions),
        'wealth_income_transactions': wealth_income_transactions,
        'net_wealth_flow': net_wealth_flow,
        'real_wealth_profit': real_wealth_profit,
        'self_transfer_income': self_transfer_income,
        'self_transfer_expense': self_transfer_expense,
        'self_transfer_count': len(self_transfer_transactions),
        'self_transfer_transactions': self_transfer_transactions,
        # 新增
        'loan_inflow': loan_inflow,
        'refund_inflow': refund_inflow,
        
        'category_stats': category_stats,
        'yearly_stats': yearly_stats,
        'total_transactions': len(wealth_purchase_transactions) + len(wealth_redemption_transactions) + len(wealth_income_transactions)
    }
    
    if result['total_transactions'] > 0:
        logger.info(f'理财产品: 购买{utils.format_currency(wealth_purchase)}, 赎回{utils.format_currency(wealth_redemption)}')
        logger.info(f'隐性剔除: 自我转账{utils.format_currency(self_transfer_income)}, 贷款{utils.format_currency(loan_inflow)}, 退款{utils.format_currency(refund_inflow)}')
    
    return result

def generate_profile_report(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    生成资金画像报告
    
    Args:
        df: 交易DataFrame
        entity_name: 实体名称(人员或公司)
        
    Returns:
        完整的资金画像报告
    """
    logger.info(f'正在为 {entity_name} 生成资金画像...')
    
    if df.empty:
        logger.warning(f'{entity_name} 无交易数据')
        return {
            'entity_name': entity_name,
            'has_data': False
        }
    
    # 收支结构
    income_structure = calculate_income_structure(df, entity_name=entity_name)
    
    # 资金去向
    fund_flow = analyze_fund_flow(df)
    
    # 理财产品分析（传入entity_name以识别自我转账）
    wealth_management = analyze_wealth_management(df, entity_name=entity_name)
    
    # 大额现金
    large_cash = extract_large_cash(df)
    
    # 交易分类
    categories = categorize_transactions(df)
    
    # 计算真实收入/支出
    # 真实收入 = 总收入 - 自我转账 - 理财赎回 - 理财收益 - 贷款发放 - 退款
    # 注意：理财收益虽然是赚的，但为了反映“非投资性”的真实经济来源（如工资、受贿等），通常也单列。
    # 用户之前的定义似乎是把理财收益也排除了，这里保持一致。
    real_income = (income_structure['total_income'] 
                  - wealth_management['self_transfer_income'] 
                  - wealth_management['wealth_redemption'] 
                  - wealth_management['wealth_income']
                  - wealth_management['loan_inflow']
                  - wealth_management['refund_inflow'])
                  
    real_expense = (income_structure['total_expense'] 
                   - wealth_management['self_transfer_expense'] 
                   - wealth_management['wealth_purchase'])
    
    profile = {
        'entity_name': entity_name,
        'has_data': True,
        'income_structure': income_structure,
        'fund_flow': fund_flow,
        'wealth_management': wealth_management,  # 新增
        'large_cash': large_cash,
        'categories': categories,
        'summary': {
            'total_income': income_structure['total_income'],
            'total_expense': income_structure['total_expense'],
            'net_flow': income_structure['net_flow'],
            'real_income': real_income,
            'real_expense': real_expense,
            'salary_ratio': income_structure['salary_ratio'],
            'third_party_ratio': fund_flow['third_party_ratio'],
            'large_cash_count': len(large_cash),
            'wealth_transactions': wealth_management['total_transactions'],
            'transaction_count': len(df),
            'date_range': income_structure['date_range']
        }
    }
    
    logger.info(f'{entity_name} 资金画像生成完成')
    
    return profile

def extract_large_cash(df: pd.DataFrame, threshold: float = None) -> List[Dict]:
    """
    提取大额现金存取记录
    
    Args:
        df: 交易DataFrame
        threshold: 金额阈值,默认使用配置
        
    Returns:
        大额现金记录列表
    """
    if threshold is None:
        threshold = config.LARGE_CASH_THRESHOLD
    
    logger.info(f'正在筛查大额现金(阈值: {utils.format_currency(threshold)})...')
    
    large_cash_records = []
    
    for _, row in df.iterrows():
        # 检查是否为现金交易
        is_cash = utils.contains_keywords(row['description'], config.CASH_KEYWORDS)
        
        if is_cash:
            amount = max(row['income'], row['expense'])
            if amount >= threshold:
                record = row.to_dict()
                record['cash_type'] = 'deposit' if row['income'] > 0 else 'withdrawal'
                record['amount'] = amount
                
                # 判断风险等级
                if amount >= config.CASH_THRESHOLDS['level_4']:
                    record['risk_level'] = 'high'
                elif amount >= config.CASH_THRESHOLDS['level_3']:
                    record['risk_level'] = 'medium'
                else:
                    record['risk_level'] = 'low'
                
                large_cash_records.append(record)
    
    logger.info(f'发现 {len(large_cash_records)} 笔大额现金交易')
    
    return large_cash_records


def categorize_transactions(df: pd.DataFrame) -> Dict[str, List[Dict]]:
    """
    交易分类
    
    Args:
        df: 交易DataFrame
        
    Returns:
        分类后的交易字典
    """
    categories = {
        'salary': [],          # 工资性收入
        'non_salary': [],      # 非工资性收入
        'third_party': [],     # 第三方支付
        'cash': [],            # 现金交易
        'large_amount': [],    # 大额交易
        'property': [],        # 疑似购房
        'vehicle': [],         # 疑似购车
        'other': []            # 其他
    }
    
    for _, row in df.iterrows():
        record = row.to_dict()
        
        # 收入分类
        if row['income'] > 0:
            if utils.contains_keywords(row['description'], config.SALARY_KEYWORDS):
                categories['salary'].append(record)
            else:
                categories['non_salary'].append(record)
        
        # 支出分类
        if row['expense'] > 0:
            # 第三方支付
            if utils.contains_keywords(row['description'], config.THIRD_PARTY_PAYMENT_KEYWORDS):
                categories['third_party'].append(record)
            
            # 疑似购房
            if utils.contains_keywords(row['description'], config.PROPERTY_KEYWORDS):
                if row['expense'] >= config.PROPERTY_THRESHOLD:
                    categories['property'].append(record)
            
            # 疑似购车
            if utils.contains_keywords(row['description'], config.VEHICLE_KEYWORDS):
                if row['expense'] >= config.VEHICLE_THRESHOLD:
                    categories['vehicle'].append(record)
        
        # 现金交易
        if utils.contains_keywords(row['description'], config.CASH_KEYWORDS):
            categories['cash'].append(record)
        
        # 大额交易
        amount = max(row['income'], row['expense'])
        if amount >= config.LARGE_CASH_THRESHOLD:
            categories['large_amount'].append(record)
    
    return categories


def generate_profile_report(df: pd.DataFrame, entity_name: str) -> Dict:
    """
    生成资金画像报告
    
    Args:
        df: 交易DataFrame
        entity_name: 实体名称(人员或公司)
        
    Returns:
        完整的资金画像报告
    """
    logger.info(f'正在为 {entity_name} 生成资金画像...')
    
    if df.empty:
        logger.warning(f'{entity_name} 无交易数据')
        return {
            'entity_name': entity_name,
            'has_data': False
        }
    
    # 收支结构
    income_structure = calculate_income_structure(df, entity_name=entity_name)
    
    # 资金去向
    fund_flow = analyze_fund_flow(df)
    
    # 理财产品分析（传入entity_name以识别自我转账）
    wealth_management = analyze_wealth_management(df, entity_name=entity_name)
    
    # 大额现金
    large_cash = extract_large_cash(df)
    
    # 交易分类
    categories = categorize_transactions(df)
    
    profile = {
        'entity_name': entity_name,
        'has_data': True,
        'income_structure': income_structure,
        'fund_flow': fund_flow,
        'wealth_management': wealth_management,  # 新增
        'large_cash': large_cash,
        'categories': categories,
        'summary': {
            'total_income': income_structure['total_income'],
            'total_expense': income_structure['total_expense'],
            'net_flow': income_structure['net_flow'],
            'real_income': income_structure['total_income'] - wealth_management['self_transfer_income'] - wealth_management['wealth_redemption'] - wealth_management['wealth_income'],
            'real_expense': income_structure['total_expense'] - wealth_management['self_transfer_expense'] - wealth_management['wealth_purchase'],
            'salary_ratio': income_structure['salary_ratio'],
            'third_party_ratio': fund_flow['third_party_ratio'],
            'large_cash_count': len(large_cash),
            'wealth_transactions': wealth_management['total_transactions'],
            'transaction_count': len(df),
            'date_range': income_structure['date_range']
        }
    }
    
    logger.info(f'{entity_name} 资金画像生成完成')
    
    return profile
