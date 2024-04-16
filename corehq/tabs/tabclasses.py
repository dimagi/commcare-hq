from django.conf import settings
from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html, strip_tags
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from django_prbac.utils import has_privilege
from memoized import memoized
from six.moves.urllib.parse import urlencode

from corehq import privileges, toggles
from corehq.apps.accounting.dispatcher import (
    AccountingAdminInterfaceDispatcher,
)
from corehq.apps.accounting.models import BillingAccount, Invoice, Subscription
from corehq.apps.accounting.utils import (
    domain_has_privilege,
    domain_is_on_trial,
    is_accounting_admin,
)
from corehq.apps.accounting.utils.subscription import is_domain_enterprise
from corehq.apps.accounting.views import (
    TriggerAutopaymentsView,
    TriggerDowngradeView,
)
from corehq.apps.app_manager.dbaccessors import (
    domain_has_apps,
    get_brief_apps_in_domain,
)
from corehq.apps.app_manager.util import is_remote_app, is_linked_app
from corehq.apps.builds.views import EditMenuView
from corehq.apps.data_dictionary.views import DataDictionaryView
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.internal import ProjectLimitsView
from corehq.apps.domain.views.releases import ManageReleasesByLocation
from corehq.apps.email.views import EmailSMTPSettingsView
from corehq.apps.enterprise.dispatcher import EnterpriseReportDispatcher
from corehq.apps.enterprise.views import ManageEnterpriseMobileWorkersView
from corehq.apps.events.models import AttendeeModel
from corehq.apps.events.views import (
    AttendeeEditView,
    AttendeesListView,
    EventsView,
)
from corehq.apps.geospatial.dispatchers import CaseManagementMapDispatcher

from corehq.apps.hqadmin.reports import (
    DeployHistoryReport,
    DeviceLogSoftAssertReport,
    UserAuditReport,
    UserListReport,
)
from corehq.apps.hqadmin.views.system import GlobalThresholds
from corehq.apps.hqwebapp.models import GaTracker
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.integration.views import (
    DialerSettingsView,
    GaenOtpServerSettingsView,
    HmacCalloutSettingsView,
)
from corehq.apps.linked_domain.util import can_user_access_linked_domains
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.receiverwrapper.rate_limiter import (
    SHOULD_RATE_LIMIT_SUBMISSIONS,
)
from corehq.apps.reminders.views import (
    AddNormalKeywordView,
    AddStructuredKeywordView,
    EditNormalKeywordView,
    EditStructuredKeywordView,
    KeywordsListView,
)
from corehq.apps.reports.dispatcher import (
    CustomProjectReportDispatcher,
    ProjectReportDispatcher,
)
from corehq.apps.reports.standard.users.reports import UserHistoryReport
from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.request_helpers import is_request_using_sso
from corehq.apps.styleguide.views import MainStyleGuideView
from corehq.apps.translations.integrations.transifex.utils import (
    transifex_details_available_for_domain,
)
from corehq.apps.userreports.util import has_report_builder_access
from corehq.apps.users.decorators import get_permission_name
from corehq.apps.users.permissions import (
    can_download_data_files,
    can_view_sms_exports,
)
from corehq.feature_previews import (
    EXPLORE_CASE_DATA_PREVIEW,
    is_eligible_for_ecd_preview,
)
from corehq.messaging.scheduling.views import \
    BroadcastListView as NewBroadcastListView
from corehq.messaging.scheduling.views import (
    ConditionalAlertListView,
    CreateConditionalAlertView,
    CreateScheduleView,
    EditConditionalAlertView,
    EditScheduleView,
    MessagingDashboardView,
    UploadConditionalAlertView,
)
from corehq.motech.dhis2.views import DataSetMapListView
from corehq.motech.openmrs.views import OpenmrsImporterView
from corehq.motech.views import ConnectionSettingsListView, MotechLogListView
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.tabs.uitab import UITab
from corehq.tabs.utils import dropdown_dict, sidebar_to_dropdown
from corehq.apps.users.models import HqPermissions
from corehq.apps.geospatial.views import (
    GeospatialConfigPage,
    GPSCaptureView,
)


class ProjectReportsTab(UITab):
    title = gettext_noop("Reports")
    view = "reports_home"

    url_prefix_formats = (
        '/a/{domain}/reports/',
        '/a/{domain}/configurable_reports/',
        '/a/{domain}/location_reassignment_download/',
    )

    @property
    def _is_viewable(self):
        if not has_privilege(self._request, privileges.PROJECT_ACCESS):
            return False
        if user_can_view_reports(self.project, self.couch_user):
            return True
        if toggles.EMBEDDED_TABLEAU.enabled(self.domain):
            if self.couch_user.can_view_some_tableau_viz(self.domain):
                return True
        return False

    @property
    def sidebar_items(self):
        tools = self._get_tools_items()
        tableau = self._get_tableau_items()
        report_builder_nav = self._get_report_builder_items()

        project_reports = ProjectReportDispatcher.navigation_sections(
            request=self._request, domain=self.domain)
        custom_reports = CustomProjectReportDispatcher.navigation_sections(
            request=self._request, domain=self.domain)
        sidebar_items = (tools + tableau + report_builder_nav + custom_reports + project_reports)
        return self._filter_sidebar_items(sidebar_items)

    def _get_tools_items(self):
        from corehq.apps.reports.views import MySavedReportsView

        if not user_can_view_reports(self.project, self.couch_user):
            return []

        tools = [{
            'title': _(MySavedReportsView.page_title),
            'url': reverse(MySavedReportsView.urlname, args=[self.domain]),
            'icon': 'icon-tasks fa fa-tasks',
            'show_in_dropdown': True,
        }]
        is_ucr_toggle_enabled = (
            toggles.USER_CONFIGURABLE_REPORTS.enabled(
                self.domain, namespace=toggles.NAMESPACE_DOMAIN
            )
            or toggles.USER_CONFIGURABLE_REPORTS.enabled(
                self.couch_user.username, namespace=toggles.NAMESPACE_USER
            )
        )
        has_ucr_permissions = self.couch_user.has_permission(
            self.domain,
            get_permission_name(HqPermissions.edit_ucrs)
        )

        if is_ucr_toggle_enabled and has_ucr_permissions:

            from corehq.apps.userreports.views import UserConfigReportsHomeView
            title = _(UserConfigReportsHomeView.section_name)
            if toggles.UCR_UPDATED_NAMING.enabled(self.domain):
                title = _("Custom Web Reports")
            tools.append({
                'title': title,
                'url': reverse(UserConfigReportsHomeView.urlname, args=[self.domain]),
                'icon': 'icon-tasks fa fa-wrench',
            })
        return [(_("Tools"), tools)]

    def _get_tableau_items(self):
        if not toggles.EMBEDDED_TABLEAU.enabled(self.domain):
            return []

        from corehq.apps.reports.models import TableauVisualization
        from corehq.apps.reports.standard.tableau import TableauView
        items = [
            {
                'title': viz.title or viz.name,
                'url': reverse(TableauView.urlname, args=[self.domain, viz.id]),
                'show_in_dropdown': i < 2,
            }
            for i, viz in enumerate(TableauVisualization.for_user(self.domain, self.couch_user))
        ]

        return [(_("Tableau Reports"), items)] if items else []

    def _get_report_builder_items(self):
        user_reports = []
        if self.couch_user.can_edit_reports():
            has_access = has_report_builder_access(self._request)
            user_reports = [(
                _("Report Builder"),
                [{
                    "title": _('Create New Report'),
                    "url": self._get_create_report_url(),
                    "icon": "icon-plus fa fa-plus {}".format(
                        "has-access" if has_access else "preview"
                    ),
                    "id": "create-new-report-left-nav",
                }]
            )]
        return user_reports

    def _get_create_report_url(self):
        """
        Return the url for the start of the report builder, or the paywall.
        """
        from corehq.apps.userreports.views import ReportBuilderDataSourceSelect
        return reverse(ReportBuilderDataSourceSelect.urlname, args=[self.domain])

    @staticmethod
    def _filter_sidebar_items(sidebar_items):
        """
        Exclude sidebar items where `item["show_in_navigation"] == False`
        """
        filtered_sidebar_items = []
        for section, items in sidebar_items:
            filtered_items = []
            for item in items:
                if not item.get("show_in_navigation", True):
                    continue
                filtered_items.append(item)
            if filtered_items:
                filtered_sidebar_items.append((section, filtered_items))
        return filtered_sidebar_items

    def _get_saved_reports_dropdown(self):
        saved_report_header = dropdown_dict(_('My Saved Reports'), is_header=True)
        saved_reports_list = list(ReportConfig.by_domain_and_owner(
                                  self.domain,
                                  self.couch_user._id))

        MAX_DISPLAYABLE_SAVED_REPORTS = 5
        first_five_items = [
            dropdown_dict(saved_report.name, url=saved_report.url)
            for counter, saved_report in enumerate(saved_reports_list)
            if counter < MAX_DISPLAYABLE_SAVED_REPORTS
        ]
        rest_as_second_level_items = [
            dropdown_dict("More Saved Reports", "#", second_level_dropdowns=[
                dropdown_dict(saved_report.name, url=saved_report.url)
                for counter, saved_report in enumerate(saved_reports_list)
                if counter >= MAX_DISPLAYABLE_SAVED_REPORTS
            ])
        ] if len(saved_reports_list) > MAX_DISPLAYABLE_SAVED_REPORTS else []

        if first_five_items:
            return ([saved_report_header] + first_five_items + rest_as_second_level_items)
        else:
            return []

    @property
    def dropdown_items(self):
        items = self._get_saved_reports_dropdown()

        if not self.can_access_all_locations:
            items.extend(self._get_all_sidebar_items_as_dropdown())
            return items

        reports = sidebar_to_dropdown(
            self._get_tableau_items()
            + ProjectReportDispatcher.navigation_sections(request=self._request, domain=self.domain),
            current_url=self.url
        )
        items.extend(reports)

        return items

    def _get_all_sidebar_items_as_dropdown(self):
        def show(page):
            page['show_in_dropdown'] = True
            return page
        return sidebar_to_dropdown([
            (header, list(map(show, pages)))
            for header, pages in self.sidebar_items
        ])


class DashboardTab(UITab):
    title = gettext_noop("Dashboard")
    view = 'dashboard_default'

    url_prefix_formats = ('/a/{domain}/dashboard/project/',)

    @property
    def _is_viewable(self):
        if self.domain and self.project and not self.project.is_snapshot and self.couch_user:
            if self.couch_user.is_commcare_user():
                # never show the dashboard for mobile workers
                return False
            else:
                return domain_has_apps(self.domain)
        return False

    @property
    @memoized
    def url(self):
        from corehq.apps.dashboard.views import DomainDashboardView
        return reverse(DomainDashboardView.urlname, args=[self.domain])


class SetupTab(UITab):
    title = gettext_noop("Setup")
    view = "default_commtrack_setup"

    url_prefix_formats = (
        '/a/{domain}/settings/products/',
        '/a/{domain}/settings/programs/',
        '/a/{domain}/settings/commtrack/',
    )

    @property
    def dropdown_items(self):
        # circular import
        from corehq.apps.commtrack.views import (
            CommTrackSettingsView,
            DefaultConsumptionView,
            SMSSettingsView,
        )
        from corehq.apps.products.views import ProductListView
        from corehq.apps.programs.views import ProgramListView

        if self.project.commtrack_enabled:
            dropdown_items = [(_(view.page_title), view) for view in (
                ProductListView,
                ProgramListView,
                SMSSettingsView,
                DefaultConsumptionView,
                CommTrackSettingsView,
            )]

            return [
                dropdown_dict(
                    item[0],
                    url=reverse(item[1].urlname, args=[self.domain])
                ) for item in dropdown_items
            ] + [
                self.divider,
                dropdown_dict(_("View All"), url=reverse(ProductListView.urlname, args=[self.domain])),
            ]

        return []

    @property
    def _is_viewable(self):
        return (self.couch_user.is_domain_admin()
                and self.project.commtrack_enabled)

    @property
    @memoized
    def url(self):
        from corehq.apps.commtrack.views import default_commtrack_url
        return default_commtrack_url(self.domain)

    @property
    def sidebar_items(self):
        # circular import
        from corehq.apps.commtrack.views import (
            CommTrackSettingsView,
            DefaultConsumptionView,
            SMSSettingsView,
        )
        from corehq.apps.products.views import (
            EditProductView,
            NewProductView,
            ProductFieldsView,
            ProductListView,
            UploadProductView,
        )
        from corehq.apps.programs.views import (
            EditProgramView,
            NewProgramView,
            ProgramListView,
        )

        if self.project.commtrack_enabled:
            commcare_supply_setup = [
                {
                    'title': _(ProductListView.page_title),
                    'url': reverse(ProductListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _(NewProductView.page_title),
                            'urlname': NewProductView.urlname,
                        },
                        {
                            'title': _(EditProductView.page_title),
                            'urlname': EditProductView.urlname,
                        },
                        {
                            'title': _(ProductFieldsView.page_name()),
                            'urlname': ProductFieldsView.urlname,
                        },
                        {
                            'title': _(UploadProductView.page_title),
                            'urlname': UploadProductView.urlname,
                        },
                    ]
                },
                {
                    'title': _(ProgramListView.page_title),
                    'url': reverse(ProgramListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _(NewProgramView.page_title),
                            'urlname': NewProgramView.urlname,
                        },
                        {
                            'title': _(EditProgramView.page_title),
                            'urlname': EditProgramView.urlname,
                        },
                    ]
                },
                {
                    'title': _(SMSSettingsView.page_title),
                    'url': reverse(SMSSettingsView.urlname, args=[self.domain]),
                },
                {
                    'title': _(DefaultConsumptionView.page_title),
                    'url': reverse(DefaultConsumptionView.urlname, args=[self.domain]),
                },
                {
                    'title': _(CommTrackSettingsView.page_title),
                    'url': reverse(CommTrackSettingsView.urlname, args=[self.domain]),
                },
            ]
            return [[_('CommCare Supply Setup'), commcare_supply_setup]]


class ProjectDataTab(UITab):
    title = gettext_noop("Data")
    view = "data_interfaces_default"
    url_prefix_formats = (
        '/a/{domain}/data/',
        '/a/{domain}/fixtures/',
        '/a/{domain}/data_dictionary/',
        '/a/{domain}/importer/',
        '/a/{domain}/case/',
        '/a/{domain}/geospatial/',
    )

    @property
    @memoized
    def url(self):
        from corehq.apps.data_interfaces.views import default_data_view_url
        try:
            return default_data_view_url(self._request, self.domain)
        except Http404:
            return None

    @property
    @memoized
    def can_edit_commcare_data(self):
        return self.couch_user.can_edit_data()

    @property
    @memoized
    def can_use_data_cleanup(self):
        return domain_has_privilege(self.domain, privileges.DATA_CLEANUP)

    @property
    @memoized
    def can_use_dedupe(self):
        return domain_has_privilege(self.domain, privileges.CASE_DEDUPE)

    @property
    @memoized
    def can_export_data(self):
        return (self.project and not self.project.is_snapshot
                and self.couch_user.can_access_any_exports(self.domain))

    @property
    @memoized
    def can_view_form_exports(self):
        from corehq.apps.export.views.utils import can_view_form_exports
        return can_view_form_exports(self.couch_user, self.domain)

    @property
    @memoized
    def can_view_case_exports(self):
        from corehq.apps.export.views.utils import can_view_case_exports
        return can_view_case_exports(self.couch_user, self.domain)

    @property
    @memoized
    def can_view_form_or_case_exports(self):
        return self.can_view_case_exports or self.can_view_form_exports

    @property
    @memoized
    def can_view_sms_exports(self):
        return can_view_sms_exports(self.couch_user, self.domain)

    @property
    @memoized
    def can_export_data_source(self):
        return (
            toggles.EXPORT_DATA_SOURCE_DATA.enabled(self.domain)
            and self.can_view_case_exports
            and self.can_view_form_exports
        )

    @property
    @memoized
    def should_see_daily_saved_export_list_view(self):
        return (
            self.can_view_form_or_case_exports
            and domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)
        )

    @property
    @memoized
    def should_see_daily_saved_export_paywall(self):
        return (
            self.can_view_form_or_case_exports
            and not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)
        )

    @property
    @memoized
    def should_see_dashboard_feed_list_view(self):
        return (
            self.can_view_form_or_case_exports
            and domain_has_privilege(self.domain, EXCEL_DASHBOARD)
        )

    @property
    @memoized
    def should_see_dashboard_feed_paywall(self):
        return (
            self.can_view_form_or_case_exports
            and not domain_has_privilege(self.domain, EXCEL_DASHBOARD)
        )

    @property
    @memoized
    def can_only_see_deid_exports(self):
        from corehq.apps.export.views.utils import user_can_view_deid_exports
        return (not self.can_view_form_exports
                and user_can_view_deid_exports(self.domain, self.couch_user))

    @property
    @memoized
    def can_view_odata_feed(self):
        from corehq.apps.export.views.utils import user_can_view_odata_feed
        return user_can_view_odata_feed(self.domain, self.couch_user)

    @property
    @memoized
    def can_use_lookup_tables(self):
        return domain_has_privilege(self.domain, privileges.LOOKUP_TABLES)

    @property
    def can_view_ecd_preview(self):
        return (EXPLORE_CASE_DATA_PREVIEW.enabled_for_request(self._request)
                and is_eligible_for_ecd_preview(self._request))

    @property
    def _can_view_geospatial(self):
        return toggles.GEOSPATIAL.enabled(self.domain)

    @property
    def _is_viewable(self):
        return self.domain and (
            self.can_edit_commcare_data
            or self.can_export_data
            or can_download_data_files(self.domain, self.couch_user)
        ) and has_privilege(self._request, privileges.PROJECT_ACCESS)

    @property
    def sidebar_items(self):
        # HELPME
        #
        # This method has been flagged for refactoring due to its complexity and
        # frequency of touches in changesets
        #
        # If you are writing code that touches this method, your changeset
        # should leave the method better than you found it.
        #
        # Please remove this flag when this method no longer triggers an 'E' or 'F'
        # classification from the radon code static analysis
        items = []

        export_data_views = self._get_export_data_views()
        if export_data_views:
            items.append([_("Export Data"), export_data_views])

        if self.can_edit_commcare_data:
            items.extend(self._get_edit_section())

        explore_data_views = self._get_explore_data_views()
        if explore_data_views:
            items.append([_("Explore Data"), explore_data_views])

        if self.can_use_lookup_tables:
            from corehq.apps.fixtures.dispatcher import (
                FixtureInterfaceDispatcher,
            )
            items.extend(FixtureInterfaceDispatcher.navigation_sections(
                request=self._request, domain=self.domain))

        if self._can_view_data_dictionary:
            items.append([DataDictionaryView.page_title, [{
                'title': DataDictionaryView.page_title,
                'url': reverse(DataDictionaryView.urlname, args=[self.domain]),
            }]])

        if toggles.UCR_EXPRESSION_REGISTRY.enabled(self.domain):
            from corehq.apps.userreports.views import UCRExpressionListView
            items.append(
                [
                    _("Data Manipulation"),
                    [
                        {
                            "title": _("Filters and Expressions"),
                            "url": reverse(UCRExpressionListView.urlname, args=[self.domain]),
                        },
                    ]
                ]
            )
        if self._can_view_geospatial:
            items += self._get_geospatial_views()
        return items

    @cached_property
    def _can_view_data_dictionary(self):
        has_view_data_dict_permission = self.couch_user.has_permission(
            self.domain,
            get_permission_name(HqPermissions.view_data_dict)
        )
        return domain_has_privilege(self.domain, privileges.DATA_DICTIONARY) and has_view_data_dict_permission

    def _get_export_data_views(self):
        export_data_views = []
        if self.can_only_see_deid_exports:
            from corehq.apps.export.views.list import (
                DeIdDailySavedExportListView,
                DeIdDashboardFeedListView,
                DeIdFormExportListView,
                ODataFeedListView,
            )
            export_data_views.append({
                'title': _(DeIdFormExportListView.page_title),
                'url': reverse(DeIdFormExportListView.urlname, args=(self.domain,)),
            })
            export_data_views.extend([
                {
                    'title': _(DeIdDailySavedExportListView.page_title),
                    'url': reverse(DeIdDailySavedExportListView.urlname, args=(self.domain,)),
                },
                {
                    'title': _(DeIdDashboardFeedListView.page_title),
                    'url': reverse(DeIdDashboardFeedListView.urlname, args=(self.domain,)),
                },
            ])

            if self.can_view_odata_feed:
                export_data_views.append({
                    'title': _(ODataFeedListView.page_title),
                    'url': reverse(ODataFeedListView.urlname, args=(self.domain,)),
                })

        elif self.can_export_data:
            from corehq.apps.export.views.download import (
                BulkDownloadNewFormExportView,
                DownloadNewCaseExportView,
                DownloadNewFormExportView,
                DownloadNewSmsExportView,
                DownloadNewDatasourceExportView,
            )
            from corehq.apps.export.views.edit import (
                EditCaseDailySavedExportView,
                EditCaseFeedView,
                EditFormDailySavedExportView,
                EditFormFeedView,
                EditNewCustomCaseExportView,
                EditNewCustomFormExportView,
                EditODataCaseFeedView,
                EditODataFormFeedView,
            )
            from corehq.apps.export.views.list import (
                CaseExportListView,
                DailySavedExportListView,
                DashboardFeedListView,
                FormExportListView,
                ODataFeedListView,
            )
            from corehq.apps.export.views.new import (
                CreateNewCaseFeedView,
                CreateNewCustomCaseExportView,
                CreateNewCustomFormExportView,
                CreateNewDailySavedCaseExport,
                CreateNewDailySavedFormExport,
                CreateNewFormFeedView,
                CreateODataCaseFeedView,
                CreateODataFormFeedView,
            )
            from corehq.apps.export.views.utils import (
                DailySavedExportPaywall,
                DashboardFeedPaywall,
            )

            if self.can_view_form_exports:
                export_data_views.append(
                    {
                        'title': _(FormExportListView.page_title),
                        'url': reverse(FormExportListView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-list-alt fa-regular fa-rectangle-list',
                        'subpages': [_f for _f in [
                            {
                                'title': _(CreateNewCustomFormExportView.page_title),
                                'urlname': CreateNewCustomFormExportView.urlname,
                            } if self.can_edit_commcare_data else None,
                            {
                                'title': _(BulkDownloadNewFormExportView.page_title),
                                'urlname': BulkDownloadNewFormExportView.urlname,
                            },
                            {
                                'title': _(DownloadNewFormExportView.page_title),
                                'urlname': DownloadNewFormExportView.urlname,
                            },
                            {
                                'title': _(EditNewCustomFormExportView.page_title),
                                'urlname': EditNewCustomFormExportView.urlname,
                            } if self.can_edit_commcare_data else None,
                        ] if _f]
                    }
                )
            if self.can_view_case_exports:
                export_data_views.append(
                    {
                        'title': _(CaseExportListView.page_title),
                        'url': reverse(CaseExportListView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa-solid fa-share-square',
                        'subpages': [_f for _f in [
                            {
                                'title': _(CreateNewCustomCaseExportView.page_title),
                                'urlname': CreateNewCustomCaseExportView.urlname,
                            } if self.can_edit_commcare_data else None,
                            {
                                'title': _(DownloadNewCaseExportView.page_title),
                                'urlname': DownloadNewCaseExportView.urlname,
                            },
                            {
                                'title': _(EditNewCustomCaseExportView.page_title),
                                'urlname': EditNewCustomCaseExportView.urlname,
                            } if self.can_edit_commcare_data else None,
                        ] if _f]
                    })

            if self.can_export_data_source:
                export_data_views.append(
                    {
                        'title': _(DownloadNewDatasourceExportView.page_title),
                        'url': reverse(DownloadNewDatasourceExportView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa fa-database',
                    })

            if self.can_view_sms_exports:
                export_data_views.append(
                    {
                        'title': _(DownloadNewSmsExportView.page_title),
                        'url': reverse(DownloadNewSmsExportView.urlname, args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa-regular fa-comment-dots',
                        'subpages': []
                    })

            if self.can_view_form_exports or self.can_view_case_exports:
                export_data_views.append({
                    'title': _('Find Data by ID'),
                    'url': reverse('data_find_by_id', args=[self.domain]),
                    'icon': 'fa fa-search',
                })

            if self.should_see_daily_saved_export_list_view:
                export_data_views.append({
                    "title": _(DailySavedExportListView.page_title),
                    "url": reverse(DailySavedExportListView.urlname, args=(self.domain,)),
                    'icon': 'fa-solid fa-calendar-days',
                    "show_in_dropdown": True,
                    "subpages": [_f for _f in [
                        {
                            'title': _(CreateNewDailySavedFormExport.page_title),
                            'urlname': CreateNewDailySavedFormExport.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': _(CreateNewDailySavedCaseExport.page_title),
                            'urlname': CreateNewDailySavedCaseExport.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': _(EditFormDailySavedExportView.page_title),
                            'urlname': EditFormDailySavedExportView.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': _(EditCaseDailySavedExportView.page_title),
                            'urlname': EditCaseDailySavedExportView.urlname,
                        } if self.can_edit_commcare_data else None,
                    ] if _f]
                })
            elif self.should_see_daily_saved_export_paywall:
                export_data_views.append({
                    'title': _(DailySavedExportListView.page_title),
                    'url': reverse(DailySavedExportPaywall.urlname, args=(self.domain,)),
                    'icon': 'fa-solid fa-calendar-days',
                    'show_in_dropdown': True,
                    'subpages': []
                })
            if self.should_see_dashboard_feed_list_view:
                subpages = []
                if self.can_edit_commcare_data:
                    subpages = [
                        {
                            'title': _(CreateNewFormFeedView.page_title),
                            'urlname': CreateNewFormFeedView.urlname,
                        },
                        {
                            'title': _(CreateNewCaseFeedView.page_title),
                            'urlname': CreateNewCaseFeedView.urlname,
                        },
                        {
                            'title': _(EditFormFeedView.page_title),
                            'urlname': EditFormFeedView.urlname,
                        },
                        {
                            'title': _(EditCaseFeedView.page_title),
                            'urlname': EditCaseFeedView.urlname,
                        },
                    ]
                export_data_views.append({
                    'title': _(DashboardFeedListView.page_title),
                    'url': reverse(DashboardFeedListView.urlname, args=(self.domain,)),
                    'icon': 'fa-solid fa-gauge',
                    'show_in_dropdown': True,
                    'subpages': subpages
                })
            elif self.should_see_dashboard_feed_paywall:
                export_data_views.append({
                    'title': _(DashboardFeedListView.page_title),
                    'url': reverse(DashboardFeedPaywall.urlname, args=(self.domain,)),
                    'icon': 'fa-solid fa-gauge',
                    'show_in_dropdown': True,
                    'subpages': []
                })
            if self.can_view_odata_feed:
                subpages = [
                    {
                        'title': _(CreateODataCaseFeedView.page_title),
                        'urlname': CreateODataCaseFeedView.urlname,
                    },
                    {
                        'title': _(EditODataCaseFeedView.page_title),
                        'urlname': EditODataCaseFeedView.urlname,
                    },
                    {
                        'title': _(CreateODataFormFeedView.page_title),
                        'urlname': CreateODataFormFeedView.urlname,
                    },
                    {
                        'title': _(EditODataFormFeedView.page_title),
                        'urlname': EditODataFormFeedView.urlname,
                    },
                ]
                export_data_views.append({
                    'title': _(ODataFeedListView.page_title),
                    'url': reverse(ODataFeedListView.urlname, args=(self.domain,)),
                    'icon': 'fa fa-plug',
                    'show_in_dropdown': False,
                    'subpages': subpages
                })

            if toggles.SUPERSET_ANALYTICS.enabled(self.domain):
                from corehq.apps.export.views.list import (
                    CommCareAnalyticsListView,
                )
                export_data_views.append({
                    'title': CommCareAnalyticsListView.page_title,
                    'url': reverse(CommCareAnalyticsListView.urlname, args=(self.domain,)),
                    'icon': 'fa-regular fa-chart-bar',
                    'show_in_dropdown': False,
                    'subpages': []
                })

        if can_download_data_files(self.domain, self.couch_user):
            from corehq.apps.export.views.utils import DataFileDownloadList

            export_data_views.append({
                'title': _(DataFileDownloadList.page_title),
                'url': reverse(DataFileDownloadList.urlname, args=(self.domain,)),
                'icon': 'fa-regular fa-file-lines',
                'show_in_dropdown': True,
                'subpages': []
            })
        return export_data_views

    def _get_edit_section(self):
        from corehq.apps.data_interfaces.dispatcher import (
            EditDataInterfaceDispatcher,
        )
        edit_section = EditDataInterfaceDispatcher.navigation_sections(
            request=self._request, domain=self.domain)

        if self.can_use_data_cleanup:
            from corehq.apps.data_interfaces.views import (
                AutomaticUpdateRuleListView,
            )
            automatic_update_rule_list_view = {
                'title': _(AutomaticUpdateRuleListView.page_title),
                'url': reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]),
            }
            if edit_section:
                edit_section[0][1].append(automatic_update_rule_list_view)
            else:
                edit_section = [(gettext_lazy('Edit Data'), [automatic_update_rule_list_view])]

        if self.can_use_dedupe:
            from corehq.apps.data_interfaces.views import (
                DeduplicationRuleListView,
            )
            deduplication_list_view = {
                'title': _(DeduplicationRuleListView.page_title),
                'url': reverse(DeduplicationRuleListView.urlname, args=[self.domain]),
            }
            edit_section[0][1].append(deduplication_list_view)

        return edit_section

    def _get_explore_data_views(self):
        explore_data_views = []
        if ((toggles.EXPLORE_CASE_DATA.enabled_for_request(self._request)
             or self.can_view_ecd_preview) and self.can_edit_commcare_data):
            from corehq.apps.data_interfaces.views import ExploreCaseDataView
            explore_data_views.append({
                'title': _(ExploreCaseDataView.page_title),
                'url': reverse(ExploreCaseDataView.urlname, args=(self.domain,)),
                'show_in_dropdown': False,
                'icon': 'fa-solid fa-location-dot',
                'subpages': [],
            })
        if self.couch_user.is_superuser or toggles.IS_CONTRACTOR.enabled(self.couch_user.username):
            from corehq.apps.case_search.models import (
                case_search_enabled_for_domain,
            )
            if case_search_enabled_for_domain(self.domain):
                from corehq.apps.case_search.views import CaseSearchView, ProfileCaseSearchView
                explore_data_views.extend([{
                    'title': _(CaseSearchView.page_title),
                    'url': reverse(CaseSearchView.urlname, args=(self.domain,)),
                    'icon': 'fa fa-search',
                    'show_in_dropdown': False,
                    'subpages': [],
                }, {
                    'title': _(ProfileCaseSearchView.page_title),
                    'url': reverse(ProfileCaseSearchView.urlname, args=(self.domain,)),
                    'icon': 'fa fa-clock',
                    'show_in_dropdown': False,
                    'subpages': [],
                }])
        return explore_data_views

    def _get_geospatial_views(self):
        geospatial_items = CaseManagementMapDispatcher.navigation_sections(
            request=self._request, domain=self.domain)
        management_sections = [
            {
                'title': _("Manage GPS Data"),
                'url': reverse(GPSCaptureView.urlname, args=(self.domain,)),
            },
            {
                'title': _("Configure Geospatial Settings"),
                'url': reverse(GeospatialConfigPage.urlname, args=(self.domain,)),
            }
        ]
        for section in management_sections:
            geospatial_items[0][1].append(section)
        return geospatial_items

    @property
    def dropdown_items(self):
        if (
            self.can_only_see_deid_exports or (
                not self.can_export_data and not can_download_data_files(self.domain, self.couch_user)
            )
        ):
            return []

        from corehq.apps.export.views.download import DownloadNewSmsExportView
        from corehq.apps.export.views.list import (
            CaseExportListView,
            FormExportListView,
        )

        items = []
        if self.can_view_form_exports:
            items.append(dropdown_dict(
                _(FormExportListView.page_title),
                url=reverse(FormExportListView.urlname, args=(self.domain,))
            ))
        if self.can_view_case_exports:
            items.append(dropdown_dict(
                _(CaseExportListView.page_title),
                url=reverse(CaseExportListView.urlname, args=(self.domain,))
            ))
        if self.can_view_sms_exports:
            items.append(dropdown_dict(
                _(DownloadNewSmsExportView.page_title),
                url=reverse(DownloadNewSmsExportView.urlname, args=(self.domain,))
            ))
        if self.can_view_ecd_preview and self.can_edit_commcare_data:
            from corehq.apps.data_interfaces.views import ExploreCaseDataView
            items.append(dropdown_dict(
                _('Explore Case Data (Preview)'),
                url=reverse(ExploreCaseDataView.urlname, args=(self.domain,)),
            ))
        if self.can_view_odata_feed:
            from corehq.apps.export.views.list import ODataFeedListView
            items.append(dropdown_dict(
                _(ODataFeedListView.page_title),
                url=reverse(ODataFeedListView.urlname, args=(self.domain,)),
            ))
        if toggles.SUPERSET_ANALYTICS.enabled(self.domain):
            from corehq.apps.export.views.list import CommCareAnalyticsListView
            items.append(dropdown_dict(
                _(CommCareAnalyticsListView.page_title),
                url=reverse(CommCareAnalyticsListView.urlname, args=(self.domain,))
            ))
        if self._can_view_data_dictionary:
            items.append(dropdown_dict(
                DataDictionaryView.page_title,
                url=reverse(DataDictionaryView.urlname, args=[self.domain]),
            ))

        if items:
            items += [self.divider]
        items += [dropdown_dict(_("View All"), url=self.url)]
        return items


class ApplicationsTab(UITab):
    view = "default_new_app"

    url_prefix_formats = ('/a/{domain}/apps/',)

    @property
    def title(self):
        return _("Applications")

    @classmethod
    def make_app_title(cls, app):
        app_type = ''
        if is_remote_app(app):
            app_type = _('Remote')
        elif is_linked_app(app):
            app_type = _('Linked')

        return format_html(
            '{}{}',
            strip_tags(app.name) or _('(Untitled)'),
            f' ({app_type})' if app_type else ''
        )

    @property
    def dropdown_items(self):
        apps = get_brief_apps_in_domain(self.domain)
        apps = sorted(apps, key=lambda item: item.name.lower())
        submenu_context = []
        if not apps:
            return submenu_context

        submenu_context.append(dropdown_dict(_('My Applications'),
                               is_header=True))
        for app in apps:
            url = reverse('view_app', args=[self.domain, app.get_id]) if self.couch_user.can_edit_apps() \
                else reverse('release_manager', args=[self.domain, app.get_id])
            app_title = self.make_app_title(app)
            if 'created_from_template' in app and app['created_from_template'] == 'appcues':
                if domain_is_on_trial(self.domain):
                    # If trial is over, domain may have lost web apps access, don't do appcues intro
                    url = url + '?appcues=1'

            submenu_context.append(dropdown_dict(
                app_title,
                url=url,
                data_id=app.get_id,
            ))

        if self.couch_user.can_edit_apps():
            submenu_context.append(self.divider)
            submenu_context.append(dropdown_dict(
                _('New Application'),
                url=(reverse('default_new_app', args=[self.domain])),
            ))
        if toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.enabled_for_request(self._request):
            submenu_context.append(dropdown_dict(
                _('Translations'),
                url=(reverse('convert_translations', args=[self.domain])),
            ))

        return submenu_context

    @property
    def _is_viewable(self):
        couch_user = self.couch_user
        return (self.domain and couch_user
                and couch_user.can_view_apps()
                and (couch_user.is_member_of(self.domain, allow_enterprise=True) or couch_user.is_superuser)
                and has_privilege(self._request, privileges.PROJECT_ACCESS))


class CloudcareTab(UITab):
    title = gettext_noop("Web Apps")
    url_prefix_formats = ('/a/{domain}/cloudcare/',)

    ga_tracker = GaTracker('CloudCare', 'Click Cloud-Care top-level nav')

    @property
    def view(self):
        from corehq.apps.cloudcare.views import FormplayerMain
        return FormplayerMain.urlname

    @property
    def _is_viewable(self):
        return (
            has_privilege(self._request, privileges.CLOUDCARE)
            and self.domain
            and (self.couch_user.can_access_web_apps() or self.couch_user.is_commcare_user())
        )


class MessagingTab(UITab):
    title = gettext_noop("Messaging")
    view = "sms_default"

    url_prefix_formats = (
        '/a/{domain}/messaging/',
        '/a/{domain}/sms/',
        '/a/{domain}/reminders/',
        '/a/{domain}/data/edit/case_groups/',
        '/a/{domain}/email/',
    )

    @property
    def _is_viewable(self):
        return ((self.can_access_reminders or self.can_use_outbound_sms)
                and (self.project
                     and not (self.project.is_snapshot
                              or self.couch_user.is_commcare_user()))
                and self.couch_user.can_edit_messaging())

    @property
    @memoized
    def can_use_outbound_sms(self):
        return has_privilege(self._request, privileges.OUTBOUND_SMS)

    @property
    @memoized
    def can_use_inbound_sms(self):
        return has_privilege(self._request, privileges.INBOUND_SMS)

    @property
    @memoized
    def can_access_reminders(self):
        return has_privilege(self._request, privileges.REMINDERS_FRAMEWORK)

    @property
    @memoized
    def reminders_urls(self):
        reminders_urls = []

        if self.can_use_inbound_sms:
            reminders_urls.append({
                'title': _("Keywords"),
                'url': reverse(KeywordsListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': _(AddNormalKeywordView.page_title),
                        'urlname': AddNormalKeywordView.urlname,
                    },
                    {
                        'title': _(AddStructuredKeywordView.page_title),
                        'urlname': AddStructuredKeywordView.urlname,
                    },
                    {
                        'title': _(EditNormalKeywordView.page_title),
                        'urlname': EditNormalKeywordView.urlname,
                    },
                    {
                        'title': _(EditStructuredKeywordView.page_title),
                        'urlname': EditStructuredKeywordView.urlname,
                    },
                ],
            })

            if self.couch_user.is_superuser or toggles.SUPPORT.enabled_for_request(self._request):
                reminders_urls.append({
                    'title': _("Test Inbound SMS"),
                    'url': reverse("message_test", args=[self.domain]),
                })

        return reminders_urls

    @property
    @memoized
    def messages_urls(self):
        messages_urls = []

        if self.can_use_outbound_sms:
            messages_urls.extend([
                {
                    'title': _('Compose SMS Message'),
                    'url': reverse('sms_compose_message', args=[self.domain])
                },
            ])

        if self.can_access_reminders:
            messages_urls.extend([
                {
                    'title': _("Broadcasts"),
                    'url': reverse(NewBroadcastListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _("New"),
                            'urlname': CreateScheduleView.urlname,
                        },
                        {
                            'title': _("Edit"),
                            'urlname': EditScheduleView.urlname,
                        },
                    ],
                },
                {
                    'title': _("Conditional Alerts"),
                    'url': reverse(ConditionalAlertListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _("New"),
                            'urlname': CreateConditionalAlertView.urlname,
                        },
                        {
                            'title': _("Edit"),
                            'urlname': EditConditionalAlertView.urlname,
                        },
                        {
                            'title': UploadConditionalAlertView.page_title,
                            'urlname': UploadConditionalAlertView.urlname,
                        },
                    ],
                },
            ])

        return messages_urls

    @property
    @memoized
    def supply_urls(self):
        supply_urls = []

        if self.project.commtrack_enabled:
            from corehq.apps.sms.views import SubscribeSMSView
            supply_urls.append(
                {'title': gettext_lazy("Subscribe to SMS Reports"),
                 'url': reverse(SubscribeSMSView.urlname, args=[self.domain])}
            )

        return supply_urls

    @property
    @memoized
    def contacts_urls(self):
        contacts_urls = []

        if self.couch_user.can_edit_messaging():
            contacts_urls.append(
                {'title': _('Chat'),
                 'url': reverse('chat_contacts', args=[self.domain])}
            )

        if self.couch_user.can_edit_messaging():
            from corehq.apps.data_interfaces.views import (
                CaseGroupCaseManagementView,
                CaseGroupListView,
            )
            contacts_urls.append({
                'title': _(CaseGroupListView.page_title),
                'url': reverse(CaseGroupListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': _(CaseGroupCaseManagementView.page_title),
                        'urlname': CaseGroupCaseManagementView.urlname,
                    }
                ]
            })

        return contacts_urls

    @property
    @memoized
    def settings_urls(self):
        settings_urls = []

        if self.can_use_outbound_sms and self.couch_user.is_domain_admin():
            from corehq.apps.sms.views import (
                AddDomainGatewayView,
                DomainSmsGatewayListView,
                EditDomainGatewayView,
            )
            settings_urls.append({
                'title': _('SMS Connectivity'),
                'url': reverse(DomainSmsGatewayListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': _("Add Gateway"),
                        'urlname': AddDomainGatewayView.urlname,
                    },
                    {
                        'title': _("Edit Gateway"),
                        'urlname': EditDomainGatewayView.urlname,
                    },
                ],
            })

        if toggles.CUSTOM_EMAIL_GATEWAY.enabled(self.domain) and self.couch_user.is_domain_admin():
            settings_urls.append({
                'title': _('Email Connectivity'),
                'url': reverse(EmailSMTPSettingsView.urlname, args=[self.domain]),
            })

        if self.couch_user.is_superuser or self.couch_user.is_domain_admin(self.domain):
            settings_urls.extend([
                {'title': gettext_lazy("General Settings"),
                 'url': reverse('sms_settings', args=[self.domain])},
                {'title': gettext_lazy("Languages"),
                 'url': reverse('sms_languages', args=[self.domain])},
            ])

        return settings_urls

    @property
    @memoized
    def whatsapp_urls(self):
        from corehq.apps.sms.models import SQLMobileBackend
        from corehq.apps.sms.views import WhatsAppTemplatesView
        from corehq.messaging.smsbackends.infobip.models import InfobipBackend
        from corehq.messaging.smsbackends.turn.models import (
            SQLTurnWhatsAppBackend,
        )

        whatsapp_urls = []

        domain_has_turn_integration = (
            SQLTurnWhatsAppBackend.get_api_id() in
            (b.get_api_id() for b in
             SQLMobileBackend.get_domain_backends(SQLMobileBackend.SMS, self.domain)))

        domain_has_infobip_integration = (
            InfobipBackend.get_api_id() in
            (b.get_api_id() for b in
             SQLMobileBackend.get_domain_backends(SQLMobileBackend.SMS, self.domain)))
        user_is_admin = (self.couch_user.is_superuser or self.couch_user.is_domain_admin(self.domain))

        if user_is_admin and (domain_has_turn_integration or domain_has_infobip_integration):
            whatsapp_urls.append({
                'title': _('Template Management'),
                'url': reverse(WhatsAppTemplatesView.urlname, args=[self.domain]),
            })
        return whatsapp_urls

    @property
    def dropdown_items(self):
        result = []

        result.append(dropdown_dict(_("Dashboard"), is_header=True))
        result.append(dropdown_dict(
            _("Dashboard"),
            url=reverse(MessagingDashboardView.urlname, args=[self.domain]),
        ))

        if result:
            result.append(self.divider)

        result.append(dropdown_dict(_("Messages"), is_header=True))
        result.append(dropdown_dict(
            _("Broadcasts"),
            url=reverse(NewBroadcastListView.urlname, args=[self.domain]),
        ))
        result.append(dropdown_dict(
            _("Conditional Alerts"),
            url=reverse(ConditionalAlertListView.urlname, args=[self.domain]),
        ))

        if result:
            result.append(self.divider)

        result.append(dropdown_dict(
            _("View All"),
            url=reverse(MessagingDashboardView.urlname, args=[self.domain]),
        ))

        return result

    @property
    def sidebar_items(self):
        items = []

        items.append((
            _("Dashboard"),
            [{
                'title': _("Dashboard"),
                'url': reverse(MessagingDashboardView.urlname, args=[self.domain])
            }]
        ))

        for title, urls in (
            (_("Messages"), self.messages_urls),
            (_("Data Collection and Reminders"), self.reminders_urls),
            (_("CommCare Supply"), self.supply_urls),
            (_("Contacts"), self.contacts_urls),
            (_("Settings"), self.settings_urls),
            (_("WhatsApp Settings"), self.whatsapp_urls),
        ):
            if urls:
                items.append((title, urls))
        return items


class ProjectUsersTab(UITab):
    title = gettext_noop("Users")
    view = "users_default"

    url_prefix_formats = (
        '/a/{domain}/reports/user_management/',
        '/a/{domain}/settings/users/',
        '/a/{domain}/settings/cloudcare/',
        '/a/{domain}/settings/locations/',
        '/a/{domain}/location_reassignment/',
    )

    @property
    def _is_viewable(self):
        can_do_something = (
            self.couch_user.can_edit_commcare_users()
            or self.couch_user.can_view_commcare_users()
            or self.couch_user.can_edit_groups()
            or self.couch_user.can_view_groups()
            or self.couch_user.can_edit_locations()
            or self.couch_user.can_view_locations()
            or self.couch_user.can_view_roles()
        ) and self.has_project_access

        return self.domain and (
            can_do_something
            or self.couch_user.can_edit_web_users()
            or self.couch_user.can_view_web_users()
        )

    @property
    def can_view_cloudcare(self):
        return (has_privilege(self._request, privileges.CLOUDCARE)
                and self.couch_user.is_domain_admin())

    @property
    def has_project_access(self):
        return has_privilege(self._request, privileges.PROJECT_ACCESS)

    def _get_mobile_users_menu(self):
        menu = []
        if ((self.couch_user.can_edit_commcare_users()
                or self.couch_user.can_view_commcare_users())
                and self.has_project_access):
            def _get_commcare_username(request=None, couch_user=None,
                                       **context):
                if (couch_user.user_id != request.couch_user.user_id
                        or couch_user.is_commcare_user()):
                    username = couch_user.username_in_report
                    if couch_user.is_deleted():
                        username = format_html('{} ({})', username, _("Deleted"))
                    return username
                else:
                    return None

            from corehq.apps.users.views.mobile import (
                ConfirmBillingAccountForExtraUsersView,
                EditCommCareUserView,
                MobileWorkerListView,
            )

            menu.append({
                'title': _(MobileWorkerListView.page_title),
                'url': reverse(MobileWorkerListView.urlname,
                               args=[self.domain]),
                'description': _(
                    "Create and manage users for CommCare and CloudCare."),
                'subpages': [
                    {'title': _get_commcare_username,
                     'urlname': EditCommCareUserView.urlname},
                    {'title': _('Bulk Upload'),
                     'urlname': 'upload_commcare_users'},
                    {'title': _('Bulk Delete'),
                     'urlname': 'delete_commcare_users'},
                    {'title': _('Bulk Lookup'),
                     'urlname': 'commcare_users_lookup'},
                    {'title': _('Edit User Fields'),
                     'urlname': 'user_fields_view'},
                    {'title': _('Filter and Download Mobile Workers'),
                     'urlname': 'filter_and_download_commcare_users'},
                    {'title': _(
                        ConfirmBillingAccountForExtraUsersView.page_title),
                        'urlname': ConfirmBillingAccountForExtraUsersView.urlname},
                ],
                'show_in_dropdown': True,
            })

        if ((self.couch_user.can_edit_groups() or self.couch_user.can_view_groups())
                and self.has_project_access):
            is_view_only_subpage = (hasattr(self._request, 'is_view_only')
                                    and self._request.is_view_only)
            menu.append({
                'title': _('Groups'),
                'url': reverse('all_groups', args=[self.domain]),
                'description': _("""Create and manage
                            reporting and case sharing groups
                            for Mobile Workers."""),
                'subpages': [
                    {'title': lambda **context: (
                        "%s %s" % (_("Viewing") if is_view_only_subpage
                                   else _("Editing"), context['group'].name)),
                     'urlname': 'group_members'},
                    {'title': _('Membership Info'),
                     'urlname': 'group_membership'}
                ],
                'show_in_dropdown': True,
            })

        if self.can_view_cloudcare:
            title = _("Web Apps Permissions")
            menu.append({
                'title': title,
                'url': reverse('cloudcare_app_settings',
                               args=[self.domain])
            })

        return menu

    def _get_project_users_menu(self):
        menu = []

        if self.couch_user.can_edit_web_users() or self.couch_user.can_view_web_users():
            def _get_web_username(request=None, couch_user=None, **context):
                if (couch_user.user_id != request.couch_user.user_id
                        or not couch_user.is_commcare_user()):
                    username = couch_user.human_friendly_name
                    if couch_user.is_deleted():
                        username = format_html('{} ({})', username, _('Deleted'))
                    return username
                else:
                    return None

            from corehq.apps.users.views import (
                EditWebUserView,
                EnterpriseUsersView,
                ListWebUsersView,
            )
            from corehq.apps.users.views.mobile.users import (
                FilteredWebUserDownload,
            )

            if toggles.ENTERPRISE_USER_MANAGEMENT.enabled_for_request(self._request):
                menu.append({
                    'title': _(EnterpriseUsersView.page_title),
                    'url': reverse(EnterpriseUsersView.urlname, args=[self.domain]),
                    'show_in_dropdown': True,
                })

            menu = menu + [{
                'title': _(ListWebUsersView.page_title),
                'url': reverse(ListWebUsersView.urlname,
                               args=[self.domain]),
                'description': _(
                    "Grant other CommCare HQ users access to your project."),
                'subpages': [
                    {
                        'title': _("Invite Web User"),
                        'urlname': 'invite_web_user'
                    },
                    {
                        'title': _get_web_username,
                        'urlname': EditWebUserView.urlname
                    },
                    {
                        'title': FilteredWebUserDownload.page_title,
                        'urlname': FilteredWebUserDownload.urlname,
                    },
                    {
                        'title': _("Bulk Upload"),
                        'urlname': 'upload_web_users',
                    },
                ],
                'show_in_dropdown': True,
            }]

        if ((self.couch_user.is_domain_admin() or self.couch_user.can_view_roles())
                and self.has_project_access):
            from corehq.apps.users.views import ListRolesView
            menu.append({
                'title': _(ListRolesView.page_title),
                'url': reverse(ListRolesView.urlname,
                               args=[self.domain]),
                'description': _(
                    "View and manage user roles."),
                'subpages': [],
                'show_in_dropdown': True,
            })

        return menu

    def _get_locations_menu(self):
        if (not has_privilege(self._request, privileges.LOCATIONS)
                and users_have_locations(self.domain)):
            return [
                {
                    'title': _("No longer available"),
                    'url': reverse('downgrade_locations', args=[self.domain]),
                    'show_in_dropdown': True,
                },
            ]

        if not has_privilege(self._request, privileges.LOCATIONS):
            return []

        menu = []

        if (self.couch_user.can_edit_locations()
                or self.couch_user.can_view_locations()):
            from corehq.apps.locations.views import (
                EditLocationView,
                FilteredLocationDownload,
                LocationFieldsView,
                LocationImportStatusView,
                LocationImportView,
                LocationsListView,
                NewLocationView,
            )
            is_view_only = (hasattr(self._request, 'is_view_only')
                            and self._request.is_view_only)
            menu.append({
                'title': _(LocationsListView.page_title),
                'url': reverse(LocationsListView.urlname, args=[self.domain]),
                'show_in_dropdown': True,
                'subpages': [
                    {
                        'title': _(NewLocationView.page_title),
                        'urlname': NewLocationView.urlname,
                    },
                    {
                        'title': _("View Location") if is_view_only
                        else _(EditLocationView.page_title),
                        'urlname': EditLocationView.urlname,
                    },
                    {
                        'title': _(LocationImportView.page_title),
                        'urlname': LocationImportView.urlname,
                    },
                    {
                        'title': _(LocationImportStatusView.page_title),
                        'urlname': LocationImportStatusView.urlname,
                    },
                    {
                        'title': _(LocationFieldsView.page_name()),
                        'urlname': LocationFieldsView.urlname,
                    },
                    {
                        'title': _(FilteredLocationDownload.page_title),
                        'urlname': FilteredLocationDownload.urlname,
                    },
                ]
            })

        from corehq.apps.locations.permissions import (
            user_can_edit_location_types,
        )
        if (user_can_edit_location_types(self.couch_user, self.domain)
                and self.couch_user.can_edit_locations()):
            from corehq.apps.locations.views import LocationTypesView
            menu.append({
                'title': _(LocationTypesView.page_title),
                'url': reverse(LocationTypesView.urlname, args=[self.domain]),
                'show_in_dropdown': True,
            })

        return menu

    @property
    def sidebar_items(self):
        items = []

        mobile_users_menu = self._get_mobile_users_menu()
        if mobile_users_menu:
            items.append((_('Application Users'), mobile_users_menu))

        project_users_menu = self._get_project_users_menu()
        if project_users_menu:
            items.append((_('Project Users'), project_users_menu))

        locations_menu = self._get_locations_menu()
        if locations_menu:
            items.append((_('Organization'), locations_menu))

        if (
                user_can_view_reports(self.project, self.couch_user)
                and has_privilege(self._request, privileges.PROJECT_ACCESS)
                and toggles.USER_HISTORY_REPORT.enabled(self.couch_user.username)
        ):
            user_management_menu = [{
                'title': UserHistoryReport.name,
                'url': reverse('user_management_report_dispatcher',
                               args=[self.domain, UserHistoryReport.slug])
            }]
            items.append((_('User Management'), user_management_menu))
        return items


class EnterpriseSettingsTab(UITab):
    title = gettext_noop("Enterprise Settings")

    url_prefix_formats = (
        '/a/{domain}/enterprise/',
    )

    _is_viewable = False

    @property
    def sidebar_items(self):
        items = super(EnterpriseSettingsTab, self).sidebar_items
        enterprise_views = []
        enterprise_user_management_views = []

        if has_privilege(self._request, privileges.PROJECT_ACCESS):
            enterprise_views.extend([
                {
                    'title': _('Enterprise Dashboard'),
                    'url': reverse('enterprise_dashboard', args=[self.domain]),
                },
                {
                    'title': _('Enterprise Settings'),
                    'url': reverse('enterprise_settings', args=[self.domain]),
                },
            ])
        enterprise_views.append({
            'title': _('Billing Statements'),
            'url': reverse('enterprise_billing_statements',
                        args=[self.domain])
        })
        if IdentityProvider.domain_has_editable_identity_provider(self.domain):
            from corehq.apps.sso.views.enterprise_admin import (
                EditIdentityProviderEnterpriseView,
                ManageSSOEnterpriseView,
            )
            manage_sso = {
                'title': _(ManageSSOEnterpriseView.page_title),
                'url': reverse(ManageSSOEnterpriseView.urlname, args=(self.domain,)),
                'subpages': [
                    {
                        'title': _(EditIdentityProviderEnterpriseView.page_title),
                        'urlname': EditIdentityProviderEnterpriseView.urlname,
                    },
                ],
            }
            if toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.enabled_for_request(self._request):
                enterprise_user_management_views.append(manage_sso)
            else:
                enterprise_views.append(manage_sso)
        if self.couch_user.is_superuser:
            from corehq.apps.enterprise.models import EnterprisePermissions
            if toggles.DOMAIN_PERMISSIONS_MIRROR.enabled_for_request(self._request) \
                    or EnterprisePermissions.get_by_domain(self.domain).is_enabled:
                enterprise_views.append({
                    'title': _("Enterprise Permissions"),
                    'url': reverse("enterprise_permissions", args=[self.domain]),
                    'description': _("View project spaces where users receive automatic access"),
                    'subpages': [],
                    'show_in_dropdown': False,
                })
        items.append((_('Manage Enterprise'), enterprise_views))
        if toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.enabled_for_request(self._request):
            enterprise_user_management_views.append({
                'title': _(ManageEnterpriseMobileWorkersView.page_title),
                'url': reverse(ManageEnterpriseMobileWorkersView.urlname, args=[self.domain]),
            })
            items.append((_("User Management"), enterprise_user_management_views))

        if BillingAccount.should_show_sms_billable_report(self.domain):
            items.extend(EnterpriseReportDispatcher.navigation_sections(
                request=self._request, domain=self.domain))

        return items


class TranslationsTab(UITab):
    title = gettext_noop('Translations')

    url_prefix_formats = (
        '/a/{domain}/translations/',
    )
    _is_viewable = False

    @property
    def sidebar_items(self):
        items = super(TranslationsTab, self).sidebar_items
        items.append((_('Translations'), [
            {'url': reverse('convert_translations', args=[self.domain]),
             'title': 'Convert Translations'
             }
        ]))
        if transifex_details_available_for_domain(self.domain):
            if toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.enabled_for_request(self._request):
                items.append((_('Translations'), [
                    {
                        'url': reverse('app_translations', args=[self.domain]),
                        'title': _('Manage App Translations')
                    },
                    {
                        'url': reverse('pull_resource', args=[self.domain]),
                        'title': _('Pull Resource')
                    },
                    {
                        'url': reverse('blacklist_translations', args=[self.domain]),
                        'title': _('Blacklist Translations')
                    },
                    {
                        'url': reverse('download_translations', args=[self.domain]),
                        'title': _('Download Translations')
                    },
                    {
                        'url': reverse('migrate_transifex_project', args=[self.domain]),
                        'title': _('Migrate Project')
                    },
                ]))
        return items


class ProjectSettingsTab(UITab):
    title = gettext_noop("Project Settings")
    view = 'domain_settings_default'

    url_prefix_formats = (
        '/a/{domain}/settings/project/',
        '/a/{domain}/phone/prime_restore/',
        '/a/{domain}/motech/',
        '/a/{domain}/dhis2/',
        '/a/{domain}/openmrs/',
        '/a/{domain}/registries/',
    )

    _is_viewable = False

    @property
    def sidebar_items(self):
        items = []
        user_is_admin = self.couch_user.is_domain_admin(self.domain)
        user_is_billing_admin = self.couch_user.can_edit_billing()
        user_can_manage_domain_alerts = self.couch_user.can_manage_domain_alerts(self.domain)
        has_project_access = has_privilege(self._request, privileges.PROJECT_ACCESS)

        project_info = []

        if user_is_admin and has_project_access:
            from corehq.apps.domain.views.settings import (
                EditBasicProjectInfoView,
                EditPrivacySecurityView,
            )

            project_info.extend([
                {
                    'title': _(EditBasicProjectInfoView.page_title),
                    'url': reverse(EditBasicProjectInfoView.urlname, args=[self.domain])
                },
                {
                    'title': _(EditPrivacySecurityView.page_title),
                    'url': reverse(EditPrivacySecurityView.urlname, args=[self.domain])
                }
            ])

        from corehq.apps.domain.views.settings import EditMyProjectSettingsView
        project_info.append({
            'title': _(EditMyProjectSettingsView.page_title),
            'url': reverse(EditMyProjectSettingsView.urlname, args=[self.domain])
        })

        items.append((_('Project Information'), project_info))

        if (user_is_admin or user_can_manage_domain_alerts) and has_project_access:
            section = []
            if user_is_admin:
                section = _get_administration_section(self.domain)
            elif user_can_manage_domain_alerts:
                section = _get_manage_domain_alerts_section(self.domain)
            if section:
                items.append((_('Project Administration'), section))

        if self.couch_user.can_edit_motech() and has_project_access:
            integration_nav = _get_integration_section(self.domain, self.couch_user)
            if integration_nav:
                items.append((_('Integration'), integration_nav))

        feature_flag_items = _get_feature_flag_items(self.domain, self.couch_user)
        if feature_flag_items and has_project_access:
            items.append((_('Pre-release Features'), feature_flag_items))

        release_management_title, release_management_items = _get_release_management_items(self.couch_user,
                                                                                           self.domain)
        if release_management_items:
            items.append((release_management_title, release_management_items))

        from corehq.apps.users.models import WebUser
        if isinstance(self.couch_user, WebUser):
            if (user_is_billing_admin or self.couch_user.is_superuser) and not settings.ENTERPRISE_MODE:
                from corehq.apps.domain.views.accounting import (
                    ConfirmSubscriptionRenewalView,
                    DomainBillingStatementsView,
                    DomainSubscriptionView,
                    EditExistingBillingAccountView,
                    InternalSubscriptionManagementView,
                )
                current_subscription = Subscription.get_active_subscription_by_domain(self.domain)
                subscription = [
                    {
                        'title': _(DomainSubscriptionView.page_title),
                        'url': reverse(DomainSubscriptionView.urlname,
                                       args=[self.domain]),
                        'subpages': [
                            {
                                'title': _(ConfirmSubscriptionRenewalView.page_title),
                                'urlname': ConfirmSubscriptionRenewalView.urlname,
                                'url': reverse(
                                    ConfirmSubscriptionRenewalView.urlname,
                                    args=[self.domain]),
                            }
                        ]
                    },
                ]
                if current_subscription is not None:
                    subscription.append(
                        {
                            'title': _(EditExistingBillingAccountView.page_title),
                            'url': reverse(EditExistingBillingAccountView.urlname,
                                           args=[self.domain]),
                        },
                    )
                if (current_subscription is not None
                        and Invoice.exists_for_domain(self.domain)):
                    subscription.append(
                        {
                            'title': _(DomainBillingStatementsView.page_title),
                            'url': reverse(DomainBillingStatementsView.urlname,
                                           args=[self.domain]),
                        }
                    )
                if self.couch_user.is_superuser:
                    subscription.append({
                        'title': _('Internal Subscription Management (Dimagi Only)'),
                        'url': reverse(
                            InternalSubscriptionManagementView.urlname,
                            args=[self.domain],
                        )
                    })
                items.append((_('Subscription'), subscription))

        if self.couch_user.is_superuser:
            from corehq.apps.domain.views.internal import (
                EditInternalCalculationsView,
                EditInternalDomainInfoView,
                FlagsAndPrivilegesView,
            )

            internal_admin = [
                {
                    'title': _(EditInternalDomainInfoView.page_title),
                    'url': reverse(EditInternalDomainInfoView.urlname,
                                   args=[self.domain])
                },
                {
                    'title': _(EditInternalCalculationsView.page_title),
                    'url': reverse(EditInternalCalculationsView.urlname,
                                   args=[self.domain])
                },
                {
                    'title': _(FlagsAndPrivilegesView.page_title),
                    'url': reverse(FlagsAndPrivilegesView.urlname, args=[self.domain])
                },
            ]
            if SHOULD_RATE_LIMIT_SUBMISSIONS:
                internal_admin.append({
                    'title': _(ProjectLimitsView.page_title),
                    'url': reverse(ProjectLimitsView.urlname, args=[self.domain])
                })
            items.append((_('Internal Data (Dimagi Only)'), internal_admin))

        return items


def _get_administration_section(domain):
    from corehq.apps.domain.views.internal import TransferDomainView
    from corehq.apps.domain.views.settings import (
        FeaturePreviewsView,
        ManageDomainMobileWorkersView,
        RecoveryMeasuresHistory,
    )
    from corehq.apps.ota.models import MobileRecoveryMeasure

    administration = []
    if (toggles.MOBILE_RECOVERY_MEASURES.enabled(domain)
            and MobileRecoveryMeasure.objects.filter(domain=domain).exists()):
        administration.append({
            'title': _(RecoveryMeasuresHistory.page_title),
            'url': reverse(RecoveryMeasuresHistory.urlname, args=[domain])
        })

    administration.append({
        'title': _(FeaturePreviewsView.page_title),
        'url': reverse(FeaturePreviewsView.urlname, args=[domain])
    })

    administration.extend(_get_manage_domain_alerts_section(domain))

    if toggles.TRANSFER_DOMAIN.enabled(domain):
        administration.append({
            'title': _(TransferDomainView.page_title),
            'url': reverse(TransferDomainView.urlname, args=[domain])
        })

    if toggles.MANAGE_RELEASES_PER_LOCATION.enabled(domain):
        administration.append({
            'title': _(ManageReleasesByLocation.page_title),
            'url': reverse(ManageReleasesByLocation.urlname, args=[domain])
        })

    if (toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.enabled(domain)
            and not is_domain_enterprise(domain)):
        administration.append(({
            'title': _(ManageDomainMobileWorkersView.page_title),
            'url': reverse(ManageDomainMobileWorkersView.urlname, args=[domain]),
        }))

    return administration


def _get_manage_domain_alerts_section(domain):
    from corehq.apps.domain.views.settings import ManageDomainAlertsView
    section = []

    if domain_has_privilege(domain, privileges.CUSTOM_DOMAIN_ALERTS):
        section.append({
            'title': _(ManageDomainAlertsView.page_title),
            'url': reverse(ManageDomainAlertsView.urlname, args=[domain])
        })
    return section


def _get_integration_section(domain, couch_user):
    from corehq.motech.repeaters.views import DomainForwardingRepeatRecords

    def _get_forward_name(repeater_type=None, **context):
        if repeater_type == 'FormRepeater':
            return _("Forward Forms")
        elif repeater_type == 'ShortFormRepeater':
            return _("Forward Form Stubs")
        elif repeater_type == 'CaseRepeater':
            return _("Forward Cases")

    integration = []

    if domain_has_privilege(domain, privileges.DATA_FORWARDING):
        integration.extend([
            {
                'title': _(ConnectionSettingsListView.page_title),
                'url': reverse(ConnectionSettingsListView.urlname, args=[domain])
            },
            {
                'title': _('Data Forwarding'),
                'url': reverse('domain_forwarding', args=[domain]),
                'subpages': [
                    {
                        'title': _get_forward_name,
                        'urlname': 'add_repeater',
                    },
                    {
                        'title': _get_forward_name,
                        'urlname': 'add_form_repeater',
                    },
                ]
            },
            {
                'title': _('Data Forwarding Records'),
                'url': reverse('domain_report_dispatcher',
                               args=[domain, DomainForwardingRepeatRecords.slug])
            },
            {
                'title': _(MotechLogListView.page_title),
                'url': reverse(MotechLogListView.urlname, args=[domain])
            }
        ])

    if toggles.BIOMETRIC_INTEGRATION.enabled(domain):
        from corehq.apps.integration.views import BiometricIntegrationView
        integration.append({
            'title': _(BiometricIntegrationView.page_title),
            'url': reverse(BiometricIntegrationView.urlname, args=[domain])
        })

    if toggles.DHIS2_INTEGRATION.enabled(domain):
        integration.append({
            'title': _(DataSetMapListView.page_title),
            'url': reverse(DataSetMapListView.urlname, args=[domain])
        })

    if toggles.OPENMRS_INTEGRATION.enabled(domain):
        integration.append({
            'title': _(OpenmrsImporterView.page_title),
            'url': reverse(OpenmrsImporterView.urlname, args=[domain])
        })

    if toggles.WIDGET_DIALER.enabled(domain):
        integration.append({
            'title': _(DialerSettingsView.page_title),
            'url': reverse(DialerSettingsView.urlname, args=[domain])
        })

    if toggles.HMAC_CALLOUT.enabled(domain):
        integration.append({
            'title': _(HmacCalloutSettingsView.page_title),
            'url': reverse(HmacCalloutSettingsView.urlname, args=[domain])
        })

    if toggles.GAEN_OTP_SERVER.enabled(domain):
        integration.append({
            'title': _(GaenOtpServerSettingsView.page_title),
            'url': reverse(GaenOtpServerSettingsView.urlname, args=[domain])
        })

    if toggles.EMBEDDED_TABLEAU.enabled(domain):
        if couch_user.is_superuser:
            from corehq.apps.reports.views import TableauServerView
            integration.append({
                'title': _(TableauServerView.page_title),
                'url': reverse(TableauServerView.urlname, args=[domain])
            })

        from corehq.apps.reports.views import TableauVisualizationListView
        integration.append({
            'title': _(TableauVisualizationListView.page_title),
            'url': reverse(TableauVisualizationListView.urlname, args=[domain])
        })

    if toggles.GENERIC_INBOUND_API.enabled(domain):
        from corehq.motech.generic_inbound.reports import ApiRequestLogReport
        from corehq.motech.generic_inbound.views import ConfigurableAPIListView
        integration.extend([{
            'title': ConfigurableAPIListView.page_title,
            'url': reverse(ConfigurableAPIListView.urlname, args=[domain])
        }, {
            'title': ApiRequestLogReport.name,
            'url': ApiRequestLogReport.get_url(domain),
        }])

    return integration


def _get_feature_flag_items(domain, couch_user):
    user_is_admin = couch_user.is_domain_admin(domain)

    from corehq.apps.domain.views.fixtures import LocationFixtureConfigView
    feature_flag_items = []
    if user_is_admin and toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain):
        feature_flag_items.append({
            'title': _('Case Search'),
            'url': reverse('case_search_config', args=[domain])
        })
    if user_is_admin and toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(domain):
        feature_flag_items.append({
            'title': _('Location Fixture'),
            'url': reverse(LocationFixtureConfigView.urlname, args=[domain])
        })

    from corehq.apps.registry.utils import RegistryPermissionCheck
    permission_check = RegistryPermissionCheck(domain, couch_user)
    if toggles.DATA_REGISTRY.enabled(domain) and permission_check.can_manage_some:
        feature_flag_items.append({
            'title': _('Data Registries'),
            'url': reverse('data_registries', args=[domain]),
            'subpages': [
                {
                    'title': _("Manage Registry"),
                    'urlname': "manage_registry",
                },
            ],
        })
    return feature_flag_items


def _get_release_management_items(user, domain):
    items = []
    title = None
    if not can_user_access_linked_domains(user, domain):
        return title, items

    if domain_has_privilege(domain, privileges.RELEASE_MANAGEMENT):
        title = _('Enterprise Release Management')
    elif domain_has_privilege(domain, privileges.LITE_RELEASE_MANAGEMENT):
        title = _('Multi-Environment Release Management')

    if title:
        items.append({
            'title': _('Linked Project Spaces'),
            'url': reverse('domain_links', args=[domain])
        })
        items.append({
            'title': _('Linked Project Space History'),
            'url': reverse('domain_report_dispatcher', args=[domain, 'project_link_report'])
        })

    return title, items


class MySettingsTab(UITab):
    title = gettext_noop("My Settings")
    view = 'default_my_settings'
    url_prefix_formats = ('/account/',)

    _is_viewable = False

    @property
    def sidebar_items(self):
        from corehq.apps.settings.views import (
            ApiKeyView,
            ChangeMyPasswordView,
            EnableMobilePrivilegesView,
            MyAccountSettingsView,
            MyProjectsList,
            TwoFactorProfileView,
        )
        menu_items = [
            {
                'title': _(MyAccountSettingsView.page_title),
                'url': reverse(MyAccountSettingsView.urlname),
            },
        ]

        if self.couch_user and self.couch_user.is_web_user():
            menu_items.append({
                'title': _(MyProjectsList.page_title),
                'url': reverse(MyProjectsList.urlname),
            })

        menu_items.append({
            'title': _(ChangeMyPasswordView.page_title),
            'url': reverse(ChangeMyPasswordView.urlname),
        })
        if Domain.active_for_couch_user(self.couch_user):
            menu_items.append({
                'title': _(TwoFactorProfileView.page_title),
                'url': reverse(TwoFactorProfileView.urlname),
            })
        menu_items.append({
            'title': _(ApiKeyView.page_title),
            'url': reverse(ApiKeyView.urlname),
        })

        if EnableMobilePrivilegesView.is_user_authorized(self.couch_user):
            menu_items.append({
                'title': _(EnableMobilePrivilegesView.page_title),
                'url': reverse(EnableMobilePrivilegesView.urlname),
            })
        return [[_("Manage My Settings"), menu_items]]


class AccountingTab(UITab):
    title = gettext_noop("Accounting")
    view = "accounting_default"

    url_prefix_formats = ('/hq/accounting/',)
    show_by_default = False

    @property
    def _is_viewable(self):
        return is_accounting_admin(self._request.user)

    @property
    @memoized
    def sidebar_items(self):
        items = AccountingAdminInterfaceDispatcher.navigation_sections(request=self._request, domain=self.domain)

        from corehq.apps.accounting.views import ManageAccountingAdminsView
        items.append(('Permissions', (
            {
                'title': _(ManageAccountingAdminsView.page_title),
                'url': reverse(ManageAccountingAdminsView.urlname),
            },
        )))

        from corehq.apps.accounting.views import (
            TestRenewalEmailView,
            TriggerBookkeeperEmailView,
            TriggerCustomerInvoiceView,
            TriggerInvoiceView,
        )
        other_actions = [
            {
                'title': _(TriggerInvoiceView.page_title),
                'url': reverse(TriggerInvoiceView.urlname),
            },
            {
                'title': _(TriggerCustomerInvoiceView.page_title),
                'url': reverse(TriggerCustomerInvoiceView.urlname),
            },
            {
                'title': _(TriggerBookkeeperEmailView.page_title),
                'url': reverse(TriggerBookkeeperEmailView.urlname),
            },
            {
                'title': _(TestRenewalEmailView.page_title),
                'url': reverse(TestRenewalEmailView.urlname),
            }
        ]
        if toggles.ACCOUNTING_TESTING_TOOLS.enabled_for_request(self._request):
            other_actions.extend([
                {
                    'title': _(TriggerDowngradeView.page_title),
                    'url': reverse(TriggerDowngradeView.urlname),
                },
                {
                    'title': _(TriggerAutopaymentsView.page_title),
                    'url': reverse(TriggerAutopaymentsView.urlname),
                },
            ])
        items.append(('Other Actions', other_actions))
        return items


class SMSAdminTab(UITab):
    title = gettext_noop("SMS Connectivity & Billing")
    view = "default_sms_admin_interface"

    url_prefix_formats = ('/hq/sms/',)
    show_by_default = False

    @property
    @memoized
    def sidebar_items(self):
        from corehq.apps.sms.views import (
            AddGlobalGatewayView,
            EditGlobalGatewayView,
            GlobalSmsGatewayListView,
        )
        items = SMSAdminInterfaceDispatcher.navigation_sections(request=self._request, domain=self.domain)
        if has_privilege(self._request, privileges.GLOBAL_SMS_GATEWAY):
            items.append((_('SMS Connectivity'), [
                {'title': _('Gateways'),
                'url': reverse(GlobalSmsGatewayListView.urlname),
                'subpages': [
                    {'title': _('Add Gateway'),
                    'urlname': AddGlobalGatewayView.urlname},
                    {'title': _('Edit Gateway'),
                    'urlname': EditGlobalGatewayView.urlname},
                ]},
                {'title': _('Default Gateways'),
                'url': reverse('global_backend_map')},
            ]))
        return items

    @property
    def _is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class AdminTab(UITab):
    title = gettext_noop("Admin")
    view = "default_admin_report"

    url_prefix_formats = ('/hq/admin/',)

    @property
    def dropdown_items(self):
        if (self.couch_user and not self.couch_user.is_superuser
                and (toggles.IS_CONTRACTOR.enabled(self.couch_user.username))):
            return [
                dropdown_dict(_("System Info"), url=reverse("system_info")),
                dropdown_dict(_("Feature Flags"), url=reverse("toggle_list")),
            ]

        submenu_context = [
            dropdown_dict(_("Reports"), is_header=True),
            dropdown_dict(_("Admin Reports"), url=reverse("default_admin_report")),
            dropdown_dict(_("System Info"), url=reverse("system_info")),
            dropdown_dict(_("Management"), is_header=True),
        ]
        try:
            if AccountingTab(self._request)._is_viewable:
                submenu_context.append(
                    dropdown_dict(AccountingTab.title, url=reverse('accounting_default'))
                )
        except Exception:
            pass
        submenu_context.extend([
            dropdown_dict(_("Feature Flags"), url=reverse("toggle_list")),
            dropdown_dict(_("SMS Connectivity & Billing"), url=reverse("default_sms_admin_interface")),
            self.divider,
        ])
        if self.couch_user.is_staff:
            submenu_context.append(dropdown_dict(_("Django Admin"), url="/admin"))
        submenu_context.append(dropdown_dict(_("View All"), url=self.url))
        return submenu_context

    @property
    def sidebar_items(self):
        # todo: convert these to dispatcher-style like other reports
        if (self.couch_user
                and (
                not self.couch_user.is_superuser
                and toggles.IS_CONTRACTOR.enabled(self.couch_user.username))):
            return [
                (_('System Health'), [
                    {'title': _('System Info'),
                     'url': reverse('system_info')},
                ])]

        admin_operations = [
            {'title': _('Style Guide'),
             'url': reverse(MainStyleGuideView.urlname),
             'icon': 'fa fa-paint-brush'},
        ]
        data_operations = []
        system_operations = []
        user_operations = [
            {'title': _('Look up user by email'),
             'url': reverse('web_user_lookup'),
             'icon': 'fa fa-address-book'},
        ]

        if self.couch_user and self.couch_user.is_staff:
            from corehq.apps.hqadmin.views.operations import (
                ReprocessMessagingCaseUpdatesView,
            )
            from corehq.apps.notifications.views import ManageNotificationView
            data_operations = [
                {'title': _('View raw documents'),
                 'url': reverse('raw_doc')},
                {'title': _('View documents in ES'),
                 'url': reverse('doc_in_es')},
            ]
            system_operations = [
                {'title': _('System Info'),
                 'url': reverse('system_info'),
                 'icon': 'fa fa-heartbeat'},
                {'title': _('Branches on Staging'),
                 'url': reverse('branches_on_staging'),
                 'icon': 'fa fa-tree'},
                {'title': GlobalThresholds.page_title,
                 'url': reverse(GlobalThresholds.urlname),
                 'icon': 'fa fa-fire'},
            ]
            user_operations = user_operations + [
                {'title': _('Grant superuser privileges'),
                 'url': reverse('superuser_management'),
                 'icon': 'fa fa-magic'},
                {'title': _('Get users for offboarding'),
                 'url': reverse('get_offboarding_list'),
                 'icon': 'fa fa-sign-out'},
                {'title': _('Manage deleted domains'),
                 'url': reverse('tombstone_management'),
                 'icon': 'fa fa-minus-circle'},
            ]
            admin_operations = [
                {'title': _('CommCare Builds'),
                 'url': reverse(EditMenuView.urlname),
                 'icon': 'fa fa-wrench'},
                {'title': _('Manage Notifications'),
                 'url': reverse(ManageNotificationView.urlname),
                 'icon': 'fa fa-bell'},
                {'title': _('Mass Email Users'),
                 'url': reverse('mass_email'),
                 'icon': 'fa fa-envelope'},
                {'title': _('Maintenance Alerts'),
                 'url': reverse('alerts'),
                 'icon': 'fa fa-warning'},
                {'title': _('Check Call Center UCR tables'),
                 'url': reverse('callcenter_ucr_check'),
                 'icon': 'fa fa-table'},
                {'title': _('Reprocess Messaging Case Updates'),
                 'url': reverse(ReprocessMessagingCaseUpdatesView.urlname),
                 'icon': 'fa fa-refresh'},
            ] + admin_operations
        sections = [
            (_('Administrative Reports'), [
                {'title': _('User List'),
                 'url': UserListReport.get_url()},
                {'title': _('Deploy History'),
                 'url': DeployHistoryReport.get_url()},
                {'title': _('Download Malt table'),
                 'url': reverse('download_malt')},
                {'title': _('Download Global Impact Report'),
                 'url': reverse('download_gir')},
                {'title': _('Admin Phone Number Report'),
                 'url': reverse('admin_report_dispatcher', args=('phone_number_report',))},
            ]),
        ]
        if admin_operations:
            sections.append((_('Administrative Operations'), admin_operations))
        if user_operations:
            sections.append((_('User Administration'), user_operations))
        if system_operations:
            sections.append((_('System Health'), system_operations))
        if data_operations:
            sections.append((_('Inspect Data'), data_operations))
        sections.append((_('CommCare Reports'), [
            {
                'title': report.name,
                'url': '{url}{params}'.format(
                    url=reverse('admin_report_dispatcher', args=(report.slug,)),
                    params="?{}".format(urlencode(report.default_params)) if report.default_params else ""
                )
            } for report in [DeviceLogSoftAssertReport, UserAuditReport]
        ]))
        return sections

    @property
    def _is_viewable(self):
        return (self.couch_user
                and (self.couch_user.is_superuser
                     or toggles.IS_CONTRACTOR.enabled(self.couch_user.username))
                and not is_request_using_sso(self._request))


class AttendanceTrackingTab(UITab):
    title = gettext_noop("Attendance Tracking")
    view = EventsView.urlname

    url_prefix_formats = (
        '/a/{domain}/settings/events',
    )

    @property
    def dropdown_items(self):
        items = [
            dropdown_dict(_("Attendees"), url=reverse(AttendeesListView.urlname, args=(self.domain,))),
            dropdown_dict(_("Events"), url=reverse(EventsView.urlname, args=(self.domain,))),
            self.divider,
            dropdown_dict(_("View All"), url=reverse(EventsView.urlname, args=(self.domain,))),
        ]
        return items

    @property
    def sidebar_items(self):

        def _get_attendee_name(domain, attendee_id=None, **kwargs):
            if attendee_id:
                model = AttendeeModel.objects.get(
                    case_id=attendee_id,
                    domain=domain,
                )
                return model.name
            return None

        items = [
            (_("Attendees"), [
                {
                    'title': _("View All Attendees"),
                    'url': reverse(AttendeesListView.urlname, args=(self.domain,)),
                    'description': _('Manage attendees for Attendance Tracking Events'),
                    'subpages': [{
                        'title': _get_attendee_name,
                        'urlname': AttendeeEditView.urlname,
                    }],
                },
            ]),
            (_("Events"), [
                {
                    'title': _("View All Events"),
                    'url': reverse(EventsView.urlname, args=(self.domain,)),
                    'description': _('Manage Attendance Tracking Events'),
                },
            ]),
        ]
        return items

    @property
    def _is_viewable(self):
        # The FF check is temporary until the full feature is released
        return toggles.ATTENDANCE_TRACKING.enabled(self.domain) and self.couch_user.can_manage_events(self.domain)
