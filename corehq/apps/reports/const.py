USER_QUERY_LIMIT = 5000
DEFAULT_PAGE_LIMIT = 10


def get_report_class(slug):
    # Used by export_all_rows_task to retrieve the correct report class to instantiate
    from .commtrack import CurrentStockStatusReport
    from .standard.cases.case_list_explorer import CaseListExplorer
    from .standard.cases.duplicate_cases import DuplicateCasesExplorer
    from .standard.deployments import ApplicationStatusReport
    from .standard.monitoring import WorkerActivityReport, DailyFormStatsReport, CaseActivityReport
    from corehq.apps.enterprise.interface import EnterpriseSMSBillablesReport
    from corehq.apps.hqadmin.reports import DeviceLogSoftAssertReport
    from corehq.apps.smsbillables.interface import SMSBillablesInterface, SMSGatewayFeeCriteriaInterface
    from phonelog.reports import DeviceLogDetailsReport

    reports = {
        ApplicationStatusReport.slug: ApplicationStatusReport,
        CaseActivityReport.slug: CaseActivityReport,
        DailyFormStatsReport.slug: DailyFormStatsReport,
        DeviceLogDetailsReport.slug: DeviceLogDetailsReport,
        SMSBillablesInterface.slug: SMSBillablesInterface,
        SMSGatewayFeeCriteriaInterface.slug: SMSGatewayFeeCriteriaInterface,
        WorkerActivityReport.slug: WorkerActivityReport,
        DeviceLogSoftAssertReport.slug: DeviceLogSoftAssertReport,
        EnterpriseSMSBillablesReport.slug: EnterpriseSMSBillablesReport,
        CaseListExplorer.slug: CaseListExplorer,
        DuplicateCasesExplorer.slug: DuplicateCasesExplorer,
        CurrentStockStatusReport.slug: CurrentStockStatusReport,
    }

    if slug not in reports:
        raise Exception("Report class not supported yet, try adding the slug in reports/const.py")
    else:
        return reports[slug]
