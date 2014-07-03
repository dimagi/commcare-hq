from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from sqlagg.columns import SumColumn, SimpleColumn, SumWhen, CountUniqueColumn, CountColumn
from sqlagg import filters
from corehq.apps.callcenter.utils import MAPPING_NAME_CASES, MAPPING_NAME_CASE_OWNERSHIP
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings

PCI_CHILD_FORM = 'http://openrosa.org/formdesigner/85823851-3622-4E9E-9E86-401500A39354'
PCI_MOTHER_FORM = 'http://openrosa.org/formdesigner/366434ec56aba382966f77639a2414bbc3c56cbc'
AAROHI_CHILD_FORM = 'http://openrosa.org/formdesigner/09486EF6-04C8-480C-BA11-2F8887BBBADD'
AAROHI_MOTHER_FORM = 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170'

NO_CASE_TAG = 'NO CASE'
TYPE_DURATION = 'duration'
TYPE_SUM = 'sum'

TABLE_PREFIX = '%s_' % settings.CTABLE_PREFIX if hasattr(settings, 'CTABLE_PREFIX') else ''

FORMDATA_TABLE = 'sofabed_formdata'


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
