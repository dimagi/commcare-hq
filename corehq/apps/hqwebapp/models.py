from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe, mark_for_escaping
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.domain.utils import get_adm_enabled_domains
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.utils import get_indicator_domains

from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
    CustomProjectReportDispatcher)
from corehq.apps.adm.dispatcher import (ADMAdminInterfaceDispatcher,
    ADMSectionDispatcher)
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
from hqbilling.dispatcher import BillingInterfaceDispatcher
from corehq.apps.announcements.dispatcher import (
    HQAnnouncementAdminInterfaceDispatcher)


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
    @memoized
    def is_active(self):
        if self.subtabs and any(st.is_active for st in self.subtabs):
            return True

        request_path = self._request.get_full_path()

        if self.urls:
            return (any(request_path.startswith(url) for url in self.urls) or
                    self._current_url_name in self.subpage_url_names)

        elif self.url:
            return request_path.startswith(self.url)
        else:
            return False

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
    def is_active(self):
        # HACK. We need a more overarching way to avoid doing things this way
        if 'reports/adm' in self._request.get_full_path():
            return False

        return super(ProjectReportsTab, self).is_active

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
            {'title': 'My Saved Reports',
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
    view = "corehq.apps.reports.views.default"
    subtab_classes = (ProjectReportsTab, ADMReportsTab, IndicatorAdminTab)


class ProjectInfoTab(UITab):
    title = ugettext_noop("Project Info")
    view = "corehq.apps.appstore.views.project_info"

    @property
    def is_viewable(self):
        return self.project and self.project.is_snapshot


class ManageDataTab(UITab):
    title = ugettext_noop("Manage Data")
    view = "corehq.apps.data_interfaces.views.default"
    dispatcher = DataInterfaceDispatcher

    @property
    def is_viewable(self):
        if self.project.commtrack_enabled:
            return False

        return self.domain and self.couch_user.can_edit_data()

    @property
    @memoized
    def is_active(self):
        # hack because subpages of excel importer are at a different url
        return ('importer/excel' in self._request.get_full_path() or
                super(ManageDataTab, self).is_active)


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

                url = reverse('view_app', args=[self.domain, app_id])
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
        return (self.domain
                and (self.couch_user.can_edit_data() or self.couch_user.is_commcare_user())
                and not self.project.commconnect_enabled)


class MessagingTab(UITab):
    title = ugettext_noop("Messaging")
    view = "corehq.apps.sms.views.default"

    @property
    def is_viewable(self):
        return (self.project and not
                (self.project.is_snapshot or
                 self.couch_user.is_commcare_user()))

    @property
    def sidebar_items(self):
        from corehq.apps.reports.standard.sms import MessageLogReport
        def reminder_subtitle(form=None, **context):
            return form['nickname'].value

        def keyword_subtitle(keyword=None, **context):
            return keyword.keyword

        items = [
            (_("Messages"), [
                {'title': _('Compose SMS Message'),
                 'url': reverse('sms_compose_message', args=[self.domain])},
                {'title': _('Message Log'),
                 'url': MessageLogReport.get_url(domain=self.domain)},
                {'title': _('SMS Connectivity'),
                 'url': reverse('list_domain_backends', args=[self.domain]),
                 'subpages': [
                     {'title': _('Add Connection'),
                      'urlname': 'add_domain_backend'},
                     {'title': _('Edit Connection'),
                      'urlname': 'edit_domain_backend'},
                 ]},
            ]),
            (_("Data Collection and Reminders"), [
                {'title': _("Reminders"),
                 'url': reverse('list_reminders', args=[self.domain]),
                 'subpages': [
                     {'title': reminder_subtitle,
                      'urlname': 'edit_complex'},
                     {'title': _("New Reminder Definition"),
                      'urlname': 'add_complex_reminder_schedule'},
                 ]},

                {'title': _("Reminder Calendar"),
                 'url': reverse('scheduled_reminders', args=[self.domain])},

                {'title': _("Keywords"),
                 'url': reverse('manage_keywords', args=[self.domain]),
                 'subpages': [
                     {'title': keyword_subtitle,
                      'urlname': 'edit_keyword'},
                     {'title': _("New Keyword"),
                      'urlname': 'add_keyword'},
                 ]},
                #{'title': _("User Registration"),
                 #'url': ...},
                {'title': _("Reminders in Error"),
                 'url': reverse('reminders_in_error', args=[self.domain])},
            ])
        ]

        if self.project.survey_management_enabled:
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

        return items

    @property
    def dropdown_items(self):
        return []


class ProjectSettingsTab(UITab):
    view = "corehq.apps.settings.views.default"

    @property
    def dropdown_items(self):
        return []

    @property
    def title(self):
        if not (self.couch_user.can_edit_commcare_users() or
                self.couch_user.can_edit_web_users()):
            return _("Settings")
        return _("Settings & Users")

    @property
    def is_viewable(self):
        return self.domain and self.couch_user

    @property
    def sidebar_items(self):
        items = []
 
        if self.couch_user.can_edit_commcare_users():
            def commcare_username(request=None, couch_user=None, **context):
                if (couch_user.user_id != request.couch_user.user_id and
                    couch_user.is_commcare_user()):
                    username = couch_user.username_in_report
                    if couch_user.is_deleted():
                        username += " (%s)" % _("Deleted")
                    return mark_safe(username)
                else:
                    return None

            items.append((_('Mobile Users'), [
                {'title': _('Mobile Workers'),
                 'url': reverse('commcare_users', args=[self.domain]),
                 'subpages': [
                     {'title': commcare_username,
                      'urlname': 'commcare_user_account'},
                     {'title': _('New Mobile Worker'),
                      'urlname': 'add_commcare_account'},
                     {'title': _('Bulk Upload'),
                      'urlname': 'upload_commcare_users'},
                     {'title': _('Transfer Mobile Workers'),
                      'urlname': 'user_domain_transfer'},
                 ]},

                {'title': _('Groups'),
                 'url': reverse('all_groups', args=[self.domain]),
                 'subpages': [
                     {'title': lambda **context: (
                         "%s %s" % (_("Editing"), context['group'].name)),
                      'urlname': 'group_members'},
                     {'title': _('Membership Info'),
                      'urlname': 'group_membership'}
                 ]}
            ]))

        if self.couch_user.can_edit_web_users():
            def web_username(request=None, couch_user=None, **context):
                if (couch_user.user_id != request.couch_user.user_id and
                    not couch_user.is_commcare_user()):
                    username = couch_user.html_username()
                    if couch_user.is_deleted():
                        username += " (%s)" % _("Deleted")
                    return mark_safe(username)
                else:
                    return None

            items.append((_('CommCare HQ Users'), [
                {'title': _('Web Users'),
                 'url': reverse('web_users', args=[self.domain]),
                 'subpages': [
                     {'title': _("Invite Web User"),
                      'urlname': 'invite_web_user'},
                     {'title': web_username,
                      'urlname': 'user_account'}
                 ]}
            ]))

        items.append((_('My Account'), [
            {'title': _('My Account Settings'),
             'url': reverse('my_account', args=[self.domain])},
            {'title': _('Change My Password'),
             'url': reverse('change_my_password', args=[self.domain])}
        ]))

        if self.couch_user.is_domain_admin():
            items.append((_('CloudCare Settings'), [
                {'title': _('App Access'),
                 'url': reverse('cloudcare_app_settings',
                             args=[self.domain])}
            ]))

        if self.couch_user.can_edit_web_users():
            def forward_name(repeater_type=None, **context):
                if repeater_type == 'FormRepeater':
                    return _("Forward Forms")
                elif repeater_type == 'ShortFormRepeater':
                    return _("Forward Form Stubs")
                elif repeater_type == 'CaseRepeater':
                    return _("Forward Cases")

            administration = [
                {'title': _('Project Settings'),
                 'url': reverse('domain_project_settings',
                     args=[self.domain])},
                {'title': _('CommCare Exchange'),
                 'url': reverse('domain_snapshot_settings',
                     args=[self.domain])},
                {'title': _('Multimedia Sharing'),
                 'url': reverse('domain_manage_multimedia',
                     args=[self.domain])}
            ]

            if self.couch_user.is_superuser:
                administration.append({
                    'title': _('Internal Settings'),
                    'url': reverse('domain_internal_settings',
                        args=[self.domain])
                })

            administration.extend([
                {'title': _('Data Forwarding'),
                 'url': reverse('domain_forwarding', args=[self.domain]),
                 'subpages': [
                     {'title': forward_name,
                      'urlname': 'add_repeater'}
                 ]}
            ])
            items.append((_('Project Administration'), administration))

        if self.project.commtrack_enabled:
            items.append((_('CommTrack'), [
                {'title': _('Project Settings'),
                 'url': reverse('domain_commtrack_settings',
                     args=[self.domain])},
                {'title': _('Advanced Settings'),
                 'url': reverse('commtrack_settings_advanced',
                     args=[self.domain])},
                {'title': _('Manage Products'),
                 'url': reverse('commtrack_product_list',
                     args=[self.domain])},
                {'title': _('Manage Locations'),
                 'url': reverse('manage_locations', args=[self.domain])}
            ]))

        return items


class AdminReportsTab(UITab):
    title = ugettext_noop("Admin Reports")
    view = "corehq.apps.hqadmin.views.default"

    @property
    def sidebar_items(self):
        # todo: convert these to dispatcher-style like other reports

        admin_operations = [
            {'title': _('View/Update Domain Information'),
             'url': reverse('domain_update')},
        ]

        if self.couch_user and self.couch_user.is_staff:
            admin_operations.append(
                {'title': _('Mass Email Users'),
                 'url': reverse('mass_email')}
            )
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
            ]),
            (_('Administrative Operations'), admin_operations)
        ]

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class GlobalADMConfigTab(UITab):
    title = ugettext_noop("Global ADM Report Configuration")
    view = "corehq.apps.adm.views.default_adm_admin"
    dispatcher = ADMAdminInterfaceDispatcher

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class BillingTab(UITab):
    title = ugettext_noop("Billing")
    view = "billing_default"
    dispatcher = BillingInterfaceDispatcher

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


class SMSAdminTab(UITab):
    title = ugettext_noop("SMS Connectivity")
    view = "default_sms_admin_interface"

    @property
    def sidebar_items(self):
        return [
            (_('SMS Connectivity'), [
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
            ]),
        ]

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
        BillingTab,
        SMSAdminTab,
        AnnouncementsTab,
    )

    @property
    def dropdown_items(self):
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
            submenu_context.append(format_submenu_context(mark_for_escaping(_("Billing")),
                url=reverse("billing_default")))
        except Exception:
            pass
        submenu_context.extend([
            format_submenu_context(_("SMS Connectivity"), url=reverse("default_sms_admin_interface")),
            format_submenu_context(None, is_divider=True),
            format_submenu_context(_("Django Admin"), url="/admin")
        ])
        return submenu_context

    @property
    def is_viewable(self):
        return self.couch_user and self.couch_user.is_superuser


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
        return not self.couch_user.is_commcare_user()


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
            format_submenu_context(_("Visualize Forms"), url=reverse("orgs_stats", args=(self.org.name, "forms"))),
            format_submenu_context(_("Visualize Cases"), url=reverse("orgs_stats", args=(self.org.name, "cases"))),
            format_submenu_context(_("Visualize Users"), url=reverse("orgs_stats", args=(self.org.name, "users"))),
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
