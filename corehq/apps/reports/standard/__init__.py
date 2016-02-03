from datetime import datetime
import dateutil
from django.core.cache import cache
from django.core.urlresolvers import reverse
import operator
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.reports import util
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.users import UserTypeFilter
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.users.models import CommCareUser
from dimagi.utils.dates import DateSpan
from django.utils.translation import ugettext_noop
from dimagi.utils.decorators.memoized import memoized


class ProjectReport(GenericReportView):
    # overriding properties from GenericReportView
    section_name = ugettext_noop("Project Reports")
    base_template = 'reports/bootstrap2/base_template.html'
    dispatcher = ProjectReportDispatcher
    asynchronous = True

    @property
    def default_report_url(self):
        return reverse('reports_home', args=[self.request.project])


class CustomProjectReport(ProjectReport):
    dispatcher = CustomProjectReportDispatcher
    emailable = True

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
        return self.group_ids[0] if len(self.group_ids) else ''

    @property
    @memoized
    def group(self):
        if self.group_id:
            return Group.get(self.group_id)
        else:
            return self.groups[0] if len(self.groups) else None

    @property
    def group_ids(self):
        return filter(None, self.request.GET.getlist('group'))

    @property
    @memoized
    def groups(self):
        from corehq.apps.groups.models import Group
        if not self.group_ids or self.request.GET.get('all_groups', 'off') == 'on':
            return Group.get_reporting_groups(self.domain)
        return [Group.get(g) for g in self.group_ids]

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
                cache.set(cache_str, ids, 24*60*60)
        return ids

    @property
    @memoized
    def users(self):
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
    @memoized
    def usernames(self):
        return {user.user_id: user.username_in_report for user in self.users}

    @property
    @memoized
    def users_by_group(self):
        user_dict = {}
        for group in self.groups:
            user_dict["%s|%s" % (group.name, group._id)] = self.get_all_users_by_domain(
                group=group,
                user_filter=tuple(self.default_user_filter),
                simplified=True
            )

        return user_dict

    @property
    @memoized
    def users_by_mobile_workers(self):
        from corehq.apps.reports.util import _report_user_dict
        user_dict = {}
        for mw in self.mobile_worker_ids:
            user_dict[mw] = _report_user_dict(CommCareUser.get_by_user_id(mw))

        return user_dict

    def get_admins_and_demo_users(self, ufilters=None):
        ufilters = ufilters if ufilters is not None else ['1', '2', '3']
        users = self.get_all_users_by_domain(
            group=None,
            user_filter=tuple(HQUserType.use_filter(ufilters)),
            simplified=True
        ) if ufilters else []
        return users

    @property
    @memoized
    def admins_and_demo_users(self):
        ufilters = [uf for uf in ['1', '2', '3'] if uf in self.request.GET.getlist('ufilter')]
        users = self.get_admins_and_demo_users(ufilters)
        return users

    @property
    @memoized
    def admins_and_demo_user_ids(self):
        return [user.user_id for user in self.admins_and_demo_users]


    @property
    @memoized
    def combined_users(self):
        #todo: replace users with this and make sure it doesn't break existing reports
        all_users = [user for sublist in self.users_by_group.values() for user in sublist]
        all_users.extend([user for user in self.users_by_mobile_workers.values()])
        all_users.extend([user for user in self.admins_and_demo_users])
        return dict([(user['user_id'], user) for user in all_users]).values()

    @property
    @memoized
    def combined_user_ids(self):
        return [user.user_id for user in self.combined_users]

    @property
    @memoized
    def case_sharing_groups(self):
        return set(reduce(operator.add, [[u['group_ids'] for u in self.combined_users]]))

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
        from corehq.apps.reports.filters.select import SelectOpenCloseFilter
        return self.request_params.get(SelectOpenCloseFilter.slug, '')

    @property
    def case_group_ids(self):
        return filter(None, self.request.GET.getlist('case_group'))

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
        datespan = DateSpan.since(self.datespan_default_days, timezone=self.timezone, inclusive=self.inclusive)
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
