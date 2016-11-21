from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.userreports.es.adapter import IndicatorESAdapter
from corehq.apps.userreports.sql.adapter import IndicatorSqlAdapter


class IndicatorLaboratoryAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorLaboratoryAdapter, self).__init__(config)
        self.es_adapter = IndicatorESAdapter(config)
        self.sql_adapter = IndicatorSqlAdapter(config)

    def rebuild_table(self):
        self.es_adapter.rebuild_table()
        self.sql_adapter.rebuild_table()

    def drop_table(self):
        self.es_adapter.drop_table()
        self.sql_adapter.drop_table()

    def rebuild_table_if_necessary(self):
        self.es_adapter.rebuild_table_if_necessary()
        # sql doesn't have this

    def refresh_table(self):
        self.es_adapter.refresh_table()
        self.sql_adapter.refresh_table()

    def get_query_object(self):
        raise NotImplementedError

    def get_distinct_values(self, column, limit):
        raise NotImplementedError

    def best_effort_save(self, doc):
        self.es_adapter.best_effort_save(doc)
        self.sql_adapter.best_effort_save(doc)

    def save(self, doc):
        self.es_adapter.save(doc)
        self.sql_adapter.save(doc)
