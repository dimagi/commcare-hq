from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings
from django.http import Http404
from django.urls import reverse
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from django_prbac.utils import has_privilege
from memoized import memoized
from six.moves import map
from six.moves.urllib.parse import urlencode

from corehq import privileges, toggles
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.models import Invoice, Subscription
from corehq.apps.accounting.utils import domain_has_privilege, domain_is_on_trial, is_accounting_admin
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_brief_apps_in_domain
from corehq.apps.builds.views import EditMenuView
from corehq.apps.domain.utils import user_has_custom_top_menu
from corehq.apps.domain.views.releases import (
    ManageReleasesByLocation,
    ManageReleasesByAppProfile,
)
from corehq.apps.hqadmin.reports import RealProjectSpacesReport, \
    CommConnectProjectSpacesReport, CommTrackProjectSpacesReport, \
    DeviceLogSoftAssertReport, UserAuditReport
from corehq.apps.hqwebapp.models import GaTracker
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.linked_domain.dbaccessors import is_linked_domain
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.reminders.views import (
    KeywordsListView,
    AddNormalKeywordView,
    AddStructuredKeywordView,
    EditNormalKeywordView,
    EditStructuredKeywordView,
)
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, \
    CustomProjectReportDispatcher
from corehq.apps.reports.models import ReportsSidebarOrdering
from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from corehq.apps.translations.integrations.transifex.utils import transifex_details_available_for_domain
from corehq.apps.userreports.util import has_report_builder_access
from corehq.apps.users.models import AnonymousCouchUser
from corehq.apps.users.permissions import (
    can_view_sms_exports,
    can_download_data_files,
)
from corehq.feature_previews import (
    EXPLORE_CASE_DATA_PREVIEW,
    is_eligible_for_ecd_preview,
)
from corehq.messaging.scheduling.views import (
    MessagingDashboardView,
    BroadcastListView as NewBroadcastListView,
    CreateScheduleView,
    EditScheduleView,
    ConditionalAlertListView,
    CreateConditionalAlertView,
    EditConditionalAlertView,
    UploadConditionalAlertView,
)
from corehq.apps.styleguide.views import MainStyleGuideView
from corehq.messaging.util import show_messaging_dashboard
from corehq.motech.dhis2.view import Dhis2ConnectionView, DataSetMapView
from corehq.motech.openmrs.views import OpenmrsImporterView
from corehq.motech.views import MotechLogListView
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.tabs.uitab import UITab
from corehq.tabs.utils import dropdown_dict, sidebar_to_dropdown, regroup_sidebar_items
from corehq.toggles import PUBLISH_CUSTOM_REPORTS
from custom.icds.views.hosted_ccz import (
    ManageHostedCCZLink,
    ManageHostedCCZ,
)


class ProjectReportsTab(UITab):
    title = ugettext_noop("Reports")
    view = "reports_home"

    url_prefix_formats = ('/a/{domain}/reports/', '/a/{domain}/configurable_reports/')

    @property
    def _is_viewable(self):
        return user_can_view_reports(self.project, self.couch_user)

    @property
    def view(self):
        from corehq.apps.reports.views import MySavedReportsView
        return MySavedReportsView.urlname

    @property
    def sidebar_items(self):
        tools = self._get_tools_items()
        report_builder_nav = self._get_report_builder_items()
        project_reports = ProjectReportDispatcher.navigation_sections(
            request=self._request, domain=self.domain)
        custom_reports = CustomProjectReportDispatcher.navigation_sections(
            request=self._request, domain=self.domain)
        sidebar_items = tools + report_builder_nav + self._regroup_sidebar_items(custom_reports + project_reports)
        return self._filter_sidebar_items(sidebar_items)

    def _regroup_sidebar_items(self, sidebar_items):
        try:
            ordering = ReportsSidebarOrdering.objects.get(domain=self.domain)
        except ReportsSidebarOrdering.DoesNotExist:
            return sidebar_items
        return regroup_sidebar_items(ordering.config, sidebar_items)

    def _get_tools_items(self):
        from corehq.apps.reports.views import MySavedReportsView
        if isinstance(self.couch_user, AnonymousCouchUser) and PUBLISH_CUSTOM_REPORTS.enabled(self.domain):
            return []
        return [(_("Tools"), [
            {'title': _(MySavedReportsView.page_title),
             'url': reverse(MySavedReportsView.urlname, args=[self.domain]),
             'icon': 'icon-tasks fa fa-tasks',
             'show_in_dropdown': True}
        ])]

    def _get_report_builder_items(self):
        user_reports = []
        if self.couch_user.can_edit_data():
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
        if self.can_access_all_locations:
            reports = sidebar_to_dropdown(
                ProjectReportDispatcher.navigation_sections(
                    request=self._request, domain=self.domain),
                current_url=self.url)
            return self._get_saved_reports_dropdown() + reports

        else:
            return (self._get_saved_reports_dropdown()
                    + self._get_all_sidebar_items_as_dropdown())

    def _get_all_sidebar_items_as_dropdown(self):
        def show(page):
            page['show_in_dropdown'] = True
            return page
        return sidebar_to_dropdown([
            (header, list(map(show, pages)))
            for header, pages in self.sidebar_items
        ])


class DashboardTab(UITab):
    title = ugettext_noop("Dashboard")
    view = 'dashboard_default'

    url_prefix_formats = ('/a/{domain}/dashboard/project/',)

    @property
    def _is_viewable(self):
        if self.domain and self.project and not self.project.is_snapshot and self.couch_user:
            # domain hides Dashboard tab if user is non-admin
            if not user_has_custom_top_menu(self.domain, self.couch_user):
                if self.couch_user.is_commcare_user():
                    # never show the dashboard for mobile workers
                    return False
                else:
                    return domain_has_apps(self.domain)
        return False

    @property
    @memoized
    def url(self):
        from corehq.apps.dashboard.views import default_dashboard_url
        return default_dashboard_url(self._request, self.domain)


class ProjectInfoTab(UITab):
    title = ugettext_noop("Project Info")
    view = "corehq.apps.appstore.views.project_info"

    url_prefix_formats = ('/exchange/{domain}/info/',)

    @property
    def _is_viewable(self):
        return self.project and self.project.is_snapshot


class SetupTab(UITab):
    title = ugettext_noop("Setup")
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
        from corehq.apps.programs.views import ProgramListView
        from corehq.apps.products.views import ProductListView

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
                dropdown_dict(None, is_divider=True),
                dropdown_dict(_("View All"), url=ProductListView.urlname),
            ]

        return []

    @property
    def _is_viewable(self):
        return (self.couch_user.is_domain_admin() and
                self.project.commtrack_enabled)

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
            StockLevelsView,
        )
        from corehq.apps.programs.views import (
            ProgramListView,
            NewProgramView,
            EditProgramView,
        )
        from corehq.apps.products.views import (
            ProductListView,
            NewProductView,
            EditProductView,
            ProductFieldsView,
            UploadProductView,
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
            if toggles.LOCATION_TYPE_STOCK_RATES.enabled(self.domain):
                commcare_supply_setup.append({
                    'title': _(StockLevelsView.page_title),
                    'url': reverse(StockLevelsView.urlname, args=[self.domain]),
                })
            return [[_('CommCare Supply Setup'), commcare_supply_setup]]


class ProjectDataTab(UITab):
    title = ugettext_noop("Data")
    view = "data_interfaces_default"
    url_prefix_formats = (
        '/a/{domain}/data/',
        '/a/{domain}/fixtures/',
        '/a/{domain}/data_dictionary/',
        '/a/{domain}/importer/'
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
    def can_use_lookup_tables(self):
        return domain_has_privilege(self.domain, privileges.LOOKUP_TABLES)

    @property
    def can_view_ecd_preview(self):
        return (EXPLORE_CASE_DATA_PREVIEW.enabled_for_request(self._request) and
                is_eligible_for_ecd_preview(self._request))

    @property
    def _is_viewable(self):
        return self.domain and (
            self.can_edit_commcare_data
            or self.can_export_data
            or can_download_data_files(self.domain, self.couch_user)
        )

    @property
    def sidebar_items(self):
        items = []

        export_data_views = []
        if self.can_only_see_deid_exports:
            from corehq.apps.export.views.list import (
                DeIdFormExportListView,
                DeIdDailySavedExportListView,
                DeIdDashboardFeedListView,
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

        elif self.can_export_data:
            from corehq.apps.export.views.download import (
                DownloadNewFormExportView,
                DownloadNewCaseExportView,
                DownloadNewSmsExportView,
                BulkDownloadNewFormExportView,
            )
            from corehq.apps.export.views.edit import (
                EditCaseDailySavedExportView,
                EditCaseFeedView,
                EditODataCaseFeedView,
                EditODataFormFeedView,
                EditFormDailySavedExportView,
                EditFormFeedView,
                EditNewCustomCaseExportView,
                EditNewCustomFormExportView,
            )
            from corehq.apps.export.views.list import (
                FormExportListView,
                CaseExportListView,
                DashboardFeedListView,
                DailySavedExportListView,
                ODataFeedListView,
            )
            from corehq.apps.export.views.new import (
                CreateNewCustomFormExportView,
                CreateNewCustomCaseExportView,
                CreateNewDailySavedFormExport,
                CreateNewDailySavedCaseExport,
                CreateNewFormFeedView,
                CreateNewCaseFeedView,
                CreateODataCaseFeedView,
                CreateODataFormFeedView,
            )
            from corehq.apps.export.views.utils import (
                DashboardFeedPaywall,
                DailySavedExportPaywall
            )

            if self.can_view_form_exports:
                export_data_views.append(
                    {
                        'title': _(FormExportListView.page_title),
                        'url': reverse(FormExportListView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-list-alt fa fa-list-alt',
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
                        'icon': 'icon icon-share fa fa-share-square-o',
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

            if self.can_view_sms_exports:
                export_data_views.append(
                    {
                        'title': _(DownloadNewSmsExportView.page_title),
                        'url': reverse(DownloadNewSmsExportView.urlname, args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa fa-commenting-o',
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
                    'show_in_dropdown': True,
                    'subpages': subpages
                })
            elif self.should_see_dashboard_feed_paywall:
                export_data_views.append({
                    'title': _(DashboardFeedListView.page_title),
                    'url': reverse(DashboardFeedPaywall.urlname, args=(self.domain,)),
                    'show_in_dropdown': True,
                    'subpages': []
                })
            if toggles.ODATA.enabled(self.domain):
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
                    'show_in_dropdown': True,
                    'subpages': subpages
                })

        if can_download_data_files(self.domain, self.couch_user):
            from corehq.apps.export.views.utils import DataFileDownloadList

            export_data_views.append({
                'title': _(DataFileDownloadList.page_title),
                'url': reverse(DataFileDownloadList.urlname, args=(self.domain,)),
                'show_in_dropdown': True,
                'subpages': []
            })

        if export_data_views:
            items.append([_("Export Data"), export_data_views])

        if self.can_edit_commcare_data:
            from corehq.apps.data_interfaces.dispatcher \
                import EditDataInterfaceDispatcher
            edit_section = EditDataInterfaceDispatcher.navigation_sections(
                request=self._request, domain=self.domain)

            from corehq.apps.data_interfaces.views import AutomaticUpdateRuleListView

            if self.can_use_data_cleanup:
                edit_section[0][1].append({
                    'title': _(AutomaticUpdateRuleListView.page_title),
                    'url': reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]),
                })

            items.extend(edit_section)

        if ((toggles.EXPLORE_CASE_DATA.enabled_for_request(self._request) or
             self.can_view_ecd_preview) and self.can_edit_commcare_data):
            from corehq.apps.data_interfaces.views import ExploreCaseDataView
            explore_data_views = [
                {
                    'title': _(ExploreCaseDataView.page_title),
                    'url': reverse(ExploreCaseDataView.urlname,
                                   args=(self.domain,)),
                    'show_in_dropdown': False,
                    'icon': 'fa fa-search',
                    'subpages': [],
                }
            ]
            items.append([_("Explore Data"), explore_data_views])

        if self.can_use_lookup_tables:
            from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
            items.extend(FixtureInterfaceDispatcher.navigation_sections(
                request=self._request, domain=self.domain))

        if toggles.DATA_DICTIONARY.enabled(self.domain):
            items.append([_('Data Dictionary'),
                          [{'title': 'Data Dictionary',
                            'url': reverse('data_dictionary', args=[self.domain])}]])
        return items

    @property
    def dropdown_items(self):
        if (
            self.can_only_see_deid_exports or (
                not self.can_export_data and not can_download_data_files(self.domain, self.couch_user)
            )
        ):
            return []

        from corehq.apps.export.views.download import (
            DownloadNewSmsExportView,
        )
        from corehq.apps.export.views.list import (
            FormExportListView, CaseExportListView
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

        if items:
            items += [dropdown_dict(None, is_divider=True)]
        items += [dropdown_dict(_("View All"), url=self.url)]
        return items


class ApplicationsTab(UITab):
    view = "default_app"

    url_prefix_formats = ('/a/{domain}/apps/',)

    @property
    def view(self):
        return "default_new_app"

    @property
    def title(self):
        return _("Applications")

    @classmethod
    def make_app_title(cls, app_name, doc_type):
        return mark_safe("%s%s" % (
            escape(strip_tags(app_name)) or '(Untitled)',
            ' (Remote)' if doc_type == 'RemoteApp' else '',
        ))

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
            app_title = self.make_app_title(app.name, app.doc_type)
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
            submenu_context.append(dropdown_dict(None, is_divider=True))
            submenu_context.append(dropdown_dict(
                _('New Application'),
                url=(reverse('default_new_app', args=[self.domain])),
            ))
        if toggles.APP_TRANSLATIONS_WITH_TRANSIFEX.enabled_for_request(self._request):
            submenu_context.append(dropdown_dict(
                _('Translations'),
                url=(reverse('convert_translations', args=[self.domain])),
            ))
        if toggles.MANAGE_CCZ_HOSTING.enabled_for_request(self._request):
            submenu_context.append(dropdown_dict(
                ManageHostedCCZ.page_title,
                url=reverse(ManageHostedCCZ.urlname, args=[self.domain])
            ))
        return submenu_context

    @property
    def _is_viewable(self):
        couch_user = self.couch_user
        return (self.domain and couch_user and
                (couch_user.is_web_user() or couch_user.can_edit_apps()) and
                (couch_user.is_member_of(self.domain) or couch_user.is_superuser) and
                # domain hides Applications tab if user is non-admin
                not user_has_custom_top_menu(self.domain, couch_user))


class CloudcareTab(UITab):
    title = ugettext_noop("Web Apps")
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
            and not isinstance(self.couch_user, AnonymousCouchUser)
            and (self.couch_user.can_edit_data() or self.couch_user.is_commcare_user())
        )


class MessagingTab(UITab):
    title = ugettext_noop("Messaging")
    view = "sms_default"

    url_prefix_formats = (
        '/a/{domain}/messaging/',
        '/a/{domain}/sms/',
        '/a/{domain}/reminders/',
        '/a/{domain}/data/edit/case_groups/',
    )

    @property
    def _is_viewable(self):
        return (self.can_access_reminders or self.can_use_outbound_sms) and (
            self.project and not (self.project.is_snapshot or
                                  self.couch_user.is_commcare_user())
        ) and self.couch_user.can_edit_data()

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

        return reminders_urls

    @property
    @memoized
    def show_dashboard(self):
        return show_messaging_dashboard(self.domain, self.couch_user)

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
                {'title': ugettext_lazy("Subscribe to SMS Reports"),
                 'url': reverse(SubscribeSMSView.urlname, args=[self.domain])}
            )

        return supply_urls

    @property
    @memoized
    def contacts_urls(self):
        contacts_urls = []

        if toggles.MOBILE_WORKER_SELF_REGISTRATION.enabled(self.domain):
            from corehq.apps.sms.views import ManageRegistrationInvitationsView
            contacts_urls.append(
                {'title': _("Mobile Worker Registration"),
                 'url': reverse(ManageRegistrationInvitationsView.urlname, args=[self.domain])}
            )

        if self.couch_user.can_edit_data():
            contacts_urls.append(
                {'title': _('Chat'),
                 'url': reverse('chat_contacts', args=[self.domain])}
            )

        if self.couch_user.can_edit_data():
            from corehq.apps.data_interfaces.views import CaseGroupListView, CaseGroupCaseManagementView
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

        if self.can_use_outbound_sms:
            from corehq.apps.sms.views import (
                DomainSmsGatewayListView, AddDomainGatewayView,
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

        if self.couch_user.is_superuser or self.couch_user.is_domain_admin(self.domain):
            settings_urls.extend([
                {'title': ugettext_lazy("General Settings"),
                 'url': reverse('sms_settings', args=[self.domain])},
                {'title': ugettext_lazy("Languages"),
                 'url': reverse('sms_languages', args=[self.domain])},
            ])

        return settings_urls

    @property
    def dropdown_items(self):
        result = []

        if self.show_dashboard:
            result.append(dropdown_dict(_("Dashboard"), is_header=True))
            result.append(dropdown_dict(
                _("Dashboard"),
                url=reverse(MessagingDashboardView.urlname, args=[self.domain]),
            ))

        if result:
            result.append(dropdown_dict(None, is_divider=True))

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
            result.append(dropdown_dict(None, is_divider=True))

        view_all_view = MessagingDashboardView.urlname if self.show_dashboard else 'sms_compose_message'
        result.append(dropdown_dict(
            _("View All"),
            url=reverse(view_all_view, args=[self.domain]),
        ))

        return result

    @property
    def sidebar_items(self):
        items = []

        if self.show_dashboard:
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
            (_("Settings"), self.settings_urls)
        ):
            if urls:
                items.append((title, urls))

        return items


class ProjectUsersTab(UITab):
    title = ugettext_noop("Users")
    view = "users_default"

    url_prefix_formats = (
        '/a/{domain}/settings/users/',
        '/a/{domain}/settings/cloudcare/',
        '/a/{domain}/settings/locations/',
    )

    @property
    def _is_viewable(self):
        return self.domain and (self.couch_user.can_edit_commcare_users() or
                                self.couch_user.can_view_commcare_users() or
                                self.couch_user.can_edit_groups() or
                                self.couch_user.can_view_groups() or
                                self.couch_user.can_edit_locations() or
                                self.couch_user.can_view_locations() or
                                self.couch_user.can_edit_web_users() or
                                self.couch_user.can_view_web_users() or
                                self.couch_user.can_view_roles())

    @property
    def can_view_cloudcare(self):
        return has_privilege(self._request, privileges.CLOUDCARE) and self.couch_user.is_domain_admin()

    def _get_mobile_users_menu(self):
        menu = []
        if self.couch_user.can_edit_commcare_users() or self.couch_user.can_view_commcare_users():
            def _get_commcare_username(request=None, couch_user=None,
                                       **context):
                if (couch_user.user_id != request.couch_user.user_id or
                        couch_user.is_commcare_user()):
                    username = couch_user.username_in_report
                    if couch_user.is_deleted():
                        username += " (%s)" % _("Deleted")
                    return mark_safe(username)
                else:
                    return None

            from corehq.apps.users.views.mobile import (
                EditCommCareUserView,
                ConfirmBillingAccountForExtraUsersView,
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
                    {'title': _(
                        ConfirmBillingAccountForExtraUsersView.page_title),
                        'urlname': ConfirmBillingAccountForExtraUsersView.urlname},
                ],
                'show_in_dropdown': True,
            })

        if self.couch_user.can_edit_groups() or self.couch_user.can_view_groups():
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
                if (couch_user.user_id != request.couch_user.user_id or
                        not couch_user.is_commcare_user()):
                    username = couch_user.human_friendly_name
                    if couch_user.is_deleted():
                        username += " (%s)" % _("Deleted")
                    return mark_safe(username)
                else:
                    return None

            from corehq.apps.users.views import (
                EditWebUserView,
                ListWebUsersView,
            )
            menu.append({
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
                    }
                ],
                'show_in_dropdown': True,
            })

        if self.couch_user.is_domain_admin() or self.couch_user.can_view_roles():
            from corehq.apps.users.views import (
                ListRolesView,
            )
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
                LocationsListView,
                NewLocationView,
                EditLocationView,
                LocationImportView,
                LocationImportStatusView,
                LocationFieldsView,
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
                ]
            })

        from corehq.apps.locations.permissions import user_can_edit_location_types
        if (user_can_edit_location_types(self.couch_user, self.domain) and
                self.couch_user.can_edit_locations()):
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

        return items


class EnterpriseSettingsTab(UITab):
    title = ugettext_noop("Enterprise Settings")

    url_prefix_formats = (
        '/a/{domain}/enterprise/',
    )

    _is_viewable = False

    @property
    def sidebar_items(self):
        items = super(EnterpriseSettingsTab, self).sidebar_items
        items.append((_('Manage Enterprise'), [
            {
                'title': _('Enterprise Dashboard'),
                'url': reverse('enterprise_dashboard', args=[self.domain]),
            },
            {
                'title': _('Enterprise Settings'),
                'url': reverse('enterprise_settings', args=[self.domain]),
            },
            {
                'title': _('Billing Statements'),
                'url': reverse('enterprise_billing_statements', args=[self.domain])
            }
        ]))
        return items


class HostedCCZTab(UITab):
    title = ugettext_noop('CCZ Hostings')
    url_prefix_formats = (
        '/a/{domain}/ccz/hostings/',
    )
    _is_viewable = False

    @property
    def sidebar_items(self):
        items = super(HostedCCZTab, self).sidebar_items
        items.append((_('Manage CCZ Hostings'), [
            {'url': reverse(ManageHostedCCZLink.urlname, args=[self.domain]),
             'title': ManageHostedCCZLink.page_title
             },
            {'url': reverse(ManageHostedCCZ.urlname, args=[self.domain]),
             'title': ManageHostedCCZ.page_title
             },
        ]))
        return items


class TranslationsTab(UITab):
    title = ugettext_noop('Translations')

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
    title = ugettext_noop("Project Settings")
    view = 'domain_settings_default'

    url_prefix_formats = (
        '/a/{domain}/settings/project/',
        '/a/{domain}/phone/prime_restore/',
        '/a/{domain}/motech/',
        '/a/{domain}/dhis2/',
        '/a/{domain}/openmrs/',
    )

    _is_viewable = False

    @property
    def sidebar_items(self):
        items = []
        user_is_admin = self.couch_user.is_domain_admin(self.domain)
        user_is_billing_admin = self.couch_user.can_edit_billing()

        project_info = []

        if user_is_admin:
            from corehq.apps.domain.views.settings import EditBasicProjectInfoView, EditPrivacySecurityView

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

        if toggles.OPENCLINICA.enabled(self.domain):
            from corehq.apps.domain.views.settings import EditOpenClinicaSettingsView
            project_info.append({
                'title': _(EditOpenClinicaSettingsView.page_title),
                'url': reverse(EditOpenClinicaSettingsView.urlname, args=[self.domain])
            })

        items.append((_('Project Information'), project_info))

        if user_is_admin:
            items.append((_('Project Administration'), _get_administration_section(self.domain)))

        if self.couch_user.can_edit_motech():
            items.append((_('Integration'), _get_integration_section(self.domain)))

        feature_flag_items = _get_feature_flag_items(self.domain)
        if feature_flag_items and user_is_admin:
            items.append((_('Pre-release Features'), feature_flag_items))

        from corehq.apps.users.models import WebUser
        if isinstance(self.couch_user, WebUser):
            if (user_is_billing_admin or self.couch_user.is_superuser) and not settings.ENTERPRISE_MODE:
                from corehq.apps.domain.views.accounting import (
                    DomainSubscriptionView, EditExistingBillingAccountView,
                    DomainBillingStatementsView, ConfirmSubscriptionRenewalView,
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
                EditInternalDomainInfoView,
                EditInternalCalculationsView,
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
            items.append((_('Internal Data (Dimagi Only)'), internal_admin))

        return items


def _get_administration_section(domain):
    from corehq.apps.domain.views.internal import TransferDomainView
    from corehq.apps.domain.views.settings import (
        FeaturePreviewsView,
        RecoveryMeasuresHistory,
    )
    from corehq.apps.ota.models import MobileRecoveryMeasure

    administration = []
    if not settings.ENTERPRISE_MODE and not is_linked_domain(domain):
        administration.extend([
            {
                'title': _('CommCare Exchange'),
                'url': reverse('domain_snapshot_settings', args=[domain])
            }])
    if not settings.ENTERPRISE_MODE:
        administration.extend([
            {
                'title': _('Multimedia Sharing'),
                'url': reverse('domain_manage_multimedia', args=[domain])
            }
        ])

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

    if toggles.RELEASE_BUILDS_PER_PROFILE.enabled(domain):
        administration.append({
            'title': _(ManageReleasesByAppProfile.page_title),
            'url': reverse(ManageReleasesByAppProfile.urlname, args=[domain])
        })

    return administration


def _get_integration_section(domain):

    def _get_forward_name(repeater_type=None, **context):
        if repeater_type == 'FormRepeater':
            return _("Forward Forms")
        elif repeater_type == 'ShortFormRepeater':
            return _("Forward Form Stubs")
        elif repeater_type == 'CaseRepeater':
            return _("Forward Cases")

    integration = [
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
            'url': reverse('domain_report_dispatcher', args=[domain, 'repeat_record_report'])
        }
    ]

    if toggles.BIOMETRIC_INTEGRATION.enabled(domain):
        from corehq.apps.integration.views import BiometricIntegrationView
        integration.append({
            'title': _(BiometricIntegrationView.page_title),
            'url': reverse(BiometricIntegrationView.urlname, args=[domain])
        })

    if toggles.DHIS2_INTEGRATION.enabled(domain):
        integration.extend([{
            'title': _(Dhis2ConnectionView.page_title),
            'url': reverse(Dhis2ConnectionView.urlname, args=[domain])
        }, {
            'title': _(DataSetMapView.page_title),
            'url': reverse(DataSetMapView.urlname, args=[domain])
        }])

    if toggles.OPENMRS_INTEGRATION.enabled(domain):
        integration.append({
            'title': _(OpenmrsImporterView.page_title),
            'url': reverse(OpenmrsImporterView.urlname, args=[domain])
        })

    if toggles.DHIS2_INTEGRATION.enabled(domain) or toggles.OPENMRS_INTEGRATION.enabled(domain):
        integration.append({
            'title': _(MotechLogListView.page_title),
            'url': reverse(MotechLogListView.urlname, args=[domain])
        })

    return integration


def _get_feature_flag_items(domain):
    from corehq.apps.domain.views.fixtures import CalendarFixtureConfigView, LocationFixtureConfigView
    feature_flag_items = []
    if toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain):
        feature_flag_items.append({
            'title': _('Case Search'),
            'url': reverse('case_search_config', args=[domain])
        })
    if toggles.CUSTOM_CALENDAR_FIXTURE.enabled(domain):
        feature_flag_items.append({
            'title': _('Calendar Fixture'),
            'url': reverse(CalendarFixtureConfigView.urlname, args=[domain])
        })
    if toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(domain):
        feature_flag_items.append({
            'title': _('Location Fixture'),
            'url': reverse(LocationFixtureConfigView.urlname, args=[domain])
        })

    if toggles.LINKED_DOMAINS.enabled(domain):
        feature_flag_items.append({
            'title': _('Linked Projects'),
            'url': reverse('domain_links', args=[domain])
        })
        feature_flag_items.append({
            'title': _('Linked Project History'),
            'url': reverse('domain_report_dispatcher', args=[domain, 'project_link_report'])
        })
    return feature_flag_items


class MySettingsTab(UITab):
    title = ugettext_noop("My Settings")
    view = 'default_my_settings'
    url_prefix_formats = ('/account/',)

    _is_viewable = False

    @property
    def sidebar_items(self):
        from corehq.apps.settings.views import (
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

        menu_items.extend([
            {
                'title': _(ChangeMyPasswordView.page_title),
                'url': reverse(ChangeMyPasswordView.urlname),
            },
            {
                'title': _(TwoFactorProfileView.page_title),
                'url': reverse(TwoFactorProfileView.urlname),
            }
        ])

        if (
            self.couch_user and self.couch_user.is_dimagi or
            toggles.MOBILE_PRIVILEGES_FLAG.enabled(self.couch_user.username)
        ):
            menu_items.append({
                'title': _(EnableMobilePrivilegesView.page_title),
                'url': reverse(EnableMobilePrivilegesView.urlname),
            })
        return [[_("Manage My Settings"), menu_items]]


class AccountingTab(UITab):
    title = ugettext_noop("Accounting")
    view = "accounting_default"
    dispatcher = AccountingAdminInterfaceDispatcher

    url_prefix_formats = ('/hq/accounting/',)
    show_by_default = False

    @property
    def _is_viewable(self):
        return is_accounting_admin(self._request.user)

    @property
    @memoized
    def sidebar_items(self):
        items = super(AccountingTab, self).sidebar_items

        from corehq.apps.accounting.views import ManageAccountingAdminsView
        items.append(('Permissions', (
            {
                'title': _(ManageAccountingAdminsView.page_title),
                'url': reverse(ManageAccountingAdminsView.urlname),
            },
        )))

        from corehq.apps.accounting.views import (
            TriggerInvoiceView, TriggerBookkeeperEmailView,
            TestRenewalEmailView, TriggerCustomerInvoiceView
        )
        items.append(('Other Actions', (
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
        )))
        return items


class SMSAdminTab(UITab):
    title = ugettext_noop("SMS Connectivity & Billing")
    view = "default_sms_admin_interface"
    dispatcher = SMSAdminInterfaceDispatcher

    url_prefix_formats = ('/hq/sms/',)
    show_by_default = False

    @property
    @memoized
    def sidebar_items(self):
        from corehq.apps.sms.views import (GlobalSmsGatewayListView,
            AddGlobalGatewayView, EditGlobalGatewayView)
        items = super(SMSAdminTab, self).sidebar_items
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
    title = ugettext_noop("Admin")
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
            dropdown_dict(_("Submission Map"), url=reverse("dimagisphere")),
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
            dropdown_dict(None, is_divider=True),
            dropdown_dict(_("Django Admin"), url="/admin"),
            dropdown_dict(_("View All"), url=self.url),
        ])
        return submenu_context

    @property
    def sidebar_items(self):
        # todo: convert these to dispatcher-style like other reports
        if (self.couch_user and
                (not self.couch_user.is_superuser and
                 toggles.IS_CONTRACTOR.enabled(self.couch_user.username))):
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
            from corehq.apps.hqadmin.views.operations import ReprocessMessagingCaseUpdatesView
            from corehq.apps.hqadmin.views.system import RecentCouchChangesView
            from corehq.apps.hqadmin.views.users import AuthenticateAs
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
                {'title': _('PillowTop Errors'),
                 'url': reverse('admin_report_dispatcher',
                                args=('pillow_errors',)),
                 'icon': 'fa fa-bed'},
                {'title': RecentCouchChangesView.page_title,
                 'url': reverse(RecentCouchChangesView.urlname),
                 'icon': 'fa fa-newspaper-o'},
                {'title': _('Branches on Staging'),
                 'url': reverse('branches_on_staging'),
                 'icon': 'fa fa-tree'},
            ]
            user_operations = [
                {'title': _('Login as another user'),
                 'url': reverse(AuthenticateAs.urlname),
                 'icon': 'fa fa-user-secret'},
            ] + user_operations + [
                {'title': _('Grant superuser privileges'),
                 'url': reverse('superuser_management'),
                 'icon': 'fa fa-magic'},
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
                {'title': _('Project Space List'),
                 'url': reverse('admin_report_dispatcher', args=('domains',))},
                {'title': _('Submission Map'),
                 'url': reverse('dimagisphere')},
                {'title': _('Active Project Map'),
                 'url': reverse('admin_report_dispatcher', args=('project_map',))},
                {'title': _('User List'),
                 'url': reverse('admin_report_dispatcher', args=('user_list',))},
                {'title': _('Application List'),
                 'url': reverse('admin_report_dispatcher', args=('app_list',))},
                {'title': _('Download Malt table'),
                 'url': reverse('download_malt')},
                {'title': _('Download Global Impact Report'),
                 'url': reverse('download_gir')},
                {'title': _('CommCare Version'),
                 'url': reverse('admin_report_dispatcher', args=('commcare_version', ))},
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
            } for report in [
                RealProjectSpacesReport,
                CommConnectProjectSpacesReport,
                CommTrackProjectSpacesReport,
                DeviceLogSoftAssertReport,
                UserAuditReport,
            ]
        ]))
        return sections

    @property
    def _is_viewable(self):
        return (self.couch_user and
                (self.couch_user.is_superuser or
                 toggles.IS_CONTRACTOR.enabled(self.couch_user.username)))
