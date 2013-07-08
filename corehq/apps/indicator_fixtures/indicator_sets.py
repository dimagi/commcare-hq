import sqlagg
import sqlalchemy
import settings


class IndicatorSetException(Exception):
    pass


class SqlIndicatorSet(object):
    name = ''
    table_name = None

    def __init__(self, config):
        self.config = config

    @property
    def available_columns(self):
        """
        Returns a list of Column objects
        [SumColumn('cases_updated', alias='casesUpdatedInLastWeek'), ...]

        Each column should be self contained and not refer to any other columns
        i.e. no AliasColumn
        """
        raise NotImplementedError()

    @property
    def actual_columns(self):
        return [c for c in self.available_columns if c.name in self.config['columns']]

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
    def data(self):
        group_by = [self.group_by] if self.group_by else []
        qc = sqlagg.QueryContext(self.table_name, self.filters, group_by)
        for c in self.actual_columns:
            qc.append_column(c)
        engine = sqlalchemy.create_engine(settings.SQL_REPORTING_DATABASE_URL)
        conn = engine.connect()
        try:
            data = qc.resolve(conn, self.filter_values)
        finally:
            conn.close()

        return data
