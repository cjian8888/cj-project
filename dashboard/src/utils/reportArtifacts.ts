import type { Report, ReportGroup, ReportSemanticOverview } from '../services/api';

const BUSINESS_REPORT_GROUP_KEYS = new Set(['primary_reports', 'appendices']);
const BUSINESS_REPORT_EXTENSIONS = new Set(['html', 'htm', 'pdf', 'txt']);

function normalizeReportFilename(report: Report): string {
    return String(report.filename || report.name || '').trim();
}

function normalizeReportPath(report: Report): string {
    return String(report.path || normalizeReportFilename(report))
        .replace(/\\/g, '/')
        .trim()
        .toLowerCase();
}

function normalizeReportExtension(report: Report): string {
    const explicitExtension = String(report.extension || '').trim().toLowerCase().replace(/^\./, '');
    if (explicitExtension) {
        return explicitExtension;
    }

    const filename = normalizeReportFilename(report).toLowerCase();
    const segments = filename.split('.');
    return segments.length > 1 ? String(segments.pop() || '').trim() : '';
}

export function isBusinessFacingReport(report: Report): boolean {
    const filename = normalizeReportFilename(report);
    if (!filename) {
        return false;
    }

    const groupKey = String(report.groupKey || '').trim().toLowerCase();
    if (groupKey && !BUSINESS_REPORT_GROUP_KEYS.has(groupKey)) {
        return false;
    }

    const normalizedPath = normalizeReportPath(report);
    if (
        !normalizedPath
        || normalizedPath.includes('/qa/')
        || normalizedPath.startsWith('qa/')
        || normalizedPath.endsWith('.json')
        || normalizedPath.includes('report_package')
        || normalizedPath.includes('report_consistency_check')
        || normalizedPath.includes('/workpapers/')
        || normalizedPath.includes('/technical/')
        || normalizedPath.includes('/tmp_')
        || normalizedPath.includes('e2e_')
    ) {
        return false;
    }

    return BUSINESS_REPORT_EXTENSIONS.has(normalizeReportExtension(report));
}

export function filterBusinessFacingReports(reports: Report[]): Report[] {
    return reports.filter(isBusinessFacingReport);
}

export function buildBusinessFacingReportGroups(groups: ReportGroup[], reports: Report[]): ReportGroup[] {
    const filteredGroups = groups
        .map((group) => ({
            ...group,
            items: filterBusinessFacingReports(Array.isArray(group.items) ? group.items : []),
        }))
        .filter((group) => BUSINESS_REPORT_GROUP_KEYS.has(String(group.key || '').trim().toLowerCase()) && group.items.length > 0)
        .map((group) => ({
            ...group,
            count: group.items.length,
        }));

    if (filteredGroups.length > 0) {
        return filteredGroups;
    }

    const fallbackItems = filterBusinessFacingReports(reports);
    if (fallbackItems.length === 0) {
        return [];
    }

    return [{
        key: 'business_reports',
        label: '正式报告',
        description: '仅展示供业务人员阅读的正式报告终稿。',
        order: 10,
        count: fallbackItems.length,
        items: fallbackItems,
    }];
}

export function filterBusinessSemanticOverview(
    semanticOverview: ReportSemanticOverview | null,
    reportGroups: ReportGroup[],
): ReportSemanticOverview | null {
    if (!semanticOverview) {
        return null;
    }

    const groupKeys = new Set(reportGroups.map((group) => String(group.key || '').trim().toLowerCase()));

    return {
        mainReport: semanticOverview.mainReport,
        appendices: groupKeys.has('appendices') ? semanticOverview.appendices : undefined,
        dossiers: semanticOverview.dossiers,
    };
}

export function pickPreferredBusinessPreviewReport(reports: Report[]): Report | null {
    const visibleReports = filterBusinessFacingReports(reports);

    const htmlPrimary = visibleReports.find((item) => {
        const extension = normalizeReportExtension(item);
        return String(item.groupKey || '').trim().toLowerCase() === 'primary_reports' && (extension === 'html' || extension === 'htm');
    });
    if (htmlPrimary) {
        return htmlPrimary;
    }

    const textPrimary = visibleReports.find((item) => {
        const extension = normalizeReportExtension(item);
        return String(item.groupKey || '').trim().toLowerCase() === 'primary_reports'
            && item.isPreviewable
            && (extension === 'txt' || extension === 'html' || extension === 'htm');
    });
    if (textPrimary) {
        return textPrimary;
    }

    const htmlFallback = visibleReports.find((item) => {
        const extension = normalizeReportExtension(item);
        return item.isPreviewable && (extension === 'html' || extension === 'htm');
    });
    if (htmlFallback) {
        return htmlFallback;
    }

    return visibleReports.find((item) => {
        const extension = normalizeReportExtension(item);
        return item.isPreviewable && extension === 'txt';
    }) || null;
}
