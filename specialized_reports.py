#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专项报告生成器 - 穿云审计系统

【功能】
生成7个专项txt报告，每个对应一个分析维度

【报告清单】
1. 借贷行为分析报告.txt - 借贷关系检测
2. 异常收入来源分析报告.txt - 收入来源分析
3. 时序分析报告.txt - 时间序列分析
4. 资金穿透分析报告.txt - 资金流向穿透
5. 疑点检测分析报告.txt - 异常交易检测
6. 行为特征分析报告.txt - 行为画像分析
7. 资产全貌分析报告.txt - 资产统计

【数据溯源】
每条记录包含 source_file 和 source_row_index，可定位到原始Excel文件的具体行

版本: 1.1.0
日期: 2026-02-25
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
import config
import utils

logger = utils.setup_logger(__name__)


class SpecializedReportGenerator:
    """专项报告生成器"""

    def __init__(
        self, analysis_results: Dict, profiles: Dict, suspicions: Dict, output_dir: str
    ):
        """
        初始化

        Args:
            analysis_results: 完整分析结果（从缓存加载）
            profiles: 画像数据
            suspicions: 疑点检测结果
            output_dir: 输出目录
        """
        self.analysis_results = analysis_results
        self.profiles = profiles
        self.suspicions = suspicions
        self.output_dir = output_dir

        logger.info(
            f"[专项报告] 初始化完成，分析结果包含: {', '.join(list(analysis_results.keys()))}"
        )

    def generate_all_reports(self) -> List[str]:
        """
        生成所有专项txt报告

        Returns:
            生成的文件路径列表
        """
        generated_files = []

        # 创建专项报告目录
        reports_dir = os.path.join(self.output_dir, "专项报告")
        os.makedirs(reports_dir, exist_ok=True)

        # 生成7个专项报告
        report_generators = [
            ("借贷行为分析报告.txt", self._generate_loan_report),
            ("异常收入来源分析报告.txt", self._generate_income_report),
            ("时序分析报告.txt", self._generate_time_series_report),
            ("资金穿透分析报告.txt", self._generate_penetration_report),
            ("疑点检测分析报告.txt", self._generate_suspicion_report),
            ("行为特征分析报告.txt", self._generate_behavioral_report),
            ("资产全貌分析报告.txt", self._generate_asset_report),
        ]

        for filename, generator in report_generators:
            try:
                content = generator()
                if content.strip():  # 只生成非空报告
                    file_path = os.path.join(reports_dir, filename)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    generated_files.append(file_path)
                    logger.info(f"[专项报告] 已生成: {filename}")
                else:
                    logger.info(f"[专项报告] 跳过（无内容）: {filename}")
            except Exception as e:
                logger.error(f"[专项报告] 生成 {filename} 失败: {e}")

        # 生成报告目录清单
        index_file = self._generate_report_index(reports_dir, generated_files)
        if index_file:
            generated_files.append(index_file)

        logger.info(f"[专项报告] 共生成 {len(generated_files)} 个文件")
        return generated_files

    # ==================== 工具方法 ====================

    def _format_date(self, date_val) -> str:
        """格式化日期"""
        if not date_val:
            return "未知"
        date_str = str(date_val)
        if "T" in date_str:
            return date_str.split("T")[0]
        return date_str[:10] if len(date_str) > 10 else date_str

    def _add_traceability(self, lines: List, item: Dict, prefix: str = "  "):
        """添加数据溯源信息"""
        source_file = item.get("source_file", "")
        source_row = item.get("source_row_index")

        if source_file:
            lines.append(f"{prefix}📁 溯源: {source_file}")
        if source_row is not None:
            lines.append(f"{prefix}📍 行号: 第{source_row}行")
    
    def _classify_transaction(self, counterparty: str, description: str, amount: float, person_name: str, category: str = '') -> Dict[str, Any]:
        """
        识别交易类型
        
        Args:
            counterparty: 交易对手
            description: 交易摘要
            amount: 金额
            person_name: 账户持有人姓名
            category: 交易分类（来自原始Excel数据）
        
        Returns:
            {'type': str, 'icon': str, 'detail': str}
        """
        cp = str(counterparty).lower() if counterparty else ''
        desc = str(description).lower() if description else ''
        person = person_name.lower() if person_name else ''
        cat = str(category).lower() if category else ''
        
        # 首先检查原始交易分类
        if cat:
            if '投资理财' in category:
                return {'type': '投资理财', 'icon': '💰', 'detail': f'原始分类: {category}'}
            if '工资' in category:
                return {'type': '工资/奖金', 'icon': '💵', 'detail': f'原始分类: {category}'}
            # 大额 + 分类为"其他" + 对手方空 = 疑似理财/定存赎回
            if cat == '其他' and amount >= 100000 and (not cp or cp in ['nan', 'none', '', '-']):
                return {'type': '疑似理财/定存', 'icon': '💰', 'detail': '大额收入但分类为其他，疑似理财产品到期赎回'}
        
        # 自我转账：对手方与自己同名
        if cp and person and cp == person:
            return {'type': '自我转账', 'icon': '🔄', 'detail': f'与本人账户转账'}
        
        # 理财/证券相关
        wealth_keywords = ['证券', '基金', '理财', '金条', '借呗', '花呗', '微粒贷', '京东金融']
        if any(kw in cp for kw in wealth_keywords) or any(kw in desc for kw in wealth_keywords):
            if '银转证' in desc or '证转银' in desc:
                return {'type': '证券转账', 'icon': '📈', 'detail': '银行与证券账户互转'}
            if '理财' in cp or '理财' in desc:
                return {'type': '理财赎回', 'icon': '💰', 'detail': '理财产品赎回'}
            return {'type': '证券/理财', 'icon': '📊', 'detail': '证券或理财相关'}
        """
        识别交易类型
        
        Returns:
            {
                'type': str,  # 交易类型
                'icon': str,  # 图标
                'detail': str  # 详细信息
            }
        """
        cp = str(counterparty).lower() if counterparty else ''
        desc = str(description).lower() if description else ''
        person = person_name.lower() if person_name else ''
        
        # 自我转账：对手方与自己同名
        if cp and person and cp == person:
            return {'type': '自我转账', 'icon': '🔄', 'detail': f'与本人账户转账'}
        
        # 理财/证券相关
        wealth_keywords = ['证券', '基金', '理财', '金条', '借呗', '花呗', '微粒贷', '京东金融']
        if any(kw in cp for kw in wealth_keywords) or any(kw in desc for kw in wealth_keywords):
            if '银转证' in desc or '证转银' in desc:
                return {'type': '证券转账', 'icon': '📈', 'detail': '银行与证券账户互转'}
            if '理财' in cp or '理财' in desc:
                return {'type': '理财赎回', 'icon': '💰', 'detail': '理财产品赎回'}
            return {'type': '证券/理财', 'icon': '📊', 'detail': '证券或理财相关'}
        
        # 公积金/房改
        if '公积金' in cp or '房改' in cp or '社保' in cp:
            return {'type': '公积金/社保', 'icon': '🏠', 'detail': '公积金或社保转入'}
        
        # 工资/奖金
        salary_keywords = ['工资', '奖金', '绩效', '补贴', '报销']
        if any(kw in cp for kw in salary_keywords) or any(kw in desc for kw in salary_keywords):
            return {'type': '工资/奖金', 'icon': '💵', 'detail': '工资或奖金收入'}
        
        # 退款
        refund_keywords = ['退款', '退货', '还款', '退回']
        if any(kw in desc for kw in refund_keywords):
            return {'type': '退款', 'icon': '↩️', 'detail': '退款或退货款'}
        
        # 大额个人转账
        if cp and amount >= 50000:
            import re
            if re.match(r'^[\u4e00-\u9fa5]{2,4}$', cp):
                return {'type': '大额个人转账', 'icon': '👤', 'detail': f'来自个人: {counterparty}'}
        
        # 空对手方
        if not cp or cp in ['nan', 'none', '', '-']:
            return {'type': '对手方不明', 'icon': '❓', 'detail': '对手方信息缺失，需核实'}
        
        return {'type': '正常交易', 'icon': '✅', 'detail': f'对手方: {counterparty}'}
    
    def _get_day_transactions(self, person: str, target_date: str) -> List[Dict]:
        """获取指定人员指定日期的所有交易"""
        try:
            # 构建文件路径
            file_path = os.path.join(self.output_dir, 'cleaned_data', '个人', f'{person}_合并流水.xlsx')
            if not os.path.exists(file_path):
                return []
            
            df = pd.read_excel(file_path)
            df['date'] = pd.to_datetime(df['交易时间'])
            df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
            
            # 筛选当天交易
            day_df = df[df['date_str'] == target_date]
            
            transactions = []
            for _, row in day_df.iterrows():
                amount = row.get('收入(元)', 0) or row.get('income', 0) or 0
                if amount > 0:
                    cp = row.get('交易对手', '')
                    desc = row.get('交易摘要', '')
                    time = row.get('交易时间', '')
                    if pd.notna(time):
                        time = str(time)[11:16]  # 只取时间部分
                    # 读取交易分类字段
                    category = row.get('交易分类', '')
                    if pd.notna(category):
                        category = str(category)
                    
                    # 识别交易类型（传入交易分类）
                    tx_type = self._classify_transaction(cp, desc, amount, person, category)
                    
                    transactions.append({
                        'time': time,
                        'amount': amount,
                        'counterparty': cp if pd.notna(cp) else '',
                        'description': desc if pd.notna(desc) else '',
                        'category': category,
                        'type_info': tx_type
                    })
            
            return transactions
        except Exception as e:
            logger.warning(f"获取{person} {target_date}交易失败: {e}")
            return []

    # ==================== 借贷行为报告 ====================

    def _generate_loan_report(self) -> str:
        """生成借贷行为分析报告.txt"""
        lines = []

        # ==================== 报告头部：算法说明 ====================
        lines.append("=" * 70)
        lines.append("借贷行为分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 双向往来关系分析：")
        lines.append("   遍历所有交易对手方，计算A→B和B→A的收支总额，")
        lines.append("   判断是否存在双向资金流动，识别民间借贷关系。")
        lines.append("")
        lines.append("2. 规律还款识别：")
        lines.append("   按对手方分组，筛选每月固定日期发生的交易，")
        lines.append("   计算日期间隔的标准差，CV<0.3视为规律还款。")
        lines.append("")
        lines.append("3. 网贷平台检测：")
        lines.append("   匹配已知网贷平台关键词（蚂蚁借呗、京东金条等），")
        lines.append("   识别非正规渠道借贷行为。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 发现民间借贷关系")
        lines.append("• 识别潜在债务风险")
        lines.append("• 追踪还款资金来源")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 数据加载 ====================
        loan_data = self.analysis_results.get("loan", {})
        bidirectional_flows = loan_data.get("bidirectional_flows", [])
        if not isinstance(bidirectional_flows, list):
            bidirectional_flows = []

        regular_repayments = loan_data.get("regular_repayments", [])
        if not isinstance(regular_repayments, list):
            regular_repayments = []

        online_loan_platforms = loan_data.get("online_loan_platforms", [])
        if not isinstance(online_loan_platforms, list):
            online_loan_platforms = []

        # ==================== 一、双向往来关系 ====================
        lines.append("一、双向往来关系分析")
        lines.append("-" * 70)

        if bidirectional_flows:
            for i, flow in enumerate(bidirectional_flows, 1):
                lines.append(f"【发现 {i}】")
                # 修复键名映射
                person1 = flow.get("person", flow.get("person1", "未知"))
                person2 = flow.get("counterparty", flow.get("person2", "未知"))
                income_total = flow.get("income_total", flow.get("a_to_b_total", 0))
                expense_total = flow.get("expense_total", flow.get("b_to_a_total", 0))
                income_count = flow.get("income_count", flow.get("a_to_b_count", 0))
                expense_count = flow.get("expense_count", flow.get("b_to_a_count", 0))
                net_flow = expense_total - income_total

                lines.append(f"  关系方A: {person1}")
                lines.append(f"  关系方B: {person2}")
                lines.append(
                    f"  A → B 总金额: {utils.format_currency(income_total)} 元"
                )
                lines.append(
                    f"  B → A 总金额: {utils.format_currency(expense_total)} 元"
                )
                lines.append(f"  收支差额: {utils.format_currency(net_flow)} 元")
                lines.append(
                    f"   交易频次: A→B {income_count} 笔, B→A {expense_count} 笔"
                )

                # 添加溯源
                self._add_traceability(lines, flow)
                lines.append("")
        else:
            lines.append("  未发现双向往来关系")

        lines.append("")

        # ==================== 二、无还款借贷 ====================
        lines.append("二、无还款借贷识别")
        lines.append("-" * 70)
        lines.append("  未发现无还款借贷（当前版本暂未实现检测）")
        lines.append("")

        # ==================== 三、规律还款 ====================
        lines.append("三、规律还款分析")
        lines.append("-" * 70)

        # 提取通用审计提示
        audit_tip_printed = False

        if regular_repayments:
            for i, repayment in enumerate(regular_repayments, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  还款人: {repayment.get('person', '未知')}")
                lines.append(f"  还款对手方: {repayment.get('counterparty', '未知')}")
                avg_amount = repayment.get("avg_amount", repayment.get("amount", 0))
                occurrences = repayment.get("occurrences", repayment.get("count", 0))
                date_range = repayment.get("date_range", [None, None])
                start_date = self._format_date(date_range[0]) if date_range else "未知"
                end_date = (
                    self._format_date(date_range[1])
                    if date_range and len(date_range) > 1
                    else "未知"
                )

                lines.append(f"  还款金额: {utils.format_currency(avg_amount)} 元")
                lines.append(f"  还款次数: {occurrences} 笔")
                lines.append(f"  时间跨度: {start_date} 至 {end_date}")

                # 添加溯源
                self._add_traceability(lines, repayment)
                lines.append("")

            # 通用审计提示（只打印一次）
            lines.append("  【审计提示】: 规律性还款可能对应:")
            lines.append("            1. 每月固定还款（房贷、车贷等）")
            lines.append("            2. 定期债务偿还")
            lines.append("            建议核对该规律还款的用途是否与资产匹配，")
            lines.append("            是否存在借贷资金来源不明的情形。")
            lines.append("")
        else:
            lines.append("  未发现规律还款")

        lines.append("")

        # ==================== 四、网贷平台 ====================
        lines.append("四、网贷平台交易识别")
        lines.append("-" * 70)

        if online_loan_platforms:
            platform_summary = {}
            for transaction in online_loan_platforms:
                platform = transaction.get("platform", "未知")
                if platform not in platform_summary:
                    platform_summary[platform] = {"count": 0, "amount": 0.0}
                platform_summary[platform]["count"] += transaction.get("count", 0)
                platform_summary[platform]["amount"] += transaction.get("amount", 0)

            lines.append(f"发现 {len(platform_summary)} 个网贷平台相关交易:")
            lines.append("")
            for platform, stats in platform_summary.items():
                lines.append(f"  平台: {platform}")
                lines.append(f"  交易笔数: {stats['count']} 笔")
                lines.append(
                    f"   交易金额: {utils.format_currency(stats['amount'])} 元"
                )
                lines.append("")

            lines.append("  【审计提示】: 网贷平台交易可能涉及:")
            lines.append("            1. 高利率网络贷款")
            lines.append("            2. 消费分期付款")
            lines.append("            3. 借贷资金来源不明")
            lines.append("            建议核对借款合同、利率、还款情况，")
            lines.append("            评估是否存在过度负债和资金用途不当。")
        else:
            lines.append("  未发现网贷平台交易")

        lines.append("")

        # ==================== 五、综合研判 ====================
        lines.append("五、综合研判与建议")
        lines.append("-" * 70)

        if bidirectional_flows or regular_repayments or online_loan_platforms:
            lines.append("【总体评价】: ")
            lines.append("  发现多层次借贷行为，建议深入调查借贷关系网络，")
            lines.append("  追踪资金最终用途和来源，评估是否存在利益输送或洗钱风险。")
        else:
            lines.append("【总体评价】: ")
            lines.append("  未发现明显异常借贷行为，整体借贷风险较低。")

        lines.append("")
        lines.append("【下一步核查建议】:")
        lines.append("  1. 核对大额借入资金的来源和用途")
        lines.append("  2. 询问当事人关于借贷关系的背景说明")
        lines.append("  3. 查阅相关合同、凭证等书面材料")
        lines.append("  4. 关注后续还款记录，观察还款资金来源")
        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 异常收入报告 ====================

    def _generate_income_report(self) -> str:
        """生成异常收入来源分析报告.txt"""
        lines = []

        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("异常收入来源分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 规律性非工资收入：")
        lines.append("   同一对手方≥3次转入，间隔CV<0.3，金额CV<0.3，")
        lines.append("   排除工资/理财关键词，识别隐性收入。")
        lines.append("")
        lines.append("2. 个人大额转入：")
        lines.append("   来自2-4字汉语姓名的≥5万元收入，")
        lines.append("   识别个人之间的大额资金往来。")
        lines.append("")
        lines.append("3. 来源不明收入：")
        lines.append("   对手方为空/nan且金额≥1万元，")
        lines.append("   排除理财到账，识别无法追溯的资金。")
        lines.append("")
        lines.append("4. 同源多次收入：")
        lines.append("   同一对手方≥5次转入且累计≥1万元，")
        lines.append("   识别重复性资金来源。")
        lines.append("")
        lines.append("5. 疑似分期受贿：")
        lines.append("   个人每月固定金额转入，持续≥4个月，CV<0.5，")
        lines.append("   识别周期性利益输送模式。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 发现隐性收入")
        lines.append("• 识别人情往来")
        lines.append("• 追踪资金真正来源")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 数据加载 ====================
        income_results = self.analysis_results.get("income", {})

        # ==================== 一、大额单笔收入 ====================
        lines.append("一、大额单笔收入分析（≥10万元）")
        lines.append("-" * 70)

        large_single = income_results.get("large_single_income", [])
        if large_single:
            for i, income in enumerate(large_single, 1):
                lines.append(f"【发现 {i}】")
                # 修复字段映射：name -> person
                person = income.get("person", income.get("name", "未知"))
                lines.append(f"  收款人: {person}")
                lines.append(
                    f"  收款金额: {utils.format_currency(income.get('amount', 0))} 元"
                )
                lines.append(
                    f"  收款日期: {self._format_date(income.get('date', '未知'))}"
                )
                lines.append(f"   付款方: {income.get('counterparty', '未知')}")
                lines.append(
                    f"   交易摘要: {income.get('description', income.get('income_type', '未知'))}"
                )

                # 添加溯源
                self._add_traceability(lines, income)
                lines.append("")

            # 通用审计提示
            lines.append("  【审计提示】: 大额单笔收入需核实:")
            lines.append("            1. 收款来源是否合法合规")
            lines.append("            2. 是否与业务往来匹配")
            lines.append("            3. 是否存在代收代付情形")
            lines.append("")
        else:
            lines.append("  未发现大额单笔收入")

        lines.append("")

        # ==================== 二、疑似分期受贿 ====================
        lines.append("二、疑似分期受贿分析")
        lines.append("-" * 70)

        bribe_installments = income_results.get("potential_bribe_installment", [])
        if bribe_installments:
            for i, case in enumerate(bribe_installments, 1):
                lines.append(f"【发现 {i}】")
                person = case.get("person", case.get("name", "未知"))
                lines.append(f"  收款人: {person}")
                lines.append(
                    f"  分期模式: 每 {case.get('interval_days', 0)} 天收 {case.get('occurrences', 0)} 次"
                )
                lines.append(
                    f"  单笔金额: {utils.format_currency(case.get('amount', 0))} 元"
                )
                lines.append(
                    f"  总金额: {utils.format_currency(case.get('total', 0))} 元"
                )
                lines.append(
                    f"  时间跨度: {case.get('start_date', '未知')} 至 {case.get('end_date', '未知')}"
                )

                # 添加溯源
                self._add_traceability(lines, case)
                lines.append("")

            lines.append("  【审计提示】: 疑似分期受贿特征:")
            lines.append("            1. 固定周期规律性收款")
            lines.append("            2. 收款人与被调查人存在潜在关系")
            lines.append("            3. 单笔金额相对固定")
            lines.append("            4. 长期持续性收款")
            lines.append("            建议核实收款人身份、工作职责，")
            lines.append("            调查收款业务背景是否存在。")
            lines.append("")
        else:
            lines.append("  未发现疑似分期受贿模式")

        lines.append("")

        # ==================== 三、同源多次收入 ====================
        lines.append("三、同源多次收入分析")
        lines.append("-" * 70)

        same_source = income_results.get("same_source_multi", [])
        if same_source:
            for i, item in enumerate(same_source, 1):
                lines.append(f"【发现 {i}】")
                person = item.get("person", item.get("name", "未知"))
                lines.append(f"  收款人: {person}")
                lines.append(f"   付款方: {item.get('counterparty', '未知')}")
                lines.append(
                    f"   累计次数: {item.get('count', item.get('occurrences', 0))} 次"
                )
                lines.append(
                    f"   累计金额: {utils.format_currency(item.get('total', item.get('total_amount', 0)))} 元"
                )
                lines.append(
                    f"   平均金额: {utils.format_currency(item.get('avg_amount', 0))} 元"
                )

                # 添加溯源
                self._add_traceability(lines, item)
                lines.append("")
            lines.append("")
        else:
            lines.append("  未发现同源多次收入")

        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 时序分析报告 ====================

    def _generate_time_series_report(self) -> str:
        """生成时序分析报告.txt"""
        lines = []

        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("时序分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 周期性收入检测：")
        lines.append("   按对手方分组，计算日期间隔的变异系数CV<0.3，")
        lines.append("   金额CV<0.1，识别固定间隔的规律收入。")
        lines.append("   排除工资/理财关键词，识别养廉资金模式。")
        lines.append("")
        lines.append("2. 资金突变检测：")
        lines.append("   使用滑动窗口（默认30天）计算均值和标准差，")
        lines.append("   Z-score>3且金额>10万视为突变，识别异常资金流入。")
        lines.append("")
        lines.append("3. 固定延迟转账：")
        lines.append("   A收入后1-7天内有相近金额（差异<10%）转给B，")
        lines.append("   ≥3次视为固定模式，识别利益分配协议。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 发现养廉资金模式")
        lines.append("• 识别利益输送协议")
        lines.append("• 关联异常事件时间线")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 数据加载 ====================
        time_series = self.analysis_results.get("timeSeries", {})
        periodic_income = time_series.get("periodic_income", [])
        sudden_changes = time_series.get("sudden_changes", [])

        # ==================== 一、周期性收入 ====================
        lines.append("一、周期性收入分析（疑似养廉资金）")
        lines.append("-" * 70)

        if periodic_income:
            for i, income in enumerate(periodic_income, 1):
                lines.append(f"【发现 {i}】")
                # 修复字段映射：name -> person
                person = income.get("person", income.get("name", "未知"))
                lines.append(f"  收款人: {person}")
                lines.append(f"  付款方: {income.get('counterparty', '未知')}")
                lines.append(
                    f"  周期: {income.get('period_type', '每' + str(income.get('avg_interval_days', 0)) + '天')}"
                )
                lines.append(f"  收款次数: {income.get('occurrences', 0)} 次")
                lines.append(
                    f"  平均金额: {utils.format_currency(income.get('avg_amount', 0))} 元"
                )
                lines.append(
                    f"  总金额: {utils.format_currency(income.get('total_amount', 0))} 元"
                )

                date_range = income.get("date_range", "")
                if isinstance(date_range, str):
                    lines.append(f"  时间跨度: {date_range}")
                else:
                    start = self._format_date(date_range[0]) if date_range else "未知"
                    end = (
                        self._format_date(date_range[1])
                        if date_range and len(date_range) > 1
                        else "未知"
                    )
                    lines.append(f"  时间跨度: {start} 至 {end}")

                # 添加溯源
                self._add_traceability(lines, income)
                lines.append("")

            lines.append("  【审计提示】: 周期性收入可能对应:")
            lines.append("            1. 兼职收入或劳务报酬")
            lines.append("            2. 隐形补贴或福利")
            lines.append("            3. 投资分红收益")
            lines.append("            建议核实收入来源的合法性，")
            lines.append("            查阅相关合同或证明文件。")
            lines.append("")
        else:
            lines.append("  未发现周期性收入")

        lines.append("")

        # ==================== 二、资金突变 ====================
        lines.append("二、大额突变分析")
        lines.append("-" * 70)

        if sudden_changes:
            for i, change in enumerate(sudden_changes, 1):
                lines.append(f"【发现 {i}】")
                # 修复字段映射：name -> person, type -> change_type
                person = change.get("person", change.get("name", "未知"))
                change_type = change.get("change_type", change.get("type", "收入突增"))
                lines.append(f"  人员: {person}")
                lines.append(f"  变化类型: {change_type}")
                lines.append(
                    f"  变化日期: {self._format_date(change.get('date', '未知'))}"
                )
                lines.append(
                    f"  变化金额: {utils.format_currency(change.get('amount', 0))} 元"
                )
                lines.append(f"  Z-Score: {change.get('z_score', '未知')}")
                lines.append(
                    f"  事前均值: {utils.format_currency(change.get('avg_before', 0))} 元"
                )
                
                # 获取该日交易明细
                target_date = self._format_date(change.get('date', ''))
                day_transactions = self._get_day_transactions(person, target_date)
                
                if day_transactions:
                    lines.append(f"  📋 该日收入交易明细（共{len(day_transactions)}笔）:")
                    for tx in day_transactions:
                        amount_str = utils.format_currency(tx['amount'])
                        type_info = tx['type_info']
                        cp = tx['counterparty'] if tx['counterparty'] else '(对手方不明)'
                        cat = tx.get('category', '')
                        cat_str = f" [{cat}]" if cat else ""
                        lines.append(f"    {tx['time']} {type_info['icon']} {amount_str:>12}元{cat_str} | {cp}")
                        if type_info['type'] != '正常交易':
                            lines.append(f"           └─ {type_info['type']}: {type_info['detail']}")
                else:
                    lines.append(f"  ⚠️ 无法获取该日交易明细")
                
                lines.append("")
            lines.append("")
        else:
            lines.append("  未发现大额突变")

        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 资金穿透报告 ====================

    def _generate_penetration_report(self) -> str:
        """生成资金穿透分析报告.txt"""
        lines = []

        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("资金穿透分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 资金闭环检测：")
        lines.append("   构建资金流向图谱，识别资金回到原点的循环路径，")
        lines.append("   发现洗钱或利益回流模式。")
        lines.append("")
        lines.append("2. 过账通道识别：")
        lines.append("   识别资金停留时间短、净流量接近0的节点，")
        lines.append("   发现空壳公司或资金中介。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 穿透复杂资金关系")
        lines.append("• 发现最终受益人")
        lines.append("• 追踪跨境转移路径")
        lines.append("")

        lines.append("【说明】: 资金穿透分析已通过资金流向图谱进行可视化展示。")
        lines.append("本报告重点描述关键发现和审计建议。")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 数据加载 ====================
        penetration = self.analysis_results.get("penetration", {})

        # ==================== 一、资金闭环 ====================
        lines.append("一、资金闭环检测")
        lines.append("-" * 70)

        cycles = penetration.get("fund_cycles", [])
        if cycles:
            for i, cycle in enumerate(cycles, 1):
                lines.append(f"【资金闭环 {i}】")
                lines.append(f"  闭环路径: {' → '.join(cycle.get('nodes', []))}")
                lines.append(f"  闭环长度: {len(cycle.get('nodes', []))} 个节点")
                lines.append(
                    f"  总资金: {utils.format_currency(cycle.get('total_amount', 0))} 元"
                )
                lines.append("")
                lines.append("  【审计提示】: 资金闭环可能是:")
                lines.append("            1. 资金回流洗钱（通过多层转账回到原点）")
                lines.append("            2. 利益输送证据链路")
                lines.append("            3. 隐匿的关联关系网")
                lines.append("            建议核查每个节点的身份关系，")
                lines.append("            追踪资金最终用途和资产来源。")
                lines.append("")
        else:
            lines.append("  未发现资金闭环")

        lines.append("")

        # ==================== 二、过账通道 ====================
        lines.append("二、过账通道识别")
        lines.append("-" * 70)

        pass_throughs = penetration.get("pass_through_nodes", [])
        if pass_throughs:
            for i, node in enumerate(pass_throughs, 1):
                lines.append(f"【过账通道 {i}】")
                lines.append(f"  节点: {node.get('name', '未知')}")
                lines.append(
                    f"  总流入: {utils.format_currency(node.get('total_inflow', 0))} 元"
                )
                lines.append(
                    f"  总流出: {utils.format_currency(node.get('total_outflow', 0))} 元"
                )
                lines.append(
                    f"  净流量: {utils.format_currency(node.get('net_flow', 0))} 元"
                )
                lines.append(f"  转账频次: {node.get('transfer_count', 0)} 笔")
                lines.append("")
                lines.append("  【审计提示】: 过账通道特征:")
                lines.append("            1. 大额资金快速进出（停留时间短）")
                lines.append("            2. 净流量接近0（全部转出）")
                lines.append("            3. 频繁大额转账")
                lines.append("            建议核查该节点是否为空壳公司或中介，")
                lines.append("            追踪资金最终去向，排查是否存在洗钱行为。")
                lines.append("")
        else:
            lines.append("  未发现过账通道")

        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 疑点检测报告 ====================

    def _generate_suspicion_report(self) -> str:
        """生成疑点检测分析报告.txt"""
        lines = []

        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("疑点检测分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 现金时空伴随检测：")
        lines.append("   同一人在48小时内取现和存现，时间差<小时，")
        lines.append("   金额差异<10%，识别现金搬运模式。")
        lines.append("")
        lines.append("2. 跨实体现金碰撞：")
        lines.append("   不同人之间A取现后B存现，时间窗口内金额接近，")
        lines.append("   识别洗钱或资金对敲模式。")
        lines.append("")
        lines.append("3. 直接资金往来：")
        lines.append("   核心人员与涉案公司之间的收支记录，")
        lines.append("   识别利益输送通道。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 识别洗钱模式")
        lines.append("• 发现资金闭环")
        lines.append("• 追踪非法资金流向")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 一、现金时空伴随 ====================
        lines.append("一、现金时空伴随检测")
        
        # 加载现金碰撞数据（支持两种键名）
        cash_collisions = self.suspicions.get('cashCollisions', []) or self.suspicions.get('cash_collisions', [])
        
        if cash_collisions:
            for i, collision in enumerate(cash_collisions, 1):
                lines.append(f"【现金伴随 {i}】")
                # 支持 camelCase 和 snake_case 两种格式
                withdrawal_entity = collision.get('withdrawal_entity') or collision.get('person1', '未知')
                deposit_entity = collision.get('deposit_entity') or collision.get('person2', '未知')
                withdrawal_date = collision.get('withdrawal_date') or collision.get('time1', '未知')
                deposit_date = collision.get('deposit_date') or collision.get('time2', '未知')
                withdrawal_amount = collision.get('withdrawal_amount') or collision.get('amount1', 0)
                deposit_amount = collision.get('deposit_amount') or collision.get('amount2', 0)
                time_diff = collision.get('time_diff_hours') or collision.get('timeDiff', 0)
                risk_level = collision.get('risk_level') or collision.get('riskLevel', '未知')
                
                lines.append(f"  取现方: {withdrawal_entity}")
                lines.append(f"  存现方: {deposit_entity}")
                lines.append(f"  取现时间: {self._format_date(withdrawal_date)}")
                lines.append(f"  存现时间: {self._format_date(deposit_date)}")
                lines.append(f"  时间差: {time_diff:.1f} 小时")
                lines.append(f"  取现金额: {utils.format_currency(withdrawal_amount)} 元")
                lines.append(f"  存现金额: {utils.format_currency(deposit_amount)} 元")
                lines.append(f"  风险等级: {risk_level}")

                # 添加溯源
                source_file = collision.get("withdrawalSource", collision.get("withdrawal_source", ""))
                if source_file:
                    lines.append(f"  📁 取现来源: {source_file}")
                source_file = collision.get("depositSource", collision.get("deposit_source", ""))
                if source_file:
                    lines.append(f"  📁 存现来源: {source_file}")

                lines.append("")

            lines.append("  【审计提示】: 现金时空伴随特征:")
            lines.append("            1. 短时间内大额取现后存现")
            lines.append("            2. 金额接近（差异<5%）")
            lines.append("            3. 可能规避银行系统监控")
            lines.append("            建议核实取现地点、用途，")
            lines.append("            排查是否存在隐匿资产或贿赂资金。")
            lines.append("")
        else:
            lines.append("  未发现现金时空伴随")
        lines.append("")

        # ==================== 二、直接资金往来 ====================
        lines.append("二、直接资金往来分析")
        lines.append("-" * 70)

        direct_transfers = self.suspicions.get(
            "direct_transfers", []
        ) or self.suspicions.get("directTransfers", [])
        if direct_transfers:
            for i, transfer in enumerate(direct_transfers, 1):
                lines.append(f"【直接往来 {i}】")
                lines.append(f"  交易人: {transfer.get('person', '未知')}")
                lines.append(f"  对方: {transfer.get('company', '未知')}")
                lines.append(
                    f"  交易时间: {self._format_date(transfer.get('date', '未知'))}"
                )
                lines.append(
                    f"  交易金额: {utils.format_currency(transfer.get('amount', 0))} 元"
                )
                lines.append(f"   方向: {transfer.get('direction', '未知')}")
                lines.append(f"   摘要: {transfer.get('description', '未知')}")
                lines.append(f"   风险等级: {transfer.get('risk_level', '未知')}")

                # 添加溯源
                self._add_traceability(lines, transfer)
                lines.append("")

            lines.append("  【审计提示】: 核心人员与涉案公司直接往来:")
            lines.append("            1. 可能是利益输送")
            lines.append("            2. 可能是公私往来")
            lines.append("            3. 可能是关联交易")
            lines.append("            建议核查交易背景、业务合理性，")
            lines.append("            查阅相关合同、凭证。")
            lines.append("")
        else:
            lines.append("  未发现直接资金往来")

        lines.append("")

        # ==================== 三、反洗钱预警 ====================
        lines.append("三、反洗钱预警")
        lines.append("-" * 70)

        aml_alerts = self.suspicions.get("amlAlerts", [])
        if aml_alerts:
            for alert in aml_alerts:
                name = alert.get("name", "未知")
                alert_type = alert.get("alert_type", "未知")
                lines.append(f"【预警】{name} - {alert_type}")
                suspicious_count = alert.get("suspicious_transaction_count", 0)
                large_count = alert.get("large_transaction_count", 0)
                lines.append(f"  可疑交易数: {suspicious_count}")
                lines.append(f"  大额交易数: {large_count}")
                source = alert.get("source", "")
                if source:
                    lines.append(f"  📁 数据来源: {source}")
                lines.append("")
        else:
            lines.append("  未发现反洗钱预警")

        lines.append("")

        # ==================== 四、征信预警 ====================
        lines.append("四、征信预警")
        lines.append("-" * 70)

        credit_alerts = self.suspicions.get("creditAlerts", [])
        if credit_alerts:
            for alert in credit_alerts:
                name = alert.get("name", "未知")
                alert_type = alert.get("alert_type", "未知")
                count = alert.get("count", 0)
                lines.append(f"【预警】{name} - {alert_type} ({count} 次)")
                lines.append("")
        else:
            lines.append("  未发现征信预警")

        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 行为特征报告 ====================

    def _generate_behavioral_report(self) -> str:
        """生成行为特征分析报告.txt"""
        lines = []

        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("行为特征分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 快进快出检测：")
        lines.append("   24小时内有大额收入(≥1万)又有相近金额支出，")
        lines.append("   识别过账或洗钱模式。")
        lines.append("   过滤条件：排除公司账户、自转账、无效对手方。")
        lines.append("")
        lines.append("2. 整进散出检测：")
        lines.append("   一笔大额进来后7天内多笔小额出去，总额接近80%-120%，")
        lines.append("   识别规避监管的拆分模式。")
        lines.append("")
        lines.append("3. 散进整出检测：")
        lines.append("   多笔小额进来后一笔大额出去，")
        lines.append("   识别资金归集模式。")
        lines.append("")
        lines.append("4. 休眠激活检测：")
        lines.append("   连续180天无交易后突然大额进出(≥5万)，")
        lines.append("   发现沉睡资金突然激活。")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 识别洗钱/过桥账户")
        lines.append("• 发现规避监管行为")
        lines.append("• 发现沉睡资金突然激活")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        # ==================== 数据加载 ====================
        behavioral = self.analysis_results.get("behavioral", {})

        # ==================== 一、快进快出检测 ====================
        lines.append("一、快进快出检测（过滤后）")
        lines.append("-" * 70)

        fast_in_out = behavioral.get("fast_in_out", [])

        # 过滤：排除公司账户、自转账、无效对手方
        company_keywords = ["公司", "有限公司", "股份", "企业", "集团"]
        normal_sources = ["公积金", "房改", "社保"]

        filtered_fast_in_out = []
        for f in fast_in_out:
            entity = f.get("entity", "")

            # 排除公司账户
            if any(kw in entity for kw in company_keywords):
                continue

            income_cp = str(f.get("income_counterparty", "")).strip()
            expense_cp = str(f.get("expense_counterparty", "")).strip()

            # 排除自转账（收入方或支出方与账户持有人相同）
            if income_cp and income_cp == entity:
                continue
            if expense_cp and expense_cp == entity:
                continue

            # 排除对手方为空或无效
            if income_cp in ["nan", "-", ""] or expense_cp in ["nan", "-", ""]:
                continue

            # 排除正常资金来源
            if any(src in income_cp for src in normal_sources):
                continue

            filtered_fast_in_out.append(f)

        lines.append(
            f"原始数据: {len(fast_in_out)}条 → 过滤后: {len(filtered_fast_in_out)}条"
        )
        lines.append("（已排除：公司账户、自转账、正常资金来源）")
        lines.append("")

        if filtered_fast_in_out:
            for i, pattern in enumerate(filtered_fast_in_out, 1):
                lines.append(f"【快进快出 {i}】")
                entity = pattern.get("entity", pattern.get("name", "未知"))
                income_date = self._format_date(
                    pattern.get("income_date", pattern.get("in_time", "未知"))
                )
                expense_date = self._format_date(
                    pattern.get("expense_date", pattern.get("out_time", "未知"))
                )
                income_amount = pattern.get(
                    "income_amount", pattern.get("in_amount", 0)
                )
                expense_amount = pattern.get(
                    "expense_amount", pattern.get("out_amount", 0)
                )
                hours_diff = pattern.get(
                    "hours_diff", pattern.get("time_diff_hours", 0)
                )

                lines.append(f"  人员: {entity}")
                lines.append(f"  流入时间: {income_date}")
                lines.append(f"  流出时间: {expense_date}")
                lines.append(f"  时间差: {hours_diff:.1f} 小时")
                lines.append(f"  流入金额: {utils.format_currency(income_amount)} 元")
                lines.append(f"  流出金额: {utils.format_currency(expense_amount)} 元")
                income_cp = str(pattern.get('income_counterparty', '')).strip()
                expense_cp = str(pattern.get('expense_counterparty', '')).strip()
                lines.append(f"  收入方: {income_cp}")
                lines.append(f"  支出方: {expense_cp}")

                # 添加溯源
                self._add_traceability(lines, pattern)
                lines.append("")

            # 通用审计提示
            lines.append("  【审计提示】: 快进快出特征:")
            lines.append("            1. 资金在账户内停留时间极短")
            lines.append("            2. 可能是过账或洗钱")
            lines.append("            3. 规避银行系统监控")
            lines.append("            建议核查资金用途，")
            lines.append("            排查是否与洗钱团伙相关。")
            lines.append("")
        else:
            lines.append("  未发现快进快出模式（过滤后）")

        lines.append("")

        # ==================== 二、整进散出 ====================
        lines.append("二、整进散出/散进整出检测")
        lines.append("-" * 70)

        structuring = behavioral.get("structuring", [])
        if structuring:
            for i, pattern in enumerate(structuring[:20], 1):
                lines.append(f"【发现 {i}】")
                entity = pattern.get("entity", "未知")
                pattern_type = pattern.get("type", "")
                lines.append(f"  主体: {entity}")
                lines.append(
                    f"  类型: {'整进散出' if pattern_type == 'large_in_split_out' else '散进整出'}"
                )
                lines.append(f"  大额方: {pattern.get('large_counterparty', '未知')}")
                lines.append(
                    f"  大额金额: {utils.format_currency(pattern.get('large_amount', 0))} 元"
                )
                lines.append(f"  拆分笔数: {pattern.get('split_count', 0)} 笔")
                lines.append(
                    f"  拆分总额: {utils.format_currency(pattern.get('split_total', 0))} 元"
                )
                lines.append(f"  时间窗口: {pattern.get('time_window_days', 0)} 天")

                # 添加溯源
                self._add_traceability(lines, pattern)
                lines.append("")

            lines.append("  【审计提示】: 整进散出特征:")
            lines.append("            1. 大额资金拆分转出，规避监管")
            lines.append("            2. 可能涉及虚假交易或洗钱")
            lines.append("            3. 建议核查资金去向和交易背景")
            lines.append("")
        else:
            lines.append("  未发现整进散出/散进整出模式")

        lines.append("")

        # ==================== 三、休眠激活 ====================
        lines.append("三、休眠激活检测")
        lines.append("-" * 70)

        dormant = behavioral.get("dormant_activation", [])
        if dormant:
            for i, pattern in enumerate(dormant, 1):
                lines.append(f"【发现 {i}】")
                entity = pattern.get("entity", "未知")
                lines.append(f"  人员: {entity}")
                lines.append(f"  休眠天数: {pattern.get('dormant_days', 0)} 天")
                lines.append(
                    f"  激活日期: {self._format_date(pattern.get('activation_date', '未知'))}"
                )
                lines.append(
                    f"  激活金额: {utils.format_currency(pattern.get('activation_amount', 0))} 元"
                )
                lines.append(f"  方向: {pattern.get('activation_direction', '未知')}")
                lines.append(f"  对手方: {pattern.get('counterparty', '未知')}")

                # 添加溯源
                self._add_traceability(lines, pattern)
                lines.append("")

            lines.append("  【审计提示】: 休眠激活特征:")
            lines.append("            1. 长期不活跃账户突然大额资金流动")
            lines.append("            2. 可能涉及隐藏资产或突然资金需求")
            lines.append("            3. 建议核查激活原因和资金用途")
            lines.append("")
        else:
            lines.append("  未发现休眠激活模式")

        lines.append("")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ==================== 资产全貌报告 ====================

    def _generate_asset_report(self) -> str:
        """生成资产全貌分析报告.txt"""
        lines = []
        
        # ==================== 报告头部 ====================
        lines.append("=" * 70)
        lines.append("资产全貌分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 算法说明
        lines.append("【算法说明】")
        lines.append("-" * 50)
        lines.append("1. 读取 precisePropertyData.json（精准房产数据）")
        lines.append("2. 读取 family_units_v2 获取家庭单元结构")
        lines.append("3. 按地址去重（地址前缀+面积作为唯一键）")
        lines.append("4. 按家庭单元归集，显示共同共有情况")
        lines.append("")
        lines.append("【审计价值】")
        lines.append("-" * 50)
        lines.append("• 核实家庭申报资产")
        lines.append("• 发现隐匿财产")
        lines.append("• 比对资金来源与资产规模")
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        # ==================== 数据加载 ====================
        
        # 1. 加载房产数据
        property_data = {}
        try:
            if os.path.basename(self.output_dir) == 'output':
                cache_dir = os.path.join(self.output_dir, 'analysis_cache')
            else:
                cache_dir = os.path.join(os.path.dirname(self.output_dir), 'analysis_cache')
            property_file = os.path.join(cache_dir, 'precisePropertyData.json')
            if os.path.exists(property_file):
                with open(property_file, 'r', encoding='utf-8') as f:
                    property_data = json.load(f)
        except Exception as e:
            logger.warning(f"[资产报告] 加载 precisePropertyData.json 失败: {e}")
        
        # 2. 加载家庭单元
        family_units = self.analysis_results.get('family_units_v2', [])
        
        # 3. 构建身份证→姓名映射
        id_to_name = {}
        for id_num, props in property_data.items():
            if isinstance(props, list) and props:
                id_to_name[id_num] = props[0].get('owner_name', '')
        
        # ==================== 按地址去重 ====================
        dedup_properties = {}
        for id_number, props in property_data.items():
            if not isinstance(props, list):
                continue
            for prop in props:
                addr = prop.get('location', '')
                area = prop.get('area', '')
                if '号' in addr:
                    addr_prefix = addr.split('号')[0] + '号'
                else:
                    addr_prefix = addr[:20] if len(addr) > 20 else addr
                
                area_num = 0
                if area:
                    try:
                        area_num = float(str(area).replace('平方米', '').replace('㎡', '').strip())
                    except:
                        pass
                
                dedup_key = (addr_prefix, area_num)
                owner_name = prop.get('owner_name', '')
                owner_id = prop.get('owner_id', '')
                
                if dedup_key not in dedup_properties:
                    dedup_properties[dedup_key] = {
                        'location': prop.get('location', ''),
                        'area': area,
                        'owners': [],
                        'usage': prop.get('usage', ''),
                        'register_date': prop.get('register_date', ''),
                        'status': prop.get('status', '现势'),
                        'is_mortgaged': prop.get('is_mortgaged', False),
                        'is_sealed': prop.get('is_sealed', False),
                        'source': prop.get('source_file', ''),
                        'value': prop.get('transaction_amount', 0) or (area_num * 30000)
                    }
                
                if owner_name and owner_id:
                    exists = False
                    for o_name, o_id in dedup_properties[dedup_key]['owners']:
                        if o_name == owner_name:
                            exists = True
                            break
                    if not exists:
                        dedup_properties[dedup_key]['owners'].append((owner_name, owner_id))
        
        unique_properties = list(dedup_properties.values())
        total_value = sum(p['value'] for p in unique_properties)
        
        # ==================== 按家庭单元归集 ====================
        def find_family_for_owner(owner_name: str, family_units: list) -> tuple:
            for fu in family_units:
                members = fu.get('members', [])
                if owner_name in members:
                    return (fu.get('anchor', ''), fu.get('householder', ''))
            return (None, None)
        
        family_assets = {}
        
        for i, fu in enumerate(family_units):
            anchor = fu.get('anchor', f'家庭{i+1}')
            family_assets[anchor] = {
                'householder': fu.get('householder', anchor),
                'members': fu.get('members', []),
                'properties': [],
                'total_value': 0
            }
        
        for prop in unique_properties:
            assigned = False
            for owner_name, owner_id in prop['owners']:
                anchor, householder = find_family_for_owner(owner_name, family_units)
                if anchor:
                    family_assets[anchor]['properties'].append(prop)
                    family_assets[anchor]['total_value'] += prop['value']
                    assigned = True
                    break
            
            if not assigned:
                if '未归属' not in family_assets:
                    family_assets['未归属'] = {
                        'householder': '-',
                        'members': [],
                        'properties': [],
                        'total_value': 0
                    }
                family_assets['未归属']['properties'].append(prop)
                family_assets['未归属']['total_value'] += prop['value']
        
        # ==================== 生成报告 ====================
        lines.append("【资产总览】")
        lines.append("-" * 50)
        lines.append(f"  家庭单元数: {len(family_units)} 个")
        lines.append(f"  房产总数: {len(unique_properties)} 套（去重后）")
        lines.append(f"  房产总价值: {total_value/10000:.2f} 万元")
        lines.append("")
        
        lines.append("【家庭资产明细】")
        lines.append("-" * 50)
        
        for anchor, data in family_assets.items():
            if not data['properties']:
                continue
                
            lines.append("")
            lines.append(f"===== 家庭单元: {anchor}家庭 =====")
            lines.append(f"  户主: {data['householder']}")
            lines.append(f"  成员: {', '.join(data['members'])}")
            lines.append(f"  房产数: {len(data['properties'])} 套")
            lines.append(f"  总价值: {data['total_value']/10000:.2f} 万元")
            lines.append("")
            lines.append("  房产明细:")
            
            for i, prop in enumerate(data['properties'], 1):
                owner_names = [o[0] for o in prop['owners']]
                is_coowned = len(prop['owners']) > 1
                
                lines.append(f"    {i}. {prop['location']}")
                lines.append(f"       产权人: {', '.join(owner_names)}")
                if is_coowned:
                    lines.append(f"       共有情况: 共同共有")
                lines.append(f"       面积: {prop['area']}㎡")
                lines.append(f"       用途: {prop['usage']}")
                lines.append(f"       登记时间: {prop['register_date']}")
                lines.append(f"       估值: {prop['value']/10000:.2f} 万元")
                if prop['is_mortgaged']:
                    lines.append(f"       ⚠️ 状态: 已抵押")
                if prop['is_sealed']:
                    lines.append(f"       ⚠️ 状态: 已查封")
                if prop['source']:
                    lines.append(f"       📁 来源: {prop['source']}")
                lines.append("")
        
        lines.append("-" * 50)
        lines.append("")
        lines.append("【统计汇总】")
        lines.append(f"  • 家庭单元: {len(family_units)} 个")
        lines.append(f"  • 房产总数: {len(unique_properties)} 套")
        lines.append(f"  • 房产总价值: {total_value/10000:.2f} 万元")
        if family_units:
            avg_per_family = total_value / len(family_units)
            lines.append(f"  • 户均资产: {avg_per_family/10000:.2f} 万元")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_report_index(self, reports_dir: str, generated_files: List[str]) -> str:
        """生成报告目录清单.txt"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("报告文件目录清单")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"报告数量: {len(generated_files)} 个")
        lines.append("")
        lines.append("-" * 70)
        lines.append("")
        
        # 按类别分组
        txt_files = [f for f in generated_files if f.endswith('.txt')]
        
        if txt_files:
            lines.append("【专项txt报告】")
            for filepath in txt_files:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) / 1024  # KB
                lines.append(f"  • {filename} ({file_size:.1f} KB)")
            lines.append("")
        
        lines.append("-" * 70)
        lines.append("")
        lines.append("【使用说明】:")
        lines.append("  1. 每个报告开头包含算法说明和审计价值")
        lines.append("  2. 每条记录包含数据溯源信息（文件路径+行号）")
        lines.append("  3. 可根据溯源信息在Excel中定位原始数据")
        lines.append("  4. 所有分析基于 output/cleaned_data/ 中的标准化银行流水")
        lines.append("")
        
        lines.append("=" * 70)
        lines.append("")
        
        index_path = os.path.join(reports_dir, '报告目录清单.txt')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        

