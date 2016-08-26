from elasticsearch import NotFoundError
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.elastic import get_es_new
from pillowtop.es_utils import INDEX_STANDARD_SETTINGS


def normalize_id(values):
    return '-'.join(values).replace(' ', '_')


class IndicatorESAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorESAdapter, self).__init__(config)
        self.es = get_es_new()
        self.table_name = get_table_name(config.domain, config.table_id)

    def rebuild_table(self):
        self.drop_table()
        self.es.indices.create(index=self.table_name, body=INDEX_STANDARD_SETTINGS)

    def drop_table(self):
        try:
            self.es.indices.delete(index=self.table_name)
        except NotFoundError:
            # index doesn't exist yet
            pass

    def best_effort_save(self, doc):
        try:
            self.save(doc)
        except Exception as e:
            self.handle_exception(doc, e)

    def save(self, doc):
        """
        Saves the document. Should bubble up known errors.
        """
        indicator_rows = self.config.get_all_values(doc)
        if indicator_rows:
            es = get_es_new()
            for indicator_row in indicator_rows:
                primary_key_values = [i.value for i in indicator_row if i.column.is_primary_key]
                all_values = {i.column.database_column_name: i.value for i in indicator_row}
                es.index(
                    index=self.table_name, body=all_values,
                    id=normalize_id(primary_key_values), doc_type="indicator"
                )
