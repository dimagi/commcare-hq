from corehq.apps.reports.standard import (monitoring, inspect, export,
    deployments, sms, ivr)
import corehq.apps.receiverwrapper.reports as receiverwrapper
import phonelog.reports as phonelog
from corehq.apps.reports.commtrack import psi_prototype
from corehq.apps.reports.commtrack import standard as commtrack_reports
from corehq.apps.reports.commtrack import maps as commtrack_maps

from django.utils.translation import ugettext_noop as _

REPORTS = (
    (_("Commtrack"), (
        commtrack_reports.ReportingRatesReport,
        commtrack_reports.CurrentStockStatusReport,
        commtrack_reports.AggregateStockStatusReport,
        psi_prototype.VisitReport,
        psi_prototype.SalesAndConsumptionReport,
        psi_prototype.CumulativeSalesAndConsumptionReport,
        psi_prototype.StockOutReport,
        psi_prototype.StockReportExport,
        commtrack_maps.StockStatusMapReport,
    )),
    (_("Monitor Workers"), (
        monitoring.DailyFormStatsReport,
        monitoring.SubmissionsByFormReport,
        monitoring.FormCompletionTimeReport,
        monitoring.CaseActivityReport,
        monitoring.FormCompletionVsSubmissionTrendsReport,
        monitoring.WorkerActivityTimes,
    )),
    (_("Inspect Data"), (
        inspect.SubmitHistory,
        inspect.CaseListReport,
        inspect.MapReport,
    )),
    (_("Raw Data"), (
        export.ExcelExportReport,
        export.CaseExportReport,
        export.DeidExportReport,
    )),
    (_("Manage Deployments"), (
        deployments.ApplicationStatusReport,
        receiverwrapper.SubmissionErrorReport,
        phonelog.FormErrorReport,
        phonelog.DeviceLogDetailsReport
    )),
    (lambda project, user: (
        _("Logs") if project.commtrack_enabled else _("CommConnect")), (
        sms.MessagesReport,
        sms.MessageLogReport,
        ivr.CallLogReport,
        ivr.ExpectedCallbackReport,
    )),
)

from corehq.apps.data_interfaces.interfaces import CaseReassignmentInterface
from corehq.apps.importer.base import ImportCases

DATA_INTERFACES = (
    (_('Case Management'), (
        CaseReassignmentInterface,
        ImportCases
    )),
)


from corehq.apps.adm.reports.supervisor import SupervisorReportsADMSection

ADM_SECTIONS = (
    (_('Supervisor Report'), (
        SupervisorReportsADMSection,
    )),
)

from corehq.apps.adm.admin import columns, reports

ADM_ADMIN_INTERFACES = (
    (_("ADM Default Columns"), (
        columns.ReducedADMColumnInterface,
        columns.DaysSinceADMColumnInterface,
        columns.ConfigurableADMColumnInterface
    )),
    (_("ADM Default Reports"), (
        reports.ADMReportAdminInterface,
    ))
)

from corehq.apps.indicators.admin import document_indicators, couch_indicators, dynamic_indicators

INDICATOR_ADMIN_INTERFACES = (
    (_("Form Based Indicators"), (
        document_indicators.FormLabelIndicatorDefinitionAdminInterface,
        document_indicators.FormAliasIndicatorDefinitionAdminInterface,
        document_indicators.CaseDataInFormAdminInterface,
    )),
    (_("Case Based Indicators"), (
        document_indicators.FormDataInCaseAdminInterface,
    )),
    (_("Dynamic Indicators"), (
        dynamic_indicators.CombinedIndicatorAdminInterface,
    )),
    (_("Couch Based Indicators"), (
        couch_indicators.CouchIndicatorAdminInterface,
        couch_indicators.CountUniqueCouchIndicatorAdminInterface,
        couch_indicators.MedianCouchIndicatorAdminInterface,
        couch_indicators.SumLastEmittedCouchIndicatorAdminInterface,
    )),
)

from corehq.apps.announcements.interface import (
    ManageGlobalHQAnnouncementsInterface,
    ManageReportAnnouncementsInterface)

ANNOUNCEMENTS_ADMIN_INTERFACES = (
    (_("Manage Announcements"), (
        ManageGlobalHQAnnouncementsInterface,
        ManageReportAnnouncementsInterface
    )),
)

from corehq.apps.appstore.interfaces import CommCareExchangeAdvanced

APPSTORE_INTERFACES = (
    (_('App Store'), (
        CommCareExchangeAdvanced,
    )),
)

from corehq.apps.reports.standard.domains import OrgDomainStatsReport, AdminDomainStatsReport

BASIC_REPORTS = (
    (_('Project Stats'), (
        OrgDomainStatsReport,
    )),
)

ADMIN_REPORTS = (
    (_('Domain Stats'), (
        AdminDomainStatsReport,
    )),
)

from corehq.apps.hqwebapp.models import *

TABS = (
    ProjectInfoTab,
    ReportsTab,
    ManageDataTab,
    ApplicationsTab,
    CloudcareTab,
    MessagesTab,
    RemindersTab,
    ProjectSettingsTab,
    OrgReportTab,
    OrgSettingsTab,
    AdminTab,
    ExchangeTab,
    ManageSurveysTab,
)
