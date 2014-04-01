from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from sqlagg.columns import SumColumn, SimpleColumn, SumWhen, CountUniqueColumn, CountColumn
from sqlagg import filters
from corehq.apps.callcenter.utils import MAPPING_NAME_FORMS, MAPPING_NAME_CASES, MAPPING_NAME_CASE_OWNERSHIP
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings

NO_CASE_TAG = 'NO CASE'
TYPE_DURATION = 'duration'
TYPE_SUM = 'sum'

TABLE_PREFIX = '%s_' % settings.CTABLE_PREFIX if hasattr(settings, 'CTABLE_PREFIX') else ''

PER_DOMAIN_FORM_INDICATORS = {
    'aarohi': [
        {'slug': 'motherForms', 'type': TYPE_SUM, 'xmlns': 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170'},
        {'slug': 'childForms', 'type': TYPE_SUM, 'xmlns': 'http://openrosa.org/formdesigner/09486EF6-04C8-480C-BA11-2F8887BBBADD'},
        {'slug': 'motherDuration', 'type': TYPE_DURATION, 'xmlns': 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170'},
    ],
    'pci-india': [
        {'slug': 'motherForms', 'type': TYPE_SUM, 'xmlns': 'http://openrosa.org/formdesigner/366434ec56aba382966f77639a2414bbc3c56cbc'},
        {'slug': 'childForms', 'type': TYPE_SUM, 'xmlns': 'http://openrosa.org/formdesigner/85823851-3622-4E9E-9E86-401500A39354'},
    ]
}

filters_week0 = [filters.GTE('date', 'weekago'), filters.LT('date', 'today')]
filters_week1 = [filters.GTE('date', '2weekago'), filters.LT('date', 'weekago')]
filters_month0 = [filters.GTE('date', '30daysago'), filters.LT('date', 'today')]
filters_month1 = [filters.GTE('date', '60daysago'), filters.LT('date', '30daysago')]
filters_ever = [filters.LT('date', 'today')]

custom_form_ranges = {
    'Week0': None,
    'Week1': filters_week1,
    'Month0': filters_month0,
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
        return '%s%s_%s' % (TABLE_PREFIX, self.domain.name, MAPPING_NAME_FORMS)

    @property
    def filters(self):
        return filters_week0

    @property
    def filter_values(self):
        return {
            'today': date.today(),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
            '30daysago': date.today() - timedelta(days=30),
            '60daysago': date.today() - timedelta(days=60),
            'ccCaseType': self.domain.call_center_config.case_type,
        }

    @property
    def group_by(self):
        return ['user_id']

    @property
    def columns(self):
        case_table_name = '%s%s_%s' % (TABLE_PREFIX, self.domain.name, MAPPING_NAME_CASES)
        case_ownership_table_name = '%s%s_%s' % (TABLE_PREFIX, self.domain.name, MAPPING_NAME_CASE_OWNERSHIP)
        case_type_filters = [filters.NOTEQ('case_type', 'ccCaseType')]

        columns = [
            DatabaseColumn("case", SimpleColumn('user_id'),
                           format_fn=self.get_user_case_id,
                           sortable=False),
            DatabaseColumn('formsSubmittedWeek0',
                           CountColumn('date', alias='formsSubmittedWeek0'),
                           sortable=False),
            DatabaseColumn('formsSubmittedWeek1',
                           CountColumn('date',
                                     filters=filters_week1,
                                     alias='formsSubmittedWeek1'),
                           sortable=False),
            DatabaseColumn('formsSubmittedMonth0',
                           CountColumn('date',
                                     filters=filters_month0,
                                     alias='formsSubmittedMonth0'),
                           sortable=False),
            DatabaseColumn('casesUpdatedMonth0',
                           CountUniqueColumn('case_id',
                                     table_name=case_table_name,
                                     filters=filters_month0 + case_type_filters,
                                     alias='casesUpdatedMonth0'),
                           sortable=False),
            DatabaseColumn('casesUpdatedMonth1',
                           CountUniqueColumn('case_id',
                                     table_name=case_table_name,
                                     filters=filters_month1 + case_type_filters,
                                     alias='casesUpdatedMonth1'),
                           sortable=False),
            DatabaseColumn('totalCases',
                           SumColumn('open_cases',
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
            whens={"xmlns = '%s'" % meta['xmlns']: 1},
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
            whens={when: 1},
            else_=0,
            filters=filters,
            alias='%s_count' % slug)
        return AggregateColumn(slug, mean_seconds, [dur_col, count_col], sortable=False)

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
