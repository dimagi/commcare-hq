import phonelog.reports as phonelog

from corehq.apps.accounting import interface as accounting
from corehq.apps.enterprise.interface import EnterpriseSMSBillablesReport
from corehq.apps.fixtures import interface as fixtures
from corehq.apps.geospatial import reports as geospatial
from corehq.apps.hqadmin import reports as hqadmin
from corehq.apps.linked_domain.views import DomainLinkHistoryReport
from corehq.apps.reports import commtrack
from corehq.apps.reports.standard import (
    deployments,
    inspect,
    monitoring,
    sms,
)
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.case_list_explorer import CaseListExplorer
from corehq.apps.reports.standard.cases.duplicate_cases import DuplicateCasesExplorer
from corehq.apps.reports.standard.forms import reports as receiverwrapper
from corehq.apps.reports.standard.project_health import ProjectHealthDashboard
from corehq.apps.reports.standard.users.reports import UserHistoryReport
from corehq.apps.sso.views.accounting_admin import IdentityProviderInterface
from corehq.motech.generic_inbound.reports import ApiRequestLogReport
from corehq.motech.repeaters.views import DomainForwardingRepeatRecords


ALL_REPORTS = [
    monitoring.WorkerActivityReport,
    monitoring.DailyFormStatsReport,
    monitoring.SubmissionsByFormReport,
    monitoring.FormCompletionTimeReport,
    monitoring.CaseActivityReport,
    monitoring.FormCompletionVsSubmissionTrendsReport,
    ProjectHealthDashboard,
    inspect.SubmitHistory,
    CaseListReport,
    CaseListExplorer,
    DuplicateCasesExplorer,
    deployments.ApplicationStatusReport,
    deployments.AggregateUserStatusReport,
    receiverwrapper.SubmissionErrorReport,
    phonelog.DeviceLogDetailsReport,
    deployments.ApplicationErrorReport,
    commtrack.SimplifiedInventoryReport,
    commtrack.InventoryReport,
    commtrack.CurrentStockStatusReport,
    sms.MessagesReport,
    sms.MessagingEventsReport,
    sms.MessageEventDetailReport,
    sms.SurveyDetailReport,
    sms.MessageLogReport,
    sms.SMSOptOutReport,
    sms.PhoneNumberReport,
    sms.ScheduleInstanceReport,
    fixtures.FixtureEditInterface,
    fixtures.FixtureViewInterface,
    accounting.AccountingInterface,
    accounting.SubscriptionInterface,
    accounting.SoftwarePlanInterface,
    accounting.InvoiceInterface,
    accounting.WireInvoiceInterface,
    accounting.CustomerInvoiceInterface,
    accounting.PaymentRecordInterface,
    accounting.SubscriptionAdjustmentInterface,
    accounting.CreditAdjustmentInterface,
    IdentityProviderInterface,
    EnterpriseSMSBillablesReport,
    hqadmin.UserListReport,
    hqadmin.AdminPhoneNumberReport,
    hqadmin.UserAuditReport,
    hqadmin.DeployHistoryReport,
    hqadmin.UCRDataLoadReport,
    DomainForwardingRepeatRecords,
    DomainLinkHistoryReport,
    ApiRequestLogReport,
    UserHistoryReport,
    geospatial.CaseManagementMap,
    geospatial.CaseGroupingReport,
]


def get_report_class(name):
    for report_class in ALL_REPORTS:
        if report_class.__name__ == name:
            return report_class


def get_bootstrap5_reports():
    return [report_class.__name__ for report_class in ALL_REPORTS if report_class.use_bootstrap5]
