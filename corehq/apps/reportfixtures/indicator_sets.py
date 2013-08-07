import logging
from sqlagg.base import TableNotFoundException, ColumnNotFoundException
from corehq.apps.reports.sqlreport import SqlData, DictDataFormatter

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

        return DictDataFormatter(data, self.columns, keys=self.keys,
                                 group_by=self.group_by, no_value=self.no_value,
                                 row_filter=self.include_row).format()

    def include_row(self, key, row):
        """
        Final opportunity to determine if row gets included in results.
        """
        return True
