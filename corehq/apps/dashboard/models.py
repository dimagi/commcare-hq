from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext as _
from corehq import privileges
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.views import DefaultProjectSettingsView
from corehq.apps.reports.models import ReportConfig
from corehq.apps.users.views import DefaultProjectUserSettingsView
from dimagi.utils.decorators.memoized import memoized
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege


class BaseTile(object):
    """This class defines the context and template for one of the squares
    in the returning user dashboard.
    """
    title = None
    slug = None
    ng_directive = None

    def __init__(self, domain, request, in_data=None):
        super(BaseTile, self).__init__()
        self.domain = domain
        self.couch_user = request.couch_user
        self.request = request
        self.in_data = in_data

    @property
    def is_visible(self):
        """Override this to hide tiles from the dashboard.
        :return: Boolean
        """
        return True

    @property
    def context(self):
        """This is the context that's used to initialize the angular controller.
        :return: dict
        """
        return {}

    @classmethod
    def get_init_context(cls):
        """This is the context that's used by the django template to initialize
        the tiles.
        :return: dict
        """
        return {
            'title': cls.title,
            'slug': cls.slug,
            'ng_directive': cls.ng_directive,
        }


class NgPaginatedTileProviderMixin(object):
    """A resource for serving data to the Angularjs PaginatedTileController
    for the hq.dashboard module.
    """

    @property
    def request_data(self):
        """The data generally from a GET or POST request
        :return: dict
        """
        raise NotImplementedError('request_data should return a dict')

    @property
    def limit(self):
        return self.request_data.get('limit', 5)

    @property
    def current_page(self):
        return self.request_data.get('currentPage', 1)

    @property
    def skip(self):
        return (self.current_page - 1) * self.limit

    @property
    def total(self):
        """The total number of objects being paginated over
        :return: integer
        """
        raise NotImplementedError('total must return an int')

    @property
    def pagination_context(self):
        return {
            'total': self.total,
            'limit': self.limit,
            'currentPage': self.current_page,
            'paginatedItems': self.paginated_items,
        }

    @property
    def paginated_items(self):
        return []


class BasePaginatedTile(BaseTile, NgPaginatedTileProviderMixin):
    ng_directive = 'paginate'
    default_icon = None

    @property
    def request_data(self):
        return self.in_data.get('pagination', {}) if self.in_data else {}

    @property
    def context(self):
        context = super(BasePaginatedTile, self).context
        context.update({
            'pagination': self.pagination_context,
            'default': {
                'show': self.default_icon is not None,
                'icon': self.default_icon,
                'url': self.default_url,
            },
        })
        return context

    @property
    def default_url(self):
        """ Returns the default url if the paginated list is not visible.
        :return: string
        """
        return ''

    @staticmethod
    def _fmt_item_name(name):
        if len(name) > 38:
            return "%s..." % name[0:36]
        return name


class AppsTile(BasePaginatedTile):
    title = ugettext_noop("Applications")
    slug = 'applications'

    @property
    def is_visible(self):
        return (
            self.couch_user.is_web_user() or self.couch_user.can_edit_apps()
        )

    @property
    def default_icon(self):
        if self.request.project.commtrack_enabled:
            return 'dashboard-icon-commtrack'
        return 'dashboard-icon-applications'

    @property
    def total(self):
        # todo: optimize this at some point. unfortunately applications_brief
        # doesn't have a reduce view and for now we'll avoid refactoring.
        return len(self.applications)

    @property
    @memoized
    def applications(self):
        key = [self.domain]
        return Application.get_db().view(
            'app_manager/applications_brief',
            reduce=False,
            startkey=key,
            endkey=key+[{}],
        ).all()

    @property
    def paginated_items(self):
        def _get_app_url(app):
            return (
                reverse('view_app', args=[self.domain, app['id']])
                if self.couch_user.can_edit_apps()
                else reverse('release_manager', args=[self.domain, app['id']])
            )

        apps = self.applications[self.skip:self.skip + self.limit]
        return [{
            'name': a['key'][1],
            'url': _get_app_url(a),
        } for a in apps]


class ReportsTile(BasePaginatedTile):
    title = ugettext_noop("Reports")
    slug = 'reports'
    blank_template_name = 'icon_tile.html'
    default_icon = 'dashboard-icon-report'

    @property
    def is_visible(self):
        return (self.couch_user.can_view_reports()
                or self.couch_user.get_viewable_reports())

    @property
    def total(self):
        key = ["name", self.domain, self.couch_user._id]
        results = ReportConfig.get_db().view(
            'reportconfig/configs_by_domain',
            include_docs=False,
            startkey=key,
            endkey=key+[{}],
            reduce=True,
        ).all()
        return results[0]['value'] if results else 0

    @property
    def paginated_items(self):
        reports = ReportConfig.by_domain_and_owner(
            self.domain, self.couch_user._id,
            limit=self.limit, skip=self.skip
        )

        return [{
            'name': self._fmt_item_name(r.name),
            'name_full': r.full_name,
            'description': "%(desc)s (%(date)s)" % {
                'desc': r.description,
                'date': r.date_description,
            },
            'url': r.url,
        } for r in reports]

    @property
    def default_url(self):
        return reverse('reports_home', args=[self.domain])


class BaseIconTile(BaseTile):
    ng_directive = 'icon'
    icon = None
    is_external_link = False

    @property
    def context(self):
        context = super(BaseIconTile, self).context
        context.update({
            'url': self.url,
            'icon': self.icon,
            'isExternal': self.is_external_link,
        })
        return context

    @property
    def url(self):
        raise NotImplementedError("you must implement url")


class DataTile(BaseIconTile):
    title = ugettext_noop("Data")
    slug = 'data'
    icon = 'dashboard-icon-data'

    @property
    def is_visible(self):
        return (
            self.couch_user.can_edit_data() or self.couch_user.can_export_data()
        )

    @property
    def url(self):
        return reverse('data_interfaces_default', args=[self.domain])


class UsersTile(BaseIconTile):
    title = ugettext_noop("Users")
    slug = 'users'
    icon = 'dashboard-icon-users'

    @property
    def is_visible(self):
        return (
            self.couch_user.can_edit_commcare_users()
            or self.couch_user.can_edit_web_users()
        )

    @property
    def url(self):
        return reverse(DefaultProjectUserSettingsView.urlname,
                       args=[self.domain])


class SettingsTile(BaseIconTile):
    title = ugettext_noop("Settings")
    slug = 'settings'
    icon = 'dashboard-icon-settings'

    @property
    def is_visible(self):
        return self.couch_user.is_domain_admin(self.domain)

    @property
    def url(self):
        return reverse(DefaultProjectSettingsView.urlname,
                       args=[self.domain])


class MessagingTile(BaseIconTile):
    title = ugettext_noop("Messaging")
    slug = 'messages'
    icon = 'dashboard-icon-messaging'

    @property
    def url(self):
        return reverse('sms_default',
                       args=[self.domain])

    @property
    def is_visible(self):
        return (
            (self.can_access_reminders or self.can_access_sms)
            and not self.couch_user.is_commcare_user()
            and self.couch_user.can_edit_data()
        )

    @property
    @memoized
    def can_access_sms(self):
        try:
            ensure_request_has_privilege(self.request, privileges.OUTBOUND_SMS)
        except PermissionDenied:
            return False
        return True

    @property
    @memoized
    def can_access_reminders(self):
        try:
            ensure_request_has_privilege(self.request, privileges.REMINDERS_FRAMEWORK)
            return True
        except PermissionDenied:
            return False


class ExchangeTile(BaseIconTile):
    title = ugettext_noop("Exchange")
    slug = 'exchange'
    icon = 'dashboard-icon-exchange'

    @property
    def is_visible(self):
        return self.couch_user.can_edit_apps()

    @property
    def url(self):
        return reverse('appstore')


class HelpTile(BaseIconTile):
    title = ugettext_noop("Help Site")
    slug = 'help'
    icon = 'dashboard-icon-help'
    is_external_link = True

    @property
    def url(self):
        return "http://help.commcarehq.org/"
