from urllib import urlencode

from django.core.urlresolvers import reverse
from django.conf import settings
from django.http import Http404
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe, mark_for_escaping
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy
from corehq import privileges, toggles
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.models import Invoice, Subscription
from corehq.apps.accounting.utils import domain_has_privilege, is_accounting_admin
from corehq.apps.app_manager.dbaccessors import domain_has_apps, get_brief_apps_in_domain
from corehq.apps.domain.utils import user_has_custom_top_menu
from corehq.apps.hqadmin.reports import RealProjectSpacesReport, \
    CommConnectProjectSpacesReport, CommTrackProjectSpacesReport, \
    DeviceLogSoftAssertReport
from corehq.apps.hqwebapp.models import GaTracker
from corehq.apps.hqwebapp.view_permissions import user_can_view_reports
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.utils import get_indicator_domains
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, \
    CustomProjectReportDispatcher
from corehq.apps.reports.models import ReportConfig, ReportsSidebarOrdering
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from corehq.apps.userreports.util import has_report_builder_access
from corehq.apps.users.permissions import can_view_form_exports, can_view_case_exports, can_view_sms_exports
from corehq.form_processor.utils import use_new_exports
from corehq.privileges import DAILY_SAVED_EXPORT, EXCEL_DASHBOARD
from corehq.tabs.uitab import UITab
from corehq.tabs.utils import dropdown_dict, sidebar_to_dropdown, regroup_sidebar_items
from custom.world_vision import WORLD_VISION_DOMAINS
from dimagi.utils.decorators.memoized import memoized
from django_prbac.utils import has_privilege


class ProjectReportsTab(UITab):
    title = ugettext_noop("Reports")
    view = "reports_home"

    url_prefix_formats = ('/a/{domain}/reports/',)

    @property
    def _is_viewable(self):
        return user_can_view_reports(self.project, self.couch_user)

    @property
    def view(self):
        if self.domain in WORLD_VISION_DOMAINS:
            return "reports_home"
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
        return [(_("Tools"), [
            {'title': MySavedReportsView.page_title,
             'url': reverse(MySavedReportsView.urlname, args=[self.domain]),
             'icon': 'icon-tasks fa fa-tasks',
             'show_in_dropdown': True}
        ])]

    def _get_report_builder_items(self):
        user_reports = []
        if self.couch_user.can_edit_data():
            user_reports = [(
                _("Create Reports"),
                [{
                    "title": _('Create new report'),
                    "url": self._get_create_report_url(),
                    "icon": "icon-plus fa fa-plus",
                    "id": "create-new-report-left-nav",
                }]
            )]
        return user_reports

    def _get_create_report_url(self):
        """
        Return the url for the start of the report builder, or the paywall.
        """
        if has_report_builder_access(self._request):
            url = reverse("report_builder_select_type", args=[self.domain])
        else:
            from corehq.apps.userreports.views import paywall_home
            url = paywall_home(self.domain)
        return url

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
                    + self._get_configurable_reports_dropdown()
                    + self._get_all_sidebar_items_as_dropdown())

    def _get_all_sidebar_items_as_dropdown(self):
        def show(page):
            page['show_in_dropdown'] = True
            return page
        return sidebar_to_dropdown([
            (header, map(show, pages))
            for header, pages in self.sidebar_items
        ])

    def _get_configurable_reports_dropdown(self):
        """Returns all the configurable reports turned on for that user
        """
        from corehq.reports import _safely_get_report_configs, _make_report_class
        configurable_reports = [
            _make_report_class(config, show_in_dropdown=True)
            for config in _safely_get_report_configs(self.domain)
        ]
        configurable_reports_dropdown = [
            dropdown_dict(report.name, report.get_url(self.domain))
            for report in configurable_reports
            if report.display_in_dropdown(domain=self.domain, project=self.project, user=self.couch_user)
        ]
        return configurable_reports_dropdown


class IndicatorAdminTab(UITab):
    title = ugettext_noop("Administer Indicators")
    view = "corehq.apps.indicators.views.default_admin"
    dispatcher = IndicatorAdminInterfaceDispatcher

    url_prefix_formats = ('/a/{domain}/indicators/',)

    @property
    def _is_viewable(self):
        indicator_enabled_projects = get_indicator_domains()
        return (self.couch_user.can_edit_data() and
                self.domain in indicator_enabled_projects)

    @property
    def sidebar_items(self):
        items = super(IndicatorAdminTab, self).sidebar_items
        from corehq.apps.indicators.views import (
            BulkExportIndicatorsView,
            BulkImportIndicatorsView,
        )
        items.append([
            _("Other Actions"), [
                {
                    'title': BulkImportIndicatorsView.page_title,
                    'url': reverse(BulkImportIndicatorsView.urlname,
                                   args=[self.domain]),
                    'urlname': BulkImportIndicatorsView.urlname,
                },
                {
                    'title': _("Download Indicators Export"),
                    'url': reverse(BulkExportIndicatorsView.urlname,
                                   args=[self.domain]),
                }
            ]
        ])
        return items


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

        dropdown_items = []

        if self.project.commtrack_enabled:
            dropdown_items += [(_(view.page_title), view) for view in (
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
        ]

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
        )

        if self.project.commtrack_enabled:
            commcare_supply_setup = [
                {
                    'title': ProductListView.page_title,
                    'url': reverse(ProductListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': NewProductView.page_title,
                            'urlname': NewProductView.urlname,
                        },
                        {
                            'title': EditProductView.page_title,
                            'urlname': EditProductView.urlname,
                        },
                        {
                            'title': ProductFieldsView.page_name(),
                            'urlname': ProductFieldsView.urlname,
                        },
                    ]
                },
                {
                    'title': ProgramListView.page_title,
                    'url': reverse(ProgramListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': NewProgramView.page_title,
                            'urlname': NewProgramView.urlname,
                        },
                        {
                            'title': EditProgramView.page_title,
                            'urlname': EditProgramView.urlname,
                        },
                    ]
                },
                {
                    'title': SMSSettingsView.page_title,
                    'url': reverse(SMSSettingsView.urlname, args=[self.domain]),
                },
                {
                    'title': DefaultConsumptionView.page_title,
                    'url': reverse(DefaultConsumptionView.urlname, args=[self.domain]),
                },
                {
                    'title': CommTrackSettingsView.page_title,
                    'url': reverse(CommTrackSettingsView.urlname, args=[self.domain]),
                },
            ]
            if toggles.LOCATION_TYPE_STOCK_RATES.enabled(self.domain):
                commcare_supply_setup.append({
                    'title': StockLevelsView.page_title,
                    'url': reverse(StockLevelsView.urlname, args=[self.domain]),
                })
            return [[_('CommCare Supply Setup'), commcare_supply_setup]]


class ProjectDataTab(UITab):
    title = ugettext_noop("Data")
    view = "data_interfaces_default"
    url_prefix_formats = (
        '/a/{domain}/data/',
        '/a/{domain}/fixtures/',
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
        return can_view_form_exports(self.couch_user, self.domain)

    @property
    @memoized
    def can_view_case_exports(self):
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
    def use_new_daily_saved_exports_ui(self):
        from corehq.apps.export.views import use_new_daily_saved_exports_ui
        return use_new_daily_saved_exports_ui(self.domain)

    @property
    @memoized
    def should_see_daily_saved_export_list_view(self):
        return (
            self.can_view_form_or_case_exports
            and self.use_new_daily_saved_exports_ui
            and domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)
        )

    @property
    @memoized
    def should_see_daily_saved_export_paywall(self):
        return (
            self.can_view_form_or_case_exports
            and self.use_new_daily_saved_exports_ui
            and not domain_has_privilege(self.domain, DAILY_SAVED_EXPORT)
        )

    @property
    @memoized
    def should_see_dashboard_feed_list_view(self):
        return (
            self.can_view_form_or_case_exports
            and self.use_new_daily_saved_exports_ui  # dashboard feeds are a special kind of daily saved export
            and domain_has_privilege(self.domain, EXCEL_DASHBOARD)
        )

    @property
    @memoized
    def should_see_dashboard_feed_paywall(self):
        return (
            self.can_view_form_or_case_exports
            and self.use_new_daily_saved_exports_ui  # dashboard feeds are a special kind of daily saved export
            and not domain_has_privilege(self.domain, EXCEL_DASHBOARD)
        )

    @property
    @memoized
    def can_only_see_deid_exports(self):
        from corehq.apps.export.views import user_can_view_deid_exports
        return (not self.can_view_form_exports
                and user_can_view_deid_exports(self.domain, self.couch_user))

    @property
    @memoized
    def can_use_lookup_tables(self):
        return domain_has_privilege(self.domain, privileges.LOOKUP_TABLES)

    @property
    def _is_viewable(self):
        return self.domain and (self.can_edit_commcare_data or self.can_export_data)

    @property
    def sidebar_items(self):
        items = []

        export_data_views = []
        if self.can_only_see_deid_exports:
            from corehq.apps.export.views import (
                DeIdFormExportListView,
                DownloadFormExportView,
                DeIdDailySavedExportListView,
                DeIdDashboardFeedListView,
            )
            export_data_views.append({
                'title': DeIdFormExportListView.page_title,
                'url': reverse(DeIdFormExportListView.urlname, args=(self.domain,)),
                'subpages': [
                    {
                        'title': DownloadFormExportView.page_title,
                        'urlname': DownloadFormExportView.urlname,
                    },
                ]
            })
            if use_new_exports(self.domain):
                export_data_views.extend([
                    {
                        'title': DeIdDailySavedExportListView.page_title,
                        'url': reverse(DeIdDailySavedExportListView.urlname, args=(self.domain,)),
                    },
                    {
                        'title': DeIdDashboardFeedListView.page_title,
                        'url': reverse(DeIdDashboardFeedListView.urlname, args=(self.domain,)),
                    },
                ])

        elif self.can_export_data:
            from corehq.apps.export.views import (
                FormExportListView,
                CaseExportListView,
                CreateCustomFormExportView,
                CreateCustomCaseExportView,
                CreateNewCustomFormExportView,
                CreateNewCustomCaseExportView,
                DownloadFormExportView,
                DownloadNewFormExportView,
                DownloadCaseExportView,
                DownloadNewCaseExportView,
                DownloadNewSmsExportView,
                BulkDownloadFormExportView,
                BulkDownloadNewFormExportView,
                EditCustomFormExportView,
                EditCustomCaseExportView,
                EditNewCustomFormExportView,
                EditNewCustomCaseExportView,
                DashboardFeedListView,
                DailySavedExportListView,
                CreateNewDailySavedFormExport,
                CreateNewDailySavedCaseExport,
                EditFormDailySavedExportView,
                EditCaseDailySavedExportView,
                CreateNewFormFeedView,
                CreateNewCaseFeedView,
                EditFormFeedView,
                EditCaseFeedView,
                DashboardFeedPaywall,
                DailySavedExportPaywall
            )
            if use_new_exports(self.domain):
                create_case_cls = CreateNewCustomCaseExportView
                create_form_cls = CreateNewCustomFormExportView
                edit_form_cls = EditNewCustomFormExportView
                edit_case_cls = EditNewCustomCaseExportView
            else:
                create_case_cls = CreateCustomCaseExportView
                create_form_cls = CreateCustomFormExportView
                edit_form_cls = EditCustomFormExportView
                edit_case_cls = EditCustomCaseExportView

            if self.can_view_form_exports:
                export_data_views.append(
                    {
                        'title': FormExportListView.page_title,
                        'url': reverse(FormExportListView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-list-alt fa fa-list-alt',
                        'subpages': filter(None, [
                            {
                                'title': create_form_cls.page_title,
                                'urlname': create_form_cls.urlname,
                            } if self.can_edit_commcare_data else None,
                            {
                                'title': BulkDownloadFormExportView.page_title,
                                'urlname': BulkDownloadFormExportView.urlname,
                            },
                            {
                                'title': BulkDownloadNewFormExportView.page_title,
                                'urlname': BulkDownloadNewFormExportView.urlname,
                            },
                            {
                                'title': DownloadFormExportView.page_title,
                                'urlname': DownloadFormExportView.urlname,
                            },
                            {
                                'title': DownloadNewFormExportView.page_title,
                                'urlname': DownloadNewFormExportView.urlname,
                            },
                            {
                                'title': edit_form_cls.page_title,
                                'urlname': edit_form_cls.urlname,
                            } if self.can_edit_commcare_data else None,
                        ])
                    }
                )
            if self.can_view_case_exports:
                export_data_views.append(
                    {
                        'title': CaseExportListView.page_title,
                        'url': reverse(CaseExportListView.urlname,
                                       args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa fa-share-square-o',
                        'subpages': filter(None, [
                            {
                                'title': create_case_cls.page_title,
                                'urlname': create_case_cls.urlname,
                            } if self.can_edit_commcare_data else None,
                            {
                                'title': DownloadCaseExportView.page_title,
                                'urlname': DownloadCaseExportView.urlname,
                            },
                            {
                                'title': DownloadNewCaseExportView.page_title,
                                'urlname': DownloadNewCaseExportView.urlname,
                            },
                            {
                                'title': edit_case_cls.page_title,
                                'urlname': edit_case_cls.urlname,
                            } if self.can_edit_commcare_data else None,
                        ])
                    })

            if self.can_view_sms_exports:
                export_data_views.append(
                    {
                        'title': DownloadNewSmsExportView.page_title,
                        'url': reverse(DownloadNewSmsExportView.urlname, args=(self.domain,)),
                        'show_in_dropdown': True,
                        'icon': 'icon icon-share fa fa-commenting-o',
                        'subpages': []
                    })

            if self.should_see_daily_saved_export_list_view:
                export_data_views.append({
                    "title": DailySavedExportListView.page_title,
                    "url": reverse(DailySavedExportListView.urlname, args=(self.domain,)),
                    "show_in_dropdown": True,
                    "subpages": filter(None, [
                        {
                            'title': CreateNewDailySavedFormExport.page_title,
                            'urlname': CreateNewDailySavedFormExport.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': CreateNewDailySavedCaseExport.page_title,
                            'urlname': CreateNewDailySavedCaseExport.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': EditFormDailySavedExportView.page_title,
                            'urlname': EditFormDailySavedExportView.urlname,
                        } if self.can_edit_commcare_data else None,
                        {
                            'title': EditCaseDailySavedExportView.page_title,
                            'urlname': EditCaseDailySavedExportView.urlname,
                        } if self.can_edit_commcare_data else None,
                    ])
                })
            elif self.should_see_daily_saved_export_paywall:
                export_data_views.append({
                    'title': DailySavedExportListView.page_title,
                    'url': reverse(DailySavedExportPaywall.urlname, args=(self.domain,)),
                    'show_in_dropdown': True,
                    'subpages': []
                })
            if self.should_see_dashboard_feed_list_view:
                subpages = []
                if self.can_edit_commcare_data:
                    subpages = [
                        {
                            'title': CreateNewFormFeedView.page_title,
                            'urlname': CreateNewFormFeedView.urlname,
                        },
                        {
                            'title': CreateNewCaseFeedView.page_title,
                            'urlname': CreateNewCaseFeedView.urlname,
                        },
                        {
                            'title': EditFormFeedView.page_title,
                            'urlname': EditFormFeedView.urlname,
                        },
                        {
                            'title': EditCaseFeedView.page_title,
                            'urlname': EditCaseFeedView.urlname,
                        },
                    ]
                export_data_views.append({
                    'title': DashboardFeedListView.page_title,
                    'url': reverse(DashboardFeedListView.urlname, args=(self.domain,)),
                    'show_in_dropdown': True,
                    'subpages': subpages
                })
            elif self.should_see_dashboard_feed_paywall:
                export_data_views.append({
                    'title': DashboardFeedListView.page_title,
                    'url': reverse(DashboardFeedPaywall.urlname, args=(self.domain,)),
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

            from corehq.apps.data_interfaces.views \
                import ArchiveFormView, AutomaticUpdateRuleListView

            if self.can_use_data_cleanup:
                edit_section[0][1].append({
                    'title': AutomaticUpdateRuleListView.page_title,
                    'url': reverse(AutomaticUpdateRuleListView.urlname, args=[self.domain]),
                })

            if toggles.BULK_ARCHIVE_FORMS.enabled(self._request.user.username):
                edit_section[0][1].append({
                    'title': ArchiveFormView.page_title,
                    'url': reverse(ArchiveFormView.urlname, args=[self.domain]),
                })
            items.extend(edit_section)

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
        if self.can_only_see_deid_exports or not self.can_export_data:
            return []
        from corehq.apps.export.views import (
            FormExportListView, CaseExportListView, DownloadNewSmsExportView,
        )
        items = []
        if self.can_view_form_exports:
            items.append(dropdown_dict(
                FormExportListView.page_title,
                url=reverse(FormExportListView.urlname, args=(self.domain,))
            ))
        if self.can_view_case_exports:
            items.append(dropdown_dict(
                CaseExportListView.page_title,
                url=reverse(CaseExportListView.urlname, args=(self.domain,))
            ))
        if self.can_view_sms_exports:
            items.append(dropdown_dict(
                DownloadNewSmsExportView.page_title,
                url=reverse(DownloadNewSmsExportView.urlname, args=(self.domain,))
            ))

        items += [
            dropdown_dict(None, is_divider=True),
            dropdown_dict(_("View All"), url=self.url),
        ]
        return items


class ApplicationsTab(UITab):
    view = "default_app"

    url_prefix_formats = ('/a/{domain}/apps/',)

    @property
    def title(self):
        return _("Applications")

    @classmethod
    def make_app_title(cls, app_name, doc_type):
        return mark_safe("%s%s" % (
            mark_for_escaping(strip_tags(app_name) or '(Untitled)'),
            mark_for_escaping(' (Remote)' if doc_type == 'RemoteApp' else ''),
        ))

    @property
    def dropdown_items(self):
        # todo async refresh submenu when on the applications page and
        # you change the application name
        apps = get_brief_apps_in_domain(self.domain)
        submenu_context = []
        if not apps:
            return submenu_context

        submenu_context.append(dropdown_dict(_('My Applications'),
                               is_header=True))
        for app in apps:
            url = reverse('view_app', args=[self.domain, app.get_id]) if self.couch_user.can_edit_apps() \
                else reverse('release_manager', args=[self.domain, app.get_id])
            app_title = self.make_app_title(app.name, app.doc_type)

            submenu_context.append(dropdown_dict(
                app_title,
                url=url,
                data_id=app.get_id,
            ))

        if self.couch_user.can_edit_apps():
            submenu_context.append(dropdown_dict(None, is_divider=True))
            submenu_context.append(dropdown_dict(
                _('New Application'),
                url=(reverse('default_new_app', args=[self.domain])
                     if toggles.APP_MANAGER_V2.enabled(self.domain)
                     else reverse('default_app', args=[self.domain])),
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
    url_prefix_formats = ('/a/{domain}/cloudcare/',)

    ga_tracker = GaTracker('CloudCare', 'Click Cloud-Care top-level nav')

    @property
    def view(self):
        from corehq.apps.cloudcare.views import FormplayerMain
        if not toggles.USE_OLD_CLOUDCARE.enabled(self.domain):
            return FormplayerMain.urlname
        else:
            return "cloudcare_default"

    @property
    def title(self):
        if not toggles.USE_OLD_CLOUDCARE.enabled(self.domain):
            return _("Web Apps")
        else:
            return _("CloudCare")

    @property
    def _is_viewable(self):
        return (
            has_privilege(self._request, privileges.CLOUDCARE)
            and self.domain
            and (self.couch_user.can_edit_data() or self.couch_user.is_commcare_user())
        )


class MessagingTab(UITab):
    title = ugettext_noop("Messaging")
    view = "sms_default"

    url_prefix_formats = (
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

        if self.can_access_reminders:
            from corehq.apps.reminders.views import (
                EditScheduledReminderView,
                CreateScheduledReminderView,
                CreateComplexScheduledReminderView,
                RemindersListView,
            )
            reminders_urls.extend([
                {
                    'title': _("Reminders"),
                    'url': reverse(RemindersListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _("Edit Reminder"),
                            'urlname': EditScheduledReminderView.urlname,
                        },
                        {
                            'title': _("Schedule Reminder"),
                            'urlname': CreateScheduledReminderView.urlname,
                        },
                        {
                            'title': _("Schedule Multi Event Reminder"),
                            'urlname': CreateComplexScheduledReminderView.urlname,
                        },
                    ],
                    'show_in_dropdown': True,
                },
                {
                    'title': _("Reminder Calendar"),
                    'url': reverse('scheduled_reminders', args=[self.domain]),
                    'show_in_dropdown': True,
                },
            ])

        if self.can_use_inbound_sms:
            from corehq.apps.reminders.views import (
                KeywordsListView, AddNormalKeywordView,
                AddStructuredKeywordView, EditNormalKeywordView,
                EditStructuredKeywordView,
            )
            reminders_urls.append({
                'title': _("Keywords"),
                'url': reverse(KeywordsListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': AddNormalKeywordView.page_title,
                        'urlname': AddNormalKeywordView.urlname,
                    },
                    {
                        'title': AddStructuredKeywordView.page_title,
                        'urlname': AddStructuredKeywordView.urlname,
                    },
                    {
                        'title': EditNormalKeywordView.page_title,
                        'urlname': EditNormalKeywordView.urlname,
                    },
                    {
                        'title': EditStructuredKeywordView.page_title,
                        'urlname': EditStructuredKeywordView.urlname,
                    },
                ],
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
            from corehq.apps.reminders.views import (
                BroadcastListView,
                CreateBroadcastView,
                EditBroadcastView,
                CopyBroadcastView,
            )
            messages_urls.extend([
                {
                    'title': _("Broadcast Messages"),
                    'url': reverse(BroadcastListView.urlname, args=[self.domain]),
                    'subpages': [
                        {
                            'title': _("Edit Broadcast"),
                            'urlname': EditBroadcastView.urlname,
                        },
                        {
                            'title': _("New Broadcast"),
                            'urlname': CreateBroadcastView.urlname,
                        },
                        {
                            'title': _("Copy Broadcast"),
                            'urlname': CopyBroadcastView.urlname,
                        },
                    ],
                    'show_in_dropdown': True,
                },
            ])

        return messages_urls

    @property
    @memoized
    def performance_urls(self):
        performance_urls = []
        if self.can_access_reminders and toggles.SMS_PERFORMANCE_FEEDBACK.enabled(self.domain):
            performance_urls.append(
                {
                    'title': _('Configure Performance Messages'),
                    'url': reverse('performance_sms.list_performance_configs', args=[self.domain]),
                    'show_in_dropdown': True,
                }
            )
        return performance_urls

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
                'title': CaseGroupListView.page_title,
                'url': reverse(CaseGroupListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': CaseGroupCaseManagementView.page_title,
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
    def sidebar_items(self):
        items = []

        for title, urls in (
            (_("Messages"), self.messages_urls),
            (_("Data Collection and Reminders"), self.reminders_urls),
            (_("Performance Messaging"), self.performance_urls),
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
                                self.couch_user.can_edit_locations() or
                                self.couch_user.can_edit_web_users())

    @property
    def can_view_cloudcare(self):
        return has_privilege(self._request, privileges.CLOUDCARE) and self.couch_user.is_domain_admin()

    @property
    def sidebar_items(self):
        items = []

        if self.couch_user.can_edit_commcare_users():
            def commcare_username(request=None, couch_user=None, **context):
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

            mobile_users_menu = [
                {
                    'title': MobileWorkerListView.page_title,
                    'url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
                    'description': _(
                        "Create and manage users for CommCare and CloudCare."),
                    'subpages': [
                        {'title': commcare_username,
                         'urlname': EditCommCareUserView.urlname},
                        {'title': _('Bulk Upload'),
                         'urlname': 'upload_commcare_users'},
                        {'title': ConfirmBillingAccountForExtraUsersView.page_title,
                         'urlname': ConfirmBillingAccountForExtraUsersView.urlname},
                    ],
                    'show_in_dropdown': True,
                },
                {
                    'title': _('Groups'),
                    'url': reverse('all_groups', args=[self.domain]),
                    'description': _("""Create and manage
                        reporting and case sharing groups
                        for Mobile Workers."""),
                    'subpages': [
                        {'title': lambda **context: (
                            "%s %s" % (_("Editing"), context['group'].name)),
                         'urlname': 'group_members'},
                        {'title': _('Membership Info'),
                         'urlname': 'group_membership'}
                    ],
                    'show_in_dropdown': True,
                }
            ]

            if self.can_view_cloudcare:
                if not toggles.USE_OLD_CLOUDCARE.enabled(self.domain):
                    title = _("Web Apps Permissions")
                else:
                    title = _("CloudCare Permissions")
                mobile_users_menu.append({
                    'title': title,
                    'url': reverse('cloudcare_app_settings',
                                   args=[self.domain])
                })

            items.append((_('Application Users'), mobile_users_menu))

        if self.couch_user.can_edit_web_users():
            def web_username(request=None, couch_user=None, **context):
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
            items.append((_('Project Users'), [
                {
                    'title': ListWebUsersView.page_title,
                    'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
                    'description': _("Grant other CommCare HQ users access to your project and manage user roles."),
                    'subpages': [
                        {
                            'title': _("Add Web User"),
                            'urlname': 'invite_web_user'
                        },
                        {
                            'title': web_username,
                            'urlname': EditWebUserView.urlname
                        }
                    ],
                    'show_in_dropdown': True,
                }
            ]))

        if has_privilege(self._request, privileges.LOCATIONS):
            locations_config = []
            if self.couch_user.can_edit_locations():
                from corehq.apps.locations.views import (
                    LocationsListView,
                    NewLocationView,
                    EditLocationView,
                    LocationImportView,
                    LocationImportStatusView,
                    LocationFieldsView,
                )

                locations_config.append({
                    'title': LocationsListView.page_title,
                    'url': reverse(LocationsListView.urlname, args=[self.domain]),
                    'show_in_dropdown': True,
                    'subpages': [
                        {
                            'title': NewLocationView.page_title,
                            'urlname': NewLocationView.urlname,
                        },
                        {
                            'title': EditLocationView.page_title,
                            'urlname': EditLocationView.urlname,
                        },
                        {
                            'title': LocationImportView.page_title,
                            'urlname': LocationImportView.urlname,
                        },
                        {
                            'title': LocationImportStatusView.page_title,
                            'urlname': LocationImportStatusView.urlname,
                        },
                        {
                            'title': LocationFieldsView.page_name(),
                            'urlname': LocationFieldsView.urlname,
                        },
                    ]
                })

            from corehq.apps.locations.permissions import user_can_edit_location_types
            if user_can_edit_location_types(self.couch_user, self.project):
                from corehq.apps.locations.views import LocationTypesView
                locations_config.append({
                    'title': LocationTypesView.page_title,
                    'url': reverse(LocationTypesView.urlname, args=[self.domain]),
                    'show_in_dropdown': True,
                })
            if locations_config:
                items.append((_('Organization'), locations_config))

        elif users_have_locations(self.domain):  # This domain was downgraded
            items.append((_('Organization'), [{
                'title': _("No longer available"),
                'url': reverse('downgrade_locations', args=[self.domain]),
                'show_in_dropdown': True,
            }]))

        return items


class ProjectSettingsTab(UITab):
    title = ugettext_noop("Project Settings")
    view = 'domain_settings_default'

    url_prefix_formats = ('/a/{domain}/settings/project/',)

    @property
    def _is_viewable(self):
        return (self.domain and self.couch_user and
                self.couch_user.is_domain_admin(self.domain))

    @property
    def sidebar_items(self):
        from corehq.apps.domain.views import FeatureFlagsView

        items = []
        user_is_admin = self.couch_user.is_domain_admin(self.domain)
        user_is_billing_admin = self.couch_user.can_edit_billing()

        project_info = []

        if user_is_admin:
            from corehq.apps.domain.views import EditBasicProjectInfoView, EditPrivacySecurityView

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

        from corehq.apps.domain.views import EditMyProjectSettingsView
        project_info.append({
            'title': _(EditMyProjectSettingsView.page_title),
            'url': reverse(EditMyProjectSettingsView.urlname, args=[self.domain])
        })

        if toggles.OPENCLINICA.enabled(self.domain):
            from corehq.apps.domain.views import EditOpenClinicaSettingsView
            project_info.append({
                'title': _(EditOpenClinicaSettingsView.page_title),
                'url': reverse(EditOpenClinicaSettingsView.urlname, args=[self.domain])
            })

        items.append((_('Project Information'), project_info))

        if user_is_admin:
            items.append((_('Project Administration'), _get_administration_section(self.domain)))

        feature_flag_items = _get_feature_flag_items(self.domain)
        if feature_flag_items:
            items.append((_('Pre-release Features'), feature_flag_items))

        from corehq.apps.users.models import WebUser
        if isinstance(self.couch_user, WebUser):
            if (user_is_billing_admin or self.couch_user.is_superuser) and not settings.ENTERPRISE_MODE:
                from corehq.apps.domain.views import (
                    DomainSubscriptionView, EditExistingBillingAccountView,
                    DomainBillingStatementsView, ConfirmSubscriptionRenewalView,
                    InternalSubscriptionManagementView,
                )
                current_subscription = Subscription.get_subscribed_plan_by_domain(self.domain)[1]
                subscription = [
                    {
                        'title': DomainSubscriptionView.page_title,
                        'url': reverse(DomainSubscriptionView.urlname,
                                       args=[self.domain]),
                        'subpages': [
                            {
                                'title': ConfirmSubscriptionRenewalView.page_title,
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
                            'title': EditExistingBillingAccountView.page_title,
                            'url': reverse(EditExistingBillingAccountView.urlname,
                                           args=[self.domain]),
                        },
                    )
                if (current_subscription is not None
                        and Invoice.exists_for_domain(self.domain)):
                    subscription.append(
                        {
                            'title': DomainBillingStatementsView.page_title,
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

        if any(toggles.PRIME_RESTORE.enabled(item) for item in [self.couch_user.username, self.domain]):
            from corehq.apps.ota.views import PrimeRestoreCacheView
            project_tools = [
                {
                    'title': _(PrimeRestoreCacheView.page_title),
                    'url': reverse(PrimeRestoreCacheView.urlname,
                                   args=[self.domain])
                },
            ]
            items.append((_('Project Tools'), project_tools))

        if self.couch_user.is_superuser:
            from corehq.apps.domain.views import EditInternalDomainInfoView, \
                EditInternalCalculationsView
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
                    'title': _(FeatureFlagsView.page_title),
                    'url': reverse(FeatureFlagsView.urlname, args=[self.domain])
                },
            ]
            items.append((_('Internal Data (Dimagi Only)'), internal_admin))

        return items


def _get_administration_section(domain):
    from corehq.apps.domain.views import FeaturePreviewsView, TransferDomainView, Dhis2ConnectionView

    administration = []
    if not settings.ENTERPRISE_MODE:
        administration.extend([
            {
                'title': _('CommCare Exchange'),
                'url': reverse('domain_snapshot_settings', args=[domain])
            },
            {
                'title': _('Multimedia Sharing'),
                'url': reverse('domain_manage_multimedia', args=[domain])
            }
        ])

    def forward_name(repeater_type=None, **context):
        if repeater_type == 'FormRepeater':
            return _("Forward Forms")
        elif repeater_type == 'ShortFormRepeater':
            return _("Forward Form Stubs")
        elif repeater_type == 'CaseRepeater':
            return _("Forward Cases")

    administration.extend([
        {'title': _('Data Forwarding'),
         'url': reverse('domain_forwarding', args=[domain]),
         'subpages': [
             {
                 'title': forward_name,
                 'urlname': 'add_repeater',
             },
             {
                 'title': forward_name,
                 'urlname': 'add_form_repeater',
             },
        ]},
        {
            'title': _('Data Forwarding Records'),
            'url': reverse('domain_report_dispatcher', args=[domain, 'repeat_record_report'])
        }
    ])

    administration.append({
        'title': _(FeaturePreviewsView.page_title),
        'url': reverse(FeaturePreviewsView.urlname, args=[domain])
    })

    if toggles.TRANSFER_DOMAIN.enabled(domain):
        administration.append({
            'title': _(TransferDomainView.page_title),
            'url': reverse(TransferDomainView.urlname, args=[domain])
        })

    if toggles.DHIS2_INTEGRATION.enabled(domain):
        administration.append({
            'title': _(Dhis2ConnectionView.page_title),
            'url': reverse(Dhis2ConnectionView.urlname, args=[domain])
        })

    return administration


def _get_feature_flag_items(domain):
    from corehq.apps.domain.views import CalendarFixtureConfigView, LocationFixtureConfigView
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
    return feature_flag_items


class MySettingsTab(UITab):
    title = ugettext_noop("My Settings")
    view = 'default_my_settings'
    url_prefix_formats = ('/account/',)

    @property
    def _is_viewable(self):
        return self.couch_user is not None

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
                'title': MyAccountSettingsView.page_title,
                'url': reverse(MyAccountSettingsView.urlname),
            },
        ]

        if self.couch_user and self.couch_user.is_web_user():
            menu_items.append({
                'title': MyProjectsList.page_title,
                'url': reverse(MyProjectsList.urlname),
            })

        menu_items.extend([
            {
                'title': ChangeMyPasswordView.page_title,
                'url': reverse(ChangeMyPasswordView.urlname),
            },
            {
                'title': TwoFactorProfileView.page_title,
                'url': reverse(TwoFactorProfileView.urlname),
            }
        ])

        if (
            self.couch_user and self.couch_user.is_dimagi or
            toggles.MOBILE_PRIVILEGES_FLAG.enabled(self.couch_user.username)
        ):
            menu_items.append({
                'title': EnableMobilePrivilegesView.page_title,
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
                'title': ManageAccountingAdminsView.page_title,
                'url': reverse(ManageAccountingAdminsView.urlname),
            },
        )))

        from corehq.apps.accounting.views import (
            TriggerInvoiceView, TriggerBookkeeperEmailView,
            TestRenewalEmailView,
        )
        items.append(('Other Actions', (
            {
                'title': TriggerInvoiceView.page_title,
                'url': reverse(TriggerInvoiceView.urlname),
            },
            {
                'title': TriggerBookkeeperEmailView.page_title,
                'url': reverse(TriggerBookkeeperEmailView.urlname),
            },
            {
                'title': TestRenewalEmailView.page_title,
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
                and (toggles.IS_DEVELOPER.enabled(self.couch_user.username))):
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
            # dropdown_dict(mark_for_escaping("HQ Announcements"),
            #                      url=reverse("default_announcement_admin")),
        ]
        try:
            if AccountingTab(self._request)._is_viewable:
                submenu_context.append(
                    dropdown_dict(AccountingTab.title, url=reverse('accounting_default'))
                )
        except Exception:
            pass
        try:
            submenu_context.append(dropdown_dict(
                mark_for_escaping(_("Old SMS Billing")),
                url=reverse("billing_default")))
        except Exception:
            pass
        submenu_context.extend([
            dropdown_dict(_("SMS Connectivity & Billing"), url=reverse("default_sms_admin_interface")),
            dropdown_dict(_("Feature Flags"), url=reverse("toggle_list")),
            dropdown_dict(_("CommCare Builds"), url="/builds/edit_menu"),
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
                 toggles.IS_DEVELOPER.enabled(self.couch_user.username))):
            return [
                (_('Administrative Reports'), [
                    {'title': _('System Info'),
                     'url': reverse('system_info')},
                ])]

        admin_operations = []

        if self.couch_user and self.couch_user.is_staff:
            from corehq.apps.hqadmin.views import (AuthenticateAs, ReprocessMessagingCaseUpdatesView)
            admin_operations.extend([
                {'title': _('PillowTop Errors'),
                 'url': reverse('admin_report_dispatcher',
                                args=('pillow_errors',))},
                {'title': _('Login as another user'),
                 'url': reverse(AuthenticateAs.urlname)},
                {'title': _('Look up user by email'),
                 'url': reverse('web_user_lookup')},
                {'title': _('View raw couch documents'),
                 'url': reverse('raw_couch')},
                {'title': _('Check Call Center UCR tables'),
                 'url': reverse('callcenter_ucr_check')},
                {'title': _('Grant superuser privileges'),
                 'url': reverse('superuser_management')},
                {'title': _('Reprocess Messaging Case Updates'),
                 'url': reverse(ReprocessMessagingCaseUpdatesView.urlname)},
            ])
        return [
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
                {'title': _('System Info'),
                 'url': reverse('system_info')},
                {'title': _('Download Malt table'),
                 'url': reverse('download_malt')},
                {'title': _('Download Global Impact Report'),
                 'url': reverse('download_gir')},
                {'title': _('CommCare Version'),
                 'url': reverse('admin_report_dispatcher', args=('commcare_version', ))},
                {'title': _('Admin Phone Number Report'),
                 'url': reverse('admin_report_dispatcher', args=('phone_number_report',))},
            ]),
            (_('Administrative Operations'), admin_operations),
            (_('CommCare Reports'), [
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
                ]
            ]),
        ]

    @property
    def _is_viewable(self):
        return (self.couch_user and
                (self.couch_user.is_superuser or
                 toggles.IS_DEVELOPER.enabled(self.couch_user.username)))
