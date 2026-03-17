import type {
    AmlAlert,
    CashCollision,
    CashTimingPattern,
    CreditAlert,
    HolidayTransaction,
    SuspicionResult,
    SuspiciousTransaction,
    TimeSeriesAlert,
    WalletAlert,
} from '../types';

export type RiskActivityType =
    | 'direct'
    | 'cash'
    | 'timing'
    | 'holiday'
    | 'wallet'
    | 'aml'
    | 'credit';

export interface RiskActivity {
    type: RiskActivityType;
    date: string;
    from: string;
    to: string;
    amount: number | null;
    description: string;
    riskLevel: string;
    timeDiff?: number | null;
}

export interface RiskActivityGroups {
    all: RiskActivity[];
    direct: RiskActivity[];
    cash: RiskActivity[];
    timing: RiskActivity[];
    holiday: RiskActivity[];
    wallet: RiskActivity[];
    aml: RiskActivity[];
    credit: RiskActivity[];
}

const toAmount = (value: unknown): number => {
    const amount = Number(value);
    return Number.isFinite(amount) ? amount : 0;
};

const normalizeText = (value: unknown): string => {
    if (value === null || value === undefined) {
        return '';
    }

    return String(value).replace(/\s+/g, ' ').trim();
};

const directTransferScore = (tx: SuspiciousTransaction): number => {
    let score = 0;
    if (normalizeText(tx.sourceFile)) {
        score += 2;
    }
    if (normalizeText(tx.transactionId)) {
        score += 1;
    }
    if (typeof tx.sourceRowIndex === 'number') {
        score += 1;
    }
    return score;
};

const buildDirectTransferKey = (tx: SuspiciousTransaction): string => {
    return [
        normalizeText(tx.from),
        normalizeText(tx.to),
        normalizeText(tx.direction),
        toAmount(tx.amount).toFixed(2),
        normalizeText(tx.date),
        normalizeText(tx.description || '核心人员与涉案企业直接资金往来'),
    ].join('|');
};

export const dedupeDirectTransfers = (
    transfers: SuspiciousTransaction[] = [],
): SuspiciousTransaction[] => {
    const deduped = new Map<string, SuspiciousTransaction>();

    for (const tx of transfers) {
        const key = buildDirectTransferKey(tx);
        const existing = deduped.get(key);
        if (!existing || directTransferScore(tx) > directTransferScore(existing)) {
            deduped.set(key, tx);
        }
    }

    return Array.from(deduped.values());
};

const resolvePairAmount = (...values: unknown[]): number | null => {
    const amount = Math.max(...values.map(toAmount), 0);
    return amount > 0 ? amount : null;
};

const resolveRiskLevel = (...values: Array<string | undefined | null>): string => {
    for (const value of values) {
        const normalized = normalizeText(value);
        if (normalized) {
            return normalized;
        }
    }
    return 'medium';
};

const resolveTimeSeriesDescription = (alert: TimeSeriesAlert): string => {
    return (
        normalizeText(alert.description)
        || normalizeText(alert.riskReason)
        || normalizeText(alert.risk_reason)
        || normalizeText(alert.alertType)
        || normalizeText(alert.alert_type)
        || normalizeText(alert.anomalyType)
        || normalizeText(alert.anomaly_type)
        || '时间序列异常预警'
    );
};

const resolveAmlDescription = (alert: AmlAlert): string => {
    const alertType = normalizeText(alert.alertType || alert.alert_type) || '反洗钱查询命中';
    const suspiciousCount = toAmount(alert.suspiciousTransactionCount ?? alert.suspicious_transaction_count);
    const largeCount = toAmount(alert.largeTransactionCount ?? alert.large_transaction_count);
    const paymentCount = toAmount(alert.paymentTransactionCount ?? alert.payment_transaction_count);

    const details = [
        suspiciousCount > 0 ? `可疑交易${suspiciousCount}笔` : '',
        largeCount > 0 ? `大额交易${largeCount}笔` : '',
        paymentCount > 0 ? `支付交易${paymentCount}笔` : '',
    ].filter(Boolean);

    return details.length > 0 ? `${alertType}；${details.join('，')}` : alertType;
};

const resolveCreditDescription = (alert: CreditAlert): string => {
    const alertType = normalizeText(alert.alertType || alert.alert_type) || '征信预警';
    const count = toAmount(alert.count);
    return count > 0 ? `${alertType}（${count}次）` : alertType;
};

const resolveHolidayDescription = (record: HolidayTransaction): string => {
    return (
        normalizeText(record.riskReason)
        || normalizeText(record.description)
        || normalizeText(record.holidayName)
        || '节假日敏感交易'
    );
};

const toSortableTimestamp = (value: string): number => {
    if (!value) {
        return Number.NEGATIVE_INFINITY;
    }

    const timestamp = Date.parse(value);
    return Number.isFinite(timestamp) ? timestamp : Number.NEGATIVE_INFINITY;
};

const sortActivities = (activities: RiskActivity[]): RiskActivity[] => {
    return [...activities].sort((left, right) => {
        return toSortableTimestamp(right.date) - toSortableTimestamp(left.date);
    });
};

const buildDirectActivities = (
    transfers: SuspiciousTransaction[],
): RiskActivity[] => {
    return dedupeDirectTransfers(transfers).map((tx) => ({
        type: 'direct',
        date: tx.date,
        from: tx.from,
        to: tx.to,
        amount: resolvePairAmount(tx.amount),
        description: normalizeText(tx.description) || '核心人员与涉案企业直接资金往来',
        riskLevel: resolveRiskLevel(tx.riskLevel),
    }));
};

const buildCashActivities = (items: CashCollision[]): RiskActivity[] => {
    return items.map((item) => ({
        type: 'cash',
        date: item.time1,
        from: item.person1,
        to: item.person2,
        amount: resolvePairAmount(
            item.amount1,
            item.amount2,
            (item as CashCollision & { amount?: number }).amount,
        ),
        timeDiff: item.timeDiff ?? null,
        description: normalizeText(item.riskReason) || '现金取存时间差异常，疑似绕开银行转账监控',
        riskLevel: resolveRiskLevel(item.riskLevel),
    }));
};

const buildTimingActivities = (
    timingPatterns: CashTimingPattern[],
    timeSeriesAlerts: TimeSeriesAlert[],
): RiskActivity[] => {
    const cashTimingActivities = timingPatterns.map((item) => ({
        type: 'timing' as const,
        date: item.time1 || '',
        from: item.person1 || '-',
        to: item.person2 || '-',
        amount: resolvePairAmount(item.amount1, item.amount2),
        timeDiff: item.timeDiff ?? null,
        description: normalizeText(item.riskReason || item.description) || '取现与存入存在时序规律，需进一步核查',
        riskLevel: resolveRiskLevel(item.riskLevel),
    }));

    const seriesActivities = timeSeriesAlerts.map((item) => ({
        type: 'timing' as const,
        date: normalizeText(item.date || item.timestamp),
        from: normalizeText(item.person || item.name || item.entity) || '-',
        to: normalizeText(item.counterparty) || '-',
        amount: resolvePairAmount(item.amount),
        description: resolveTimeSeriesDescription(item),
        riskLevel: resolveRiskLevel(item.riskLevel, item.risk_level),
    }));

    return [...cashTimingActivities, ...seriesActivities];
};

const buildHolidayActivities = (
    holidayTransactions: Record<string, HolidayTransaction[]>,
): RiskActivity[] => {
    return Object.entries(holidayTransactions || {}).flatMap(([entityName, records]) =>
        records.map((record) => {
            const direction = normalizeText(record.direction);
            const counterparty = normalizeText(record.counterparty) || '-';
            const isIncome = direction === 'income' || direction === 'receive';

            return {
                type: 'holiday' as const,
                date: record.date,
                from: isIncome ? counterparty : entityName,
                to: isIncome ? entityName : counterparty,
                amount: resolvePairAmount(record.amount),
                description: resolveHolidayDescription(record),
                riskLevel: resolveRiskLevel(record.riskLevel),
            };
        }),
    );
};

const buildWalletActivities = (alerts: WalletAlert[]): RiskActivity[] => {
    return alerts.map((alert) => ({
        type: 'wallet',
        date: alert.date || '',
        from: alert.person || '-',
        to: alert.counterparty || '-',
        amount: resolvePairAmount(alert.amount),
        description: normalizeText(alert.description || alert.riskReason) || '电子钱包补充数据命中预警规则',
        riskLevel: resolveRiskLevel(alert.riskLevel),
    }));
};

const buildAmlActivities = (alerts: AmlAlert[]): RiskActivity[] => {
    return alerts.map((alert) => ({
        type: 'aml',
        date: '',
        from: normalizeText(alert.name) || '-',
        to: normalizeText(alert.source) || 'AML查询',
        amount: null,
        description: resolveAmlDescription(alert),
        riskLevel: resolveRiskLevel(alert.riskLevel),
    }));
};

const buildCreditActivities = (alerts: CreditAlert[]): RiskActivity[] => {
    return alerts.map((alert) => ({
        type: 'credit',
        date: '',
        from: normalizeText(alert.name) || '-',
        to: normalizeText(alert.source) || '征信数据',
        amount: null,
        description: resolveCreditDescription(alert),
        riskLevel: resolveRiskLevel(alert.riskLevel),
    }));
};

export const buildRiskActivityGroups = (
    suspicions: SuspicionResult,
): RiskActivityGroups => {
    const direct = buildDirectActivities(suspicions.directTransfers || []);
    const cash = buildCashActivities(suspicions.cashCollisions || []);
    const timing = buildTimingActivities(
        suspicions.cashTimingPatterns || [],
        suspicions.timeSeriesAlerts || [],
    );
    const holiday = buildHolidayActivities(suspicions.holidayTransactions || {});
    const wallet = buildWalletActivities(suspicions.walletAlerts || []);
    const aml = buildAmlActivities(suspicions.amlAlerts || []);
    const credit = buildCreditActivities(suspicions.creditAlerts || []);

    return {
        direct: sortActivities(direct),
        cash: sortActivities(cash),
        timing: sortActivities(timing),
        holiday: sortActivities(holiday),
        wallet: sortActivities(wallet),
        aml: sortActivities(aml),
        credit: sortActivities(credit),
        all: sortActivities([
            ...direct,
            ...cash,
            ...timing,
            ...holiday,
            ...wallet,
            ...aml,
            ...credit,
        ]),
    };
};

export const calculateRiskDashboardMetrics = (suspicions: SuspicionResult) => {
    const groups = buildRiskActivityGroups(suspicions);
    const transactionAmount = [
        ...groups.direct,
        ...groups.cash,
        ...groups.timing,
    ].reduce((sum, item) => sum + (item.amount || 0), 0);

    return {
        groups,
        suspicionCount: groups.all.length,
        transactionRiskAmount: transactionAmount,
        transactionClueCount: [
            ...groups.direct,
            ...groups.cash,
            ...groups.timing,
        ].length,
    };
};
