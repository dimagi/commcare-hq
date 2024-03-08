import datetime
import logging

from django.urls import reverse
from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_noop as _

from jsonobject.exceptions import BadValueError

import phonelog.reports as phonelog

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
    CaseCopyInterface,
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
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
from corehq.apps.reports.standard import deployments, inspect, monitoring, sms
from corehq.apps.reports.standard.cases.case_list_explorer import (
    CaseListExplorer,
)
from corehq.apps.reports.standard.cases.duplicate_cases import (
    DuplicateCasesExplorer,
)
from corehq.apps.reports.standard.forms import reports as receiverwrapper
from corehq.apps.reports.standard.project_health import ProjectHealthDashboard
from corehq.apps.reports.standard.users.reports import UserHistoryReport
from corehq.apps.smsbillables.interface import (
    SMSBillablesInterface,
    SMSGatewayFeeCriteriaInterface,
)
from corehq.apps.enterprise.interface import EnterpriseSMSBillablesReport
from corehq.apps.sso.views.accounting_admin import IdentityProviderInterface
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    ReportConfiguration,
    StaticReportConfiguration, RegistryReportConfiguration,
)
from corehq.apps.userreports.reports.view import (
    ConfigurableReportView,
    CustomConfigurableReportDispatcher,
)
from corehq.apps.userreports.const import TEMP_REPORT_PREFIX
from corehq.motech.generic_inbound.reports import ApiRequestLogReport
from corehq.motech.repeaters.views import DomainForwardingRepeatRecords
from corehq.apps.geospatial.reports import (
    CaseManagementMap,
    CaseGroupingReport,
)

from . import toggles


def REPORTS(project):
    from corehq.apps.reports.standard.cases.basic import CaseListReport

    reports = []

    reports.extend(_get_configurable_reports(project))

    monitoring_reports = (
        monitoring.WorkerActivityReport,
        monitoring.DailyFormStatsReport,
        monitoring.SubmissionsByFormReport,
        monitoring.FormCompletionTimeReport,
        monitoring.CaseActivityReport,
        monitoring.FormCompletionVsSubmissionTrendsReport,
        ProjectHealthDashboard,
    )
    inspect_reports = [
        inspect.SubmitHistory, CaseListReport,
    ]

    from corehq.apps.accounting.utils import domain_has_privilege

    domain_can_access_case_list_explorer = domain_has_privilege(project.name, privileges.CASE_LIST_EXPLORER)
    if toggles.CASE_LIST_EXPLORER.enabled(project.name) or domain_can_access_case_list_explorer:
        inspect_reports.append(CaseListExplorer)

    if domain_has_privilege(project.name, privileges.CASE_DEDUPE):
        inspect_reports.append(DuplicateCasesExplorer)

    deployments_reports = (
        deployments.ApplicationStatusReport,
        deployments.AggregateUserStatusReport,
        receiverwrapper.SubmissionErrorReport,
        phonelog.DeviceLogDetailsReport,
        deployments.ApplicationErrorReport,
    )

    reports.extend([
        (gettext_lazy("Monitor Workers"), monitoring_reports),
        (gettext_lazy("Inspect Data"), inspect_reports),
        (gettext_lazy("Manage Deployments"), deployments_reports),
    ])

    if project.commtrack_enabled:
        supply_reports = (
            commtrack.SimplifiedInventoryReport,
            commtrack.InventoryReport,
            commtrack.CurrentStockStatusReport,
            commtrack.StockStatusMapReport,
        )
        reports.insert(0, (gettext_lazy("CommCare Supply"), supply_reports))

    reports = list(_get_report_builder_reports(project)) + reports

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

    messaging = (gettext_lazy("Messaging"), messaging_reports)
    reports.append(messaging)

    return reports


def _safely_get_report_configs(project_name):
    return (
        _safely_get_report_configs_generic(project_name, ReportConfiguration) +  # noqa: W504
        _safely_get_report_configs_generic(project_name, RegistryReportConfiguration) +  # noqa: W504
        _safely_get_static_report_configs(project_name)
    )


def _safely_get_report_configs_generic(project_name, report_class):
    try:
        configs = report_class.by_domain(project_name)
    except (BadSpecError, BadValueError) as e:
        logging.exception(e)

        # Pick out the UCRs that don't have spec errors
        configs = []
        for config_id in get_doc_ids_in_domain_by_class(project_name, report_class):
            try:
                configs.append(report_class.get(config_id))
            except (BadSpecError, BadValueError) as e:
                logging.error("%s with report config %s" % (str(e), config_id))
    return configs


def _safely_get_static_report_configs(project_name):
    try:
        return StaticReportConfiguration.by_domain(project_name)
    except (BadSpecError, BadValueError) as e:
        logging.exception(e)


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
                config.visible
                or (user and toggles.USER_CONFIGURABLE_REPORTS.enabled(user.username))
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


def EDIT_DATA_INTERFACES(domain_obj):
    from corehq.apps.accounting.utils import domain_has_privilege
    reports = [CaseReassignmentInterface]

    if (
        toggles.COPY_CASES.enabled(domain_obj.name)
        and domain_has_privilege(domain_obj.name, privileges.CASE_COPY)
    ):
        reports.append(CaseCopyInterface)

    reports.extend([ImportCases, BulkFormManagementInterface])

    return (
        (gettext_lazy('Edit Data'), reports),
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
        DomainLinkHistoryReport,
        ApiRequestLogReport,
    )),
)


USER_MANAGEMENT_REPORTS = (
    (_("User Management"), (
        UserHistoryReport,
    )),
)

GEOSPATIAL_MAP = (
    (_("Case Mapping"), (
        CaseManagementMap,
        CaseGroupingReport,
    )),
)
