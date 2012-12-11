from django.template.loader import render_to_string
from django.utils.safestring import mark_safe, mark_for_escaping
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

class DropdownMenuItem(object):
    title = None
    view = None
    css_id = None

    def __init__(self, request, domain):
        self.request = request
        self.domain = domain
        if self.title is None:
            raise NotImplementedError("A title is required")
        if self.view is None:
            raise NotImplementedError("A view is required")

    @property
    def menu_context(self):
        return {
            'url': self.url,
            'title': mark_for_escaping(self.title),
            'css_id': self.css_id,
            'is_active': self.is_active,
            'submenu': self.submenu_items,
        }

    @property
    def submenu_items(self):
        return []

    def _format_submenu_context(self, title, url=None, html=None,
                                is_header=False, is_divider=False):
        return {
            'title': title,
            'url': url,
            'html': html,
            'is_header': is_header,
            'is_divider': is_divider,
        }

    def _format_second_level_context(self, title, url, menu):
        return {
            'title': title,
            'url': url,
            'is_second_level': True,
            'submenu': menu,
        }

    @property
    @memoized
    def url(self):
        if self.domain:
            try:
                return reverse(self.view, args=[self.domain])
            except Exception:
                pass
        return reverse(self.view)

    @property
    def is_active(self):
        return self.request.get_full_path().startswith(self.url)

    @classmethod
    def is_viewable(cls, request, domain):
        raise NotImplementedError


class ReportsMenuItem(DropdownMenuItem):
    title = ugettext_noop("Reports")
    view = "corehq.apps.reports.views.default"
    css_id = "project_reports"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and not request.project.is_snapshot and request.couch_user.is_web_user()


class ProjectInfoMenuItem(DropdownMenuItem):
    title = ugettext_noop("Project Info")
    view = "corehq.apps.appstore.views.project_info"
    css_id = "project_info"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and request.project.is_snapshot


class ManageDataMenuItem(DropdownMenuItem):
    title = ugettext_noop("Manage Data")
    view = "corehq.apps.data_interfaces.views.default"
    css_id = "manage_data"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and request.couch_user.can_edit_data()


class ApplicationsMenuItem(DropdownMenuItem):
    title = ugettext_noop("Applications")
    view = "corehq.apps.app_manager.views.default"
    css_id = "applications"

    @property
    @memoized
    def submenu_items(self):
        # todo async refresh submenu when on the applications page and you change the application name
        key = [self.domain]
        apps = get_db().view('app_manager/applications_brief',
            reduce=False,
            startkey=key,
            endkey=key+[{}],
        ).all()
        submenu_context = []
        if not apps:
            return submenu_context

        submenu_context.append(self._format_submenu_context(_('My Applications'), is_header=True))
        for app in apps:
            app_info = app['value']
            if app_info:
                url = reverse('view_app', args=[self.domain, app_info['_id']])
                app_name = mark_safe("%s" % mark_for_escaping(app_info['name'] or '(Untitled)'))
                submenu_context.append(self._format_submenu_context(app_name, url=url))

        if self.request.couch_user.can_edit_apps():
            submenu_context.append(self._format_submenu_context(None, is_divider=True))
            newapp_options = [
                self._format_submenu_context(None, html=self._new_app_link(_('Blank Application'))),
                self._format_submenu_context(None, html=self._new_app_link(_('RemoteApp (Advanced Users Only)'),
                    is_remote=True)),
            ]
            newapp_options.append(self._format_submenu_context(_('Visit CommCare Exchange to copy existing app...'),
                url=reverse('appstore')))
            submenu_context.append(self._format_second_level_context(
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

    @classmethod
    def is_viewable(cls, request, domain):
        return (domain is not None and request.couch_user.is_web_user() and
                (request.couch_user.is_member_of(domain) or request.couch_user.is_superuser))


class CloudcareMenuItem(DropdownMenuItem):
    title = ugettext_noop("CloudCare")
    view = "corehq.apps.cloudcare.views.default"
    css_id = "cloudcare"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and request.couch_user.can_edit_data()


class MessagesMenuItem(DropdownMenuItem):
    title = ugettext_noop("Messages")
    view = "corehq.apps.sms.views.messaging"
    css_id = "messages"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and not request.project.is_snapshot


class ProjectSettingsMenuItem(DropdownMenuItem):
    view = "corehq.apps.settings.views.default"
    css_id = "project_settings"

    @property
    @memoized
    def submenu_items(self):
        return []

    @property
    def title(self):
        if not (self.request.couch_user.can_edit_commcare_users() or self.request.couch_user.can_edit_web_users()):
            return _("Settings")
        return _("Settings & Users")

    @classmethod
    def is_viewable(cls, request, domain):
        return domain is not None



class AdminReportsMenuItem(DropdownMenuItem):
    title = ugettext_noop("Admin")
    view = "corehq.apps.hqadmin.views.default"
    css_id = "admin_tab"

    @property
    @memoized
    def submenu_items(self):
        submenu_context = [
            self._format_submenu_context(_("Reports"), is_header=True),
            self._format_submenu_context(_("Admin Reports"), url=reverse("default_admin_report")),
            self._format_submenu_context(_("System Info"), url=reverse("system_info")),
            self._format_submenu_context(_("Management"), is_header=True),
            self._format_submenu_context(mark_for_escaping(_("ADM Reports & Columns")),
                url=reverse("default_adm_admin_interface")),
#            self._format_submenu_context(mark_for_escaping("HQ Announcements"),
#                url=reverse("default_announcement_admin")),
        ]
        try:
            submenu_context.append(self._format_submenu_context(mark_for_escaping(_("Billing")),
                url=reverse("billing_default")))
        except Exception:
            pass
        submenu_context.extend([
            self._format_submenu_context(None, is_divider=True),
            self._format_submenu_context(_("Django Admin"), url="/admin")
        ])
        return submenu_context

    @classmethod
    def is_viewable(cls, request, domain):
        return request.couch_user.is_superuser


class ExchangeMenuItem(DropdownMenuItem):
    title = ugettext_noop("Exchange")
    view = "corehq.apps.appstore.views.appstore"
    css_id = "exchange_tab"

    @property
    @memoized
    def submenu_items(self):
        submenu_context = None
        if self.domain and self.request.couch_user.is_domain_admin(self.domain):
            submenu_context = [
                self._format_submenu_context(_("CommCare Exchange"), url=reverse("appstore")),
                self._format_submenu_context(_("Publish this project"),
                    url=reverse("domain_snapshot_settings", args=[self.domain]))
            ]
        return submenu_context

    @classmethod
    def is_viewable(cls, request, domain):
        return not getattr(request, 'couch_user', False) or not request.couch_user.is_commcare_user()

class ManageSurveysMenuItem(DropdownMenuItem):
    title = ugettext_noop("Manage Surveys")
    view = "corehq.apps.reminders.views.sample_list"
    css_id = "manage_surveys"

    @classmethod
    def is_viewable(cls, request, domain):
        return domain and request.couch_user.can_edit_data() and request.project.survey_management_enabled

