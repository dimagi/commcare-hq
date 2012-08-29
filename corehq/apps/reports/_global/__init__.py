import dateutil
from django.core.urlresolvers import reverse
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.fields import FilterUsersField
from corehq.apps.reports.generic import GenericReportView
from dimagi.utils.dates import DateSpan

DATE_FORMAT = "%Y-%m-%d"

class ProjectReport(GenericReportView):
    # overriding properties from GenericReportView
    section_name = "Reports"
    app_slug = 'reports'
    dispatcher = ProjectReportDispatcher
    asynchronous = True

    @property
    def default_report_url(self):
        return reverse('default_report', args=[self.request.project])

class CustomProjectReport(ProjectReport):
    dispatcher = CustomProjectReportDispatcher


class ProjectReportParametersMixin(object):
    """
        All the paramaters necessary for the project reports.
        Intended to be mixed in with a GenericReportView object.
    """
    def __getattr__(self, item):
        return super(ProjectReportParametersMixin, self).__getattribute__(item)

    _user_filter = None
    @property
    def user_filter(self):
        if self._user_filter is None:
            self._user_filter, _ = FilterUsersField.get_user_filter(self.request)
        return self._user_filter

    _group_name = None
    @property
    def group_name(self):
        if self._group_name is None:
            self._group_name = self.request_params.get('group', '')
        return self._group_name

    _group = None
    @property
    def group(self):
        if self._group is None:
            self._group = Group.by_name(self.domain, self.group_name)
        return self._group

    _individual = None
    @property
    def individual(self):
        """
            todo: remember this: if self.individual and self.users:
            self.name = "%s for %s" % (self.name, self.users[0].get('raw_username'))
        """
        if self._individual is None:
            self._individual = self.request_params.get('individual', '')
        return self._individual

    _users = None
    @property
    def users(self):
        """
            todo: cache this baby
        """
        if self._users is None:
            self._users = util.get_all_users_by_domain(self.domain,
                group=self.group_name, individual=self.individual, user_filter=self.user_filter, simplified=True)
        return self._users

    _user_ids = None
    @property
    def user_ids(self):
        if self._user_ids is None:
            self._user_ids = [user.get('user_id') for user in self.users]
        return self._user_ids

    _usernames = None
    @property
    def usernames(self):
        if self._usernames is None:
            self._usernames = dict([(user.get('user_id'), user.get('username_in_report')) for user in self.users])
        return self._usernames

    _history = None
    @property
    def history(self):
        if self._history is None:
            self._history = self.request_params('history')
            if self._history:
                try:
                    self._history = dateutil.parser.parse(self._history)
                except ValueError:
                    pass
        return self._history

    _case_type = None
    @property
    def case_type(self):
        if self._case_type is None:
            self._case_type = self.request_params.get('case_type', '')
        return self._case_type


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

    def __getattr__(self, item):
        return super(DatespanMixin, self).__getattribute__(item)

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
