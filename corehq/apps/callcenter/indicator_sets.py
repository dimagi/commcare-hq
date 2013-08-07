from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from sqlagg.columns import SumColumn, SimpleColumn, SumWhen
from corehq.apps.callcenter.utils import MAPPING_NAME_FORMS, MAPPING_NAME_CASES
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized

NO_CASE_TAG = 'NO CASE'

CUSTOM_DOMAIN_FORMS = {
    'aarohi': {
        'mother': 'http://openrosa.org/formdesigner/6C63E53D-2F6C-4730-AA5E-BAD36B50A170',
        'child': 'http://openrosa.org/formdesigner/09486EF6-04C8-480C-BA11-2F8887BBBADD'
    },
    'pci-india': {
        'mother': 'http://openrosa.org/formdesigner/366434ec56aba382966f77639a2414bbc3c56cbc',
        'child': 'http://openrosa.org/formdesigner/85823851-3622-4E9E-9E86-401500A39354'
    }
}

filters_this_week = ['date >= :weekago', 'date < :today']
filters_last_week = ['date >= :2weekago', 'date < :weekago']
filters_this_month = ['date >= :30daysago', 'date < :today']
filters_last_month = ['date >= :60daysago', 'date < :30daysago']
filters_ever = ['date < :today']

custom_form_ranges = {
    'FormsInLastWeek': None,
    'FormsInWeekPrior': filters_last_week,
    'FormsIn30Days': filters_this_month,
}


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
        return '%s_%s' % (self.domain.name, MAPPING_NAME_FORMS)

    @property
    def filters(self):
        return filters_this_week

    @property
    def filter_values(self):
        return {
            'today': date.today(),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
            '30daysago': date.today() - timedelta(days=30),
            '60daysago': date.today() - timedelta(days=60),
        }

    @property
    def group_by(self):
        return ['user_id']

    @property
    def columns(self):
        case_table_name = '%s_%s' % (self.domain.name, MAPPING_NAME_CASES)
        case_type_filters = ["case_type != '%s'" % self.domain.call_center_config.case_type]

        columns = [
            DatabaseColumn("case", SimpleColumn('user_id'),
                           format_fn=self.get_user_case_id,
                           sortable=False),
            DatabaseColumn('formsSubmittedInLastWeek',
                           SumColumn('sumbission_count', alias='last_week'),
                           sortable=False),
            DatabaseColumn('formsSubmittedInWeekPrior',
                           SumColumn('sumbission_count',
                                     filters=filters_last_week,
                                     alias='week_prior'),
                           sortable=False),
            DatabaseColumn('formsSubmittedIn30days',
                           SumColumn('sumbission_count',
                                     filters=filters_this_month,
                                     alias='30_days'),
                           sortable=False),
            DatabaseColumn('casesUpdatedIn30days',
                           SumColumn('case_updates',
                                     table_name=case_table_name,
                                     filters=filters_this_month + case_type_filters,
                                     alias='case_30'),
                           sortable=False),
            DatabaseColumn('casesUpdatedInPev30days',
                           SumColumn('case_updates',
                                     table_name=case_table_name,
                                     filters=filters_last_month + case_type_filters,
                                     alias='case_prev_30'),
                           sortable=False),
            DatabaseColumn('totalCases',
                           SumColumn('case_updates',
                                     table_name=case_table_name,
                                     filters=filters_ever,
                                     alias='case_ever'),
                           sortable=False)
        ]

        columns.extend(self._get_custom_columns())

        return columns

    def _get_custom_columns(self):
        custom_forms = CUSTOM_DOMAIN_FORMS.get(self.domain.name)

        if not custom_forms:
            return

        for slug_prefix, xmlns in custom_forms.items():
            for slug_suffix, filters in custom_form_ranges.items():
                slug = '%s%s' % (slug_prefix, slug_suffix)
                agg_col = SumWhen(
                    whens={"xmlns = '%s'" % xmlns: 'sumbission_count'},
                    else_=0,
                    filters=filters,
                    alias=slug)
                yield DatabaseColumn(slug, agg_col, sortable=False)

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
