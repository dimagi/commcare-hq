from collections import defaultdict
from datetime import timedelta, datetime
from django.core.cache import cache
from django.db.models.aggregates import Count, Avg
from django.db.models.query_utils import Q
from jsonobject import JsonObject
from jsonobject.properties import DictProperty, StringProperty
import pytz
from casexml.apps.case.models import CommCareCase
from corehq.apps.groups.models import Group
from corehq.apps.reports.filters.select import CaseTypeMixin
from corehq.apps.sofabed.models import FormData, CaseData
from dimagi.utils.decorators.memoized import memoized
import logging

logger = logging.getLogger('callcenter')

PCI_CHILD_FORM = 'http://openrosa.org/formdesigner/85823851-3622-4E9E-9E86-401500A39354'
PCI_MOTHER_FORM = 'http://openrosa.org/formdesigner/366434ec56aba382966f77639a2414bbc3c56cbc'
AAROHI_CHILD_FORM = 'http://openrosa.org/formdesigner/09486EF6-04C8-480C-BA11-2F8887BBBADD'
AAROHI_MOTHER_FORM = 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170'

TYPE_DURATION = 'duration'
TYPE_SUM = 'sum'

PER_DOMAIN_FORM_INDICATORS = {
    'aarohi': [
        {'slug': 'motherForms', 'type': TYPE_SUM, 'xmlns': AAROHI_MOTHER_FORM},
        {'slug': 'childForms', 'type': TYPE_SUM, 'xmlns': AAROHI_CHILD_FORM},
        {'slug': 'motherDuration', 'type': TYPE_DURATION, 'xmlns': AAROHI_MOTHER_FORM},
    ],
    'pci-india': [
        {'slug': 'motherForms', 'type': TYPE_SUM, 'xmlns': PCI_MOTHER_FORM},
        {'slug': 'childForms', 'type': TYPE_SUM, 'xmlns': PCI_CHILD_FORM},
    ]
}


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

    See https://help.commcarehq.or/display/commcarepublic/How+to+set+up+a+Supervisor-Call+Center+Application
    for user docs.

    :param domain:          the domain object
    :param user:            the user to generate the fixture for
    :param custom_cache:    used in testing to verify caching
    :param override_date:   used in testing

    """
    no_value = 0
    name = 'call-center'

    def __init__(self, domain, user, custom_cache=None, override_date=None, override_cases=None):
        self.domain = domain
        self.user = user
        self.data = defaultdict(dict)
        self.cc_case_type = self.domain.call_center_config.case_type
        self.cache = custom_cache or cache
        self.override_cases = override_cases

        try:
            self.timezone = pytz.timezone(self.domain.default_timezone)
        except pytz.UnknownTimeZoneError:
            self.timezone = pytz.utc

        if override_date and isinstance(override_date, datetime):
            override_date = override_date.date()

        self.reference_date = override_date or datetime.now(self.timezone).date()

    @property
    def date_ranges(self):
        weekago = self.reference_date - timedelta(days=7)
        weekago2 = self.reference_date - timedelta(days=14)
        daysago30 = self.reference_date - timedelta(days=30)
        daysago60 = self.reference_date - timedelta(days=60)
        return [
            ('week0', weekago, self.reference_date),
            ('week1', weekago2, weekago),
            ('month0', daysago30, self.reference_date),
            ('month1', daysago60, daysago30),
        ]

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

        keys = [
            ["open type owner", self.domain.name, self.cc_case_type, owner_id]
            for owner_id in self.user.get_owner_ids()
        ]
        all_owned_cases = []
        for key in keys:
            cases = CommCareCase.view(
                'case/all_cases',
                startkey=key,
                endkey=key + [{}],
                reduce=False,
                include_docs=True
            ).all()

            all_owned_cases.extend(cases)

        return all_owned_cases

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
        case_types = set(CaseTypeMixin.get_case_types(self.domain.name))
        case_types.remove(self.cc_case_type)
        return case_types

    @property
    @memoized
    def case_sharing_groups(self):
        return Group.get_case_sharing_groups(self.domain.name)

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

    def _add_case_data(self, queryset, indicator_prefix, range_name, legacy_prefix=None):
        """
        Given a QuerySet containing data for case based indicators generate the 'total' and
        'by_case' indicators before adding them to the data set.

        QuerySet expected to contain the following columns:
        *  case_owner:  ID of the case owner - User or Group.
        *  type:        The case type.
        *  count:       The value of the indicator for the owner and the case type.

        If the value in the 'case_owner' column of the QuerySet is a Group then attribute that
        indicator value to each user in the group (adding it to any existing value that the user has).

        Also include default values for any case_types that are missing from the QuerySet
        """
        def _update_dataset(dataset, owner_id, cnt):
            if owner_id in self.group_to_user_ids:
                for user_id in self.group_to_user_ids[owner_id]:
                    if user_id in self.users_needing_data:
                        dataset[user_id] += cnt
            else:
                dataset[owner_id] += cnt

        total_data = defaultdict(lambda: 0)
        type_data = defaultdict(lambda: defaultdict(lambda: 0))
        for result in queryset:
            owner = result['case_owner']
            count = result['count']
            case_type = result['type']
            _update_dataset(total_data, owner, count)
            _update_dataset(type_data[case_type], owner, count)

        def _reformat_and_add(data_dict, indicator_name, legacy_name=None):
            rows = [dict(user_id=user, count=cnt) for user, cnt in data_dict.items()]
            self._add_data(FakeQuerySet(rows), indicator_name)
            if legacy_name:
                self._add_data(FakeQuerySet(rows), legacy_name)

        _reformat_and_add(
            total_data,
            '{}_{}'.format(indicator_prefix, range_name),
            legacy_name='{}{}'.format(legacy_prefix, range_name.title()) if legacy_prefix else None
        )

        seen_types = set()
        for case_type, data in type_data.items():
            _reformat_and_add(data, '{}_{}_{}'.format(indicator_prefix, case_type, range_name))
            seen_types.add(case_type)

        # add data for case types with no data
        unseen_cases = self.case_types - seen_types
        for case_type in unseen_cases:
            self._add_data(FakeQuerySet([]), '{}_{}_{}'.format(indicator_prefix, case_type, range_name))

    def _base_case_query_coalesce_owner(self):
        return CaseData.objects \
            .extra(
                select={"case_owner": "COALESCE(owner_id, sofabed_casedata.user_id)"},
                where={"COALESCE(owner_id, sofabed_casedata.user_id) in %s"},
                params=[tuple(self.owners_needing_data)]
            ) \
            .values('case_owner', 'type') \
            .exclude(type=self.cc_case_type) \
            .filter(
                domain=self.domain.name,
                doc_type='CommCareCase')

    def _case_query_opened_closed(self, opened_or_closed, lower, upper):
        return CaseData.objects \
            .extra(select={'case_owner': '{}_by'.format(opened_or_closed)}) \
            .values('case_owner', 'type') \
            .exclude(type=self.cc_case_type) \
            .filter(
                domain=self.domain.name,
                doc_type='CommCareCase') \
            .filter(**self._date_filters('{}_on'.format(opened_or_closed), lower, upper)) \
            .filter(**{
                '{}_by__in'.format(opened_or_closed): self.users_needing_data
            }).annotate(count=Count('case_id'))

    def add_case_total_legacy(self):
        """
        Count of cases per user that are currently open (legacy indicator).
        """
        results = CaseData.objects \
            .values('user_id') \
            .exclude(type=self.cc_case_type) \
            .filter(
                domain=self.domain.name,
                doc_type='CommCareCase',
                closed=False,
                user_id__in=self.users_needing_data) \
            .annotate(count=Count('case_id'))

        self._add_data(results, 'totalCases')

    def add_cases_total_data(self, range_name, lower, upper):
        """
        Count of cases where opened_on < upper and (closed == False or closed_on >= lower)

        cases_total_{period}
        cases_total_{case_type}_{period}
        """
        results = self._base_case_query_coalesce_owner() \
            .filter(opened_on__lt=upper) \
            .filter(Q(closed=False) | Q(closed_on__gte=lower)) \
            .annotate(count=Count('case_id'))

        self._add_case_data(results, 'cases_total', range_name)

    def add_cases_opened_closed_data(self, range_name, lower, upper):
        """
        Count of cases where lower <= opened_on < upper
            cases_opened_{period}
            cases_opened_{case_type}_{period}

        Count of cases where lower <= closed_on < upper
            cases_closed_{period}
            cases_closed_{case_type}_{period}
        """
        for oc in ['opened', 'closed']:
            results = self._case_query_opened_closed(oc, lower, upper)
            self._add_case_data(results, 'cases_{}'.format(oc), range_name)

    def add_cases_active_data(self, range_name, lower, upper):
        """
        Count of cases where lower <= case_action.date < upper

        cases_active_{period}
        cases_active_{case_type}_{period}
        """
        results = self._base_case_query_coalesce_owner() \
            .filter(
                actions__date__gte=lower,
                actions__date__lt=upper
            ).annotate(count=Count('case_id', distinct=True))

        self._add_case_data(results, 'cases_active', range_name, legacy_prefix='casesUpdated')

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
                domain=self.domain.name,
                doc_type='XFormInstance',
                user_id__in=self.users_needing_data) \
            .filter(**self._date_filters('time_end', lower, upper)) \
            .annotate(count=aggregation)

        self._add_data(
            results,
            '{}{}'.format(indicator_name, range_name.title()),
            transformer=transformer)

    def add_form_data(self, range_name, lower, upper):
        """
        Count of forms submitted by each user during the period (upper to lower)
        """
        results = FormData.objects \
            .values('user_id') \
            .filter(**self._date_filters('time_end', lower, upper)) \
            .filter(
                domain=self.domain.name,
                doc_type='XFormInstance',
                user_id__in=self.users_needing_data
            )\
            .annotate(count=Count('instance_id'))

        self._add_data(results, 'forms_submitted_{}'.format(range_name))
        #  maintained for backwards compatibility
        self._add_data(results, 'formsSubmitted{}'.format(range_name.title()))

        if self.domain.name in PER_DOMAIN_FORM_INDICATORS:
            for custom in PER_DOMAIN_FORM_INDICATORS[self.domain.name]:
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
            self.add_case_total_legacy()
            for range_name, lower, upper in self.date_ranges:
                self.add_form_data(range_name, lower, upper)
                self.add_cases_total_data(range_name, lower, upper)
                self.add_cases_opened_closed_data(range_name, lower, upper)
                self.add_cases_active_data(range_name, lower, upper)

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
                            domain=self.domain.name,
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
