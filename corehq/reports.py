from django.core.urlresolvers import reverse
from corehq import privileges
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.hqadmin.reports import (
    AdminDomainStatsReport,
    AdminDomainMapReport,
    AdminAppReport,
    AdminUserReport,
    RealProjectSpacesReport,
    CommConnectProjectSpacesReport,
    CommTrackProjectSpacesReport,
)
from corehq.apps.hqpillow_retry.views import PillowErrorsReport
from corehq.apps.reports.standard import (monitoring, inspect, export,
    deployments, sms, ivr)
from corehq.apps.reports.standard.forms import reports as receiverwrapper
from corehq.apps.reports.standard.project_health import ProjectHealthDashboard
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    StaticReportConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.view import (
    ConfigurableReport,
    CustomConfigurableReportDispatcher,
)
import phonelog.reports as phonelog
from corehq.apps.reports import commtrack
from corehq.apps.fixtures.interface import FixtureViewInterface, FixtureEditInterface
import hashlib
from dimagi.utils.modules import to_function
import logging
import toggles
from django.utils.translation import ugettext_noop as _, ugettext_lazy
from corehq.apps.indicators.admin import document_indicators, couch_indicators, dynamic_indicators
from corehq.apps.data_interfaces.interfaces import CaseReassignmentInterface, BulkFormManagementInterface
from corehq.apps.importer.base import ImportCases
from corehq.apps.accounting.interface import (
    AccountingInterface,
    SubscriptionInterface,
    SoftwarePlanInterface,
    InvoiceInterface,
    WireInvoiceInterface,
    PaymentRecordInterface,
    SubscriptionAdjustmentInterface,
    CreditAdjustmentInterface,
)
from corehq.apps.smsbillables.interface import (
    SMSBillablesInterface,
    SMSGatewayFeeCriteriaInterface,
)
from corehq.apps.domain.views import DomainForwardingRepeatRecords


def REPORTS(project):
    from corehq.apps.reports.standard.cases.basic import CaseListReport
    from corehq.apps.reports.standard.cases.careplan import make_careplan_reports
    from corehq.apps.reports.standard.maps import DemoMapReport, DemoMapReport2, DemoMapCaseList

    reports = []

    reports.extend(_get_configurable_reports(project))

    reports.extend([
        (ugettext_lazy("Monitor Workers"), (
            monitoring.WorkerActivityReport,
            monitoring.DailyFormStatsReport,
            monitoring.SubmissionsByFormReport,
            monitoring.FormCompletionTimeReport,
            monitoring.CaseActivityReport,
            monitoring.FormCompletionVsSubmissionTrendsReport,
            monitoring.WorkerActivityTimes,
            ProjectHealthDashboard,
        )),
        (ugettext_lazy("Inspect Data"), (
            inspect.SubmitHistory, CaseListReport,
        )),
        (ugettext_lazy("Manage Deployments"), (
            deployments.ApplicationStatusReport,
            receiverwrapper.SubmissionErrorReport,
            phonelog.DeviceLogDetailsReport,
            deployments.SyncHistoryReport,
        )),
        (ugettext_lazy("Demos"), (
            DemoMapReport, DemoMapReport2, DemoMapCaseList,
        )),
    ])

    if project.commtrack_enabled:
        reports.insert(0, (ugettext_lazy("CommCare Supply"), (
            commtrack.SimplifiedInventoryReport,
            commtrack.InventoryReport,
            commtrack.CurrentStockStatusReport,
            commtrack.StockStatusMapReport,
            commtrack.ReportingRatesReport,
            commtrack.ReportingStatusMapReport,
            commtrack.LedgersByLocationReport,
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

    # always have these historical reports visible
    messaging_reports.extend([
        sms.MessagingEventsReport,
        sms.MessageEventDetailReport,
        sms.SurveyDetailReport,
        sms.MessageLogReport,
        ivr.CallLogReport,
        ivr.ExpectedCallbackReport,
    ])

    messaging_reports += getattr(Domain.get_module_by_name(project.name), 'MESSAGING_REPORTS', ())
    messaging = (ugettext_lazy("Messaging"), messaging_reports)
    reports.append(messaging)

    reports.extend(_get_dynamic_reports(project))

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


def _safely_get_report_configs(project_name):
    try:
        configs = ReportConfiguration.by_domain(project_name)
    except BadSpecError as e:
        logging.exception(e)

        # Pick out the UCRs that don't have spec errors
        configs = []
        for config_id in get_doc_ids_in_domain_by_class(project_name, ReportConfiguration):
            try:
                configs.append(ReportConfiguration.get(config_id))
            except BadSpecError as e:
                logging.error("%s with report config %s" % (e.message, config_id))

    try:
        configs.extend(StaticReportConfiguration.by_domain(project_name))
    except BadSpecError as e:
        logging.exception(e)

    return configs


def _get_configurable_reports(project):
    """
    User configurable reports
    """
    configs = _safely_get_report_configs(project.name)

    if configs:
        def _make_report_class(config):
            from corehq.apps.reports.generic import GenericReportView

            # this is really annoying.
            # the report metadata should really be pulled outside of the report classes
            @classmethod
            def get_url(cls, domain, **kwargs):
                from corehq.apps.userreports.models import CUSTOM_REPORT_PREFIX
                slug = (
                    ConfigurableReport.slug
                    if not config._id.startswith(CUSTOM_REPORT_PREFIX)
                    else CustomConfigurableReportDispatcher.slug
                )
                return reverse(slug, args=[domain, config._id])

            @classmethod
            def show_in_navigation(cls, domain=None, project=None, user=None):
                return config.visible or (user and toggles.USER_CONFIGURABLE_REPORTS.enabled(user.username))

            return type('DynamicReport{}'.format(config._id), (GenericReportView, ), {
                'name': config.title,
                'description': config.description or None,
                'get_url': get_url,
                'show_in_navigation': show_in_navigation,
            })

        yield (_('Reports'), [_make_report_class(config) for config in configs])


DATA_INTERFACES = (
    (ugettext_lazy("Export Data"), (
        export.DeidExportReport,
    )),
)

EDIT_DATA_INTERFACES = (
    (ugettext_lazy('Edit Data'), (
        CaseReassignmentInterface,
        ImportCases,
        BulkFormManagementInterface,
    )),
)

FIXTURE_INTERFACES = (
    (_('Lookup Tables'), (
        FixtureEditInterface,
        FixtureViewInterface,
    )),
)


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


ACCOUNTING_ADMIN_INTERFACES = (
    (_("Accounting Admin"), (
        AccountingInterface,
        SubscriptionInterface,
        SoftwarePlanInterface,
        InvoiceInterface,
        WireInvoiceInterface,
        PaymentRecordInterface,
        SubscriptionAdjustmentInterface,
        CreditAdjustmentInterface,
    )),
)


SMS_ADMIN_INTERFACES = (
    (_("SMS Billing Administration"), (
        SMSBillablesInterface,
        SMSGatewayFeeCriteriaInterface,
    )),
)


BASIC_REPORTS = (
    (_('Project Stats'), ()),
)

ADMIN_REPORTS = (
    (_('Domain Stats'), (
        AdminDomainStatsReport,
        AdminDomainMapReport,
        AdminUserReport,
        AdminAppReport,
        PillowErrorsReport,
        RealProjectSpacesReport,
        CommConnectProjectSpacesReport,
        CommTrackProjectSpacesReport,
    )),
)

DOMAIN_REPORTS = (
    (_('Project Settings'), (
        DomainForwardingRepeatRecords,
    )),
)
