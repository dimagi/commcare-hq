from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.reports import (
    AdminDomainStatsReport,
    AdminAppReport,
    AdminUserReport,
    RealProjectSpacesReport,
    CommConnectProjectSpacesReport,
    CommTrackProjectSpacesReport,
)
from corehq.apps.hqpillow_retry.views import PillowErrorsReport
from corehq.apps.reports.standard import (monitoring, inspect, export,
    deployments, sms, ivr)
from corehq.apps.receiverwrapper import reports as receiverwrapper
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.view import ConfigurableReport
import phonelog.reports as phonelog
from corehq.apps.reports.commtrack import standard as commtrack_reports
from corehq.apps.reports.commtrack import maps as commtrack_maps
from corehq.apps.reports.commconnect import system_overview
from corehq.apps.fixtures.interface import FixtureViewInterface, FixtureEditInterface
import hashlib
from dimagi.utils.modules import to_function
import logging

from django.utils.translation import ugettext_noop as _, ugettext_lazy

def REPORTS(project):
    from corehq.apps.reports.standard.cases.basic import CaseListReport
    from corehq.apps.reports.standard.cases.careplan import make_careplan_reports
    from corehq.apps.reports.standard.maps import DemoMapReport, DemoMapReport2, DemoMapCaseList

    reports = [
        (ugettext_lazy("Monitor Workers"), (
            monitoring.WorkerActivityReport,
            monitoring.DailyFormStatsReport,
            monitoring.SubmissionsByFormReport,
            monitoring.FormCompletionTimeReport,
            monitoring.CaseActivityReport,
            monitoring.FormCompletionVsSubmissionTrendsReport,
            monitoring.WorkerActivityTimes,
        )),
        (ugettext_lazy("Inspect Data"), (
            inspect.SubmitHistory, CaseListReport,
        )),
        (ugettext_lazy("Manage Deployments"), (
            deployments.ApplicationStatusReport,
            receiverwrapper.SubmissionErrorReport,
            phonelog.FormErrorReport,
            phonelog.DeviceLogDetailsReport,
            deployments.SyncHistoryReport,
        )),
        (ugettext_lazy("Demos for Previewers"), (
            DemoMapReport, DemoMapReport2, DemoMapCaseList,
        )),
    ]

    if project.commtrack_enabled:
        reports.insert(0, (ugettext_lazy("Commtrack"), (
            commtrack_reports.SimplifiedInventoryReport,
            commtrack_reports.InventoryReport,
            commtrack_reports.CurrentStockStatusReport,
            commtrack_maps.StockStatusMapReport,
            commtrack_reports.ReportingRatesReport,
            commtrack_maps.ReportingStatusMapReport,
            # commtrack_reports.RequisitionReport,
        )))

    if project.has_careplan:
        from corehq.apps.app_manager.models import CareplanConfig
        config = CareplanConfig.for_domain(project.name)
        if config:
            cp_reports = tuple(make_careplan_reports(config))
            reports.insert(0, (ugettext_lazy("Care Plans"), cp_reports))

    from corehq.apps.accounting.utils import domain_has_privilege
    messaging_reports = []

    project_can_use_sms = domain_has_privilege(project.name, privileges.OUTBOUND_SMS)
    if project_can_use_sms:
        messaging_reports.extend([
            sms.MessagesReport,
        ])
    # always have this historical report visible
    messaging_reports.append(sms.MessageLogReport)

    project_can_use_inbound_sms = domain_has_privilege(project.name, privileges.INBOUND_SMS)
    if project_can_use_inbound_sms:
        messaging_reports.extend([
            ivr.CallLogReport,
            ivr.ExpectedCallbackReport,
            system_overview.SystemOverviewReport,
            system_overview.SystemUsersReport,
        ])

    messaging_reports += getattr(Domain.get_module_by_name(project.name), 'MESSAGING_REPORTS', ())

    messaging = (lambda project, user: (
        ugettext_lazy("Logs") if project.commtrack_enabled else ugettext_lazy("Messaging")), messaging_reports)

    if project.commconnect_enabled:
        reports.insert(0, messaging)
    else:
        reports.append(messaging)

    reports.extend(_get_dynamic_reports(project))
    reports.extend(_get_configurable_reports(project))

    return reports


def _get_dynamic_reports(project):
    """include any reports that can be configured/customized with static parameters for this domain"""
    for reportset in project.dynamic_reports:
        yield (reportset.section_title,
               filter(None,
                      (_make_dynamic_report(report, [reportset.section_title]) for report in reportset.reports)))


def _make_dynamic_report(report_config, keyprefix):
    """create a report class the descends from a generic report class but has specific parameters set"""
    # a unique key to distinguish this particular configuration of the generic report
    report_key = keyprefix + [report_config.report, report_config.name]
    slug = hashlib.sha1(':'.join(report_key)).hexdigest()[:12]
    kwargs = dict(report_config.kwargs)
    kwargs.update({
            'name': report_config.name,
            'slug': slug,
        })
    if report_config.previewers_only:
        # note this is a classmethod that will be injected into the dynamic class below
        @classmethod
        def show_in_navigation(cls, domain=None, project=None, user=None):
            return user and user.is_previewer()
        kwargs['show_in_navigation'] = show_in_navigation

    try:
        metaclass = to_function(report_config.report, failhard=True)
    except StandardError:
        logging.error('dynamic report config for [%s] is invalid' % report_config.report)
        return None

    # dynamically create a report class
    return type('DynamicReport%s' % slug, (metaclass,), kwargs)


def _get_configurable_reports(project):
    """
    User configurable reports
    """
    configs = ReportConfiguration.by_domain(project.name)
    if configs:
        def _make_report_class(config):
            from corehq.apps.reports.generic import GenericReportView

            # this is really annoying.
            # the report metadata should really be pulled outside of the report classes
            @classmethod
            def get_url(cls, domain):
                return reverse(ConfigurableReport.slug, args=[domain, config._id])

            return type('DynamicReport{}'.format(config._id), (GenericReportView, ), {
                'name': config.title,
                'description': config.description,
                'get_url': get_url,
            })

        yield (_('Configurable Reports'), [_make_report_class(config) for config in configs])



from corehq.apps.data_interfaces.interfaces import CaseReassignmentInterface
from corehq.apps.importer.base import ImportCases

DATA_INTERFACES = (
    (ugettext_lazy("Export Data"), (
        export.ExcelExportReport,
        export.CaseExportReport,
        export.DeidExportReport,
    )),
)

EDIT_DATA_INTERFACES = (
    (ugettext_lazy('Edit Data'), (
        CaseReassignmentInterface,
        ImportCases
    )),
)

FIXTURE_INTERFACES = (
    (_('Lookup Tables'), (
        FixtureEditInterface,
        FixtureViewInterface,
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
    ManageReportAnnouncementsInterface,
)

ANNOUNCEMENTS_ADMIN_INTERFACES = (
    (_("Manage Announcements"), (
        ManageGlobalHQAnnouncementsInterface,
        ManageReportAnnouncementsInterface,
    )),
)

from corehq.apps.accounting.interface import (
    AccountingInterface,
    SubscriptionInterface,
    SoftwarePlanInterface,
    InvoiceInterface,
    PaymentRecordInterface,
)

ACCOUNTING_ADMIN_INTERFACES = (
    (_("Accounting Admin"), (
        AccountingInterface,
        SubscriptionInterface,
        SoftwarePlanInterface,
        InvoiceInterface,
        PaymentRecordInterface,
    )),
)

from corehq.apps.smsbillables.interface import (
    SMSBillablesInterface,
    SMSGatewayFeeCriteriaInterface,
)

SMS_ADMIN_INTERFACES = (
    (_("SMS Billing Administration"), (
        SMSBillablesInterface,
        SMSGatewayFeeCriteriaInterface,
    )),
)

from corehq.apps.appstore.interfaces import CommCareExchangeAdvanced

APPSTORE_INTERFACES = (
    (_('App Store'), (
        CommCareExchangeAdvanced,
    )),
)

from corehq.apps.reports.standard.domains import OrgDomainStatsReport

BASIC_REPORTS = (
    (_('Project Stats'), (
        OrgDomainStatsReport,
    )),
)

ADMIN_REPORTS = (
    (_('Domain Stats'), (
        AdminDomainStatsReport,
        AdminUserReport,
        AdminAppReport,
        PillowErrorsReport,
        RealProjectSpacesReport,
        CommConnectProjectSpacesReport,
        CommTrackProjectSpacesReport,
    )),
)

from corehq.apps.hqwebapp.models import *
from corehq.apps.styleguide.tabs import SGExampleTab

TABS = (
    DashboardTab,
    ProjectInfoTab,
    ReportsTab,
    ProjectDataTab,
    CommTrackSetupTab,
    ProjectUsersTab,
    ApplicationsTab,
    CloudcareTab,
    MessagingTab,
    ExchangeTab,
    OrgReportTab,
    OrgSettingsTab, # separate menu?
    AdminTab,
    SGExampleTab,
)

from corehq.db import Session
