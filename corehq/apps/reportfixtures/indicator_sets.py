import logging
from sqlagg.base import TableNotFoundException, ColumnNotFoundException
from corehq.apps.reports.sqlreport import SqlData

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

        ret = dict()
        if self.keys and self.group_by:
            for key_group in self.keys:
                row_key = self._row_key(key_group)
                row = data.get(row_key, None)
                if not row:
                    row = dict(zip(self.group_by, key_group))

                ret[row_key] = dict([(c.view.name, self._or_no_value(c.get_value(row))) for c in self.columns])
        elif self.group_by:
            for k, v in data.items():
                ret[k] = dict([(c.view.name, self._or_no_value(c.get_value(v))) for c in self.columns])
        else:
            ret = dict([(c.view.name, self._or_no_value(c.get_value(data))) for c in self.columns])

        return ret

    def _row_key(self, key_group):
        if len(self.group_by) == 1:
            return key_group[0]
        elif len(self.group_by) > 1:
            return tuple(key_group)

    def _or_no_value(self, value):
        return value if value is not None else self.no_value
