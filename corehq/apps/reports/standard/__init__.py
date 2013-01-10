import dateutil
from django.core.urlresolvers import reverse
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.adm import utils as adm_utils
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.fields import FilterUsersField
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.users.models import CommCareUser
from dimagi.utils.dates import DateSpan
from django.utils.translation import ugettext_noop
from dimagi.utils.decorators.memoized import memoized

DATE_FORMAT = "%Y-%m-%d"

class ProjectReport(GenericReportView):
    # overriding properties from GenericReportView
    section_name = ugettext_noop("Project Reports")
    app_slug = 'reports'
    dispatcher = ProjectReportDispatcher
    asynchronous = True

    @property
    def default_report_url(self):
        return reverse('reports_home', args=[self.request.project])

    @property
    def show_subsection_navigation(self):
        return adm_utils.show_adm_nav(self.domain, self.request)

    def set_announcements(self):
        if self.request.couch_user:
            util.set_report_announcements_for_user(self.request, self.request.couch_user)


class CustomProjectReport(ProjectReport):
    dispatcher = CustomProjectReportDispatcher
    emailable = True

class CommCareUserMemoizer(object):

    @memoized
    def by_domain(self, domain):
        users = CommCareUser.by_domain(domain)
        for user in users:
            # put users in the cache for get_by_user_id
            # so that function never has to touch the database
            self.get_by_user_id.get_cache(self)[(self, user.user_id)] = user
        return users

    @memoized
    def get_by_user_id(self, user_id):
        return CommCareUser.get_by_user_id(user_id)

class ProjectReportParametersMixin(object):
    """
        All the parameters necessary for the project reports.
        Intended to be mixed in with a GenericReportView object.
    """

    default_case_type = None
    filter_group_name = None

    @property
    @memoized
    def CommCareUser(self):
        return CommCareUserMemoizer()

    @memoized
    def get_all_users_by_domain(self, group=None, individual=None, user_filter=None, simplified=False):

        return list(util.get_all_users_by_domain(
            domain=self.domain,
            group=group,
            individual=individual,
            user_filter=user_filter,
            simplified=simplified,
            CommCareUser=self.CommCareUser
        ))

    @property
    @memoized
    def user_filter(self):
        return FilterUsersField.get_user_filter(self.request)[0]

    @property
    def group_id(self):
        return self.request_params.get('group', '')

    @property
    @memoized
    def group(self):
        if self.group_id:
            return Group.get(self.group_id)
        else:
            return None

    @property
    def individual(self):
        """
            todo: remember this: if self.individual and self.users:
            self.name = "%s for %s" % (self.name, self.users[0].get('raw_username'))
        """
        return self.request_params.get('individual', '')

    @property
    @memoized
    def users(self):
        if self.filter_group_name and not (self.group_id or self.individual):
            group = Group.by_name(self.domain, self.filter_group_name)
        else:
            group = self.group_id

        return self.get_all_users_by_domain(
            group=group,
            individual=self.individual,
            user_filter=tuple(self.user_filter),
            simplified=True
        )

    @property
    @memoized
    def user_ids(self):
        return [user.get('user_id') for user in self.users]

    _usernames = None
    @property
    @memoized
    def usernames(self):
        return dict([(user.get('user_id'), user.get('username_in_report')) for user in self.users])

    @property
    def history(self):
        history = self.request_params.get('history', '')
        if history:
            try:
                return dateutil.parser.parse(history)
            except ValueError:
                pass

    @property
    def case_type(self):
        return self.default_case_type or self.request_params.get('case_type', '')

    @property
    def case_status(self):
        from corehq.apps.reports.fields import SelectOpenCloseField
        return self.request_params.get(SelectOpenCloseField.slug, '')

class CouchCachedReportMixin(object):
    """
        Use this mixin for caching reports as objects in couch.
    """
    _cached_report = None
    @property
    def cached_report(self):
        if not self._cached_report:
            self._cached_report = self.fetch_cached_report()
        return self._cached_report

    def fetch_cached_report(self):
        """
            Here's where you generate your cached report.
        """
        raise NotImplementedError


class DatespanMixin(object):
    """
        Use this where you'd like to include the datespan field.
    """
    datespan_field = 'corehq.apps.reports.fields.DatespanField'
    datespan_default_days = 7

    _datespan = None
    @property
    def datespan(self):
        if self._datespan is None:
            datespan = self.default_datespan
            if self.request.datespan.is_valid() and not self.request.datespan.is_default:
                datespan.enddate = self.request.datespan.enddate
                datespan.startdate = self.request.datespan.startdate
                datespan.is_default = False
            self.request.datespan = datespan
            # todo: don't update self.context here. find a better place! AGH! Sorry, sorry.
            self.context.update(dict(datespan=datespan))
            self._datespan = datespan
        return self._datespan

    @property
    def default_datespan(self):
        datespan = DateSpan.since(self.datespan_default_days, format="%Y-%m-%d", timezone=self.timezone)
        datespan.is_default = True
        return datespan
