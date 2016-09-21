import datetime
from elasticsearch import NotFoundError
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.es.es_query import HQESQuery
from corehq.elastic import get_es_new
from dimagi.utils.decorators.memoized import memoized
from pillowtop.es_utils import INDEX_STANDARD_SETTINGS


# todo have different settings for rebuilding and indexing esp. refresh_interval
# These settings tell ES to not tokenize strings
UCR_INDEX_SETTINGS = {
    "settings": INDEX_STANDARD_SETTINGS,
    "mappings": {
        "indicator": {
            "dynamic": "true",
            "dynamic_templates": [{
                "non_analyzed_string": {
                    "match": "*",
                    "match_mapping_type": "string",
                    "mapping": {
                        "type": "string",
                        "index": "not_analyzed"
                    }
                }
            }]
        }
    }
}


def normalize_id(values):
    return '-'.join(values).replace(' ', '_')


class ESAlchemyRow(object):

    def __init__(self, keys, values=None):
        self._keys = keys
        self._values = values or {}

    def __getattr__(self, item):
        return self._values.get(item, None)

    def __iter__(self):
        for key in self.keys():
            yield getattr(self, key)

    def keys(self):
        return self._keys


class ESAlchemy(object):
    def __init__(self, index_name, config):
        self.index_name = index_name
        self.config = config
        self.es = HQESQuery(index_name)

    def __getitem__(self, sliced_or_int):
        hits = self.es[sliced_or_int]
        hits = [self._hit_to_row(hit) for hit in hits]
        if isinstance(sliced_or_int, (int, long)):
            return hits[0]
        return hits

    def _hit_to_row(self, hit):
        def mapping_to_datatype(column, value):
            if not value:
                return value

            datatype = column.datatype
            if datatype == 'datetime':
                try:
                    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")
            elif datatype == 'date':
                return datetime.datetime.strptime(value, "%Y-%m-%d")
            return value

        return ESAlchemyRow(self.column_ordering, {
            col.database_column_name: mapping_to_datatype(col, hit[col.database_column_name])
            for col in self.columns
        })

    @property
    def columns(self):
        return self.config.indicators.get_columns()

    @property
    @memoized
    def column_ordering(self):
        return [col.database_column_name for col in self.columns]

    @property
    def column_descriptions(self):
        return [{"name": col} for col in self.column_ordering]

    def count(self):
        return self.es.count()

    def distinct_values(self, column, size):
        query = self.es.terms_aggregation(column, column, size=size).size(0)
        results = query.run()
        return getattr(results.aggregations, column).keys


class IndicatorESAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorESAdapter, self).__init__(config)
        self.es = get_es_new()
        self.table_name = get_table_name(config.domain, config.table_id).lower()

    def rebuild_table(self):
        self.drop_table()
        self.es.indices.create(index=self.table_name, body=UCR_INDEX_SETTINGS)

    def drop_table(self):
        try:
            self.es.indices.delete(index=self.table_name)
        except NotFoundError:
            # index doesn't exist yet
            pass

    def rebuild_table_if_necessary(self):
        if not self.es.indices.exists(index=self.table_name):
            self.rebuild_table()

    def refresh_table(self):
        self.es.indices.refresh(index=self.table_name)

    def get_query_object(self):
        return ESAlchemy(self.table_name, self.config)

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
                primary_key_values = [str(i.value) for i in indicator_row if i.column.is_primary_key]
                all_values = {i.column.database_column_name: i.value for i in indicator_row}
                es.index(
                    index=self.table_name, body=all_values,
                    id=normalize_id(primary_key_values), doc_type="indicator"
                )
