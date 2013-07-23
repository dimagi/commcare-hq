from datetime import date, timedelta
from couchdbkit.exceptions import MultipleResultsFound
from sqlagg.columns import SumColumn, SimpleColumn
from casexml.apps.case.models import CommCareCase
from corehq.apps.callcenter import utils
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.reportfixtures.indicator_sets import SqlIndicatorSet
from corehq.apps.reports.sqlreport import DatabaseColumn
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
        return '%s_%s' % (self.domain.name, utils.MAPPING_NAME)

    @property
    def filters(self):
        return ['date >= :weekago', 'date < :today']

    @property
    def filter_values(self):
        return {
            'today': date.today() - timedelta(days=1),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
            '30daysago': date.today() - timedelta(days=30),
        }

    @property
    def group_by(self):
        return ['user_id']

    @property
    def columns(self):
        return [
            DatabaseColumn("case", 'user_id', SimpleColumn, format_fn=self.get_user_case_id, sortable=False),
            DatabaseColumn('formsSubmittedInLastWeek', 'sumbission_count', SumColumn,
                alias='last_week', sortable=False),
            DatabaseColumn('formsSubmittedInWeekPrior', 'sumbission_count', SumColumn,
                filters=['date >= :2weekago', 'date < :weekago'], alias='week_prior', sortable=False),
            DatabaseColumn('formsSubmittedIn30days', 'sumbission_count', SumColumn,
                filters=['date >= :30daysago', 'date < :today'], alias='30_days', sortable=False),
        ]

    @property
    @memoized
    def keys(self):
        cases = CommCareCase.get_all_cases(
            self.domain.name,
            case_type=self.domain.call_center_config.case_type,
            status='open')

        return [[c['id']] for c in cases]

    def get_user_case_id(self, user_id):
        try:
            case = get_case_by_domain_hq_user_id(self.domain.name, user_id)
            return case['id'] if case else user_id
        except MultipleResultsFound:
            return user_id
