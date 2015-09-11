from collections import defaultdict
from datetime import timedelta, datetime
import functools
from django.core.cache import cache
from django.db.models.aggregates import Count, Avg
from django.db.models.query_utils import Q
from corehq.apps.callcenter.models import CallCenterIndicatorConfig
from corehq.apps.hqcase.dbaccessors import get_case_types_for_domain
from dimagi.ext.jsonobject import JsonObject, DictProperty, StringProperty
import pytz
from corehq.apps.callcenter.utils import get_call_center_cases
from corehq.apps.groups.models import Group
from corehq.apps.sofabed.models import FormData, CaseData, CaseActionData
from dimagi.utils.decorators.memoized import memoized
import logging
from corehq.apps.callcenter.const import *

logger = logging.getLogger('callcenter')


def seconds_till_midnight(timezone):
    now_in_tz = datetime.now(timezone)
    midnight_in_tz = now_in_tz.replace(hour=23, minute=59, second=59)
    return (midnight_in_tz - now_in_tz).total_seconds()


def cache_key(user_id, date):
    return 'callcenter_{}_{}'.format(user_id, date.isoformat())


class CachedIndicators(JsonObject):
    user_id = StringProperty()
    case_id = StringProperty()
    domain = StringProperty()
    indicators = DictProperty()


class FakeQuerySet(object):
    def __init__(self, results):
        self.results = results

    def iterator(self):
        return (r for r in self.results)


class CallCenterIndicators(object):
    """
    Data source class that provides the CallCenter / Supervisor indicators for users of a domain.

    Returned data will only include data for users who are 'assigned' to the current user (passed in via
    the init method). A user is 'assigned' to the current user in one of two ways:

    1. Their 'user case' is owned by the current user.
    2. Their 'user case' is owned by a case sharing group which the current user is part of.

    The data that is generated is valid for the current day so is cached on a per user basis.
    The following process is used to figure which users we need to do queries for:

    1. Get all owner IDs for current user (user ID + group IDs)
    2. Get all CallCenter cases owned by the owners in 1. This is the full set of users that should
       be included in the final data set.
    3. Get all cached data for the users.
    4. Users who we need to calculate data for = (all users assigned to current user) - (cached users)

    See https://help.commcarehq.org/display/commcarepublic/How+to+set+up+a+Supervisor-Call+Center+Application
    for user docs.

    :param domain:          the domain object
    :param user:            the user to generate the fixture for
    :param custom_cache:    used in testing to verify caching
    :param override_date:   used in testing

    """
    no_value = 0
    name = 'call-center'

    def __init__(self, domain_name, domain_timezone, cc_case_type, user,
                 custom_cache=None, override_date=None, override_cases=None,
                 override_cache=False, indicator_config=None):
        self.domain = domain_name
        self.user = user
        self.data = defaultdict(dict)
        self.cc_case_type = cc_case_type
        self.cache = custom_cache or cache
        self.override_cases = override_cases
        self.override_cache = override_cache

        self.config = indicator_config or CallCenterIndicatorConfig.for_domain(domain_name)

        try:
            self.timezone = pytz.timezone(domain_timezone)
        except pytz.UnknownTimeZoneError:
            self.timezone = pytz.utc

        if override_date and isinstance(override_date, datetime):
            override_date = override_date.date()

        self.reference_date = override_date or datetime.now(self.timezone).date()

    @property
    @memoized
    def date_ranges(self):
        weekago = self.reference_date - timedelta(days=7)
        weekago2 = self.reference_date - timedelta(days=14)
        daysago30 = self.reference_date - timedelta(days=30)
        daysago60 = self.reference_date - timedelta(days=60)
        return {
            WEEK0: (weekago, self.reference_date),
            WEEK1: (weekago2, weekago),
            MONTH0: (daysago30, self.reference_date),
            MONTH1: (daysago60, daysago30),
        }

    def _date_filters(self, date_field, lower, upper):
        return {
            '{}__gte'.format(date_field): lower,
            '{}__lt'.format(date_field): upper,
        }

    @property
    @memoized
    def call_center_cases(self):
        if self.override_cases:
            return self.override_cases

        return get_call_center_cases(self.domain, self.cc_case_type, self.user)

    @property
    @memoized
    def user_to_case_map(self):
        return {
            case.hq_user_id: case.case_id
            for case in self.call_center_cases
            if hasattr(case, 'hq_user_id') and case.hq_user_id
        }

    @property
    @memoized
    def cached_data(self):
        """
        :return: Dictionary of user_id -> CachedIndicators
        """
        if self.override_cache:
            return {}

        keys = [cache_key(user_id, self.reference_date) for user_id in self.user_to_case_map.keys()]
        cached = self.cache.get_many(keys)
        data = {data['user_id']: CachedIndicators.wrap(data) for data in cached.values()}
        return data

    @property
    @memoized
    def users_needing_data(self):
        """
        :return: Set of user_ids for whom we need to generate data
        """
        ids = set(self.user_to_case_map.keys()) - set(self.cached_data.keys())
        return ids

    @property
    @memoized
    def owners_needing_data(self):
        """
        :return: List combining user_ids and case sharing group ids
        """
        user_to_groups = self.user_id_to_groups
        owners = set()
        for user_id in self.users_needing_data:
            owners.add(user_id)
            owners = owners.union(user_to_groups.get(user_id, set()))

        return owners

    @property
    @memoized
    def case_types(self):
        """
        :return: Set of all case types for the domain excluding the CallCenter case type.
        """
        case_types = set(get_case_types_for_domain(self.domain))
        case_types.remove(self.cc_case_type)
        return case_types

    @property
    @memoized
    def case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain)

    @property
    @memoized
    def group_to_user_ids(self):
        return {group.get_id: group.users for group in self.case_sharing_groups}

    @property
    def user_id_to_groups(self):
        mapping = defaultdict(set)
        for group in self.case_sharing_groups:
            for user_id in group.users:
                mapping[user_id].add(group.get_id)

        return mapping

    def _add_data(self, queryset, indicator_name, transformer=None):
        """
        Given a QuerySet containing values for an indicator add them to the data set.
        If any user ID's are missing from the QuerySet set the value
        of the indicator for those users to a default value (self,no_value).

        QuerySet expected to contain the following columns:
        *  user_id:  ID of the user.
        *  count:    The value of the indicator for the user.

        :param queryset:        The QuerySet containing the calculated indicator data.
        :param indicator_name:  The name of the indicator.
        :param transformer:     Function to apply to each value before adding it to the dataset.
        """
        seen_users = set()

        for row in queryset.iterator():
            user_id = row['user_id']
            val = transformer(row['count']) if transformer else row['count']
            self.data[user_id][indicator_name] = val
            seen_users.add(user_id)

        # add data for user_ids with no data
        unseen_users = self.users_needing_data - seen_users
        for user_id in unseen_users:
            self.data[user_id].setdefault(indicator_name, self.no_value)

    def _update_dataset(self, dataset, owner_id, cnt):
        """
        If the value in the 'case_owner' column of the QuerySet is a Group then attribute that
        indicator value to each user in the group (adding it to any existing value that the user has).

        :param dataset: dict mapping owner_id to count
        """
        if owner_id in self.group_to_user_ids:
            for user_id in self.group_to_user_ids[owner_id]:
                if user_id in self.users_needing_data:
                    dataset[user_id] += cnt
        else:
            dataset[owner_id] += cnt

    def _reformat_and_add(self, data_dict, indicator_name, legacy_name=None):
        rows = [dict(user_id=user, count=cnt) for user, cnt in data_dict.items()]
        self._add_data(FakeQuerySet(rows), indicator_name)
        if legacy_name:
            self._add_data(FakeQuerySet(rows), legacy_name)

    def _add_case_data_total(self, queryset, indicator_prefix, range_name, legacy_prefix=None):
        """
        Given a QuerySet containing data for case based indicators generate the 'total'
        indicators before adding them to the data set.

        QuerySet expected to contain the following columns:
        *  case_owner:  ID of the case owner - User or Group.
        *  count:       The value of the indicator for the owner and the case type.
        """
        total_data = defaultdict(lambda: 0)
        for result in queryset:
            owner = result['case_owner']
            count = result['count']
            self._update_dataset(total_data, owner, count)

        self._reformat_and_add(
            total_data,
            '{}_{}'.format(indicator_prefix, range_name),
            legacy_name='{}{}'.format(legacy_prefix, range_name.title()) if legacy_prefix else None
        )

    def _add_case_data_by_type(self, queryset, indicator_prefix, range_name, all_types=None):
        """
        Given a QuerySet containing data for case based indicators generate the 'by_case'
        indicators before adding them to the data set.

        QuerySet expected to contain the following columns:
        *  case_owner:  ID of the case owner - User or Group.
        *  type:        The case type.
        *  count:       The value of the indicator for the owner and the case type.

        Also include default values for any case_types that are missing from the QuerySet
        """
        type_data = defaultdict(lambda: defaultdict(lambda: 0))
        for result in queryset:
            owner = result['case_owner']
            count = result['count']
            case_type = result['type']
            self._update_dataset(type_data[case_type], owner, count)

        seen_types = set()
        for case_type, data in type_data.items():
            self._reformat_and_add(data, '{}_{}_{}'.format(indicator_prefix, case_type, range_name))
            seen_types.add(case_type)

        all_types = all_types or self.case_types
        # add data for case types with no data
        unseen_cases = all_types - seen_types
        for case_type in unseen_cases:
            self._add_data(FakeQuerySet([]), '{}_{}_{}'.format(indicator_prefix, case_type, range_name))

    def _case_query_opened_closed(self, opened_or_closed, values, filters, lower, upper):
        """
        Count of cases where lower <= opened_on < upper
            cases_opened_{period}
            cases_opened_{case_type}_{period}

        Count of cases where lower <= closed_on < upper
            cases_closed_{period}
            cases_closed_{case_type}_{period}
        """
        return CaseData.objects \
            .extra(select={'case_owner': '{}_by'.format(opened_or_closed)}) \
            .values(*values) \
            .filter(filters) \
            .filter(
                domain=self.domain) \
            .filter(**self._date_filters('{}_on'.format(opened_or_closed), lower, upper)) \
            .filter(**{
                '{}_by__in'.format(opened_or_closed): self.users_needing_data
            }).annotate(count=Count('case_id'))

    def _case_query_active(self, values, filters, lower, upper):
        """
        Count of cases where lower <= case_action.date < upper

        cases_active_{period}
        cases_active_{case_type}_{period}
        """
        return CaseActionData.objects \
            .extra(select={'type': 'case_type'}) \
            .values(*values) \
            .filter(filters) \
            .filter(
                domain=self.domain,
                case_owner__in=self.owners_needing_data,
                date__gte=lower,
                date__lt=upper
            ).annotate(count=Count('case', distinct=True))

    def _cases_total_query(self, values, filters, lower, upper):
        """
        Count of cases where opened_on < upper and (closed == False or closed_on >= lower)

        cases_total_{period}
        cases_total_{case_type}_{period}
        """
        return CaseData.objects \
            .values(*values) \
            .filter(filters) \
            .filter(
                case_owner__in=self.owners_needing_data,
                domain=self.domain,
                opened_on__lt=upper) \
            .filter(Q(closed=False) | Q(closed_on__gte=lower)) \
            .annotate(count=Count('case_id'))

    def add_case_data(self, query_fn, slug, indicator_config, type_column='type', legacy_prefix=None):
        include_types = indicator_config.all_types or indicator_config.types
        include_total = indicator_config.total.active
        limit_types = indicator_config.types

        q_type_exclude = {type_column: self.cc_case_type}
        if include_total and include_types and not limit_types:
            for range_name in indicator_config.total.date_ranges:
                lower, upper = self.date_ranges[range_name]
                results = query_fn(['case_owner', 'type'], ~Q(**q_type_exclude), lower, upper)
                self._add_case_data_total(results, slug, range_name, legacy_prefix=legacy_prefix)
                self._add_case_data_by_type(results, slug, range_name)
        else:
            if include_total:
                for range_name in indicator_config.total.date_ranges:
                    lower, upper = self.date_ranges[range_name]
                    total_results = query_fn(['case_owner'], ~Q(**q_type_exclude), lower, upper)
                    self._add_case_data_total(total_results, slug, range_name, legacy_prefix=legacy_prefix)

            if include_types:
                for range_name, types in indicator_config.types_by_date_range().items():
                    q_type_in = {'{}__in'.format(type_column): types}
                    lower, upper = self.date_ranges[range_name]
                    type_results = query_fn(['case_owner', 'type'], Q(**q_type_in), lower, upper)
                    self._add_case_data_by_type(type_results, slug, range_name, all_types=types)

    def add_case_total_legacy(self):
        """
        Count of cases per user that are currently open (legacy indicator).
        """
        results = CaseData.objects \
            .values('user_id') \
            .exclude(type=self.cc_case_type) \
            .filter(
                domain=self.domain,
                closed=False,
                user_id__in=self.users_needing_data) \
            .annotate(count=Count('case_id'))

        self._add_data(results, LEGACY_TOTAL_CASES)

    def add_custom_form_data(self, indicator_name, range_name, xmlns, indicator_type, lower, upper):
        """
        For specific forms add the number of forms completed during the time period (lower to upper)
        In some cases also add the average duration of the forms.
        """
        aggregation = Avg('duration') if indicator_type == TYPE_DURATION else Count('instance_id')

        def millis_to_secs(x):
            return round(x / 1000)

        transformer = millis_to_secs if indicator_type == TYPE_DURATION else None

        results = FormData.objects \
            .values('user_id') \
            .filter(
                xmlns=xmlns,
                domain=self.domain,
                user_id__in=self.users_needing_data) \
            .filter(**self._date_filters('time_end', lower, upper)) \
            .annotate(count=aggregation)

        self._add_data(
            results,
            '{}{}'.format(indicator_name, range_name.title()),
            transformer=transformer)

    def add_form_data(self, indicator_config):
        """
        Count of forms submitted by each user during the period (upper to lower)
        """
        for range_name in indicator_config.date_ranges:
            lower, upper = self.date_ranges[range_name]
            results = FormData.objects \
                .values('user_id') \
                .filter(**self._date_filters('time_end', lower, upper)) \
                .filter(
                    domain=self.domain,
                    user_id__in=self.users_needing_data
                )\
                .annotate(count=Count('instance_id'))

            self._add_data(results, '{}_{}'.format(FORMS_SUBMITTED, range_name))

            if indicator_config.include_legacy:
                #  maintained for backwards compatibility
                self._add_data(results, '{}{}'.format(LEGACY_FORMS_SUBMITTED, range_name.title()))

            if self.domain in PER_DOMAIN_FORM_INDICATORS:
                for custom in PER_DOMAIN_FORM_INDICATORS[self.domain]:
                    self.add_custom_form_data(
                        custom['slug'],
                        range_name,
                        custom['xmlns'],
                        custom['type'],
                        lower,
                        upper
                    )

    def get_data(self):
        final_data = {}
        if self.users_needing_data:
            if self.config.cases_total.active and self.config.cases_total.include_legacy:
                self.add_case_total_legacy()

            if self.config.forms_updated.active:
                self.add_form_data(self.config.forms_updated)

            if self.config.cases_total.active:
                self.add_case_data(self._cases_total_query, CASES_TOTAL, self.config.cases_total)

            if self.config.cases_opened.active:
                query_fn = functools.partial(self._case_query_opened_closed, 'opened')
                self.add_case_data(query_fn, CASES_OPENED, self.config.cases_opened)

            if self.config.cases_closed.active:
                query_fn = functools.partial(self._case_query_opened_closed, 'closed')
                self.add_case_data(query_fn, CASES_CLOSED, self.config.cases_closed)

            if self.config.cases_active.active:
                legacy_prefix = LEGACY_CASES_UPDATED if self.config.cases_active.include_legacy else None
                self.add_case_data(
                    self._case_query_active,
                    CASES_ACTIVE,
                    self.config.cases_total,
                    type_column='case_type',
                    legacy_prefix=legacy_prefix
                )

            cache_timeout = seconds_till_midnight(self.timezone)
            user_to_case_map = self.user_to_case_map
            for user_id, indicators in self.data.iteritems():
                # only include data for users that we are expecting. There may be partial
                # data for other users who are part of the same case sharing groups.
                if user_id in self.users_needing_data:
                    user_case_id = user_to_case_map[user_id]
                    if user_case_id:
                        cache_data = CachedIndicators(
                            user_id=user_id,
                            case_id=user_case_id,
                            domain=self.domain,
                            indicators=indicators
                        )
                        self.cache.set(
                            cache_key(user_id, self.reference_date),
                            cache_data.to_json(),
                            cache_timeout
                        )
                        final_data[user_case_id] = indicators

        for cache_data in self.cached_data.itervalues():
            final_data[cache_data.case_id] = cache_data.indicators

        return final_data
