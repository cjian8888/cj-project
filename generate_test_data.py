#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据生成器 - 资金穿透与关联排查系统
生成模拟数据用于功能验证
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd


def generate_test_clue_txt(output_dir: str = '.'):
    """
    生成测试用的线索文本文件(简化版)
    注: 实际使用时请准备PDF格式的线索文件
    """
    print('正在生成线索文件...')
    
    txt_path = os.path.join(output_dir, '线索.txt')
    
    text_content = """举报信

举报人反映:
张伟(某局副局长)疑似收受贿赂,与华信科技有限公司存在利益往来。
李明(某局财务科科长)多次大额现金交易,疑似隐瞒资产。
王芳(某局采购科科长)名下有多处房产,与申报不符。

涉案公司:
华信科技有限公司
天宏投资有限公司

请组织调查核实。
"""
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    print(f'✓ 生成完成: {txt_path}')
    print('  注: 由于未安装reportlab,生成txt格式。系统会尝试从txt文件提取线索。')


def generate_test_transaction_excel(person_name: str, 
                                    output_dir: str = '.',
                                    has_suspicion: bool = False):
    """
    生成测试用的银行流水Excel
    
    Args:
        person_name: 人员名称
        output_dir: 输出目录
        has_suspicion: 是否包含疑点交易
    """
    print(f'正在生成 {person_name} 的流水数据...')
    
    transactions = []
    start_date = datetime(2023, 1, 1)
    current_balance = 50000.0
    
    # 生成一年的交易数据
    for i in range(200):
        transaction_date = start_date + timedelta(days=random.randint(1, 5))
        start_date = transaction_date
        
        # 随机生成交易类型
        transaction_type = random.choice(['salary', 'expense', 'third_party', 'cash', 'other'])
        
        income = 0.0
        expense = 0.0
        description = ''
        counterparty = ''
        
        if transaction_type == 'salary':
            # 工资收入(每月15日左右)
            if start_date.day >= 13 and start_date.day <= 17:
                income = random.uniform(8000, 12000)
                description = '工资'
                counterparty = '单位财务'
        
        elif transaction_type == 'expense':
            # 日常消费
            expense = random.uniform(50, 2000)
            description = random.choice(['超市购物', '餐饮消费', '网购', '水电费', '话费'])
            counterparty = random.choice(['商户', '淘宝', '京东', '中国移动'])
        
        elif transaction_type == 'third_party':
            # 第三方支付
            expense = random.uniform(100, 5000)
            description = '转账'
            counterparty = random.choice(['支付宝转账', '微信支付', '财付通'])
        
        elif transaction_type == 'cash':
            # 现金交易
            if random.random() < 0.5:
                income = random.uniform(1000, 20000)
                description = '现金存入'
                counterparty = 'ATM'
            else:
                expense = random.uniform(1000, 20000)
                description = '现金取款'
                counterparty = 'ATM'
        
        else:
            # 其他交易
            if random.random() < 0.3:
                income = random.uniform(500, 5000)
                description = random.choice(['转账收入', '理财收益', '退款'])
                counterparty = '个人'
            else:
                expense = random.uniform(500, 3000)
                description = random.choice(['转账支出', '还款', '缴费'])
                counterparty = '个人'
        
        # 更新余额
        current_balance += income - expense
        
        if income > 0 or expense > 0:
            transactions.append({
                '交易日期': transaction_date.strftime('%Y-%m-%d'),
                '摘要': description,
                '收入金额': income if income > 0 else '',
                '支出金额': expense if expense > 0 else '',
                '对手方': counterparty,
                '余额': current_balance
            })
    
    # 如果需要包含疑点交易
    if has_suspicion:
        # 添加可疑的固定频率收入
        for month in range(1, 13):
            suspicious_date = datetime(2023, month, 8)
            transactions.append({
                '交易日期': suspicious_date.strftime('%Y-%m-%d'),
                '摘要': '转账收入',
                '收入金额': 5000.0,
                '支出金额': '',
                '对手方': '个人',
                '余额': current_balance
            })
            current_balance += 5000
        
        # 添加大额现金取款
        cash_date = datetime(2023, 6, 15, 14, 30)
        transactions.append({
            '交易日期': cash_date.strftime('%Y-%m-%d %H:%M'),
            '摘要': '柜台取现',
            '收入金额': '',
            '支出金额': 80000.0,
            '对手方': '柜台',
            '余额': current_balance - 80000
        })
        current_balance -= 80000
        
        # 添加疑似购房支出
        property_date = datetime(2023, 9, 10)
        transactions.append({
            '交易日期': property_date.strftime('%Y-%m-%d'),
            '摘要': '购房首付款',
            '收入金额': '',
            '支出金额': 500000.0,
            '对手方': '某房地产开发有限公司',
            '余额': current_balance - 500000
        })
        current_balance -= 500000
    
    # 排序
    df = pd.DataFrame(transactions)
    df['日期排序'] = pd.to_datetime(df['交易日期'], format='mixed')
    df = df.sort_values('日期排序').drop('日期排序', axis=1)
    df = df.reset_index(drop=True)
    
    # 保存Excel
    excel_path = os.path.join(output_dir, f'流水_{person_name}.xlsx')
    df.to_excel(excel_path, index=False)
    
    print(f'✓ 生成完成: {excel_path} ({len(df)} 笔交易)')


def generate_test_company_transaction_excel(company_name: str,
                                            output_dir: str = '.'):
    """
    生成测试用的公司流水Excel
    """
    print(f'正在生成 {company_name} 的流水数据...')
    
    transactions = []
    start_date = datetime(2023, 1, 1)
    current_balance = 1000000.0
    
    for i in range(150):
        transaction_date = start_date + timedelta(days=random.randint(1, 7))
        start_date = transaction_date
        
        income = 0.0
        expense = 0.0
        
        # 公司交易特征
        if random.random() < 0.4:
            # 收入(项目款、销售款)
            income = random.uniform(10000, 500000)
            description = random.choice(['项目款', '销售收入', '服务费'])
            counterparty = '客户公司'
        else:
            # 支出
            expense = random.uniform(5000, 200000)
            description = random.choice(['采购款', '工资', '办公费用', '税费', '现金取款'])
            counterparty = random.choice(['供应商', '个人', '税务局', 'ATM'])
        
        current_balance += income - expense
        
        transactions.append({
            '交易日期': transaction_date.strftime('%Y-%m-%d'),
            '摘要': description,
            '收入金额': income if income > 0 else '',
            '支出金额': expense if expense > 0 else '',
            '对手方': counterparty,
            '余额': current_balance
        })
    
    # 添加大额现金取款(疑点)
    cash_date = datetime(2023, 6, 15, 10, 0)
    transactions.append({
        '交易日期': cash_date.strftime('%Y-%m-%d %H:%M'),
        '摘要': '柜台取现',
        '收入金额': '',
        '支出金额': 85000.0,
        '对手方': '柜台',
        '余额': current_balance - 85000
    })
    
    df = pd.DataFrame(transactions)
    df['日期排序'] = pd.to_datetime(df['交易日期'], format='mixed')
    df = df.sort_values('日期排序').drop('日期排序', axis=1)
    df = df.reset_index(drop=True)
    
    excel_path = os.path.join(output_dir, f'流水_{company_name}.xlsx')
    df.to_excel(excel_path, index=False)
    
    print(f'✓ 生成完成: {excel_path} ({len(df)} 笔交易)')


def generate_all_test_data(output_dir: str = '.'):
    """
    生成完整的测试数据集
    """
    print('=' * 60)
    print('开始生成测试数据')
    print('=' * 60)
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. 生成线索文件
    generate_test_clue_txt(output_dir)
    
    # 2. 生成人员流水(包含疑点)
    generate_test_transaction_excel('张伟', output_dir, has_suspicion=True)
    
    # 3. 生成人员流水(包含疑点)
    generate_test_transaction_excel('李明', output_dir, has_suspicion=True)
    
    # 4. 生成人员流水(正常)
    generate_test_transaction_excel('王芳', output_dir, has_suspicion=False)
    
    # 5. 生成公司流水
    generate_test_company_transaction_excel('华信科技有限公司', output_dir)
    
    # 6. 生成公司流水
    generate_test_company_transaction_excel('天宏投资有限公司', output_dir)
    
    print('')
    print('=' * 60)
    print('测试数据生成完成!')
    print('=' * 60)
    print(f'输出目录: {os.path.abspath(output_dir)}')
    print('')
    print('文件列表:')
    for filename in os.listdir(output_dir):
        if filename.endswith(('.xlsx', '.txt', '.pdf')):
            print(f'  - {filename}')


if __name__ == '__main__':
    import sys
    output_directory = sys.argv[1] if len(sys.argv) > 1 else './test_data'
    generate_all_test_data(output_directory)
