from elasticsearch import NotFoundError
from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.elastic import get_es_new


class IndicatorESAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorESAdapter, self).__init__(config)
        self.es = get_es_new()
        self.config_id = config._id

    def rebuild_table(self):
        self.drop_table()
        self.es.indices.create(index=self.config_id)

    def drop_table(self):
        try:
            self.es.indices.delete(index=self.config_id)
        except NotFoundError:
            # index doesn't exist yet
            pass

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
                es.create(index=self.config_id, body=all_values, id='-'.join(primary_key_values), doc_type="indicator")
