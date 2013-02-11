from corehq.apps.reports.standard import (monitoring, inspect, export,
    deployments, sms, ivr)
import corehq.apps.receiverwrapper.reports as receiverwrapper
import phonelog.reports as phonelog
from corehq.apps.reports.commtrack import psi_prototype

from django.utils.translation import ugettext_noop as _

REPORTS = (
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
    (_("CommConnect"), (
        sms.MessagesReport,
        sms.MessageLogReport,
        ivr.CallLogReport,
    )),
    (_("Commtrack"), (
        psi_prototype.VisitReport,
        psi_prototype.SalesAndConsumptionReport,
        psi_prototype.CumulativeSalesAndConsumptionReport,
        psi_prototype.StockOutReport,
        psi_prototype.StockReportExport,
    ))
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

from corehq.apps.hqwebapp.models import *

MENU_ITEMS = (
    ProjectInfoMenuItem,
    ReportsMenuItem,
    ManageDataMenuItem,
    ApplicationsMenuItem,
    CloudcareMenuItem,
    MessagesMenuItem,
    ProjectSettingsMenuItem,
    AdminReportsMenuItem,
    ExchangeMenuItem,
    ManageSurveysMenuItem,
)

