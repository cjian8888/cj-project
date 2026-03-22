import { useMemo, type ElementType } from 'react';
import {
  AlertTriangle,
  CreditCard,
  Download,
  Link2,
  ShieldCheck,
  Smartphone,
  Wallet,
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { EmptyState } from './common/EmptyState';
import {
  formatCurrency,
  formatDate,
  formatRiskLevel,
  getRiskLevelColors,
  sanitizeValue,
} from '../utils/formatters';

interface SummaryCardProps {
  label: string;
  value: string;
  hint: string;
  icon: ElementType;
  tone: string;
}

function SummaryCard({ label, value, hint, icon: Icon, tone }: SummaryCardProps) {
  return (
    <div className="glass rounded-2xl border theme-border p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] theme-text-dim">{label}</p>
          <p className="text-2xl font-semibold theme-text-secondary mt-2">{value}</p>
        </div>
        <div className={`w-11 h-11 rounded-2xl flex items-center justify-center ${tone}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <p className="text-sm theme-text-dim">{hint}</p>
    </div>
  );
}

function CounterpartyList({
  title,
  items,
}: {
  title: string;
  items: Array<{ name: string; count: number; totalAmountYuan: number }>;
}) {
  return (
    <div className="rounded-2xl border theme-border p-4 theme-bg-muted">
      <div className="flex items-center gap-2 mb-3">
        <Link2 className="w-4 h-4 text-cyan-400" />
        <h4 className="text-sm font-medium theme-text-secondary">{title}</h4>
      </div>
      {items.length === 0 ? (
        <p className="text-sm theme-text-dim">暂无可展示的对手方摘要</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={`${title}-${item.name}`}
              className="flex items-center justify-between gap-4 rounded-xl px-3 py-2 theme-bg-hover"
            >
              <div className="min-w-0">
                <p className="text-sm theme-text-secondary truncate">{sanitizeValue(item.name)}</p>
                <p className="text-xs theme-text-dim">{item.count} 笔</p>
              </div>
              <span className="text-sm font-medium text-cyan-300 whitespace-nowrap">
                {formatCurrency(item.totalAmountYuan)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function WalletSupplementTab() {
  const { data, analysis } = useApp();
  const walletData = data.walletData;
  const highRiskAlerts = useMemo(
    () =>
      [...(data.suspicions.walletAlerts || [])]
        .filter((alert) => (alert.riskLevel || '').toLowerCase() === 'high')
        .sort((a, b) => (b.amount || 0) - (a.amount || 0)),
    [data.suspicions.walletAlerts],
  );

  const subjects = useMemo(
    () => [...(walletData.subjects || [])].sort((a, b) => {
      const aCount = (a.platforms.alipay.transactionCount || 0) + (a.platforms.wechat.tenpayTransactionCount || 0);
      const bCount = (b.platforms.alipay.transactionCount || 0) + (b.platforms.wechat.tenpayTransactionCount || 0);
      return bCount - aCount;
    }),
    [walletData.subjects],
  );

  const handleExportFocusList = () => {
    const lines: string[] = [];
    const now = new Date();
    const timestamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    const fileStamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}${String(now.getSeconds()).padStart(2, '0')}`;

    lines.push('电子钱包重点核查清单（前端精简导出）');
    lines.push('='.repeat(36));
    lines.push(`导出时间: ${timestamp}`);
    lines.push(`高风险电子钱包预警数: ${highRiskAlerts.length}`);
    lines.push(`未归并微信账号数: ${walletData.unmatchedWechatAccounts.length}`);
    lines.push('');
    lines.push('一、高风险电子钱包预警');
    if (highRiskAlerts.length === 0) {
      lines.push('- 当前没有 high 级别的电子钱包预警。');
    } else {
      highRiskAlerts.forEach((alert, index) => {
        lines.push(
          `${index + 1}. ${sanitizeValue(alert.person)} -> ${sanitizeValue(alert.counterparty)} | ${formatDate(alert.date)} | ${formatCurrency(alert.amount)}`,
        );
        lines.push(`   描述: ${sanitizeValue(alert.description, '暂无描述')}`);
        lines.push(`   原因: ${sanitizeValue(alert.riskReason, '暂无原因说明')}`);
      });
    }

    lines.push('');
    lines.push('二、未归并微信账号');
    if (walletData.unmatchedWechatAccounts.length === 0) {
      lines.push('- 当前没有待映射的微信账号。');
    } else {
      walletData.unmatchedWechatAccounts.forEach((item, index) => {
        lines.push(
          `${index + 1}. 手机号 ${sanitizeValue(item.phone)} | 微信号 ${sanitizeValue(item.wxid)} | 别名 ${sanitizeValue(item.alias)} | 昵称 ${sanitizeValue(item.nickname, item.phone)}`,
        );
        lines.push(
          `   注册时间 ${formatDate(item.registeredAt)} | 最近登录 ${formatDate(item.latestLoginAt)} | 登录 ${item.loginEventCount || 0} 次`,
        );
      });
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `电子钱包重点核查清单_前端导出_${fileStamp}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  if (analysis.status !== 'completed') {
    return <EmptyState message="完成主分析后，这里会显示微信 / 支付宝 / 财付通电子钱包摘要。" />;
  }

  if (!walletData.available) {
    return (
      <div className="space-y-6">
        <EmptyState message="未检测到电子钱包数据。把样本包放入输入目录下的“补充数据/电子钱包/”后重新分析即可。" />
        <div className="glass rounded-2xl border theme-border p-6 space-y-3">
          <h3 className="text-lg font-semibold theme-text-secondary">推荐放置目录</h3>
          <div className="rounded-xl theme-bg-muted p-4 border theme-border">
            <code className="text-sm text-cyan-300">
              {walletData.directoryPolicy.recommendedPath}
            </code>
          </div>
          {walletData.notes.length > 0 && (
            <div className="space-y-2">
              {walletData.notes.map((note) => (
                <p key={note} className="text-sm theme-text-dim">{note}</p>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard
          label="匹配主体"
          value={`${walletData.summary.coreMatchedSubjectCount}/${walletData.summary.subjectCount}`}
          hint="已能映射到当前核查主体的电子钱包对象"
          icon={ShieldCheck}
          tone="bg-emerald-500/15 text-emerald-300"
        />
        <SummaryCard
          label="支付宝交易"
          value={`${walletData.summary.alipayTransactionCount}`}
          hint={`${walletData.summary.alipayAccountCount} 个实名账户`}
          icon={Wallet}
          tone="bg-sky-500/15 text-sky-300"
        />
        <SummaryCard
          label="财付通交易"
          value={`${walletData.summary.tenpayTransactionCount}`}
          hint={`${walletData.summary.tenpayAccountCount} 个财付通账号`}
          icon={CreditCard}
          tone="bg-cyan-500/15 text-cyan-300"
        />
        <SummaryCard
          label="未归并微信"
          value={`${walletData.summary.unmatchedWechatCount}`}
          hint={`${walletData.summary.loginEventCount} 条登录轨迹已纳入补充层`}
          icon={Smartphone}
          tone="bg-amber-500/15 text-amber-300"
        />
      </div>

      <div className="glass rounded-[28px] border theme-border p-6 space-y-5">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-300" />
              <h3 className="text-lg font-semibold theme-text-secondary">重点核查清单</h3>
            </div>
            <p className="text-sm theme-text-dim mt-2">
              这里直接聚焦两类最需要人工跟进的对象：高风险电子钱包预警，以及仍未归并到实名主体的微信账号。
            </p>
          </div>
          <div className="space-y-3 min-w-0 lg:min-w-[320px]">
            <button
              onClick={handleExportFocusList}
              className="w-full rounded-2xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-3 text-sm font-medium text-cyan-200 transition-colors hover:bg-cyan-500/15 flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4" />
              导出当前重点清单
            </button>
            <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
              <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">高风险预警</p>
              <p className="text-2xl font-semibold theme-text-secondary mt-2">{highRiskAlerts.length}</p>
              <p className="text-xs theme-text-dim mt-1">仅展示 `high` 级别电子钱包命中</p>
            </div>
            <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
              <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">待映射账号</p>
              <p className="text-2xl font-semibold theme-text-secondary mt-2">{walletData.unmatchedWechatAccounts.length}</p>
              <p className="text-xs theme-text-dim mt-1">建议补充手机号 / 别名 / 实名映射</p>
            </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="rounded-[24px] border theme-border p-5 theme-bg-muted space-y-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-300" />
              <h4 className="text-sm font-semibold theme-text-secondary">高风险电子钱包预警</h4>
            </div>
            {highRiskAlerts.length === 0 ? (
              <p className="text-sm theme-text-dim">当前没有 `high` 级别的电子钱包预警。</p>
            ) : (
              <div className="space-y-3">
                {highRiskAlerts.map((alert, index) => {
                  const tone = getRiskLevelColors(alert.riskLevel);
                  return (
                    <div key={`${alert.person}-${alert.counterparty}-${index}`} className="rounded-2xl border theme-border p-4 theme-bg-hover">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-medium theme-text-secondary">
                            {sanitizeValue(alert.person)} → {sanitizeValue(alert.counterparty)}
                          </p>
                          <p className="text-xs theme-text-dim mt-1">
                            {formatDate(alert.date)} · {formatCurrency(alert.amount)}
                          </p>
                        </div>
                        <span className={`px-2.5 py-1 rounded-full text-xs border ${tone.bg} ${tone.text} ${tone.border}`}>
                          {formatRiskLevel(alert.riskLevel)}
                        </span>
                      </div>
                      <p className="text-sm theme-text-dim mt-3 leading-6">
                        {sanitizeValue(alert.description, '暂无描述')}
                      </p>
                      {alert.riskReason && (
                        <div className="mt-3 rounded-xl border theme-border px-3 py-2 bg-black/10">
                          <p className="text-xs uppercase tracking-[0.14em] theme-text-dim">核查原因</p>
                          <p className="text-sm theme-text-secondary mt-1 leading-6">
                            {sanitizeValue(alert.riskReason)}
                          </p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="rounded-[24px] border theme-border p-5 theme-bg-muted space-y-4">
            <div className="flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-amber-300" />
              <h4 className="text-sm font-semibold theme-text-secondary">未归并微信账号</h4>
            </div>
            {walletData.unmatchedWechatAccounts.length === 0 ? (
              <p className="text-sm theme-text-dim">当前没有待映射的微信账号。</p>
            ) : (
              <div className="space-y-3">
                {walletData.unmatchedWechatAccounts.map((item) => (
                  <div key={`focus-${item.phone}-${item.wxid}`} className="rounded-2xl border theme-border p-4 theme-bg-hover">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium theme-text-secondary">
                          {sanitizeValue(item.nickname, item.phone)}
                        </p>
                        <p className="text-xs theme-text-dim mt-1">
                          手机号 {sanitizeValue(item.phone)} · 登录 {item.loginEventCount || 0} 次
                        </p>
                      </div>
                      <span className="px-2.5 py-1 rounded-full text-xs border border-amber-400/30 bg-amber-500/10 text-amber-300">
                        待映射
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs theme-text-dim">
                      <div>微信号: {sanitizeValue(item.wxid)}</div>
                      <div>别名: {sanitizeValue(item.alias)}</div>
                      <div>注册时间: {formatDate(item.registeredAt)}</div>
                      <div>最近登录: {formatDate(item.latestLoginAt)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="glass rounded-2xl border theme-border p-6 space-y-3">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-300" />
          <h3 className="text-lg font-semibold theme-text-secondary">接入规则</h3>
        </div>
        <p className="text-sm theme-text-dim">
          电子钱包数据是补充层，不写入银行主清洗链，只进入 `analysis_cache/walletData.json`。
        </p>
        <div className="rounded-xl theme-bg-muted p-4 border theme-border">
          <code className="text-sm text-cyan-300">{walletData.directoryPolicy.recommendedPath}</code>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-sm theme-text-dim">
          <div className="rounded-xl theme-bg-hover p-4 border theme-border">
            支付宝文件: 注册 {walletData.sourceStats.alipayRegistrationFiles} 个，明细 {walletData.sourceStats.alipayTransactionFiles} 个
          </div>
          <div className="rounded-xl theme-bg-hover p-4 border theme-border">
            微信 / 财付通文件: 注册 {walletData.sourceStats.wechatRegistrationFiles + walletData.sourceStats.tenpayRegistrationFiles} 个，行为 {walletData.sourceStats.wechatLoginFiles + walletData.sourceStats.tenpayTransactionFiles} 个
          </div>
        </div>
      </div>

      {walletData.unmatchedWechatAccounts.length > 0 && (
        <div className="glass rounded-2xl border theme-border p-6 space-y-4">
          <div className="flex items-center gap-3">
            <Smartphone className="w-5 h-5 text-amber-300" />
            <h3 className="text-lg font-semibold theme-text-secondary">未自动归并的微信账号</h3>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {walletData.unmatchedWechatAccounts.map((item) => (
              <div key={item.phone} className="rounded-2xl border theme-border p-4 theme-bg-muted">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium theme-text-secondary">{sanitizeValue(item.nickname, item.phone)}</p>
                    <p className="text-xs theme-text-dim">{item.phone}</p>
                  </div>
                  <span className="text-xs px-2 py-1 rounded-full bg-amber-500/15 text-amber-300">
                    待映射
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs theme-text-dim">
                  <div>微信号: {sanitizeValue(item.wxid)}</div>
                  <div>别名: {sanitizeValue(item.alias)}</div>
                  <div>注册时间: {formatDate(item.registeredAt)}</div>
                  <div>登录记录: {item.loginEventCount || 0}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        {subjects.length === 0 ? (
          <EmptyState message="已检测到电子钱包目录，但当前没有生成可展示的主体摘要。" />
        ) : (
          subjects.map((subject) => (
            <section key={subject.subjectId} className="glass rounded-[28px] border theme-border p-6 space-y-5">
              <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h3 className="text-xl font-semibold theme-text-secondary">{subject.subjectName}</h3>
                    <span
                      className={`text-xs px-3 py-1 rounded-full border ${
                        subject.matchedToCore
                          ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300'
                          : 'border-amber-400/30 bg-amber-500/10 text-amber-300'
                      }`}
                    >
                      {subject.matchedToCore ? '已映射到主链主体' : '仅存在于补充层'}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {subject.phones.length > 0 ? subject.phones.map((phone) => (
                      <span key={phone} className="px-3 py-1 rounded-full theme-bg-muted text-xs theme-text-dim">
                        {phone}
                      </span>
                    )) : (
                      <span className="px-3 py-1 rounded-full theme-bg-muted text-xs theme-text-dim">无手机号映射</span>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 min-w-0 xl:min-w-[520px]">
                  <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
                    <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">支付宝</p>
                    <p className="text-lg font-semibold theme-text-secondary mt-2">
                      {subject.platforms.alipay.accountCount} 账户
                    </p>
                    <p className="text-xs theme-text-dim mt-1">{subject.platforms.alipay.transactionCount} 笔有效交易</p>
                  </div>
                  <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
                    <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">微信</p>
                    <p className="text-lg font-semibold theme-text-secondary mt-2">
                      {subject.platforms.wechat.wechatAccountCount} 账号
                    </p>
                    <p className="text-xs theme-text-dim mt-1">{subject.platforms.wechat.loginEventCount} 条登录记录</p>
                  </div>
                  <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
                    <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">财付通</p>
                    <p className="text-lg font-semibold theme-text-secondary mt-2">
                      {subject.platforms.wechat.tenpayAccountCount} 账号
                    </p>
                    <p className="text-xs theme-text-dim mt-1">{subject.platforms.wechat.tenpayTransactionCount} 笔交易</p>
                  </div>
                  <div className="rounded-2xl theme-bg-muted p-4 border theme-border">
                    <p className="text-xs uppercase tracking-[0.16em] theme-text-dim">跨平台信号</p>
                    <p className="text-lg font-semibold theme-text-secondary mt-2">
                      {subject.crossSignals.phoneOverlapCount + subject.crossSignals.bankCardOverlapCount + subject.crossSignals.aliasMatchCount}
                    </p>
                    <p className="text-xs theme-text-dim mt-1">手机号 / 卡 / 别名重叠</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div className="rounded-[24px] border theme-border p-5 theme-bg-muted space-y-4">
                  <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4 text-sky-300" />
                    <h4 className="text-sm font-semibold theme-text-secondary">支付宝摘要</h4>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">收入总额</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatCurrency(subject.platforms.alipay.incomeTotalYuan)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">支出总额</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatCurrency(subject.platforms.alipay.expenseTotalYuan)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">首笔交易</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatDate(subject.platforms.alipay.firstTransactionAt)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">末笔交易</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatDate(subject.platforms.alipay.lastTransactionAt)}</p>
                    </div>
                  </div>
                  <CounterpartyList title="支付宝主要对手方" items={subject.platforms.alipay.topCounterparties} />
                </div>

                <div className="rounded-[24px] border theme-border p-5 theme-bg-muted space-y-4">
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-cyan-300" />
                    <h4 className="text-sm font-semibold theme-text-secondary">微信 / 财付通摘要</h4>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">财付通收入</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatCurrency(subject.platforms.wechat.incomeTotalYuan)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">财付通支出</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatCurrency(subject.platforms.wechat.expenseTotalYuan)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">最近登录</p>
                      <p className="theme-text-secondary font-medium mt-1">{formatDate(subject.platforms.wechat.latestLoginAt)}</p>
                    </div>
                    <div className="rounded-xl theme-bg-hover p-3">
                      <p className="theme-text-dim text-xs">银行卡重叠</p>
                      <p className="theme-text-secondary font-medium mt-1">{subject.crossSignals.bankCardOverlapCount} 张</p>
                    </div>
                  </div>
                  <CounterpartyList title="财付通主要对手方" items={subject.platforms.wechat.topCounterparties} />
                </div>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_0.9fr] gap-4">
                <div className="rounded-2xl border theme-border p-4 theme-bg-muted">
                  <div className="flex items-center gap-2 mb-3">
                    <Link2 className="w-4 h-4 text-cyan-300" />
                    <h4 className="text-sm font-semibold theme-text-secondary">匹配依据</h4>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {subject.crossSignals.matchBasis.length > 0 ? subject.crossSignals.matchBasis.map((basis) => (
                      <span key={basis} className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-200 text-xs border border-cyan-500/20">
                        {basis}
                      </span>
                    )) : (
                      <span className="text-sm theme-text-dim">当前仅按补充层主体展示</span>
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border theme-border p-4 theme-bg-muted">
                  <div className="flex items-center gap-2 mb-3">
                    <ShieldCheck className="w-4 h-4 text-emerald-300" />
                    <h4 className="text-sm font-semibold theme-text-secondary">电子钱包结论</h4>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {subject.signals.length > 0 ? subject.signals.map((signal) => (
                      <span key={signal} className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-200 text-xs border border-emerald-500/20">
                        {signal}
                      </span>
                    )) : (
                      <span className="text-sm theme-text-dim">暂无自动结论</span>
                    )}
                  </div>
                </div>
              </div>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
