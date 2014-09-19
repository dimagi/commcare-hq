from collections import defaultdict
from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from django.db.models.aggregates import Count, Avg
from django.db.models.query_utils import Q
from sqlagg.columns import SumColumn, SimpleColumn, SumWhen, CountUniqueColumn, CountColumn
from sqlagg import filters
from corehq.apps.callcenter.utils import MAPPING_NAME_CASES, MAPPING_NAME_CASE_OWNERSHIP
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id, get_callcenter_case_mapping
from corehq.apps.reports.filters.select import CaseTypeMixin
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlData, DictDataFormat, DataFormatter
from corehq.apps.sofabed.models import FormData, CaseData
from sqlagg.base import TableNotFoundException, ColumnNotFoundException
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

PCI_CHILD_FORM = 'http://openrosa.org/formdesigner/85823851-3622-4E9E-9E86-401500A39354'
PCI_MOTHER_FORM = 'http://openrosa.org/formdesigner/366434ec56aba382966f77639a2414bbc3c56cbc'
AAROHI_CHILD_FORM = 'http://openrosa.org/formdesigner/09486EF6-04C8-480C-BA11-2F8887BBBADD'
AAROHI_MOTHER_FORM = 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170'

NO_CASE_TAG = 'NO CASE'
TYPE_DURATION = 'duration'
TYPE_SUM = 'sum'

TABLE_PREFIX = '%s_' % settings.CTABLE_PREFIX if hasattr(settings, 'CTABLE_PREFIX') else ''

FORMDATA_TABLE = 'sofabed_formdata'


class IndicatorSetException(Exception):
    pass


class SqlIndicatorSet(SqlData):
    no_value = 0
    name = ''
    table_name = None

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user

    @property
    def data(self):
        try:
            data = super(SqlIndicatorSet, self).data
        except (TableNotFoundException, ColumnNotFoundException) as e:
            logger.exception(e)
            return {}

        format = DictDataFormat(self.columns, no_value=self.no_value)
        formatter = DataFormatter(format, row_filter=self.include_row)
        return formatter.format(data, keys=self.keys, group_by=self.group_by)

    def include_row(self, key, row):
        """
        Final opportunity to determine if row gets included in results.
        """
        return True


def case_table(domain):
    return '%s%s_%s' % (TABLE_PREFIX, domain, MAPPING_NAME_CASES)


def case_ownership_table(domain):
    return '%s%s_%s' % (TABLE_PREFIX, domain, MAPPING_NAME_CASE_OWNERSHIP)


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


def filters_week0(date_field):
    return [filters.GT(date_field, 'weekago'), filters.LTE(date_field, 'today')]


def filters_week1(date_field):
    return [filters.GT(date_field, '2weekago'), filters.LTE(date_field, 'weekago')]


def filters_month0(date_field):
    return [filters.GT(date_field, '30daysago'), filters.LTE(date_field, 'today')]


def filters_month1(date_field):
    return [filters.GT(date_field, '60daysago'), filters.LTE(date_field, '30daysago')]


custom_form_ranges = {
    'Week0': filters_week0('time_end'),
    'Week1': filters_week1('time_end'),
    'Month0': filters_month0('time_end'),
}


def mean_seconds(sum, count):
    if sum and count:
        return (sum / count) / 1000
    else:
        return 0


class CallCenter(SqlIndicatorSet):
    """
    Assumes SQL table 'call_center' with the following columns:
    * user_id (string): the user id
    * date (date): the date of the indicator grain
    * submission_count (integer): number of forms submitted
    """
    name = 'call-center'

    @property
    def table_name(self):
        return FORMDATA_TABLE

    @property
    def filters(self):
        return filters_week0('date')

    @property
    def filter_values(self):
        today = date.today() + timedelta(days=1)  # set to midnight of current day
        return {
            'today': today,
            'weekago': today - timedelta(days=7),
            '2weekago': today - timedelta(days=14),
            '30daysago': today - timedelta(days=30),
            '60daysago': today - timedelta(days=60),
            'ccCaseType': self.domain.call_center_config.case_type,
            'domain': self.domain.name,
            'form_doc_type': 'XFormInstance',
        }

    @property
    def group_by(self):
        return ['user_id']

    @property
    def columns(self):
        case_table_name = case_table(self.domain.name)
        case_ownership_table_name = case_ownership_table(self.domain.name)

        case_type_filters = [filters.NOTEQ('case_type', 'ccCaseType')]
        domain_filter = [filters.EQ('domain', 'domain'), filters.EQ('doc_type', 'form_doc_type')]

        columns = [
            DatabaseColumn("case",
                           SimpleColumn(
                               'user_id',
                               filters=filters_week0('time_end') + domain_filter),
                           format_fn=self.get_user_case_id,
                           sortable=False),
            DatabaseColumn('formsSubmittedWeek0',
                           CountColumn(
                               'instance_id',
                               table_name=FORMDATA_TABLE,
                               filters=filters_week0('time_end') + domain_filter,
                               alias='formsSubmittedWeek0'),
                           sortable=False),
            DatabaseColumn('formsSubmittedWeek1',
                           CountColumn(
                               'instance_id',
                               table_name=FORMDATA_TABLE,
                               filters=filters_week1('time_end') + domain_filter,
                               alias='formsSubmittedWeek1'),
                           sortable=False),
            DatabaseColumn('formsSubmittedMonth0',
                           CountColumn(
                               'instance_id',
                               table_name=FORMDATA_TABLE,
                               filters=filters_month0('time_end') + domain_filter,
                               alias='formsSubmittedMonth0'),
                           sortable=False),
            DatabaseColumn('casesUpdatedMonth0',
                           CountUniqueColumn(
                               'case_id',
                               table_name=case_table_name,
                               filters=filters_month0('date') + case_type_filters,
                               alias='casesUpdatedMonth0'),
                           sortable=False),
            DatabaseColumn('casesUpdatedMonth1',
                           CountUniqueColumn(
                               'case_id',
                               table_name=case_table_name,
                               filters=filters_month1('date') + case_type_filters,
                               alias='casesUpdatedMonth1'),
                           sortable=False),
            DatabaseColumn('totalCases',
                           SumColumn(
                               'open_cases',
                               table_name=case_ownership_table_name,
                               filters=case_type_filters,
                               alias='totalCases'),
                           sortable=False)
        ]

        columns.extend(self._get_custom_columns())

        return columns

    def _get_custom_columns(self):
        custom_indicators = PER_DOMAIN_FORM_INDICATORS.get(self.domain.name)

        if not custom_indicators:
            return

        for meta in custom_indicators:
            for slug_suffix, filters in custom_form_ranges.items():
                if meta['type'] == TYPE_SUM:
                    yield self._get_form_sum_column(meta, slug_suffix, filters)
                elif meta['type'] == TYPE_DURATION:
                    yield self._get_form_duration_column(meta, slug_suffix, filters)

    def _get_form_sum_column(self, meta, slug_suffix, filters):
        slug = '%s%s' % (meta['slug'], slug_suffix)
        agg_col = SumWhen(
            key='xmlns',
            whens={meta['xmlns']: 1},
            else_=0,
            filters=filters,
            alias=slug)
        return DatabaseColumn(slug, agg_col, sortable=False)

    def _get_form_duration_column(self, meta, slug_suffix, filters):
        slug = '%s%s' % (meta['slug'], slug_suffix)
        when = "xmlns = '%s'" % meta['xmlns']
        dur_col = SumWhen(
            whens={when: 'duration'},
            else_=0,
            filters=filters,
            alias='%s_sum' % slug)
        count_col = SumWhen(
            key='xmlns',
            whens={meta['xmlns']: 1},
            else_=0,
            filters=filters,
            alias='%s_count' % slug)
        return AggregateColumn(slug, mean_seconds, [dur_col, count_col], sortable=False, slug=slug)

    @property
    @memoized
    def keys(self):
        results = CommCareUser.by_domain(self.domain.name)
        return [[r.get_id] for r in results]

    def get_user_case_id(self, user_id):
        try:
            case = get_case_by_domain_hq_user_id(self.domain.name, user_id)
            if case:
                return case['id']
            else:
                # No case for this user so return a tag instead to enable removing this
                # row from the results
                return NO_CASE_TAG
        except MultipleResultsFound:
            return NO_CASE_TAG

    def include_row(self, key, row):
        return not row['user_id'] == NO_CASE_TAG


class FakeQuerySet(object):
    def __init__(self, results):
        self.results = results

    def iterator(self):
        return (r for r in self.results)


class CallCenterV2(object):
    no_value = 0

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user
        self.data = defaultdict(dict)
        self.cc_case_type = self.domain.call_center_config.case_type

    @property
    def date_ranges(self):
        today = date.today()
        weekago = today - timedelta(days=7)
        weekago2 = today - timedelta(days=14)
        daysago30 = today - timedelta(days=30)
        daysago60 = today - timedelta(days=60)
        return [
            ('week0', weekago, today),
            ('week1', weekago2, weekago),
            ('month0', daysago30, today),
            ('month1', daysago60, daysago30),
        ]

    def date_filter(self, date_field, lower, upper):
        return {
            '{}__gte'.format(date_field): lower,
            '{}__lte'.format(date_field): upper,
        }

    @property
    @memoized
    def user_ids(self):
        return set(CommCareUser.ids_by_domain(self.domain.name))

    @property
    @memoized
    def case_types(self):
        case_types = set(CaseTypeMixin.get_case_types(self.domain.name))
        case_types.remove(self.cc_case_type)
        return case_types

    @property
    @memoized
    def group_to_user_ids(self):
        groups = Group.get_case_sharing_groups(self.domain.name)
        return {group.get_id: group.users for group in groups}

    @property
    @memoized
    def user_to_case_map(self):
        return get_callcenter_case_mapping(self.domain.name, self.user_ids)

    def _add_data(self, queryset, indicator_name, transformer=None):
        """
        Given a QuerySet containing rows containing 'user_id' and 'count' values for an indicator
        add them to the data set. If any user ID's are missing from the QuerySet set the value
        of the indicator for those users to a default value (self,no_value).

        QuerySet expected to contain the following columns:
        *  user_id:  ID of the user.
        *  count:    The value of the indicator for the user.

        :param queryset:        The QuerySet containing the calculated indicator data.
        :param indicator_name:  The name of the indicator.
        :param user_key:        The name of the column in the QuerySet that contains the user_id.
        :param value_key:       The name of the column in the QuerySet that contains the value.
        :param transformer:     Function to apply to each value before adding it to the dataset.
        """
        seen_users = set()

        for row in queryset.iterator():
            user_case_id = self.user_to_case_map.get(row['user_id'])
            if user_case_id:
                val = transformer(row['count']) if transformer else row['count']
                self.data[user_case_id][indicator_name] = val
                seen_users.add(row['user_id'])

        # add data for user_ids with no data
        unseen_users = self.user_ids - seen_users
        for user_id in unseen_users:
            user_case_id = self.user_to_case_map.get(user_id)
            if user_case_id:
                self.data[user_case_id].setdefault(indicator_name, self.no_value)

    def _add_case_data(self, queryset, indicator_prefix, range_name, legacy_prefix=None):
        """
        Given a QuerySet containing data for case based indicators generate the 'total' and
        'by_case' indicators before adding them to the dataset.

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

    def _base_case_query(self):
        return CaseData.objects \
            .extra(select={"case_owner": "COALESCE(owner_id, sofabed_casedata.user_id)"}) \
            .values('case_owner', 'type') \
            .exclude(type=self.cc_case_type) \
            .filter(
                domain=self.domain.name,
                doc_type='CommCareCase')

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
                closed=False) \
            .annotate(count=Count('case_id'))

        self._add_data(results, 'totalCases')

    def add_cases_total_data(self, range_name, lower, upper):
        """
        Count of cases where opened_on <= upper and (closed == False or closed_on >= lower)

        cases_total_{period}
        cases_total_{case_type}_{period}
        """
        results = self._base_case_query() \
            .filter(opened_on__lte=upper) \
            .filter(Q(closed=False) | Q(closed_on__gte=lower)) \
            .annotate(count=Count('case_id'))

        self._add_case_data(results, 'cases_total', range_name)

    def add_cases_opened_data(self, range_name, lower, upper):
        """
        Count of cases where lower <= opened_on <= upper

        cases_opened_{period}
        cases_opened_{case_type}_{period}
        """
        results = self._base_case_query() \
            .filter(
                opened_on__gte=lower,
                opened_on__lte=upper
            ).annotate(count=Count('case_id'))

        self._add_case_data(results, 'cases_opened', range_name)

    def add_cases_closed_data(self, range_name, lower, upper):
        """
        Count of cases where lower <= closed_on <= upper

        cases_closed_{period}
        cases_closed_{case_type}_{period}
        """
        results = self._base_case_query() \
            .filter(
                closed_on__gte=lower,
                closed_on__lte=upper
            ).annotate(count=Count('case_id'))

        self._add_case_data(results, 'cases_closed', range_name)

    def add_cases_active_data(self, range_name, lower, upper):
        """
        Count of cases where lower <= case_action.date <= upper

        cases_active_{period}
        cases_active_{case_type}_{period}
        """
        results = self._base_case_query() \
            .filter(
                actions__date__gte=lower,
                actions__date__lte=upper
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
                doc_type='XFormInstance') \
            .filter(**self.date_filter('time_end', lower, upper)) \
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
            .values('user_id')\
            .filter(**self.date_filter('time_end', lower, upper)) \
            .filter(
                domain=self.domain.name,
                doc_type='XFormInstance'
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
        self.add_case_total_legacy()
        for range_name, lower, upper in self.date_ranges:
            self.add_form_data(range_name, lower, upper)
            self.add_cases_total_data(range_name, lower, upper)
            self.add_cases_opened_data(range_name, lower, upper)
            self.add_cases_closed_data(range_name, lower, upper)
            self.add_cases_active_data(range_name, lower, upper)

        return self.data
