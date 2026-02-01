#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资金平衡全要素模型 - 数据清洗标签化模块

功能：
1. 为每笔流水打上五种标签之一：
   - I_reg（经常性收入）
   - E_reg（经常性支出）
   - C（资本性流转）
   - F（融资性往来）
   - G（非经营性损益）

2. 为标签化数据创建专门的字段

3. 生成详细的标签统计
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import json

class TransactionLabeler:
    """交易标签化器"""
    
    def __init__(self):
        # 定义各类型的关键词和规则
        self._init_keywords()
    
    def _init_keywords(self):
        """初始化关键词规则"""
        
        # I_reg（经常性收入）
        self.I_reg_keywords = {
            'salary': ['工资', '薪金', '奖金', '绩效', '年终奖', '十三薪', '过节费', '高温补贴', '交通补贴',
                       '代发工资', '代发奖金', '工资发放', '薪金发放', '基本工资', '岗位工资', '技能工资', '绩效工资'],
            'social': ['公积金', '社保', '社保局', '公积金中心'],
            'tax': ['税务局', '财政局', '税务局'],
            'rent': ['租金', '房租', '房费'],
            'reimburse': ['报销', '退款', '差旅费'],
            'stake': ['分红', '股息', '红利']
        }
        
        # E_reg（经常性支出）
        self.E_reg_keywords = {
            'daily': ['消费', '超市', '餐饮', '购物', '交通', '旅游', '娱乐', '美团', '支付宝', '微信', '京东'],
            'life': ['水电', '煤气', '物业', '供暖', '宽带', '话费', '网费'],
            'insurance': ['保费', '保险', '人寿保险', '财产保险'],
            'education': ['教育', '培训', '学费', '幼儿园', '学校', '课外班'],
            'support': ['赡养', '抚养', '抚养费', '赡养费']
        }
        
        # C（资本性流转）
        self.C_keywords = {
            'financial': ['理财', '基金', '证券', '期货', '外汇', '投资', '股票', '债券', '定存', '大额存单', '存单'],
            'asset': ['购房', '买车', '购车', '房产', '不动产', '装修', '家电', '家具', '4S店', '汽车服务'],
            'deposit': ['存入', '开户', '活转定', '定转活']
        }
        
        # F（融资性往来）
        self.F_keywords = {
            'loan_in': ['贷款', '借入', '融资', '经营贷', '经营贷'],
            'repay': ['还贷', '还款', '还本', '付息', '按揭', '分期'],
            'credit': ['信用卡', '分期', '花呗', '借呗', '微粒贷']
        }
        
        # G（非经营性损益）
        self.G_keywords = {
            'investment_profit': ['投资收益', '理财收益', '基金收益', '利息收入'],
            'accidental': ['礼金', '红包', '偶然所得', '其他收入', '劳务费']
        }
    
    def label_transactions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        为交易数据打标签
        
        Args:
            df: 交易 DataFrame，必须包含以下列：
                - date
                - direction (income/expense)
                - amount
                - description
                - counterparty
        
        Returns:
            添加了标签列的 DataFrame
        """
        df = df.copy()
        
        # 初始化标签列
        df['transaction_label'] = None
        df['label_code'] = None  # I_reg, E_reg, C, F, G
        df['label_confidence'] = None  # 0-1，1为确定
        df['is_regular'] = None  # 是否为经常性交易
        
        print(f"开始标签化 {len(df)} 笔交易...")
        
        # 遍历每一笔交易
        for idx, row in df.iterrows():
            label_result = self._classify_transaction(row)
            
            df.at[idx, 'transaction_label'] = label_result['label']
            df.at[idx, 'label_code'] = label_result['code']
            df.at[idx, 'label_confidence'] = label_result['confidence']
            df.at[idx, 'is_regular'] = label_result['is_regular']
        
        print(f"✅ 标签化完成")
        return df
    
    def _classify_transaction(self, row: pd.Series) -> Dict[str, Any]:
        """分类单笔交易"""
        
        direction = row.get('direction', '')
        desc = str(row.get('description', '')).lower()
        cp = str(row.get('counterparty', '')).lower()
        amount = row.get('amount', 0)
        
        # 优先判断（按优先级）
        # 1. 融资性往来 (F)
        if self._is_financial_transaction(desc, cp, direction, amount):
            return {
                'label': '融资性往来',
                'code': 'F',
                'confidence': 0.9,
                'is_regular': False
            }
        
        # 2. 资本性流转 (C)
        if self._is_capital_transaction(desc, cp, direction, amount):
            return {
                'label': '资本性流转',
                'code': 'C',
                'confidence': 0.85,
                'is_regular': False
            }
        
        # 3. 非经营性损益 (G)
        if self._is_profit_loss_transaction(desc, cp, direction):
            return {
                'label': '非经营性损益',
                'code': 'G',
                'confidence': 0.7,
                'is_regular': False
            }
        
        # 4. 经常性收入 (I_reg) 或 经常性支出 (E_reg)
        if direction == 'income':
            return {
                'label': '经常性收入',
                'code': 'I_reg',
                'confidence': 0.95,
                'is_regular': True
            }
        else:  # expense
            # 检查是否为经常性支出
            if self._is_regular_expense(desc, cp, amount):
                return {
                    'label': '经常性支出',
                    'code': 'E_reg',
                    'confidence': 0.95,
                    'is_regular': True
                }
            else:
                return {
                    'label': '其他支出',
                    'code': 'E_reg',  # 默认为经常性支出
                    'confidence': 0.6,
                    'is_regular': False
                }
    
    def _is_financial_transaction(self, desc: str, cp: str, direction: str, amount: float) -> bool:
        """判断是否为融资性交易 (F)"""
        
        # 关键词匹配
        financial_keywords = []
        for category, keywords in self.F_keywords.items():
            for kw in keywords:
                if kw in desc or kw in cp:
                    financial_keywords.append((category, kw))
        
        if not financial_keywords:
            return False
        
        # 优先级判断
        # 1. 大额贷款/还款
        if amount > 500000:  # >50万
            return True
        
        # 2. 信用卡相关
        if any(kw in desc for kw in ['信用卡', '分期', '花呗', '借呗', '微粒贷']):
            return True
        
        # 3. 明确的贷款/还款
        if any(kw in desc for kw in ['贷款', '借入', '还贷', '还款', '还本', '付息', '按揭']):
            return True
        
        return False
    
    def _is_capital_transaction(self, desc: str, cp: str, direction: str, amount: float) -> bool:
        """判断是否为资本性交易 (C)"""
        
        capital_keywords = []
        for category, keywords in self.C_keywords.items():
            for kw in keywords:
                if kw in desc or kw in cp:
                    capital_keywords.append((category, kw))
        
        if not capital_keywords:
            return False
        
        # 大额交易更可能是资本性的
        if amount > 100000:  # >10万
            return True
        
        # 明确的资产购置
        asset_keywords = ['购房', '买车', '购车', '房产', '装修', '家电', '4S店', '汽车服务']
        if any(kw in desc for kw in asset_keywords):
            return True
        
        # 明确的理财
        financial_keywords = ['理财', '基金', '证券', '期货', '外汇', '投资', '股票', '债券', '定存', '大额存单', '存单']
        if any(kw in desc for kw in financial_keywords):
            return True
        
        return False
    
    def _is_profit_loss_transaction(self, desc: str, cp: str, direction: str) -> bool:
        """判断是否为非经营性损益 (G)"""
        
        if direction != 'income':
            return False  # 只有收入才是损益
        
        # 投资收益
        profit_keywords = ['投资收益', '理财收益', '基金收益', '利息收入', '分红', '股息', '红利']
        if any(kw in desc for kw in profit_keywords):
            return True
        
        # 偶然所得
        accidental_keywords = ['礼金', '红包', '偶然所得', '其他收入', '劳务费']
        if any(kw in desc for kw in accidental_keywords):
            return True
        
        return False
    
    def _is_regular_expense(self, desc: str, cp: str, amount: float) -> bool:
        """判断是否为经常性支出"""
        
        # 小额交易更可能是经常性的
        if amount > 50000:  # >5万
            return False
        
        # 日常消费
        daily_keywords = ['消费', '超市', '餐饮', '购物', '交通', '旅游', '娱乐', '美团', '支付宝', '微信', '京东']
        if any(kw in desc for kw in daily_keywords):
            return True
        
        # 生活缴费
        life_keywords = ['水电', '煤气', '物业', '供暖', '宽带', '话费', '网费', '保费', '保险']
        if any(kw in desc for kw in life_keywords):
            return True
        
        # 教育、赡养
        support_keywords = ['教育', '培训', '学费', '幼儿园', '学校', '课外班', '赡养', '抚养']
        if any(kw in desc for kw in support_keywords):
            return True
        
        return False
    
    def generate_label_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """生成标签统计"""
        
        stats = {
            'label_distribution': df['label_code'].value_counts().to_dict(),
            'label_amount_distribution': {},
            'regular_transactions': len(df[df['is_regular'] == True]),
            'capital_transactions': len(df[df['label_code'] == 'C']),
            'financial_transactions': len(df[df['label_code'] == 'F'])
        }
        
        # 各标签的金额分布
        for code in ['I_reg', 'E_reg', 'C', 'F', 'G']:
            code_df = df[df['label_code'] == code]
            direction = 'income' if code == 'I_reg' or code == 'G' else 'expense'
            
            if direction == 'income':
                total = code_df[code_df['direction'] == 'income']['amount'].sum()
            else:
                total = code_df[code_df['direction'] == 'expense']['amount'].sum()
            
            stats['label_amount_distribution'][code] = {
                'total': total,
                'count': len(code_df)
            }
        
        return stats


# ============ 主程序 ============
if __name__ == '__main__':
    print("=" * 80)
    print("🏷️ 交易标签化测试")
    print("=" * 80)
    print()
    
    # 创建测试数据
    test_data = [
        {'date': '2024-01-01', 'direction': 'income', 'amount': 500000, 'description': '工资发放', 'counterparty': '上海航天'},
        {'date': '2024-01-02', 'direction': 'income', 'amount': 50000, 'description': '年终奖', 'counterparty': '上海航天'},
        {'date': '2024-01-03', 'direction': 'expense', 'amount': 500, 'description': '超市消费', 'counterparty': '沃尔玛'},
        {'date': '2024-01-04', 'direction': 'expense', 'amount': 100000, 'description': '购车', 'counterparty': '4S店'},
        {'date': '2024-01-05', 'direction': 'income', 'amount': 5000000, 'description': '经营贷款', 'counterparty': '银行'},
        {'date': '2024-01-06', 'direction': 'expense', 'amount': 5000000, 'description': '还贷', 'counterparty': '银行'},
        {'date': '2024-01-07', 'direction': 'income', 'amount': 50000, 'description': '理财赎回', 'counterparty': '银行'},
        {'date': '2024-01-08', 'direction': 'expense', 'amount': 50000, 'description': '理财申购', 'counterparty': '银行'},
        {'date': '2024-01-09', 'direction': 'expense', 'amount': 100000, 'description': '购房首付', 'counterparty': '房产'},
        {'date': '2024-01-10', 'direction': 'income', 'amount': 10000, 'description': '投资收益', 'counterparty': '银行'},
    ]
    
    test_df = pd.DataFrame(test_data)
    
    # 标签化
    labeler = TransactionLabeler()
    labeled_df = labeler.label_transactions(test_df)
    
    # 显示结果
    print("标签化结果：")
    print("{:<10} {:<15} {:<15} {:<15} {:<10} {:<10}".format(
        'date', 'direction', 'amount', 'label_code', 'label', 'confidence'
    ))
    print("-" * 80)
    
    for _, row in labeled_df.iterrows():
        print("{:<10} {:<15} {:>12,.0f} {:<15} {:<15} {:<10}".format(
            row['date'][:10],
            row['direction'],
            row['amount'],
            row['label_code'],
            row['transaction_label'],
            f"{row['label_confidence']:.1f}"
        ))
    
    # 统计
    stats = labeler.generate_label_statistics(labeled_df)
    print("\n标签统计：")
    print("-" * 80)
    print(f"总交易数: {len(labeled_df)}")
    print(f"经常性交易: {stats['regular_transactions']} 笔")
    print(f"资本性交易: {stats['capital_transactions']} 笔")
    print(f"融资性交易: {stats['financial_transactions']} 笔")
    
    print("\n各标签金额分布：")
    for code, label_name in [('I_reg', '经常性收入'), ('E_reg', '经常性支出'), 
                                 ('C', '资本性流转'), ('F', '融资性往来'), ('G', '非经营性损益')]:
        if code in stats['label_amount_distribution']:
            dist = stats['label_amount_distribution'][code]
            direction = '收入' if code == 'I_reg' or code == 'G' else '支出'
            print(f"{label_name} ({code}): {dist['total']/10000:.2f} 万元, {dist['count']} 笔")
