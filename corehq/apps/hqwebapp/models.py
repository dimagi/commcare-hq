from django.template.loader import render_to_string
from django.utils.safestring import mark_safe, mark_for_escaping
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop, ugettext_lazy
from corehq import toggles, privileges
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.models import BillingAccountAdmin, Invoice
from corehq.apps.domain.utils import get_adm_enabled_domains
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.utils import get_indicator_domains
from corehq.apps.reminders.util import can_use_survey_reminders
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from django_prbac.exceptions import PermissionDenied
from django_prbac.models import Role, UserRole
from django_prbac.utils import ensure_request_has_privilege

from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
    CustomProjectReportDispatcher)
from corehq.apps.adm.dispatcher import (ADMAdminInterfaceDispatcher,
    ADMSectionDispatcher)
from corehq.apps.announcements.dispatcher import (
    HQAnnouncementAdminInterfaceDispatcher)
from corehq.toggles import IS_DEVELOPER


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


class UITab(object):
    title = None
    view = None
    subtab_classes = None

    dispatcher = None

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
        return []

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

        if self.urls:
            if (any(request_path.startswith(url) for url in self.urls) or
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
        return (self.domain and self.project and not self.project.is_snapshot and
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
             'icon': 'icon-tasks'}
        ])]

        project_reports = ProjectReportDispatcher.navigation_sections(
            context)
        custom_reports = CustomProjectReportDispatcher.navigation_sections(
            context)

        return tools + project_reports + custom_reports


class ADMReportsTab(UITab):
    title = ugettext_noop("Active Data Management")
    view = "corehq.apps.adm.views.default_adm_report"
    dispatcher = ADMSectionDispatcher

    @property
    def is_viewable(self):
        if not self.project or self.project.commtrack_enabled:
            return False

        adm_enabled_projects = get_adm_enabled_domains()

        return (not self.project.is_snapshot and
                self.domain in adm_enabled_projects and
                  (self.couch_user.can_view_reports() or
                   self.couch_user.get_viewable_reports()))


class IndicatorAdminTab(UITab):
    title = ugettext_noop("Administer Indicators")
    view = "corehq.apps.indicators.views.default_admin"
    dispatcher = IndicatorAdminInterfaceDispatcher

    @property
    def is_viewable(self):
        indicator_enabled_projects = get_indicator_domains()
        return self.couch_user.can_edit_data() and self.domain in indicator_enabled_projects


class ReportsTab(UITab):
    title = ugettext_noop("Reports")
    view = "corehq.apps.reports.views.saved_reports"
    subtab_classes = (ProjectReportsTab, ADMReportsTab, IndicatorAdminTab)


class ProjectInfoTab(UITab):
    title = ugettext_noop("Project Info")
    view = "corehq.apps.appstore.views.project_info"

    @property
    def is_viewable(self):
        return self.project and self.project.is_snapshot


class CommTrackSetupTab(UITab):
    title = ugettext_noop("Setup")
    view = "corehq.apps.commtrack.views.default"

    @property
    def dropdown_items(self):
        # circular import
        from corehq.apps.commtrack.views import (
            CommTrackSettingsView,
            ProductListView,
            DefaultConsumptionView,
            ProgramListView,
            SMSSettingsView,
        )
        from corehq.apps.locations.views import (
            LocationsListView,
            LocationSettingsView,
        )

        dropdown_items = [(_(view.page_title), view) for view in (
                ProductListView,
                LocationsListView,
                LocationSettingsView,
                ProgramListView,
                SMSSettingsView,
                DefaultConsumptionView,
                CommTrackSettingsView,
            )
        ]

        return [
            format_submenu_context(
                item[0],
                url=reverse(item[1].urlname, args=[self.domain])
            ) for item in dropdown_items
        ]

    @property
    def is_viewable(self):
        return self.project.commtrack_enabled and self.couch_user.is_domain_admin()

    @property
    def sidebar_items(self):
        # circular import
        from corehq.apps.commtrack.views import (
            CommTrackSettingsView,
            ProductListView,
            NewProductView,
            EditProductView,
            DefaultConsumptionView,
            ProgramListView,
            NewProgramView,
            EditProgramView,
            SMSSettingsView,
        )
        from corehq.apps.locations.views import (
            LocationsListView,
            NewLocationView,
            EditLocationView,
            FacilitySyncView,
            LocationImportView,
            LocationImportStatusView,
            LocationSettingsView,
        )

        items = []

        items.append([_('CommTrack Setup'), [
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
                ]
            },
            # locations
            {
                'title': LocationsListView.page_title,
                'url': reverse(LocationsListView.urlname, args=[self.domain]),
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
                ]
            },
            # locations (advanced)
            {
                'title': LocationSettingsView.page_title,
                'url': reverse(LocationSettingsView.urlname, args=[self.domain]),
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
            # external sync
            {
                'title': FacilitySyncView.page_title,
                'url': reverse(FacilitySyncView.urlname, args=[self.domain]),
            },
        ]])
        return items


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
        return self.project and not self.project.is_snapshot and self.couch_user.can_export_data()

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
            from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
            items.extend(DataInterfaceDispatcher.navigation_sections(context))

        if self.can_edit_commcare_data:
            from corehq.apps.data_interfaces.dispatcher import EditDataInterfaceDispatcher
            edit_section = EditDataInterfaceDispatcher.navigation_sections(context)

            from corehq.apps.data_interfaces.views import CaseGroupListView, CaseGroupCaseManagementView
            if self.couch_user.is_previewer:
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

            items.extend(edit_section)
            
        return items


class ApplicationsTab(UITab):
    view = "corehq.apps.app_manager.views.default"

    @property
    def title(self):
        if self.project.commconnect_enabled:
            return _("Surveys")
        else:
            return _("Applications")

    @classmethod
    def make_app_title(cls, app_name, doc_type):
        return mark_safe("%s%s" % (
            mark_for_escaping(app_name or '(Untitled)'),
            mark_for_escaping(' (Remote)' if doc_type == 'RemoteApp' else ''),
        ))

    @property
    def dropdown_items(self):
        # todo async refresh submenu when on the applications page and you change the application name
        key = [self.domain]
        apps = get_db().view('app_manager/applications_brief',
            reduce=False,
            startkey=key,
            endkey=key+[{}],
            #stale=settings.COUCH_STALE_QUERY,
        ).all()
        submenu_context = []
        if not apps:
            return submenu_context

        submenu_context.append(format_submenu_context(_('My Applications'), is_header=True))
        for app in apps:
            app_info = app['value']
            if app_info:
                app_id = app_info['_id']
                app_name = app_info['name']
                app_doc_type = app_info['doc_type']

                url = reverse('view_app', args=[self.domain, app_id]) if self.couch_user.can_edit_apps() \
                    else reverse('release_manager', args=[self.domain, app_id])
                app_title = self.make_app_title(app_name, app_doc_type)

                submenu_context.append(format_submenu_context(
                    app_title,
                    url=url,
                    data_id=app_id,
                ))

        if self.couch_user.can_edit_apps():
            submenu_context.append(format_submenu_context(None, is_divider=True))
            newapp_options = [
                format_submenu_context(None, html=self._new_app_link(_('Blank Application'))),
                format_submenu_context(None, html=self._new_app_link(_('RemoteApp (Advanced Users Only)'),
                                                                     is_remote=True)),
            ]
            newapp_options.append(format_submenu_context(_('Visit CommCare Exchange to copy existing app...'),
                url=reverse('appstore')))
            submenu_context.append(format_second_level_context(
                _('New Application...'),
                '#',
                newapp_options
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
                (couch_user.is_member_of(self.domain) or couch_user.is_superuser))


class CloudcareTab(UITab):
    title = ugettext_noop("CloudCare")
    view = "corehq.apps.cloudcare.views.default"

    @property
    def is_viewable(self):
        try:
            ensure_request_has_privilege(self._request, privileges.CLOUDCARE)
        except PermissionDenied:
            return False
        return (self.domain
                and (self.couch_user.can_edit_data() or self.couch_user.is_commcare_user())
                and not self.project.commconnect_enabled)


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
        try:
            ensure_request_has_privilege(self._request, privileges.OUTBOUND_SMS)
        except PermissionDenied:
            return False
        return True

    @property
    @memoized
    def can_access_reminders(self):
        try:
            ensure_request_has_privilege(self._request, privileges.REMINDERS_FRAMEWORK)
            return True
        except PermissionDenied:
            return False

    @property
    def sidebar_items(self):
        from corehq.apps.reports.standard.sms import MessageLogReport
        def reminder_subtitle(form=None, **context):
            return form['nickname'].value

        def keyword_subtitle(keyword=None, **context):
            return keyword.keyword

        reminders_urls = []
        if self.can_access_reminders:
            if toggles.REMINDERS_UI_PREVIEW.enabled(self.couch_user.username):
                from corehq.apps.reminders.views import (
                    EditScheduledReminderView,
                    CreateScheduledReminderView,
                    RemindersListView,
                )
                reminders_list_url = reverse(RemindersListView.urlname, args=[self.domain])
                edit_reminder_urlname = EditScheduledReminderView.urlname
                new_reminder_urlname = CreateScheduledReminderView.urlname
            else:
                reminders_list_url = reverse('list_reminders', args=[self.domain])
                edit_reminder_urlname = 'edit_complex'
                new_reminder_urlname = 'add_complex_reminder_schedule'
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
                },
                {
                    'title': _("Reminder Calendar"),
                    'url': reverse('scheduled_reminders', args=[self.domain])
                },
            ])

        can_use_survey = can_use_survey_reminders(self._request)
        if can_use_survey:
            from corehq.apps.reminders.views import (
                KeywordsListView, AddNormalKeywordView,
                AddStructuredKeywordView, EditNormalKeywordView,
                EditStructuredKeywordView,
            )
            if toggles.REMINDERS_UI_PREVIEW.enabled(self.couch_user.username):
                keyword_list_url = reverse(KeywordsListView.urlname, args=[self.domain])
            else:
                keyword_list_url = reverse('manage_keywords', args=[self.domain])
            reminders_urls.append({
                'title': _("Keywords"),
                'url': keyword_list_url,
                'subpages': [
                    {
                        'title': keyword_subtitle,
                        'urlname': 'edit_keyword'
                    },
                    {
                        'title': _("New Keyword"),
                        'urlname': 'add_keyword',
                    },
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
                'url': reverse('reminders_in_error', args=[self.domain])
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
                    ]
                },
            ])
        if self.can_access_sms:
            messages_urls.extend([
                {
                    'title': _('Message Log'),
                    'url': MessageLogReport.get_url(domain=self.domain)
                },
            ])
        if messages_urls:
            items.append((_("Messages"), messages_urls))
        if reminders_urls:
            items.append((_("Data Collection and Reminders"), reminders_urls))

        if self.project.commtrack_enabled:
            from corehq.apps.sms.views import SubscribeSMSView
            items.append(
                (_("CommTrack"), [
                    {'title': ugettext_lazy("Subscribe to SMS Reports"),
                    'url': reverse(SubscribeSMSView.urlname, args=[self.domain])},])
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
            if toggles.REMINDERS_UI_PREVIEW.enabled(self.couch_user.username):
                sms_connectivity_url = reverse(
                    DomainSmsGatewayListView.urlname, args=[self.domain]
                )
            else:
                sms_connectivity_url = reverse(
                    'list_domain_backends', args=[self.domain]
                )
            settings_pages.append({
                'title': _('SMS Connectivity'),
                'url': sms_connectivity_url,
                'subpages': [
                    {
                        'title': _('Add Connection'),
                        'urlname': 'add_domain_backend'
                    },
                    {
                        'title': _("Add Connection"),
                        'urlname': AddDomainGatewayView.urlname,
                    },
                    {
                        'title': _('Edit Connection'),
                        'urlname': 'edit_domain_backend'
                    },
                    {
                        'title': _("Edit Connection"),
                        'urlname': EditDomainGatewayView.urlname,
                    },
                ],
            })
        if self.couch_user.is_superuser or self.couch_user.is_domain_admin(self.domain):
            settings_pages.extend([
                {'title': ugettext_lazy("General Settings"),
                 'url': reverse('sms_settings', args=[self.domain])},
                {'title': ugettext_lazy("Languages"),
                 'url': reverse('sms_languages', args=[self.domain])},
            ])
        if settings_pages:
            items.append((_("Settings"), settings_pages))

        return items

    @property
    def dropdown_items(self):
        return []


class ProjectUsersTab(UITab):
    title = ugettext_noop("Users")
    view = "users_default"

    @property
    def dropdown_items(self):
        return []

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
        cloudcare_settings_url = reverse('cloudcare_app_settings', args=[self.domain])
        full_path = self._request.get_full_path()
        return (super(ProjectUsersTab, self).is_active
                or full_path.startswith(cloudcare_settings_url))

    @property
    def can_view_cloudcare(self):
        try:
            ensure_request_has_privilege(self._request, privileges.CLOUDCARE)
        except PermissionDenied:
            return False
        return self.couch_user.is_domain_admin()

    @property
    def sidebar_items(self):
        items = []

        if self.couch_user.can_edit_commcare_users():
            def commcare_username(request=None, couch_user=None, **context):
                if (couch_user.user_id != request.couch_user.user_id or couch_user.is_commcare_user()):
                    username = couch_user.username_in_report
                    if couch_user.is_deleted():
                        username += " (%s)" % _("Deleted")
                    return mark_safe(username)
                else:
                    return None

            from corehq.apps.users.views.mobile import EditCommCareUserView, ConfirmBillingAccountForExtraUsersView
            mobile_users_menu = [
                {'title': _('Mobile Workers'),
                 'url': reverse('commcare_users', args=[self.domain]),
                 'description': _("Create and manage users for CommCare and CloudCare."),
                 'subpages': [
                     {'title': commcare_username,
                      'urlname': EditCommCareUserView.urlname},
                     {'title': _('New Mobile Worker'),
                      'urlname': 'add_commcare_account'},
                     {'title': _('Bulk Upload'),
                      'urlname': 'upload_commcare_users'},
                     {'title': ConfirmBillingAccountForExtraUsersView.page_title,
                      'urlname': ConfirmBillingAccountForExtraUsersView.urlname},
                 ]},
                {'title': _('Groups'),
                 'url': reverse('all_groups', args=[self.domain]),
                 'description': _("Create and manage reporting and case sharing groups for Mobile Workers."),
                 'subpages': [
                     {'title': lambda **context: (
                         "%s %s" % (_("Editing"), context['group'].name)),
                      'urlname': 'group_members'},
                     {'title': _('Membership Info'),
                      'urlname': 'group_membership'}
                 ]}
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

            from corehq.apps.users.views import (EditWebUserView, EditMyAccountDomainView, ListWebUsersView)
            items.append((_('Project Users'), [
                {'title': ListWebUsersView.page_title,
                 'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
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
                 ]}
            ]))

        return items


class ProjectSettingsTab(UITab):
    title = ugettext_noop("Project Settings")
    view = 'domain_settings_default'

    @property
    def dropdown_items(self):
        return []

    @property
    def is_viewable(self):
        return self.domain and self.couch_user and self.couch_user.is_domain_admin(self.domain)

    @property
    def sidebar_items(self):
        items = []
        user_is_admin = self.couch_user.is_domain_admin(self.domain)

        project_info = []

        if user_is_admin:
            from corehq.apps.domain.views import EditBasicProjectInfoView, EditDeploymentProjectInfoView

            project_info.extend([
                {
                    'title': _(EditBasicProjectInfoView.page_title),
                    'url': reverse(EditBasicProjectInfoView.urlname, args=[self.domain])
                },
                {
                    'title': _(EditDeploymentProjectInfoView.page_title),
                    'url': reverse(EditDeploymentProjectInfoView.urlname, args=[self.domain])
                }
            ])

        from corehq.apps.domain.views import EditMyProjectSettingsView
        project_info.append({
            'title': _(EditMyProjectSettingsView.page_title),
            'url': reverse(EditMyProjectSettingsView.urlname, args=[self.domain])
        })

        can_view_orgs = (user_is_admin
                         and self.project and self.project.organization)
        if can_view_orgs:
            try:
                ensure_request_has_privilege(self._request, privileges.CROSS_PROJECT_REPORTS)
            except PermissionDenied:
                can_view_orgs = False

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
                     {'title': forward_name,
                      'urlname': 'add_repeater'}
                 ]}
            ])

            administration.append({
                    'title': _('Feature Previews'),
                    'url': reverse('feature_previews', args=[self.domain])
            })
            items.append((_('Project Administration'), administration))

        from corehq.apps.users.models import WebUser
        if isinstance(self.couch_user, WebUser):
            user_is_billing_admin, billing_account = BillingAccountAdmin.get_admin_status_and_account(
                self.couch_user, self.domain)
            if user_is_billing_admin or self.couch_user.is_superuser:
                from corehq.apps.domain.views import (
                    DomainSubscriptionView, EditExistingBillingAccountView,
                    DomainBillingStatementsView, ConfirmSubscriptionRenewalView,
                )
                subscription = [
                    {
                        'title': DomainSubscriptionView.page_title,
                        'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
                        'subpages': [
                            {
                                'title': ConfirmSubscriptionRenewalView.page_title,
                                'urlname': ConfirmSubscriptionRenewalView.urlname,
                                'url': reverse(ConfirmSubscriptionRenewalView.urlname, args=[self.domain]),
                            }
                        ]
                    },
                ]
                if billing_account is not None:
                    subscription.append(
                        {
                            'title':  EditExistingBillingAccountView.page_title,
                            'url': reverse(EditExistingBillingAccountView.urlname, args=[self.domain]),
                        },
                    )
                if (billing_account is not None
                    and Invoice.exists_for_domain(self.domain)
                ):
                    subscription.append(
                        {
                            'title': DomainBillingStatementsView.page_title,
                            'url': reverse(DomainBillingStatementsView.urlname, args=[self.domain]),
                        }
                    )
                items.append((_('Subscription'), subscription))

        if self.couch_user.is_superuser:
            from corehq.apps.domain.views import EditInternalDomainInfoView, EditInternalCalculationsView
            internal_admin = [{
                'title': _(EditInternalDomainInfoView.page_title),
                'url': reverse(EditInternalDomainInfoView.urlname, args=[self.domain])
            },
            {
                'title': _(EditInternalCalculationsView.page_title),
                'url': reverse(EditInternalCalculationsView.urlname, args=[self.domain])
            }]
            items.append((_('Internal Data (Dimagi Only)'), internal_admin))



        return items


class MySettingsTab(UITab):
    title = ugettext_noop("My Settings")
    view = 'default_my_settings'

    @property
    def dropdown_items(self):
        return []

    @property
    def is_viewable(self):
        return self.couch_user is not None

    @property
    def sidebar_items(self):
        from corehq.apps.settings.views import MyAccountSettingsView, MyProjectsList, ChangeMyPasswordView
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
        if self.couch_user and (not self.couch_user.is_superuser and IS_DEVELOPER.enabled(self.couch_user.username)):
            return [
                (_('Administrative Reports'), [
                    {'title': _('System Info'),
                     'url': reverse('system_info')},
                    ])]

        admin_operations = [
            {'title': _('View/Update Domain Information'),
             'url': reverse('domain_update')},
        ]

        if self.couch_user and self.couch_user.is_staff:
            admin_operations.extend([
                {'title': _('Mass Email Users'),
                 'url': reverse('mass_email')},
                {'title': _('PillowTop Errors'),
                 'url': reverse('admin_report_dispatcher', args=('pillow_errors',))},
                ])
        return [
            (_('Administrative Reports'), [
                {'title': _('Project Space List'),
                'url': reverse('admin_report_dispatcher', args=('domains',))},
                {'title': _('User List'),
                'url': reverse('admin_report_dispatcher', args=('user_list',))},
                {'title': _('Application List'),
                'url': reverse('admin_report_dispatcher', args=('app_list',))},
                {'title': _('Domain Activity Report'),
                 'url': reverse('domain_activity_report')},
                {'title': _('Message Logs Across All Domains'),
                 'url': reverse('message_log_report')},
                {'title': _('Global Statistics'),
                 'url': reverse('global_report')},
                {'title': _('CommCare Versions'),
                 'url': reverse('commcare_version_report')},
                {'title': _('Submissions & Error Statistics per Domain'),
                 'url': reverse('global_submissions_errors')},
                {'title': _('System Info'),
                 'url': reverse('system_info')},
                {'title': _('Mobile User Reports'),
                 'url': reverse('mobile_user_reports')},
                {'title': _('Loadtest Report'),
                 'url': reverse('loadtest_report')},
            ]), (_('Administrative Operations'), admin_operations)]

    @property
    def is_viewable(self):
        return self.couch_user and (self.couch_user.is_superuser or IS_DEVELOPER.enabled(self.couch_user.username))


class GlobalADMConfigTab(UITab):
    title = ugettext_noop("Global ADM Report Configuration")
    view = "corehq.apps.adm.views.default_adm_admin"
    dispatcher = ADMAdminInterfaceDispatcher

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class AccountingTab(UITab):
    title = ugettext_noop("Accounting")
    view = "accounting_default"
    dispatcher = AccountingAdminInterfaceDispatcher

    @property
    def is_viewable(self):
        roles = Role.objects.filter(slug=privileges.ACCOUNTING_ADMIN)
        if not roles:
            return False
        privilege = roles[0].instantiate({})
        try:
            return self._request.user.prbac_role.has_privilege(privilege)
        except UserRole.DoesNotExist:
            return False

    @property
    @memoized
    def sidebar_items(self):
        items = super(AccountingTab, self).sidebar_items

        if toggles.INVOICE_TRIGGER.enabled(self.couch_user.username):
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


class AnnouncementsTab(UITab):
    title = ugettext_noop("Announcements")
    view = "corehq.apps.announcements.views.default_announcement"
    dispatcher = HQAnnouncementAdminInterfaceDispatcher

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class AdminTab(UITab):
    title = ugettext_noop("Admin")
    view = "corehq.apps.hqadmin.views.default"
    subtab_classes = (
        AdminReportsTab,
        GlobalADMConfigTab,
        SMSAdminTab,
        AnnouncementsTab,
        AccountingTab,
        FeatureFlagsTab
    )

    @property
    def dropdown_items(self):
        if self.couch_user and not self.couch_user.is_superuser and (IS_DEVELOPER.enabled(self.couch_user.username)):
            return [format_submenu_context(_("System Info"), url=reverse("system_info"))]
        submenu_context = [
            format_submenu_context(_("Reports"), is_header=True),
            format_submenu_context(_("Admin Reports"), url=reverse("default_admin_report")),
            format_submenu_context(_("System Info"), url=reverse("system_info")),
            format_submenu_context(_("Management"), is_header=True),
            format_submenu_context(mark_for_escaping(_("ADM Reports & Columns")),
                url=reverse("default_adm_admin_interface")),
            format_submenu_context(mark_for_escaping(_("Commands")), url=reverse("management_commands")),
#            format_submenu_context(mark_for_escaping("HQ Announcements"),
#                url=reverse("default_announcement_admin")),
        ]
        try:
            if AccountingTab(self._request, self._current_url_name).is_viewable:
                submenu_context.append(format_submenu_context(AccountingTab.title, url=reverse('accounting_default')))
        except Exception:
            pass
        try:
            submenu_context.append(format_submenu_context(mark_for_escaping(_("Old SMS Billing")),
                url=reverse("billing_default")))
        except Exception:
            pass
        submenu_context.extend([
            format_submenu_context(_("SMS Connectivity & Billing"), url=reverse("default_sms_admin_interface")),
            format_submenu_context(_("Feature Flags"), url=reverse("toggle_list")),
            format_submenu_context(None, is_divider=True),
            format_submenu_context(_("Django Admin"), url="/admin")
        ])
        return submenu_context

    @property
    def is_viewable(self):
        return self.couch_user and (self.couch_user.is_superuser or IS_DEVELOPER.enabled(self.couch_user.username))


class ExchangeTab(UITab):
    title = ugettext_noop("Exchange")
    view = "corehq.apps.appstore.views.appstore"

    @property
    def dropdown_items(self):
        submenu_context = None
        if self.domain and self.couch_user.is_domain_admin(self.domain):
            submenu_context = [
                format_submenu_context(_("CommCare Exchange"), url=reverse("appstore")),
                format_submenu_context(_("Publish this project"),
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
        return self.org and self.couch_user and (self.couch_user.is_member_of_org(self.org) or self.couch_user.is_superuser)


class OrgReportTab(OrgTab):
    title = ugettext_noop("Reports")
    view = "corehq.apps.orgs.views.base_report"

    @property
    def dropdown_items(self):
        return [
            format_submenu_context(_("Projects Table"), url=reverse("orgs_report", args=(self.org.name,))),
            format_submenu_context(_("Form Data"), url=reverse("orgs_stats", args=(self.org.name, "forms"))),
            format_submenu_context(_("Case Data"), url=reverse("orgs_stats", args=(self.org.name, "cases"))),
            format_submenu_context(_("User Data"), url=reverse("orgs_stats", args=(self.org.name, "users"))),
        ]

class OrgSettingsTab(OrgTab):
    title = ugettext_noop("Settings")
    view = "corehq.apps.orgs.views.orgs_landing"

    @property
    def dropdown_items(self):
        return [
            format_submenu_context(_("Projects"), url=reverse("orgs_landing", args=(self.org.name,))),
            format_submenu_context(_("Teams"), url=reverse("orgs_teams", args=(self.org.name,))),
            format_submenu_context(_("Members"), url=reverse("orgs_stats", args=(self.org.name,))),
        ]
