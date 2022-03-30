from django.apps import AppConfig

reports = {}

class ReportsModule(AppConfig):
    name = 'corehq.apps.reports'

    def ready(self):
        from corehq.apps.reports import signals  # noqa

        # for use in export_all_rows_task
        from .commtrack import CurrentStockStatusReport
        from .standard.cases.case_list_explorer import CaseListExplorer
        from .standard.cases.duplicate_cases import DuplicateCasesExplorer
        from .standard.deployments import ApplicationStatusReport
        from .standard.monitoring import WorkerActivityReport, DailyFormStatsReport, CaseActivityReport
        from corehq.apps.enterprise.interface import EnterpriseSMSBillablesReport
        from corehq.apps.hqadmin.reports import DeviceLogSoftAssertReport
        from corehq.apps.smsbillables.interface import SMSBillablesInterface, SMSGatewayFeeCriteriaInterface
        from phonelog.reports import DeviceLogDetailsReport
        from custom.inddex.reports.r1_master_data import MasterDataReport

        global reports
        reports.update({
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
            MasterDataReport.slug: MasterDataReport,
        })


def get_report_class(slug):
    if slug not in reports:
        raise Exception("Report class not supported yet, try adding the slug in reports/app_config.py")
    else:
        return reports[slug]
