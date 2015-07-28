from collections import namedtuple
from urllib import urlencode
from corehq.toggles import OPENLMIS

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe, mark_for_escaping
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, get_language
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.core.cache import cache

from corehq import toggles, privileges, Domain, feature_previews
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.models import BillingAccount, Invoice
from corehq.apps.accounting.utils import (
    domain_has_privilege,
    is_accounting_admin
)
from corehq.apps.domain.utils import user_has_custom_top_menu
from corehq.apps.hqadmin.reports import (
    RealProjectSpacesReport,
    CommConnectProjectSpacesReport,
    CommTrackProjectSpacesReport,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from corehq.apps.hqwebapp.utils import (
    dropdown_dict,
    sidebar_to_dropdown
)
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.utils import get_indicator_domains
from corehq.apps.reminders.util import can_use_survey_reminders
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from django_prbac.utils import has_privilege
from corehq.util.markup import mark_up_urls

from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.cache import make_template_fragment_key
from dimagi.utils.web import get_url_base

from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
                                            CustomProjectReportDispatcher)
from corehq.apps.reports.models import ReportConfig
from django.db import models


def format_submenu_context(title, url=None, html=None,
                           is_header=False, is_divider=False, data_id=None):
    return {
        'title': title,
        'url': url,
        'html': html,
        'is_header': is_header,
        'is_divider': is_divider,
        'data_id': data_id,
    }


def format_second_level_context(title, url, menu):
    return {
        'title': title,
        'url': url,
        'is_second_level': True,
        'submenu': menu,
    }


class GaTracker(namedtuple('GaTracking', 'category action label')):
    """
    Info for tracking clicks using Google Analytics
    see https://developers.google.com/analytics/devguides/collection/analyticsjs/events
    """
    def __new__(cls, category, action, label=None):
        return super(GaTracker, cls).__new__(cls, category, action, label)


class UITab(object):
    title = None
    view = None
    subtab_classes = None

    dispatcher = None

    # must be instance of GaTracker
    ga_tracker = None

    def __init__(self, request, current_url_name, domain=None, couch_user=None,
                 project=None, org=None):
        if self.subtab_classes:
            self.subtabs = [cls(request, current_url_name, domain=domain,
                                couch_user=couch_user, project=project,
                                org=org)
                            for cls in self.subtab_classes]
        else:
            self.subtabs = None

        self.domain = domain
        self.couch_user = couch_user
        self.project = project
        self.org = org

        # This should not be considered as part of the subclass API unless it
        # is necessary. Try to add new explicit parameters instead.
        self._request = request
        self._current_url_name = current_url_name

    @property
    def dropdown_items(self):
        # todo: add default implementation which looks at sidebar_items and
        # sees which ones have is_dropdown_visible or something like that.
        # Also make it work for tabs with subtabs.
        return sidebar_to_dropdown(sidebar_items=self.sidebar_items,
                                   domain=self.domain, current_url_name=self.url)

    @property
    @memoized
    def sidebar_items(self):
        if self.dispatcher:
            context = {
                'request': self._request,
                'domain': self.domain,
            }
            return self.dispatcher.navigation_sections(context)
        else:
            return []

    @property
    def is_viewable(self):
        """
        Whether the tab should be displayed.  Subclass implementations can skip
        checking whether domain, couch_user, or project is not None before
        accessing an attribute of them -- this property is accessed in
        real_is_viewable and wrapped in a try block that returns False in the
        case of an AttributeError for any of those variables.

        """
        raise NotImplementedError()

    @property
    @memoized
    def real_is_viewable(self):
        if self.subtabs:
            return any(st.real_is_viewable for st in self.subtabs)
        else:
            try:
                return self.is_viewable
            except AttributeError:
                return False

    @property
    @memoized
    def url(self):
        try:
            if self.domain:
                return reverse(self.view, args=[self.domain])
            if self.org:
                return reverse(self.view, args=[self.org.name])
        except Exception:
            pass

        try:
            return reverse(self.view)
        except Exception:
            return None

    @property
    def is_active_shortcircuit(self):
        return None

    @property
    def is_active_fast(self):
        shortcircuit = self.is_active_shortcircuit
        if shortcircuit is not None:
            return shortcircuit

        request_path = self._request.get_full_path()
        return self.url and request_path.startswith(self.url)

    @property
    @memoized
    def is_active(self):
        shortcircuit = self.is_active_shortcircuit
        if shortcircuit is not None:
            return shortcircuit

        request_path = self._request.get_full_path()
        url_base = get_url_base()

        def url_matches(url, request_path):
            if url.startswith(url_base):
                return request_path.startswith(url[len(url_base):])
            return request_path.startswith(url)

        if self.urls:
            if (any(url_matches(url, request_path) for url in self.urls) or
                    self._current_url_name in self.subpage_url_names):
                return True
        elif self.subtabs and any(st.is_active for st in self.subtabs):
            return True

    @property
    @memoized
    def urls(self):
        urls = [self.url] if self.url else []
        if self.subtabs:
            for st in self.subtabs:
                urls.extend(st.urls)

        try:
            for name, section in self.sidebar_items:
                urls.extend(item['url'] for item in section)
        except Exception:
            # tried to get urls for another tab on a page that doesn't provide
            # the necessary couch_user, domain, project, etc. value
            pass

        return urls

    @property
    @memoized
    def subpage_url_names(self):
        """
        List of all url names of subpages of sidebar items that get
        displayed only when you're on that subpage.
        """
        names = []
        if self.subtabs:
            for st in self.subtabs:
                names.extend(st.subpage_url_names)

        try:
            for name, section in self.sidebar_items:
                names.extend(subpage['urlname']
                             for item in section
                             for subpage in item.get('subpages', []))
        except Exception:
            pass

        return names

    @classmethod
    def clear_dropdown_cache(cls, request, domain):
        for is_active in True, False:
            if hasattr(cls, 'get_view'):
                view = cls.get_view(domain)
            else:
                view = cls.view
            key = make_template_fragment_key('header_tab', [
                domain,
                None,  # tab.org should be None for any non org page
                view,
                is_active,
                request.couch_user.get_id,
                get_language(),
            ])
            cache.delete(key)


    @property
    def css_id(self):
        return self.__class__.__name__


class ProjectReportsTab(UITab):
    title = ugettext_noop("Project Reports")
    view = "corehq.apps.reports.views.default"

    @property
    def is_active_shortcircuit(self):
        # HACK. We need a more overarching way to avoid doing things this way
        if 'reports/adm' in self._request.get_full_path():
            return False

    @property
    def is_viewable(self):
        return (self.domain and self.project and
                not self.project.is_snapshot and
                (self.couch_user.can_view_reports() or
                 self.couch_user.get_viewable_reports()))

    @property
    def sidebar_items(self):
        context = {
            'request': self._request,
            'domain': self.domain,
        }

        tools = [(_("Tools"), [
            {'title': _('My Saved Reports'),
             'url': reverse('saved_reports', args=[self.domain]),
             'icon': 'icon-tasks',
             'show_in_dropdown': True}
        ])]

        user_reports = []
        if (toggle_enabled(self._request, toggles.USER_CONFIGURABLE_REPORTS)
                and has_privilege(self._request, privileges.REPORT_BUILDER)):
            user_reports = [(
                _("Create Reports"),
                [{
                    "title": _('Create new report'),
                    "url": reverse("report_builder_select_type", args=[self.domain]),
                    "icon": "icon-plus"
                }]
            )]

        project_reports = ProjectReportDispatcher.navigation_sections(context)
        custom_reports = CustomProjectReportDispatcher.navigation_sections(
            context)

        return tools + user_reports + project_reports + custom_reports


class IndicatorAdminTab(UITab):
    title = ugettext_noop("Administer Indicators")
    view = "corehq.apps.indicators.views.default_admin"
    dispatcher = IndicatorAdminInterfaceDispatcher

    @property
    def is_viewable(self):
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
    view = 'corehq.apps.dashboard.views.dashboard_default'

    @property
    def is_viewable(self):
        return (self.domain and self.project and
                not self.project.is_snapshot and
                self.couch_user and
                # domain hides Dashboard tab if user is non-admin
                not user_has_custom_top_menu(self.domain, self.couch_user))


class ReportsTab(UITab):
    title = ugettext_noop("Reports")
    subtab_classes = (ProjectReportsTab, IndicatorAdminTab)

    @property
    def view(self):
        return self.get_view(self.domain)

    @staticmethod
    def get_view(domain):
        module = Domain.get_module_by_name(domain)
        if hasattr(module, 'DEFAULT_REPORT_CLASS'):
            return "corehq.apps.reports.views.default"
        return "corehq.apps.reports.views.saved_reports"

    @property
    def dropdown_items(self):
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
            saved_reports_dropdown = ([saved_report_header] + first_five_items + rest_as_second_level_items)
        else:
            saved_reports_dropdown = []

        context = {
            'request': self._request,
            'domain': self.domain,
        }
        reports = sidebar_to_dropdown(
            ProjectReportDispatcher.navigation_sections(context),
            current_url_name=self.url)
        return saved_reports_dropdown + reports


class ProjectInfoTab(UITab):
    title = ugettext_noop("Project Info")
    view = "corehq.apps.appstore.views.project_info"

    @property
    def is_viewable(self):
        return self.project and self.project.is_snapshot


class SetupTab(UITab):
    title = ugettext_noop("Setup")
    view = "corehq.apps.commtrack.views.default"

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
    def is_viewable(self):
        return (self.couch_user.is_domain_admin() and
                self.project.commtrack_enabled)

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
        from corehq.apps.locations.views import FacilitySyncView

        if self.project.commtrack_enabled:
            commcare_supply_setup = [
                # products
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
                # programs
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
                # sms
                {
                    'title': SMSSettingsView.page_title,
                    'url': reverse(SMSSettingsView.urlname, args=[self.domain]),
                },
                # consumption
                {
                    'title': DefaultConsumptionView.page_title,
                    'url': reverse(DefaultConsumptionView.urlname, args=[self.domain]),
                },
                # settings
                {
                    'title': CommTrackSettingsView.page_title,
                    'url': reverse(CommTrackSettingsView.urlname, args=[self.domain]),
                },
                # stock levels
                {
                    'title': StockLevelsView.page_title,
                    'url': reverse(StockLevelsView.urlname, args=[self.domain]),
                },
            ]
            if OPENLMIS.enabled(self.domain):
                commcare_supply_setup.append(
                    # external sync
                    {
                        'title': FacilitySyncView.page_title,
                        'url': reverse(FacilitySyncView.urlname, args=[self.domain]),
                    })
            return [[_('CommCare Supply Setup'), commcare_supply_setup]]


class ProjectDataTab(UITab):
    title = ugettext_noop("Data")
    view = "corehq.apps.data_interfaces.views.default"

    @property
    @memoized
    def can_edit_commcare_data(self):
        return self.couch_user.can_edit_data()

    @property
    @memoized
    def can_export_data(self):
        return (self.project and not self.project.is_snapshot
                and self.couch_user.can_export_data())

    @property
    @memoized
    def can_use_lookup_tables(self):
        return domain_has_privilege(self.domain, privileges.LOOKUP_TABLES)

    @property
    def is_viewable(self):
        return self.domain and (self.can_edit_commcare_data or self.can_export_data)

    @property
    def sidebar_items(self):
        items = []

        context = {
            'request': self._request,
            'domain': self.domain,
        }

        if self.can_export_data:
            from corehq.apps.data_interfaces.dispatcher \
                import DataInterfaceDispatcher
            items.extend(DataInterfaceDispatcher.navigation_sections(context))

        if self.can_edit_commcare_data:
            from corehq.apps.data_interfaces.dispatcher \
                import EditDataInterfaceDispatcher
            edit_section = EditDataInterfaceDispatcher.navigation_sections(context)

            from corehq.apps.data_interfaces.views \
                import CaseGroupListView, CaseGroupCaseManagementView, ArchiveFormView
            edit_section[0][1].append({
                'title': CaseGroupListView.page_title,
                'url': reverse(CaseGroupListView.urlname, args=[self.domain]),
                'subpages': [
                    {
                        'title': CaseGroupCaseManagementView.page_title,
                        'urlname': CaseGroupCaseManagementView.urlname,
                    }
                ]
            })

            if toggles.BULK_ARCHIVE_FORMS.enabled(self._request.user.username):
                edit_section[0][1].append({
                    'title': ArchiveFormView.page_title,
                    'url': reverse(ArchiveFormView.urlname, args=[self.domain]),
                })
            items.extend(edit_section)

        if self.can_use_lookup_tables:
            from corehq.apps.fixtures.dispatcher import FixtureInterfaceDispatcher
            items.extend(FixtureInterfaceDispatcher.navigation_sections(context))

        if toggle_enabled(self._request, toggles.REVAMPED_EXPORTS):
            from corehq.apps.reports.dispatcher import DataExportInterfaceDispatcher
            items.extend(DataExportInterfaceDispatcher.navigation_sections(context))

        return items


class ApplicationsTab(UITab):
    view = "corehq.apps.app_manager.views.default"

    @property
    def title(self):
        return _("Applications")

    @classmethod
    def make_app_title(cls, app_name, doc_type):
        return mark_safe("%s%s" % (
            mark_for_escaping(app_name or '(Untitled)'),
            mark_for_escaping(' (Remote)' if doc_type == 'RemoteApp' else ''),
        ))

    @property
    def dropdown_items(self):
        # todo async refresh submenu when on the applications page and
        # you change the application name
        key = [self.domain]
        apps = get_db().view('app_manager/applications_brief',
                             reduce=False,
                             startkey=key,
                             endkey=key + [{}],).all()
        submenu_context = []
        if not apps:
            return submenu_context

        submenu_context.append(dropdown_dict(_('My Applications'),
                               is_header=True))
        for app in apps:
            app_info = app['value']
            if app_info:
                app_id = app_info['_id']
                app_name = app_info['name']
                app_doc_type = app_info['doc_type']

                url = reverse('view_app', args=[self.domain, app_id]) if self.couch_user.can_edit_apps() \
                    else reverse('release_manager', args=[self.domain, app_id])
                app_title = self.make_app_title(app_name, app_doc_type)

                submenu_context.append(dropdown_dict(
                    app_title,
                    url=url,
                    data_id=app_id,
                ))

        if self.couch_user.can_edit_apps():
            submenu_context.append(dropdown_dict(None, is_divider=True))
            newapp_options = [
                dropdown_dict(
                    None,
                    html=self._new_app_link(_('Blank Application'))
                ),
                dropdown_dict(
                    None,
                    html=self._new_app_link(_('RemoteApp (Advanced Users Only)'),
                                            is_remote=True)),
            ]
            newapp_options.append(dropdown_dict(
                _('Visit CommCare Exchange to copy existing app...'),
                url=reverse('appstore')))
            submenu_context.append(dropdown_dict(
                _('New Application...'),
                '#',
                second_level_dropdowns=newapp_options
            ))
        return submenu_context

    def _new_app_link(self, title, is_remote=False):
        template = "app_manager/partials/new_app_link.html"
        return mark_safe(render_to_string(template, {
            'domain': self.domain,
            'is_remote': is_remote,
            'action_text': title,
        }))

    @property
    def is_viewable(self):
        couch_user = self.couch_user
        return (self.domain and couch_user and
                (couch_user.is_web_user() or couch_user.can_edit_apps()) and
                (couch_user.is_member_of(self.domain) or couch_user.is_superuser) and
                # domain hides Applications tab if user is non-admin
                not user_has_custom_top_menu(self.domain, couch_user))


class CloudcareTab(UITab):
    title = ugettext_noop("CloudCare")
    view = "corehq.apps.cloudcare.views.default"

    ga_tracker = GaTracker('CloudCare', 'Click Cloud-Care top-level nav')

    @property
    def is_viewable(self):
        return (
            has_privilege(self._request, privileges.CLOUDCARE)
            and self.domain
            and (self.couch_user.can_edit_data() or self.couch_user.is_commcare_user())
        )


class MessagingTab(UITab):
    title = ugettext_noop("Messaging")
    view = "corehq.apps.sms.views.default"

    @property
    def is_viewable(self):
        return (self.can_access_reminders or self.can_access_sms) and (
            self.project and not (self.project.is_snapshot or
                                  self.couch_user.is_commcare_user())
        ) and self.couch_user.can_edit_data()

    @property
    @memoized
    def can_access_sms(self):
        return has_privilege(self._request, privileges.OUTBOUND_SMS)

    @property
    @memoized
    def can_access_reminders(self):
        return has_privilege(self._request, privileges.REMINDERS_FRAMEWORK)

    @property
    def sidebar_items(self):
        from corehq.apps.reports.standard.sms import MessageLogReport

        def reminder_subtitle(form=None, **context):
            return form['nickname'].value

        def keyword_subtitle(keyword=None, **context):
            return keyword.keyword

        reminders_urls = []
        if self.can_access_reminders:
            from corehq.apps.reminders.views import (
                EditScheduledReminderView,
                CreateScheduledReminderView,
                RemindersListView,
            )
            reminders_list_url = reverse(RemindersListView.urlname, args=[self.domain])
            edit_reminder_urlname = EditScheduledReminderView.urlname
            new_reminder_urlname = CreateScheduledReminderView.urlname
            reminders_urls.extend([
                {
                    'title': _("Reminders"),
                    'url': reminders_list_url,
                    'subpages': [
                        {
                            'title': reminder_subtitle,
                            'urlname': edit_reminder_urlname
                        },
                        {
                            'title': _("Schedule Reminder"),
                            'urlname': new_reminder_urlname,
                        },
                        {
                            'title': _("Schedule Multi Event Reminder"),
                            'urlname': 'create_complex_reminder_schedule',
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

        can_use_survey = can_use_survey_reminders(self._request)
        if can_use_survey:
            from corehq.apps.reminders.views import (
                KeywordsListView, AddNormalKeywordView,
                AddStructuredKeywordView, EditNormalKeywordView,
                EditStructuredKeywordView,
            )
            keyword_list_url = reverse(KeywordsListView.urlname, args=[self.domain])
            reminders_urls.append({
                'title': _("Keywords"),
                'url': keyword_list_url,
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

        if self.can_access_reminders:
            reminders_urls.append({
                'title': _("Reminders in Error"),
                'url': reverse('reminders_in_error', args=[self.domain]),
                'show_in_dropdown': True,
            })
        items = []
        messages_urls = []
        if self.can_access_sms:
            messages_urls.extend([
                {
                    'title': _('Compose SMS Message'),
                    'url': reverse('sms_compose_message', args=[self.domain])
                },
            ])
        if self.can_access_reminders:
            messages_urls.extend([
                {
                    'title': _("Broadcast Messages"),
                    'url': reverse('one_time_reminders', args=[self.domain]),
                    'subpages': [
                        {
                            'title': _("Edit Broadcast"),
                            'urlname': 'edit_one_time_reminder'
                        },
                        {
                            'title': _("New Broadcast"),
                            'urlname': 'add_one_time_reminder'
                        },
                        {
                            'title': _("New Broadcast"),
                            'urlname': 'copy_one_time_reminder'
                        },
                    ],
                    'show_in_dropdown': True,
                },
            ])
        if self.can_access_sms:
            messages_urls.extend([
                {
                    'title': _('Message Log'),
                    'url': MessageLogReport.get_url(domain=self.domain),
                    'show_in_dropdown': True,
                },
            ])
        if messages_urls:
            items.append((_("Messages"), messages_urls))
        if reminders_urls:
            items.append((_("Data Collection and Reminders"), reminders_urls))

        if self.project.commtrack_enabled:
            from corehq.apps.sms.views import SubscribeSMSView
            items.append(
                (_("CommCare Supply"), [
                    {'title': ugettext_lazy("Subscribe to SMS Reports"),
                     'url': reverse(SubscribeSMSView.urlname, args=[self.domain])},
                ])
            )

        if self.couch_user.is_previewer():
            items[0][1].append(
                {'title': _('Chat'),
                 'url': reverse('chat_contacts', args=[self.domain])}
            )

        if self.project.survey_management_enabled and can_use_survey:
            def sample_title(form=None, **context):
                return form['name'].value

            def survey_title(form=None, **context):
                return form['name'].value

            items.append(
                (_("Survey Management"), [
                    {'title': _("Samples"),
                     'url': reverse('sample_list', args=[self.domain]),
                     'subpages': [
                         {'title': sample_title,
                          'urlname': 'edit_sample'},
                         {'title': _("New Sample"),
                          'urlname': 'add_sample'},
                    ]},
                    {'title': _("Surveys"),
                     'url': reverse('survey_list', args=[self.domain]),
                     'subpages': [
                         {'title': survey_title,
                          'urlname': 'edit_survey'},
                         {'title': _("New Survey"),
                          'urlname': 'add_survey'},
                    ]},
                ])
            )

        settings_pages = []
        if self.can_access_sms:
            from corehq.apps.sms.views import (
                DomainSmsGatewayListView, AddDomainGatewayView,
                EditDomainGatewayView,
            )
            sms_connectivity_url = reverse(
                DomainSmsGatewayListView.urlname, args=[self.domain]
            )
            settings_pages.append({
                'title': _('SMS Connectivity'),
                'url': sms_connectivity_url,
                'subpages': [
                    {
                        'title': _("Add Connection"),
                        'urlname': AddDomainGatewayView.urlname,
                    },
                    {
                        'title': _("Edit Connection"),
                        'urlname': EditDomainGatewayView.urlname,
                    },
                ],
            })
        if self.couch_user.is_superuser or self.couch_user.is_domain_admin(self.domain):
            settings_pages.append(
                {'title': ugettext_lazy("General Settings"),
                 'url': reverse('sms_settings', args=[self.domain])},
            )
            settings_pages.append(
                {'title': ugettext_lazy("Languages"),
                 'url': reverse('sms_languages', args=[self.domain])}
            )
        if settings_pages:
            items.append((_("Settings"), settings_pages))

        return items


class ProjectUsersTab(UITab):
    title = ugettext_noop("Users")
    view = "users_default"

    @property
    def is_viewable(self):
        return self.domain and (self.couch_user.can_edit_commcare_users() or
                                self.couch_user.can_edit_web_users())

    @property
    def is_active_shortcircuit(self):
        if not self.domain:
            return False

    @property
    @memoized
    def is_active(self):
        if super(ProjectUsersTab, self).is_active:
            return True

        if not self.domain:
            return False

        cloudcare_settings_url = reverse('cloudcare_app_settings',
                                         args=[self.domain])
        full_path = self._request.get_full_path()
        return full_path.startswith(cloudcare_settings_url)

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

            from corehq.apps.users.views.mobile import \
                EditCommCareUserView, ConfirmBillingAccountForExtraUsersView
            mobile_users_menu = [
                {
                    'title': _('Mobile Workers'),
                    'url': reverse('commcare_users', args=[self.domain]),
                    'description': _(
                        "Create and manage users for CommCare and CloudCare."),
                    'subpages': [
                        {'title': commcare_username,
                         'urlname': EditCommCareUserView.urlname},
                        {'title': _('New Mobile Worker'),
                         'urlname': 'add_commcare_account',
                         'show_in_dropdown': True,
                         'show_in_first_level': True},
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
                mobile_users_menu.append({
                    'title': _('CloudCare Permissions'),
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
                EditMyAccountDomainView,
                get_web_user_list_view,
            )
            items.append((_('Project Users'), [
                {
                    'title': get_web_user_list_view(self._request).page_title,
                    'url': reverse(get_web_user_list_view(self._request).urlname, args=[self.domain]),
                    'description': _("Grant other CommCare HQ users access to your project and manage user roles."),
                    'subpages': [
                        {
                            'title': _("Invite Web User"),
                            'urlname': 'invite_web_user'
                        },
                        {
                            'title': web_username,
                            'urlname': EditWebUserView.urlname
                        },
                        {
                            'title': _('My Information'),
                            'urlname': EditMyAccountDomainView.urlname
                        }
                    ],
                    'show_in_dropdown': True,
                }
            ]))

        if (feature_previews.LOCATIONS.enabled(self.domain) and
                has_privilege(self._request, privileges.LOCATIONS)):
            from corehq.apps.locations.views import (
                LocationsListView,
                NewLocationView,
                EditLocationView,
                LocationImportView,
                LocationImportStatusView,
                LocationFieldsView,
                LocationTypesView,
            )
            from corehq.apps.locations.permissions import (
                user_can_edit_location_types
            )

            locations_config = [{
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
            }]

            if user_can_edit_location_types(self.couch_user, self.project):
                locations_config.append({
                    'title': LocationTypesView.page_title,
                    'url': reverse(LocationTypesView.urlname, args=[self.domain]),
                    'show_in_dropdown': True,
                })
            items.append((_('Locations'), locations_config))

        return items


class ProjectSettingsTab(UITab):
    title = ugettext_noop("Project Settings")
    view = 'domain_settings_default'

    @property
    def is_viewable(self):
        return (self.domain and self.couch_user and
                self.couch_user.is_domain_admin(self.domain))

    @property
    def sidebar_items(self):
        from corehq.apps.domain.views import (FeatureFlagsView,
                                              FeaturePreviewsView,
                                              TransferDomainView)

        items = []
        user_is_admin = self.couch_user.is_domain_admin(self.domain)

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

        if toggles.DHIS2_DOMAIN.enabled(self.domain):
            from corehq.apps.domain.views import EditDhis2SettingsView
            project_info.append({
                'title': _(EditDhis2SettingsView.page_title),
                'url': reverse(EditDhis2SettingsView.urlname, args=[self.domain])
            })

        can_view_orgs = (user_is_admin
                         and self.project and self.project.organization
                         and has_privilege(self._request, privileges.CROSS_PROJECT_REPORTS))

        if can_view_orgs:
            from corehq.apps.domain.views import OrgSettingsView
            project_info.append({
                'title': _(OrgSettingsView.page_title),
                'url': reverse(OrgSettingsView.urlname, args=[self.domain])
            })

        items.append((_('Project Information'), project_info))

        if user_is_admin:
            administration = [
                {
                    'title': _('CommCare Exchange'),
                    'url': reverse('domain_snapshot_settings', args=[self.domain])
                },
                {
                    'title': _('Multimedia Sharing'),
                    'url': reverse('domain_manage_multimedia', args=[self.domain])
                }
            ]

            def forward_name(repeater_type=None, **context):
                if repeater_type == 'FormRepeater':
                    return _("Forward Forms")
                elif repeater_type == 'ShortFormRepeater':
                    return _("Forward Form Stubs")
                elif repeater_type == 'CaseRepeater':
                    return _("Forward Cases")

            administration.extend([
                {'title': _('Data Forwarding'),
                 'url': reverse('domain_forwarding', args=[self.domain]),
                 'subpages': [
                     {
                         'title': forward_name,
                         'urlname': 'add_repeater',
                     },
                     {
                         'title': forward_name,
                         'urlname': 'add_form_repeater',
                     },
                ]}
            ])

            administration.append({
                'title': _(FeaturePreviewsView.page_title),
                'url': reverse(FeaturePreviewsView.urlname, args=[self.domain])
            })

            if toggles.TRANSFER_DOMAIN.enabled(self.domain):
                administration.append({
                    'title': _(TransferDomainView.page_title),
                    'url': reverse(TransferDomainView.urlname, args=[self.domain])
                })
            items.append((_('Project Administration'), administration))

        from corehq.apps.users.models import WebUser
        if isinstance(self.couch_user, WebUser):
            if user_is_admin or self.couch_user.is_superuser:
                from corehq.apps.domain.views import (
                    DomainSubscriptionView, EditExistingBillingAccountView,
                    DomainBillingStatementsView, ConfirmSubscriptionRenewalView,
                    InternalSubscriptionManagementView,
                )
                billing_account = BillingAccount.get_account_by_domain(self.domain)
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
                if billing_account is not None:
                    subscription.append(
                        {
                            'title':  EditExistingBillingAccountView.page_title,
                            'url': reverse(EditExistingBillingAccountView.urlname,
                                           args=[self.domain]),
                        },
                    )
                if (billing_account is not None
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


class MySettingsTab(UITab):
    title = ugettext_noop("My Settings")
    view = 'default_my_settings'

    @property
    def is_viewable(self):
        return self.couch_user is not None

    @property
    def sidebar_items(self):
        from corehq.apps.settings.views import MyAccountSettingsView, \
            MyProjectsList, ChangeMyPasswordView
        items = [
            (_("Manage My Settings"), (
                {
                    'title': _(MyAccountSettingsView.page_title),
                    'url': reverse(MyAccountSettingsView.urlname),
                },
                {
                    'title': _(MyProjectsList.page_title),
                    'url': reverse(MyProjectsList.urlname),
                },
                {
                    'title': _(ChangeMyPasswordView.page_title),
                    'url': reverse(ChangeMyPasswordView.urlname),
                },
            ))
        ]
        return items


class AdminReportsTab(UITab):
    title = ugettext_noop("Admin Reports")
    view = "corehq.apps.hqadmin.views.default"

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
            from corehq.apps.hqadmin.views import AuthenticateAs
            admin_operations.extend([
                {'title': _('Mass Email Users'),
                 'url': reverse('mass_email')},
                {'title': _('PillowTop Errors'),
                 'url': reverse('admin_report_dispatcher',
                                args=('pillow_errors',))},
                {'title': _('Login as another user'),
                 'url': reverse(AuthenticateAs.urlname)},
            ])
        return [
            (_('Administrative Reports'), [
                {'title': _('Project Space List'),
                 'url': reverse('admin_report_dispatcher', args=('domains',))},
                {'title': _('User List'),
                 'url': reverse('admin_report_dispatcher', args=('user_list',))},
                {'title': _('Application List'),
                 'url': reverse('admin_report_dispatcher', args=('app_list',))},
                {'title': _('Message Logs Across All Domains'),
                 'url': reverse('message_log_report')},
                {'title': _('CommCare Versions'),
                 'url': reverse('commcare_version_report')},
                {'title': _('System Info'),
                 'url': reverse('system_info')},
                {'title': _('Loadtest Report'),
                 'url': reverse('loadtest_report')},
            ]),
            (_('Administrative Operations'), admin_operations),
            (_('CommCare Reports'), [
                {
                    'title': report.name,
                    'url': '%s?%s' % (reverse('admin_report_dispatcher',
                                              args=(report.slug,)),
                                      urlencode(report.default_params))
                } for report in [
                    RealProjectSpacesReport,
                    CommConnectProjectSpacesReport,
                    CommTrackProjectSpacesReport,
                ]
            ]),
        ]

    @property
    def is_viewable(self):
        return (self.couch_user and
                (self.couch_user.is_superuser or
                 toggles.IS_DEVELOPER.enabled(self.couch_user.username)))


class AccountingTab(UITab):
    title = ugettext_noop("Accounting")
    view = "accounting_default"
    dispatcher = AccountingAdminInterfaceDispatcher

    @property
    def is_viewable(self):
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

    @property
    @memoized
    def sidebar_items(self):
        items = super(SMSAdminTab, self).sidebar_items
        items.append((_('SMS Connectivity'), [
            {'title': _('SMS Connections'),
             'url': reverse('list_backends'),
             'subpages': [
                 {'title': _('Add Connection'),
                  'urlname': 'add_backend'},
                 {'title': _('Edit Connection'),
                  'urlname': 'edit_backend'},
            ]},
            {'title': _('SMS Country-Connection Map'),
             'url': reverse('global_backend_map')},
        ]))
        return items

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class FeatureFlagsTab(UITab):
    title = ugettext_noop("Feature Flags")
    view = "toggle_list"

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class AdminTab(UITab):
    title = ugettext_noop("Admin")
    view = "corehq.apps.hqadmin.views.default"
    subtab_classes = (
        AdminReportsTab,
        SMSAdminTab,
        AccountingTab,
        FeatureFlagsTab
    )

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
            dropdown_dict(_("Management"), is_header=True),
            dropdown_dict(mark_for_escaping(_("Commands")),
                          url=reverse("management_commands")),
            # dropdown_dict(mark_for_escaping("HQ Announcements"),
            #                      url=reverse("default_announcement_admin")),
        ]
        try:
            if AccountingTab(self._request, self._current_url_name).is_viewable:
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
            dropdown_dict(None, is_divider=True),
            dropdown_dict(_("Django Admin"), url="/admin")
        ])
        return submenu_context

    @property
    def is_viewable(self):
        return (self.couch_user and
                (self.couch_user.is_superuser or
                 toggles.IS_DEVELOPER.enabled(self.couch_user.username)))


class ExchangeTab(UITab):
    title = ugettext_noop("Exchange")
    view = "corehq.apps.appstore.views.appstore"

    @property
    def dropdown_items(self):
        submenu_context = None
        if self.domain and self.couch_user.is_domain_admin(self.domain):
            submenu_context = [
                dropdown_dict(_("CommCare Exchange"), url=reverse("appstore")),
                dropdown_dict(
                    _("Publish this project"),
                    url=reverse("domain_snapshot_settings",
                                args=[self.domain]))
            ]
        return submenu_context

    @property
    def is_viewable(self):
        couch_user = self.couch_user
        return (self.domain and couch_user and couch_user.can_edit_apps() and
                (couch_user.is_member_of(self.domain) or couch_user.is_superuser))


class OrgTab(UITab):
    @property
    def is_viewable(self):
        return (self.org and self.couch_user and
                (self.couch_user.is_member_of_org(self.org) or
                    self.couch_user.is_superuser))


class OrgReportTab(OrgTab):
    title = ugettext_noop("Reports")
    view = "corehq.apps.orgs.views.base_report"

    @property
    def dropdown_items(self):
        return [
            dropdown_dict(
                _("Projects Table"),
                url=reverse("orgs_report", args=(self.org.name,))),
            dropdown_dict(
                _("Form Data"),
                url=reverse("orgs_stats", args=(self.org.name, "forms"))),
            dropdown_dict(
                _("Case Data"),
                url=reverse("orgs_stats", args=(self.org.name, "cases"))),
            dropdown_dict(
                _("User Data"),
                url=reverse("orgs_stats", args=(self.org.name, "users"))),
        ]


class OrgSettingsTab(OrgTab):
    title = ugettext_noop("Settings")
    view = "corehq.apps.orgs.views.orgs_landing"

    @property
    def dropdown_items(self):
        return [
            dropdown_dict(
                _("Projects"),
                url=reverse("orgs_landing", args=(self.org.name,))),
            dropdown_dict(
                _("Teams"),
                url=reverse("orgs_teams", args=(self.org.name,))),
            dropdown_dict(
                _("Members"),
                url=reverse("orgs_members", args=(self.org.name,))),
        ]


class MaintenanceAlert(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    text = models.TextField()

    @property
    def html(self):
        return mark_up_urls(self.text)
