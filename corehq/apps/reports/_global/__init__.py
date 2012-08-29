import datetime
import dateutil
from django.core.cache import cache
from django.core.urlresolvers import reverse
import pickle
import pytz
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.fields import FilterUsersField
from corehq.apps.reports.generic import GenericReportView
from dimagi.utils.dates import DateSpan

DATE_FORMAT = "%Y-%m-%d"

def cache_report(refresh_stale=1800, cache_timeout=3600):
#    if not isinstance(cache_timeout, int):
#        raise ValueError('Cache timeout should be an int. '
#                        'It is the number of seconds until the cache expires.')
#    if not isinstance(refresh_stale, int):
#        raise ValueError('refresh_stale should be an int. '
#                         'It is the number of seconds to wait until celery regenerates the cache.')
    def cacher(func):
        def retrieve_cache(report):
            if not isinstance(report, GenericReportView):
                raise ValueError("This decorator is only for reports that are instances of GenericReportView.")
            if report._caching:
                print "CACHING"
                return func(report)

            print "ACTIVATE CACHER"
            path = report.request.META.get('PATH_INFO')
            query = report.request.META.get('QUERY_STRING')
            cache_key = "%s_%s" % (path, query)
            cached_data = None
            try:
                cached_data = cache.get(cache_key)
            except Exception as e:
                print "ERROR getting cache %s" % e
            if cached_data is not None and isinstance(cached_data, dict):
                report_context = cached_data.get('report_context', dict())
            else:
                report_context = func(report)
            from corehq.apps.reports.tasks import report_cacher
            print "SENDING TO CELERY"
            report_cacher.delay(report, func.__name__, cache_key,
                current_cache=cached_data, refresh_stale=refresh_stale, cache_timeout=cache_timeout)
            return report_context
        return retrieve_cache
    return cacher


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
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
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
            self._users = util.get_all_users_by_domain(self.domain, self.group_name, self.individual, self.user_filter)
        return self._users

    _user_ids = None
    @property
    def user_ids(self):
        if self._user_ids is None:
            self._user_ids = [user.user_id for user in self.users]
        return self._user_ids

    _usernames = None
    @property
    def usernames(self):
        if self._usernames is None:
            self._usernames = dict([(user.user_id, user.username_in_report) for user in self.users])
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
