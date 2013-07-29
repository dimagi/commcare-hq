from corehq.apps.reports.standard import (monitoring, inspect, export,
    deployments, sms, ivr)
import corehq.apps.receiverwrapper.reports as receiverwrapper
import phonelog.reports as phonelog
from corehq.apps.reports.commtrack import psi_prototype
from corehq.apps.reports.commtrack import standard as commtrack_reports
from corehq.apps.reports.commtrack import maps as commtrack_maps
import hashlib
from dimagi.utils.modules import to_function

from django.utils.translation import ugettext_noop as _

def REPORTS(project):
    reports = [
        (_("Monitor Workers"), (
            monitoring.WorkerActivityReport,
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
        ))
    ]
    
    if project.commtrack_enabled:
        reports.insert(0, (_("Commtrack"), (
            commtrack_reports.ReportingRatesReport,
            commtrack_reports.CurrentStockStatusReport,
            commtrack_reports.AggregateStockStatusReport,
            psi_prototype.VisitReport,
            psi_prototype.SalesAndConsumptionReport,
            psi_prototype.CumulativeSalesAndConsumptionReport,
            psi_prototype.StockOutReport,
            psi_prototype.StockReportExport,
            commtrack_maps.StockStatusMapReport,
        )))

    messaging = (lambda project, user: (
        _("Logs") if project.commtrack_enabled else _("Messaging")), (
        sms.MessagesReport,
        sms.MessageLogReport,
        ivr.CallLogReport,
        ivr.ExpectedCallbackReport,
    ))
    if project.commconnect_enabled:
        reports.insert(0, messaging)
    else:
        reports.append(messaging)

    reports.extend(dynamic_reports(project))

    return reports
    
def dynamic_reports(project):
    config = get_dynamic_report_config(project.name) or []
    for section, reports in config:
        yield (section, [make_dynamic_report(report, section) for report in reports])

def make_dynamic_report(report_config, section):
    report_key = '%s:%s:%s' % (report_config['report'], section, report_config['name'])
    slug = hashlib.sha1(report_key).hexdigest()[:12]
    metaclass = to_function(report_config['report'])
    kwargs = report_config['kwargs']
    kwargs.update({
            'name': report_config['name'],
            'slug': slug,
        })
    return type('DynamicReport%s' % slug, (metaclass,), kwargs)

def get_dynamic_report_config(domain):
    if domain == 'commtrack-public-demo':
        return [('Dynamic', [
                    {
                        'report': 'corehq.apps.reports.standard.inspect.GenericPieChartReportTemplate',
                        'name': 'Pie Chart - Case Property: Product',
                        'kwargs': {
                            'mode': 'case',
                            'submission_type': 'supply-point-product',
                            'field': 'product',
                        },
                    },
                    {
                        'report': 'corehq.apps.reports.standard.inspect.GenericPieChartReportTemplate',
                        'name': 'Pie Chart - Form Field: Location',
                        'kwargs': {
                            'mode': 'form',
                            'submission_type': 'http://openrosa.org/commtrack/stock_report',
                            'field': 'location',
                        },
                    },
                ])]



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
    MessagingTab,
    ProjectSettingsTab,
    OrgReportTab,
    OrgSettingsTab,
    AdminTab,
    ExchangeTab,
)
