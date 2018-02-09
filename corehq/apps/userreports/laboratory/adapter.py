from __future__ import absolute_import
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

    def best_effort_save(self, doc, eval_context=None):
        try:
            indicator_rows = self.get_all_values(doc, eval_context)
        except Exception as e:
            self.handle_exception(doc, e)
        else:
            self.es_adapter._best_effort_save_rows(indicator_rows, doc)
            self.sql_adapter._best_effort_save_rows(indicator_rows, doc)

    def _save_rows(self, rows, doc):
        self.es_adapter._save_rows(rows, doc)
        self.sql_adapter._save_rows(rows, doc)

    def delete(self, doc):
        self.es_adapter.delete(doc)
        self.sql_adapter.delete(doc)

    def doc_exists(self, doc):
        return self.es_adapter.doc_exists(doc) or self.sql_adapter.doc_exists(doc)
