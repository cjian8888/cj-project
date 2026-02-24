#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专项报告生成器 - 穿云审计系统

【功能】
生成8个专项txt报告，每个对应Excel底稿的一个工作表

【报告清单】
1. 借贷行为分析报告.txt
2. 异常收入来源分析报告.txt
3. 时序分析报告.txt
4. 资金穿透分析报告.txt
5. 疑点检测分析报告.txt
6. 行为特征分析报告.txt
7. 资产全貌分析报告.txt
8. 报告目录清单.txt

【修复问题】
- txt报告19行，数据全0，缺失8个专项报告
- 每个专项报告应详细阐述分析过程、发现、审计提示

版本: 1.0.0
日期: 2026-02-03
"""

import os
from datetime import datetime
from typing import Dict, List, Any
import config
import utils

logger = utils.setup_logger(__name__)


class SpecializedReportGenerator:
    """专项报告生成器"""
    
    def __init__(self, analysis_results: Dict, profiles: Dict, 
                 suspicions: Dict, output_dir: str):
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
        
        logger.info(f"[专项报告] 初始化完成，分析结果包含: {', '.join(list(analysis_results.keys()))}")
    
    def generate_all_reports(self) -> List[str]:
        """
        生成所有专项txt报告
        
        Returns:
            生成的文件路径列表
        """
        generated_files = []
        
        # 创建专项报告目录
        reports_dir = os.path.join(self.output_dir, '专项报告')
        os.makedirs(reports_dir, exist_ok=True)
        
        # 生成7个专项报告
        report_generators = [
            ('借贷行为分析报告.txt', self._generate_loan_report),
            ('异常收入来源分析报告.txt', self._generate_income_report),
            ('时序分析报告.txt', self._generate_time_series_report),
            ('资金穿透分析报告.txt', self._generate_penetration_report),
            ('疑点检测分析报告.txt', self._generate_suspicion_report),
            ('行为特征分析报告.txt', self._generate_behavioral_report),
            ('资产全貌分析报告.txt', self._generate_asset_report),
        ]
        
        for filename, generator in report_generators:
            try:
                content = generator()
                if content.strip():  # 只生成非空报告
                    file_path = os.path.join(reports_dir, filename)
                    with open(file_path, 'w', encoding='utf-8') as f:
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
    
    def _generate_loan_report(self) -> str:
        """生成借贷行为分析报告.txt"""
        lines = []

        lines.append("=" * 70)
        lines.append("借贷行为分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        loan_data = self.analysis_results.get('loan', {})
        loan_details = loan_data.get('details', []) if isinstance(loan_data, dict) else []

        bidirectional_flows = []
        regular_repayments = []
        online_loan_platforms = []

        for item in loan_details:
            item_type = item.get('_type', '')
            if item_type == 'bidirectional':
                bidirectional_flows.append({
                    'person1': item.get('person'),
                    'person2': item.get('counterparty'),
                    'a_to_b_total': item.get('income_total', 0),
                    'b_to_a_total': item.get('expense_total', 0),
                    'net_flow': item.get('expense_total', 0) - item.get('income_total', 0),
                    'a_to_b_count': item.get('income_count', 0),
                    'b_to_a_count': item.get('expense_count', 0),
                })
            elif item_type == 'regular_repayment':
                if item.get('is_likely_loan', False):
                    online_loan_platforms.append({
                        'platform': item.get('counterparty'),
                        'amount': item.get('total_amount', 0),
                        'count': item.get('occurrences', 0),
                    })
                else:
                    date_range = item.get('date_range', [None, None])
                    regular_repayments.append({
                        'person': item.get('person'),
                        'counterparty': item.get('counterparty'),
                        'amount': item.get('avg_amount', 0),
                        'count': item.get('occurrences', 0),
                        'avg_days': 30.0,
                        'start_date': date_range[0],
                        'end_date': date_range[1],
                    })

        lines.append("一、双向往来关系分析")
        lines.append("-" * 70)

        if bidirectional_flows:
            for i, flow in enumerate(bidirectional_flows, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  关系方A: {flow.get('person1', '未知')}")
                lines.append(f"  关系方B: {flow.get('person2', '未知')}")
                lines.append(f"  A → B 总金额: {utils.format_currency(flow.get('a_to_b_total', 0))} 元")
                lines.append(f"  B → A 总金额: {utils.format_currency(flow.get('b_to_a_total', 0))} 元")
                lines.append(f"  收支差额: {utils.format_currency(flow.get('net_flow', 0))} 元")
                lines.append(f"   交易频次: A→B {flow.get('a_to_b_count', 0)} 笔, B→A {flow.get('b_to_a_count', 0)} 笔")
                lines.append("")
                lines.append("  【审计提示】: 双向往来可能是资金回流的证据链路，")
                lines.append("            建议核对双方背景关系、交易用途和资金来源。")
                lines.append("")
        else:
            lines.append("  未发现双向往来关系")

        lines.append("")
        lines.append("二、无还款借贷识别")
        lines.append("-" * 70)
        lines.append("  未发现无还款借贷（当前版本暂未实现检测）")

        lines.append("")
        lines.append("三、规律还款分析")
        lines.append("-" * 70)

        if regular_repayments:
            for i, repayment in enumerate(regular_repayments, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  还款人: {repayment.get('person', '未知')}")
                lines.append(f"  还款对手方: {repayment.get('counterparty', '未知')}")
                lines.append(f"  还款金额: {utils.format_currency(repayment.get('amount', 0))} 元")
                lines.append(f"  还款次数: {repayment.get('count', 0)} 笔")
                lines.append(f"  还款周期: 平均每 {repayment.get('avg_days', 0):.1f} 天")
                start_date = repayment.get('start_date', '未知')
                end_date = repayment.get('end_date', '未知')
                if start_date and isinstance(start_date, str):
                    start_date = start_date.split('T')[0]
                if end_date and isinstance(end_date, str):
                    end_date = end_date.split('T')[0]
                lines.append(f"  时间跨度: {start_date} 至 {end_date}")
                lines.append("")
                lines.append("  【审计提示】: 规律性还款可能对应:")
                lines.append("            1. 每月固定还款（房贷、车贷等）")
                lines.append("            2. 定期债务偿还")
                lines.append("            建议核对该规律还款的用途是否与资产匹配，")
                lines.append("            是否存在借贷资金来源不明的情形。")
                lines.append("")
        else:
            lines.append("  未发现规律还款")

        lines.append("")
        lines.append("四、网贷平台交易识别")
        lines.append("-" * 70)

        if online_loan_platforms:
            platform_summary = {}
            for transaction in online_loan_platforms:
                platform = transaction.get('platform', '未知')
                if platform not in platform_summary:
                    platform_summary[platform] = {'count': 0, 'amount': 0.0}
                platform_summary[platform]['count'] += transaction.get('count', 0)
                platform_summary[platform]['amount'] += transaction.get('amount', 0)

            lines.append(f"发现 {len(platform_summary)} 个网贷平台相关交易:")
            lines.append("")
            for platform, stats in platform_summary.items():
                lines.append(f"  平台: {platform}")
                lines.append(f"  交易笔数: {stats['count']} 笔")
                lines.append(f"   交易金额: {utils.format_currency(stats['amount'])} 元")
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
        lines.append("五、综合研判与建议")
        lines.append("-" * 70)

        lines.append("【总体评价】: ")
        if bidirectional_flows or regular_repayments or online_loan_platforms:
            lines.append("  发现多层次借贷行为，建议深入调查借贷关系网络，")
            lines.append("  追踪资金最终用途和来源，评估是否存在利益输送或洗钱风险。")
        else:
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
    
    def _generate_income_report(self) -> str:
        """生成异常收入来源分析报告.txt"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("异常收入来源分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        income_results = self.analysis_results.get('income', {})
        
        # 1. 大额单笔收入分析
        lines.append("一、大额单笔收入分析")
        lines.append("-" * 70)
        
        large_single = income_results.get('large_single_income', [])
        if large_single:
            for i, income in enumerate(large_single, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  收款人: {income.get('name', '未知')}")
                lines.append(f"  收款金额: {utils.format_currency(income.get('amount', 0))} 元")
                lines.append(f"  收款日期: {income.get('date', '未知')}")
                lines.append(f"   付款方: {income.get('counterparty', '未知')}")
                lines.append(f"   交易摘要: {income.get('description', '未知')}")
                lines.append("")
                lines.append("  【审计提示】: 大额单笔收入需核实:")
                lines.append("            1. 收款来源是否合法合规")
                lines.append("            2. 是否与业务往来匹配")
                lines.append("            3. 是否存在代收代付情形")
                lines.append("")
        else:
            lines.append("  未发现大额单笔收入")
        
        lines.append("")
        
        # 2. 疑似分期受贿分析
        lines.append("二、疑似分期受贿分析")
        lines.append("-" * 70)
        
        bribe_installments = income_results.get('potential_bribe_installment', [])
        if bribe_installments:
            for i, case in enumerate(bribe_installments, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  收款人: {case.get('name', '未知')}")
                lines.append(f"  分期模式: 每 {case.get('interval_days', 0)} 天收 {case.get('occurrences', 0)} 次")
                lines.append(f"  单笔金额: {utils.format_currency(case.get('amount', 0))} 元")
                lines.append(f"  总金额: {utils.format_currency(case.get('total', 0))} 元")
                lines.append(f"  时间跨度: {case.get('start_date', '未知')} 至 {case.get('end_date', '未知')}")
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
        
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_time_series_report(self) -> str:
        """生成时序分析报告.txt"""
        lines = []

        lines.append("=" * 70)
        lines.append("时序分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        time_series = self.analysis_results.get('timeSeries', {})
        periodic_income = time_series.get('periodic_income', [])

        lines.append("一、周期性收入分析")
        lines.append("-" * 70)

        if periodic_income:
            for i, income in enumerate(periodic_income, 1):
                lines.append(f"【发现 {i}】")
                lines.append(f"  收款人: {income.get('name', '未知')}")
                lines.append(f"  周期: 每 {income.get('interval_days', 0)} 天")
                lines.append(f"  收款次数: {income.get('occurrences', 0)} 次")
                lines.append(f"  单笔金额范围: {utils.format_currency(income.get('min_amount', 0))} - {utils.format_currency(income.get('max_amount', 0))} 元")
                lines.append(f"  平均金额: {utils.format_currency(income.get('avg_amount', 0))} 元")
                date_range = income.get('date_range', [None, None])
                start = date_range[0]
                end = date_range[1]
                if start and isinstance(start, str):
                    start = start.split('T')[0]
                if end and isinstance(end, str):
                    end = end.split('T')[0]
                lines.append(f"  时间跨度: {start} 至 {end}")
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
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)
    
    def _generate_penetration_report(self) -> str:
        """生成资金穿透分析报告.txt"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("资金穿透分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        penetration = self.analysis_results.get('penetration', {})
        lines.append("【说明】: 资金穿透分析已通过资金流向图谱进行可视化展示。")
        lines.append("本报告重点描述关键发现和审计建议。")
        lines.append("")
        
        lines.append("一、资金闭环检测")
        lines.append("-" * 70)
        
        cycles = penetration.get('fund_cycles', [])
        if cycles:
            for i, cycle in enumerate(cycles, 1):
                lines.append(f"【资金闭环 {i}】")
                lines.append(f"  闭环路径: {' → '.join(cycle.get('nodes', []))}")
                lines.append(f"  闭环长度: {len(cycle.get('nodes', []))} 个节点")
                lines.append(f"  总资金: {utils.format_currency(cycle.get('total_amount', 0))} 元")
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
        
        lines.append("二、过账通道识别")
        lines.append("-" * 70)
        
        pass_throughs = penetration.get('pass_through_nodes', [])
        if pass_throughs:
            for i, node in enumerate(pass_throughs, 1):
                lines.append(f"【过账通道 {i}】")
                lines.append(f"  节点: {node.get('name', '未知')}")
                lines.append(f"  总流入: {utils.format_currency(node.get('total_inflow', 0))} 元")
                lines.append(f"  总流出: {utils.format_currency(node.get('total_outflow', 0))} 元")
                lines.append(f"  净流量: {utils.format_currency(node.get('net_flow', 0))} 元")
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
    
    def _generate_suspicion_report(self) -> str:
        """生成疑点检测分析报告.txt"""
        lines = []

        lines.append("=" * 70)
        lines.append("疑点检测分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        lines.append("一、现金时空伴随检测")
        lines.append("-" * 70)

        # 支持两种键名格式：snake_case 与 camelCase，确保向后兼容
        cash_collisions = self.suspicions.get('cash_collisions', []) or self.suspicions.get('cashCollisions', [])
        if cash_collisions:
            for i, collision in enumerate(cash_collisions, 1):
                lines.append(f"【现金伴随 {i}】")
                lines.append(f"  取现方: {collision.get('withdrawal_entity', '未知')}")
                lines.append(f"  存现方: {collision.get('deposit_entity', '未知')}")
                lines.append(f"  取现时间: {collision.get('withdrawal_date', '未知')}")
                lines.append(f"  存现时间: {collision.get('deposit_date', '未知')}")
                lines.append(f"  时间差: {collision.get('time_diff_hours', 0):.1f} 小时")
                lines.append(f"  取现金额: {utils.format_currency(collision.get('withdrawal_amount', 0))} 元")
                lines.append(f"  存现金额: {utils.format_currency(collision.get('deposit_amount', 0))} 元")
                lines.append("")
                risk_level = collision.get('risk_level', 'low')
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
        lines.append("二、直接资金往来分析")
        lines.append("-" * 70)

        # 支持两种键名格式：snake_case 与 camelCase，确保向后兼容
        direct_transfers = self.suspicions.get('direct_transfers', []) or self.suspicions.get('directTransfers', [])
        if direct_transfers:
            for i, transfer in enumerate(direct_transfers, 1):
                lines.append(f"【直接往来 {i}】")
                lines.append(f"  交易人: {transfer.get('person', '未知')}")
                lines.append(f"  对方: {transfer.get('company', '未知')}")
                lines.append(f"  交易时间: {transfer.get('date', '未知')}")
                lines.append(f"  交易金额: {utils.format_currency(transfer.get('amount', 0))} 元")
                lines.append(f"   方向: {transfer.get('direction', '未知')}")
                lines.append(f"   摘要: {transfer.get('description', '未知')}")
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
        lines.append("三、反洗钱预警")
        lines.append("-" * 70)

        aml_alerts = self.suspicions.get('amlAlerts', [])
        if aml_alerts:
            for alert in aml_alerts:
                name = alert.get('name', '未知')
                alert_type = alert.get('alert_type', '未知')
                lines.append(f"【预警】{name} - {alert_type}")
                suspicious_count = alert.get('suspicious_transaction_count', 0)
                large_count = alert.get('large_transaction_count', 0)
                lines.append(f"  可疑交易数: {suspicious_count}")
                lines.append(f"  大额交易数: {large_count}")
                lines.append("")
        else:
            lines.append("  未发现反洗钱预警")

        lines.append("")
        lines.append("四、征信预警")
        lines.append("-" * 70)

        credit_alerts = self.suspicions.get('creditAlerts', [])
        if credit_alerts:
            for alert in credit_alerts:
                name = alert.get('name', '未知')
                alert_type = alert.get('alert_type', '未知')
                count = alert.get('count', 0)
                lines.append(f"【预警】{name} - {alert_type} ({count} 次)")
                lines.append("")
        else:
            lines.append("  未发现征信预警")

        lines.append("")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)
    
    def _generate_behavioral_report(self) -> str:
        """生成行为特征分析报告.txt"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("行为特征分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        behavioral = self.analysis_results.get('behavioral', {})
        
        lines.append("一、快进快出检测")
        lines.append("-" * 70)
        
        fast_in_out = behavioral.get('fast_in_out', [])
        if fast_in_out:
            for i, pattern in enumerate(fast_in_out, 1):
                lines.append(f"【快进快出 {i}】")
                lines.append(f"  人员: {pattern.get('name', '未知')}")
                lines.append(f"  流入时间: {pattern.get('in_time', '未知')}")
                lines.append(f"  流出时间: {pattern.get('out_time', '未知')}")
                lines.append(f"  时间差: {pattern.get('time_diff_hours', 0):.1f} 小时")
                lines.append(f"  流入金额: {utils.format_currency(pattern.get('in_amount', 0))} 元")
                lines.append(f"  流出金额: {utils.format_currency(pattern.get('out_amount', 0))} 元")
                lines.append("")
                lines.append("  【审计提示】: 快进快出特征:")
                lines.append("            1. 资金在账户内停留时间极短")
                lines.append("            2. 可能是过账或洗钱")
                lines.append("            3. 规避银行系统监控")
                lines.append("            建议核查资金用途，")
                lines.append("            排查是否与洗钱团伙相关。")
                lines.append("")
        else:
            lines.append("  未发现快进快出模式")
        
        lines.append("")
        
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_asset_report(self) -> str:
        """生成资产全貌分析报告.txt"""
        lines = []
        
        lines.append("=" * 70)
        lines.append("资产全貌分析报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 统计房产信息
        property_count = 0
        property_value = 0.0
        
        for name, profile in self.profiles.items():
            properties = profile.get('properties_precise', [])
            if properties:
                property_count += len(properties)
                for prop in properties:
                    property_value += prop.get('transaction_amount', 0)
        
        lines.append(f"【资产统计】")
        lines.append(f"  房产总数: {property_count} 套")
        lines.append(f"  房产总价值: {utils.format_currency(property_value)} 元")
        lines.append("")
        
        # 房产明细
        lines.append("【房产明细】")
        lines.append("-" * 70)
        
        if property_count > 0:
            idx = 1
            for name, profile in self.profiles.items():
                properties = profile.get('properties_precise', [])
                if properties:
                    for prop in properties:
                        lines.append(f"【房产 {idx}】")
                        lines.append(f"  产权人: {prop.get('owner_name', '未知')}")
                        lines.append(f"  房地坐落: {prop.get('location', '未知')}")
                        lines.append(f"  建筑面积: {prop.get('area', '未知')} ㎡")
                        lines.append(f"  交易金额: {utils.format_currency(prop.get('transaction_amount', 0))} 元")
                        lines.append(f"  登记时间: {prop.get('registration_date', '未知')}")
                        lines.append("")
                        idx += 1
        else:
            lines.append("  未发现房产数据")
        
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
        html_files = [f for f in generated_files if f.endswith('.html')]
        excel_files = [f for f in generated_files if f.endswith('.xlsx')]
        txt_files = [f for f in generated_files if f.endswith('.txt')]
        
        if html_files:
            lines.append("【HTML专业报告】")
            for filepath in html_files:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) / 1024  # KB
                lines.append(f"  • {filename} ({file_size:.1f} KB) - 综合分析报告")
            lines.append("")
        
        if txt_files:
            lines.append("【专项txt报告】")
            for filepath in txt_files:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) / 1024  # KB
                lines.append(f"  • {filename} ({file_size:.1f} KB) - 深度分析报告")
            lines.append("")
        
        if excel_files:
            lines.append("【Excel数据底稿】")
            for filepath in excel_files:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) / 1024  # KB
                lines.append(f"  • {filename} ({file_size:.1f} KB) - 完整数据底稿")
            lines.append("")
        
        lines.append("-" * 70)
        lines.append("")
        lines.append("【使用说明】:")
        lines.append("  1. 优先查看'初查报告_v4.html'获取完整分析")
        lines.append("  2. 需要深入某个方面时，查看对应的专项报告txt")
        lines.append("  3. 需要数据底稿时，打开'资金核查底稿.xlsx'")
        lines.append("  4. 所有分析基于 output/cleaned_data/ 中的标准化银行流水")
        lines.append("")
        
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)
