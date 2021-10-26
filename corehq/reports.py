import datetime
import hashlib
import logging

from django.urls import reverse
from django.utils.translation import ugettext_lazy
from django.utils.translation import ugettext_noop as _

from jsonobject.exceptions import BadValueError

import phonelog.reports as phonelog
from dimagi.utils.modules import to_function

from corehq import privileges
from corehq.apps.accounting.interface import (
    AccountingInterface,
    CreditAdjustmentInterface,
    CustomerInvoiceInterface,
    InvoiceInterface,
    PaymentRecordInterface,
    SoftwarePlanInterface,
    SubscriptionAdjustmentInterface,
    SubscriptionInterface,
    WireInvoiceInterface,
)
from corehq.apps.case_importer.base import ImportCases
from corehq.apps.data_interfaces.interfaces import (
    BulkFormManagementInterface,
    CaseReassignmentInterface,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.domain.models import Domain
from corehq.apps.export.views.incremental import IncrementalExportLogView
from corehq.apps.fixtures.interface import (
    FixtureEditInterface,
    FixtureViewInterface,
)
from corehq.apps.hqadmin.reports import (
    AdminPhoneNumberReport,
    DeployHistoryReport,
    DeviceLogSoftAssertReport,
    UserAuditReport,
    UserListReport,
)
from corehq.apps.linked_domain.views import DomainLinkHistoryReport
from corehq.apps.reports import commtrack
from corehq.apps.reports.standard import deployments, inspect, monitoring, sms, tableau
from corehq.apps.reports.standard.cases.case_list_explorer import (
    CaseListExplorer,
)
from corehq.apps.reports.standard.forms import reports as receiverwrapper
from corehq.apps.reports.standard.project_health import ProjectHealthDashboard
from corehq.apps.reports.standard.users.reports import UserHistoryReport
from corehq.apps.reports.standard.web_user_activity import WebUserActivityReport
from corehq.apps.smsbillables.interface import (
    SMSBillablesInterface,
    SMSGatewayFeeCriteriaInterface,
)
from corehq.apps.enterprise.interface import EnterpriseSMSBillablesReport
from corehq.apps.sso.views.accounting_admin import IdentityProviderInterface
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    ReportConfiguration,
    StaticReportConfiguration,
)
from corehq.apps.userreports.reports.view import (
    ConfigurableReportView,
    CustomConfigurableReportDispatcher,
)
from corehq.apps.userreports.const import TEMP_REPORT_PREFIX
from corehq.motech.repeaters.views import (
    DomainForwardingRepeatRecords,
    SQLRepeatRecordReport,
)
from custom.openclinica.reports import OdmExportReport

from . import toggles


def REPORTS(project):
    from corehq.apps.reports.standard.cases.basic import CaseListReport

    report_set = None
    if project.report_whitelist:
        report_set = set(project.report_whitelist)
    reports = []

    reports.extend(_get_configurable_reports(project))

    monitoring_reports = (
        WebUserActivityReport,
        monitoring.WorkerActivityReport,
        monitoring.DailyFormStatsReport,
        monitoring.SubmissionsByFormReport,
        monitoring.FormCompletionTimeReport,
        monitoring.CaseActivityReport,
        monitoring.FormCompletionVsSubmissionTrendsReport,
        monitoring.WorkerActivityTimes,
        ProjectHealthDashboard,
    )
    inspect_reports = [
        inspect.SubmitHistory, CaseListReport, OdmExportReport,
    ]
    if toggles.CASE_LIST_EXPLORER.enabled(project.name):
        inspect_reports.append(CaseListExplorer)
    deployments_reports = (
        deployments.ApplicationStatusReport,
        deployments.AggregateUserStatusReport,
        receiverwrapper.SubmissionErrorReport,
        phonelog.DeviceLogDetailsReport,
        deployments.ApplicationErrorReport,
    )

    monitoring_reports = _filter_reports(report_set, monitoring_reports)
    inspect_reports = _filter_reports(report_set, inspect_reports)
    deployments_reports = _filter_reports(report_set, deployments_reports)

    reports.extend([
        (ugettext_lazy("Monitor Workers"), monitoring_reports),
        (ugettext_lazy("Inspect Data"), inspect_reports),
        (ugettext_lazy("Manage Deployments"), deployments_reports),
    ])

    if project.commtrack_enabled:
        supply_reports = (
            commtrack.SimplifiedInventoryReport,
            commtrack.InventoryReport,
            commtrack.CurrentStockStatusReport,
            commtrack.StockStatusMapReport,
        )
        supply_reports = _filter_reports(report_set, supply_reports)
        reports.insert(0, (ugettext_lazy("CommCare Supply"), supply_reports))

    reports = list(_get_report_builder_reports(project)) + reports

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
        sms.SMSOptOutReport,
        sms.PhoneNumberReport,
        sms.ScheduleInstanceReport,
    ])

    messaging_reports = _filter_reports(report_set, messaging_reports)
    messaging = (ugettext_lazy("Messaging"), messaging_reports)
    reports.append(messaging)

    reports.extend(_get_dynamic_reports(project))

    return reports


def _filter_reports(report_set, reports):
    if report_set:
        return [r for r in reports if r.slug in report_set]
    else:
        return reports


def _get_dynamic_reports(project):
    """include any reports that can be configured/customized with static parameters for this domain"""
    for reportset in project.dynamic_reports:
        yield (reportset.section_title,
               [_f for _f in (_make_dynamic_report(report, [reportset.section_title]) for report in reportset.reports) if _f])


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
    except Exception:
        logging.error('dynamic report config for [%s] is invalid' % report_config.report)
        return None

    # dynamically create a report class
    return type('DynamicReport%s' % slug, (metaclass,), kwargs)


def _safely_get_report_configs(project_name):
    try:
        configs = ReportConfiguration.by_domain(project_name)
    except (BadSpecError, BadValueError) as e:
        logging.exception(e)

        # Pick out the UCRs that don't have spec errors
        configs = []
        for config_id in get_doc_ids_in_domain_by_class(project_name, ReportConfiguration):
            try:
                configs.append(ReportConfiguration.get(config_id))
            except (BadSpecError, BadValueError) as e:
                logging.error("%s with report config %s" % (str(e), config_id))

    try:
        configs.extend(StaticReportConfiguration.by_domain(project_name))
    except (BadSpecError, BadValueError) as e:
        logging.exception(e)

    return configs


def _make_report_class(config, show_in_dropdown=False, show_in_nav=False):
    from corehq.apps.reports.generic import GenericReportView

    # this is really annoying.
    # the report metadata should really be pulled outside of the report classes
    @classmethod
    def get_url(cls, domain, **kwargs):
        from corehq.apps.userreports.models import CUSTOM_REPORT_PREFIX
        slug = (
            ConfigurableReportView.slug
            if not config._id.startswith(CUSTOM_REPORT_PREFIX)
            else CustomConfigurableReportDispatcher.slug
        )
        return reverse(slug, args=[domain, config._id])

    def get_show_item_method(additional_requirement):
        @classmethod
        def show_item(cls, domain=None, project=None, user=None):
            return additional_requirement and (
                config.visible or
                (user and toggles.USER_CONFIGURABLE_REPORTS.enabled(user.username))
            )
        return show_item

    config_id = config._id.decode('utf-8') if isinstance(config._id, bytes) else config._id
    type_name = 'DynamicReport{}'.format(config_id)
    return type(type_name, (GenericReportView,), {
        'name': config.title,
        'description': config.description or None,
        'get_url': get_url,
        'show_in_navigation': get_show_item_method(show_in_nav),
        'display_in_dropdown': get_show_item_method(show_in_dropdown),
    })


def _get_configurable_reports(project):
    """
    User configurable reports
    """
    configs = _safely_get_report_configs(project.name)

    if configs:
        yield (
            _('Reports'),
            [_make_report_class(config, show_in_nav=not config.title.startswith(TEMP_REPORT_PREFIX))
             for config in configs]
        )


def _get_report_builder_reports(project):
    """
    Yield a section with the two most recently edited report builder reports
    for display in the dropdown.
    """
    configs = _safely_get_report_configs(project.name)
    report_builder_reports = [c for c in configs if c.report_meta.created_by_builder]

    def key(config):
        """Key function for sorting configs"""
        modified = config.report_meta.last_modified
        if not modified:
            # Use the minimum date for any config thats missing it
            modified = datetime.datetime(1, 1, 1)
        return modified

    report_builder_reports.sort(key=key, reverse=True)
    if len(report_builder_reports) > 2:
        report_builder_reports = report_builder_reports[:2]
    if configs:
        yield (
            _('Report Builder Reports'),
            [_make_report_class(config, show_in_dropdown=not config.title.startswith(TEMP_REPORT_PREFIX))
             for config in report_builder_reports]
        )


def get_report_builder_count(domain):
    configs = _safely_get_report_configs(domain)
    report_builder_reports = [c for c in configs if c.report_meta.created_by_builder]
    return len(report_builder_reports)


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

ACCOUNTING_ADMIN_INTERFACES = (
    (_("Accounting Admin"), (
        AccountingInterface,
        SubscriptionInterface,
        SoftwarePlanInterface,
        InvoiceInterface,
        WireInvoiceInterface,
        CustomerInvoiceInterface,
        PaymentRecordInterface,
        SubscriptionAdjustmentInterface,
        CreditAdjustmentInterface,
        IdentityProviderInterface,
    )),
)


SMS_ADMIN_INTERFACES = (
    (_("SMS Billing Administration"), (
        SMSBillablesInterface,
        SMSGatewayFeeCriteriaInterface,
    )),
)

ENTERPRISE_INTERFACES = (
    (_("Manage Billing Details"), (
        EnterpriseSMSBillablesReport,
    )),
)


ADMIN_REPORTS = (
    (_('Domain Stats'), (
        UserListReport,
        DeviceLogSoftAssertReport,
        AdminPhoneNumberReport,
        UserAuditReport,
        DeployHistoryReport,
    )),
)

DOMAIN_REPORTS = (
    (_('Project Settings'), (
        DomainForwardingRepeatRecords,
        SQLRepeatRecordReport,
        DomainLinkHistoryReport,
        IncrementalExportLogView,
    )),
)


USER_MANAGEMENT_REPORTS = (
    (_("User Management"), (
        UserHistoryReport,
    )),
)
