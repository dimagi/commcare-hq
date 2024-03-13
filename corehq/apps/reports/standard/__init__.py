import warnings
from datetime import datetime

from django.core.cache import cache
from django.urls import reverse
from django.utils.translation import gettext_noop

import dateutil
from memoized import memoized
from corehq.apps.reports.forms import EmailReportForm

from dimagi.utils.dates import DateSpan

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.dispatcher import (
    CustomProjectReportDispatcher,
    ProjectReportDispatcher,
)
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.filters.users import UserTypeFilter
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.models import HQUserType
from corehq.apps.users.models import CommCareUser
from corehq.util.timezones.conversions import ServerTime


class ProjectReport(GenericReportView):
    # overriding properties from GenericReportView
    section_name = gettext_noop("Project Reports")
    base_template = 'reports/base_template.html'
    dispatcher = ProjectReportDispatcher
    asynchronous = True

    @property
    def default_report_url(self):
        return reverse('reports_home', args=[self.request.project.name])

    @property
    def template_context(self):
        context = super().template_context
        context.update({
            'user_types': HQUserType.human_readable,
            'email_form': EmailReportForm()
        })
        return context


class CustomProjectReport(ProjectReport):
    dispatcher = CustomProjectReportDispatcher
    emailable = True
    languages = None

    @classmethod
    def get_supports_translations(cls):
        return bool(cls.languages)


class CommCareUserMemoizer(object):

    @memoized
    def by_domain(self, domain, is_active=True):
        users = CommCareUser.by_domain(domain, is_active=is_active)
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
    filter_users_field_class = UserTypeFilter
    include_inactive = False

    # set this to set the report's user ids from within the report
    # (i.e. based on a filter's return value).
    override_user_ids = None

    @property
    @memoized
    def CommCareUser(self):
        return CommCareUserMemoizer()

    @memoized
    def get_all_users_by_domain(self, group=None, user_ids=None, user_filter=None, simplified=False):
        return list(util.get_all_users_by_domain(
            domain=self.domain,
            group=group,
            user_ids=user_ids,
            user_filter=user_filter,
            simplified=simplified,
            CommCareUser=self.CommCareUser
        ))

    @property
    @memoized
    def user_filter(self):
        return self.filter_users_field_class.get_user_filter(self.request)[0]

    @property
    @memoized
    def default_user_filter(self):
        return self.filter_users_field_class.get_user_filter(None)[0]

    @property
    def group_id(self):
        return self.request.GET.get('group', '')

    @property
    @memoized
    def group(self):
        return Group.get(self.group_id) if self.group_id else None

    @property
    def individual(self):
        """
            todo: remember this: if self.individual and self.users:
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
        """
        return self.request_params.get('individual', '')

    @property
    def mobile_worker_ids(self):
        ids = self.request.GET.getlist('select_mw')
        if '_all' in ids or self.request.GET.get('all_mws', 'off') == 'on':
            cache_str = "mw_ids:%s" % self.domain
            ids = cache.get(cache_str)
            if not ids:
                cc_users = CommCareUser.by_domain(self.domain)
                if self.include_inactive:
                    cc_users += CommCareUser.by_domain(self.domain, is_active=False)
                ids = [ccu._id for ccu in cc_users]
                cache.set(cache_str, ids, 24 * 60 * 60)
        return ids

    @property
    @memoized
    def users(self):
        warnings.warn('Usage of this property is deprecated due to poor performance.', DeprecationWarning)
        if self.filter_group_name and not (self.group_id or self.individual):
            group = Group.by_name(self.domain, self.filter_group_name)
        else:
            group = self.group

        if self.override_user_ids is not None:
            user_ids = self.override_user_ids
        else:
            user_ids = [self.individual]

        return self.get_all_users_by_domain(
            group=group,
            user_ids=tuple(user_ids),
            user_filter=tuple(self.user_filter),
            simplified=True
        )

    @property
    @memoized
    def user_ids(self):
        return [user.user_id for user in self.users]

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
    def case_types(self):
        return [_f for _f in self.request.GET.getlist('case_type') if _f]

    @property
    def case_status(self):
        from corehq.apps.reports.filters.select import SelectOpenCloseFilter
        return self.request_params.get(SelectOpenCloseFilter.slug, '')

    @property
    def case_group_ids(self):
        return [_f for _f in self.request.GET.getlist('case_group') if _f]

    @property
    @memoized
    def case_groups(self):
        return [CommCareCaseGroup.get(g) for g in self.case_group_ids]

    @property
    @memoized
    def cases_by_case_group(self):
        case_ids = []
        for group in self.case_groups:
            case_ids.extend(group.cases)
        return case_ids


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
    datespan_field = 'corehq.apps.reports.filters.dates.DatespanFilter'
    datespan_default_days = 7
    datespan_max_days = None
    inclusive = True
    default_datespan_end_date_to_today = False

    _datespan = None

    @property
    def datespan(self):
        if self._datespan is None:
            datespan = self.default_datespan
            if self.request.datespan.is_valid() and not self.request.datespan.is_default:
                datespan.enddate = self.request.datespan.enddate
                datespan.startdate = self.request.datespan.startdate
                datespan.is_default = False
            elif self.request.datespan.get_validation_reason() == "You can't use dates earlier than the year 1900":
                raise BadRequestError()
            self.request.datespan = datespan
            # todo: don't update self.context here. find a better place! AGH! Sorry, sorry.
            self.context.update(dict(datespan=datespan))
            self._datespan = datespan
        return self._datespan

    @property
    def default_datespan(self):
        # DateSpan.since() will make enddate default to yesterday when it's None
        enddate = None
        if self.default_datespan_end_date_to_today:
            enddate = ServerTime(datetime.utcnow()).user_time(self.timezone).done().date()

        datespan = DateSpan.since(self.datespan_default_days, enddate=enddate, inclusive=self.inclusive,
            timezone=self.timezone)
        datespan.max_days = self.datespan_max_days
        datespan.is_default = True
        return datespan


class MonthYearMixin(object):
    """
        Similar to DatespanMixin, but works with MonthField and YearField
    """
    fields = [MonthFilter, YearFilter]

    _datespan = None

    @property
    def datespan(self):
        if self._datespan is None:
            datespan = DateSpan.from_month(self.month, self.year)
            self.request.datespan = datespan
            self.context.update(dict(datespan=datespan))
            self._datespan = datespan
        return self._datespan

    @property
    def month(self):
        if 'month' in self.request_params:
            return int(self.request_params['month'])
        else:
            return datetime.utcnow().month

    @property
    def year(self):
        if 'year' in self.request_params:
            return int(self.request_params['year'])
        else:
            return datetime.utcnow().year
