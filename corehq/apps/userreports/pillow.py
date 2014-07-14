from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.sql import get_indicator_table, get_engine
from couchforms.models import XFormInstance
from pillowtop.listener import PythonPillow


class ConfigurableIndicatorPillow(PythonPillow):

    def __init__(self, config):
        # config should be an of IndicatorConfiguration document.
        # todo: should this be a list of configs or some other relationship?
        self.config = config
        self._table = get_indicator_table(config)

    @classmethod
    def get_sql_engine(cls):
        # todo: copy pasted from fluff - cleanup
        engine = getattr(cls, '_engine', None)
        if not engine:
            cls._engine = get_engine()
        return cls._engine

    def python_filter(self, doc):
        return self.config.filter.filter(doc)

    def change_transport(self, doc):
        indicators = self.config.get_values(doc)
        if indicators:
            connection = self.get_sql_engine().connect()
            try:
                # delete all existing rows for this doc to ensure we aren't left with stale data
                delete = self._table.delete(self._table.c.doc_id == doc['_id'])
                connection.execute(delete)

                all_values = {i.column.id: i.value for i in indicators}
                insert = self._table.insert().values(**all_values)
                connection.execute(insert)
            finally:
                connection.close()
