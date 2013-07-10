from datetime import date, timedelta
import sqlagg
from sqlagg.columns import SumColumn, SimpleColumn
import sqlalchemy
import settings


class IndicatorSetException(Exception):
    pass


class SqlIndicatorSet(object):
    name = ''
    table_name = None

    def __init__(self, domain, user, config=None):
        self.domain = domain
        self.user = user
        self.config = config or {}

    @property
    def columns(self):
        """
        Returns a list of Column objects
        [SumColumn('cases_updated', alias='casesUpdatedInLastWeek'), ...]

        Each column should be self contained and not refer to any other columns
        i.e. no AliasColumn
        """
        raise NotImplementedError()

    @property
    def group_by(self):
        """
        Returns then name of the column to group the data by or None.
        """
        raise NotImplementedError()

    @property
    def filters(self):
        """
        Returns a list of filter statements e.g. ["date > :enddate"]
        """
        raise NotImplementedError()

    @property
    def filter_values(self):
        """
        Return a dict mapping the filter keys to actual values e.g. {"enddate": date(2013,01,01)}
        """
        raise NotImplementedError()

    @property
    def keys(self):
        """
        The list of report keys (e.g. users) or None to just display all the data returned from the query. Each value
        in this list should be a list of the same dimension as the 'group_by' list.

        e.g.
            group_by = ['region', 'sub_region']
            keys = [['region1', 'sub1'], ['region1', 'sub2'] ... ]
        """
        return None

    @property
    def data(self):
        group_by = [self.group_by] if self.group_by else []
        qc = sqlagg.QueryContext(self.table_name, self.filters, group_by)
        for c in self.columns:
            qc.append_column(c)
        engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
        conn = engine.connect()
        try:
            data = qc.resolve(conn, self.filter_values)
        finally:
            conn.close()

        return data


class CallCenter(SqlIndicatorSet):
    """
    Assumes SQL table with the following columns:
    * case (string): the case id
    * date (date): the date of the indicator grain
    * cases_updated (integer): number of cases updated by on date
    """
    name = 'call_center'

    @property
    def table_name(self):
        return '%s_call_center' % self.domain.name

    @property
    def filters(self):
        return ['domain_name = :domain', 'date >= :weekago', 'date < :today']

    @property
    def filter_values(self):
        return {
            'domain': self.domain.name,
            'today': date.today() - timedelta(days=1),
            'weekago': date.today() - timedelta(days=7),
            '2weekago': date.today() - timedelta(days=14),
            '30daysago': date.today() - timedelta(days=30),
        }

    @property
    def group_by(self):
        return 'user_id'

    @property
    def available_columns(self):
        return [
            SumColumn('case_updates', alias='casesUpdatedInLastWeek'),
            SumColumn('case_updates',
                      filters=['date >= :2weekago', 'date < :weekago'],
                      alias='casesUpdatedInWeekPrior'),
            SumColumn('case_updates',
                      filters=['date >= :30daysago', 'date < :today'],
                      alias='casesUpdatedIn30Days'),
        ]

