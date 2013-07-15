import logging
from datetime import date, timedelta
from couchdbkit import NoResultFound
from sqlagg.base import TableNotFoundException, ColumnNotFoundException
from sqlagg.columns import SumColumn, SimpleColumn
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn
from dimagi.utils.decorators.memoized import memoized


logger = logging.getLogger(__name__)


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

        if self.keys and self.group_by:
            for key_group in self.keys:
                row_key = self._row_key(key_group)
                row = data.get(row_key, None)
                if not row:
                    row = dict(zip(self.group_by, key_group))

                data[row_key] = dict([(c.view.name, self._or_no_value(c.get_value(row))) for c in self.columns])
        elif self.group_by:
            for k, v in data.items():
                data[k] = dict([(c.view.name, self._or_no_value(c.get_value(v))) for c in self.columns])
        else:
            data = dict([(c.view.name, self._or_no_value(c.get_value(data))) for c in self.columns])

        return data

    def _row_key(self, key_group):
        if len(self.group_by) == 1:
            return key_group[0]
        elif len(self.group_by) > 1:
            return tuple(key_group)

    def _or_no_value(self, value):
        return value if value is not None else self.no_value


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
        return '%s_call_center' % self.domain.name

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
        key = ['open type', self.domain.name, self.domain.call_center_config.case_type]
        cases = CommCareCase.view('case/all_cases',
            startkey=key,
            endkey=key + [{}],
            reduce=False,
            include_docs=False).all()
        return [[c['id']] for c in cases]

    def get_user_case_id(self, user_id):
        try:
            case = CommCareCase.view('hqcase/by_domain_hq_user_id',
                key=[self.domain.name, user_id],
                reduce=False,
                include_docs=False).one()
            return case['id'] if case else user_id
        except NoResultFound:
            return user_id
