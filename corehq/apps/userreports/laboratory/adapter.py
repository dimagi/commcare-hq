from sqlalchemy.exc import IntegrityError
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

    def build_table(self):
        self.es_adapter.build_table()
        self.sql_adapter.build_table()

    def after_table_build(self):
        self.es_adapter.after_table_build()
        self.sql_adapter.after_table_build()

    def drop_table(self):
        self.es_adapter.drop_table()
        self.sql_adapter.drop_table()

    def rebuild_table_if_necessary(self):
        self.es_adapter.rebuild_table_if_necessary()
        # sql doesn't have this

    def refresh_table(self):
        self.es_adapter.refresh_table()
        self.sql_adapter.refresh_table()

    def clear_table(self):
        self.es_adapter.clear_table()
        self.sql_adapter.clear_table()

    def get_query_object(self):
        raise NotImplementedError

    def get_distinct_values(self, column, limit):
        raise NotImplementedError

    def best_effort_save(self, doc):
        indicator_rows = self.get_all_values(doc)

        try:
            self.es_adapter.save_rows(indicator_rows, doc)
        except Exception as e:
            self.es_adapter.handle_exception(doc, e)

        try:
            self.sql_adapter.save_rows(indicator_rows, doc)
        except IntegrityError:
            pass  # can be due to users messing up their tables/data so don't bother logging
        except Exception as e:
            self.sql_adapter.handle_exception(doc, e)

    def save_rows(self, rows, doc):
        self.es_adapter.save_rows(rows, doc)
        self.sql_adapter.save_rows(rows, doc)
