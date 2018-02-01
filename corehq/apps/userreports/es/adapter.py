from __future__ import absolute_import
from __future__ import unicode_literals
from copy import deepcopy
import datetime
from elasticsearch import NotFoundError, RequestError
from corehq.apps.userreports.util import get_table_name
from corehq.apps.userreports.adapter import IndicatorAdapter
from corehq.apps.es.es_query import HQESQuery
from corehq.apps.es.aggregations import MissingAggregation
from corehq.elastic import get_es_new, ESError
from corehq.util.test_utils import unit_testing_only
from dimagi.utils.decorators.memoized import memoized
from pillowtop.es_utils import (
    set_index_reindex_settings,
    set_index_normal_settings,
)
import six


# These settings tell ES to not tokenize strings
UCR_INDEX_SETTINGS = {
    "settings": {
        "number_of_replicas": 0,
    },
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

DATATYPE_MAP = {
    'date': 'date',
    'datetime': 'date',
    'string': 'string',
    'integer': 'long',
    'decimal': 'double',
    'array': 'string',
    'boolean': 'long',
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
        if isinstance(sliced_or_int, six.integer_types):
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
        # missing aggregation can be removed on upgrade to ES 2.0
        missing_agg_name = column + '_missing'
        query = self.es.terms_aggregation(column, column, size=size, sort_field="_term").size(0)
        query = query.aggregation(MissingAggregation(missing_agg_name, column))
        results = query.run()
        missing_result = getattr(results.aggregations, missing_agg_name).result
        result = getattr(results.aggregations, column).keys
        if missing_result['doc_count'] > 0:
            result.append(None)
        return result


class IndicatorESAdapter(IndicatorAdapter):

    def __init__(self, config):
        super(IndicatorESAdapter, self).__init__(config)
        self.es = get_es_new()
        self.table_name = get_table_name(config.domain, config.table_id).lower()

    def rebuild_table(self):
        self.drop_table()
        self.build_table()

    def build_table(self):
        try:
            self.es.indices.create(index=self.table_name, body=build_es_mapping(self.config))
            set_index_reindex_settings(self.es, self.table_name)
        except RequestError:
            # table already exists
            pass

    def after_table_build(self):
        set_index_normal_settings(self.es, self.table_name)

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

    @unit_testing_only
    def clear_table(self):
        self.rebuild_table()

    def get_query_object(self):
        return ESAlchemy(self.table_name, self.config)

    def get_distinct_values(self, column, limit):
        query = self.get_query_object()
        too_many_values = False

        try:
            distinct_values = query.distinct_values(column, limit + 1)
        except ESError:
            # table doesn't exist
            return [], False

        if len(distinct_values) > limit:
            distinct_values = distinct_values[:limit]
            too_many_values = True

        return distinct_values, too_many_values

    def _best_effort_save_rows(self, rows, doc):
        try:
            self._save_rows(rows, doc)
        except Exception as e:
            self.handle_exception(doc, e)

    def _save_rows(self, rows, doc):
        if not rows:
            return

        es = get_es_new()
        for row in rows:
            primary_key_values = [str(i.value) for i in row if i.column.is_primary_key]
            all_values = {i.column.database_column_name: i.value for i in row}
            es.index(
                index=self.table_name, body=all_values,
                id=normalize_id(primary_key_values), doc_type="indicator"
            )

    def doc_exists(self, doc):
        return self.es.exists(self.table_name, 'indicator', doc['_id'])

    def delete(self, doc):
        try:
            self.es.delete(index=self.table_name, doc_type='indicator', id=doc['_id'])
        except NotFoundError:
            pass


def build_es_mapping(data_source_config):
    properties = {}
    for indicator in data_source_config.configured_indicators:
        datatype = indicator.get('type')
        if datatype not in DATATYPE_MAP:
            datatype = indicator.get('datatype', 'string')
        properties[indicator['column_id']] = {
            "type": DATATYPE_MAP[datatype],
        }
        if datatype == 'string':
            properties[indicator['column_id']]['index'] = 'not_analyzed'
    mapping = deepcopy(UCR_INDEX_SETTINGS)
    mapping['settings'].update(data_source_config.get_es_index_settings()['settings'])
    mapping['mappings']['indicator']['properties'] = properties
    return mapping
