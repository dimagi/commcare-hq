from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from sqlagg.columns import SumColumn, SimpleColumn
from corehq.apps.callcenter.utils import MAPPING_NAME_FORMS, MAPPING_NAME_CASES
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reports.sqlreport import DatabaseColumn
from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized


class CallCenter(SqlIndicatorSet):
    """
    Assumes SQL table 'call_center' with the following columns:
    * user_id (string): the user id
    * date (date): the date of the indicator grain
    * submission_count (integer): number of forms submitted
    """
    name = 'call_center'

    @property
    def table_name(self):
        return '%s_%s' % (self.domain.name, MAPPING_NAME_FORMS)

    @property
    def filters(self):
        return ['date >= :weekago', 'date < :today']

    @property
    def filter_values(self):
        return {
            'today': date.today(),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
            '30daysago': date.today() - timedelta(days=30),
        }

    @property
    def group_by(self):
        return ['user_id']

    @property
    def columns(self):
        case_table_name = '%s_%s' % (self.domain.name, MAPPING_NAME_CASES)
        case_type_filter = "case_type != '%s'" % self.domain.call_center_config.case_type
        return [
            DatabaseColumn("case", SimpleColumn('user_id'),
                           format_fn=self.get_user_case_id,
                           sortable=False),
            DatabaseColumn('formsSubmittedInLastWeek',
                           SumColumn('sumbission_count', alias='last_week'),
                           sortable=False),
            DatabaseColumn('formsSubmittedInWeekPrior',
                           SumColumn('sumbission_count',
                                     filters=['date >= :2weekago', 'date < :weekago'],
                                     alias='week_prior'),
                           sortable=False),
            DatabaseColumn('formsSubmittedIn30days',
                           SumColumn('sumbission_count',
                                     filters=['date >= :30daysago', 'date < :today'],
                                     alias='30_days'),
                           sortable=False),
            DatabaseColumn('casesUpdatedIn30days',
                           SumColumn('case_updates',
                                     table_name=case_table_name,
                                     filters=['date >= :30daysago', 'date < :today', case_type_filter]),
                           sortable=False)
        ]

    @property
    @memoized
    def keys(self):
        results = CommCareUser.by_domain(self.domain.name)
        return [[r.get_id] for r in results]

    def get_user_case_id(self, user_id):
        try:
            case = get_case_by_domain_hq_user_id(self.domain.name, user_id)
            return case['id'] if case else 'user_%s' % user_id
        except MultipleResultsFound:
            return 'user_%s' % user_id
