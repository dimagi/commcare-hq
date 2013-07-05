import sqlagg
import sqlalchemy
import settings


class SqlIndicatorSet(object):
    name = ''
    table_name = None

    @property
    def columns(self):
        """
        Returns a list of Column objects
        [SumColumn('cases_updated', alias='casesUpdatedInLastWeek'), ...]
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
