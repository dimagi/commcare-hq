import abc

from django.conf import settings

from corehq.pillows.mappings.utils import transform_for_es7
from corehq.util.es.elasticsearch import bulk


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def put_mapping(self, doc_type, mapping, index):
        return self.es.indices.put_mapping(doc_type, {doc_type: mapping}, index=index)

    def update_index_settings(self, index, settings_dict):
        assert set(settings_dict.keys()) == {'index'}, settings_dict.keys()
        return self.es.indices.put_settings(settings_dict, index=index)

    def _get_source(self, index, doc_type, doc_id, source_includes=None):
        return self.es.get_source(index, doc_type, doc_id, source_include=source_includes)

    def get_doc(self, index, doc_type, doc_id, source_includes=None):
        doc = self._get_source(index, doc_type, doc_id, source_includes=source_includes)
        doc['_id'] = doc_id
        return doc

    def doc_exists(self, index, doc_id, doc_type):
        return self.es.exists(index, doc_type, doc_id)

    def _mget(self, index, body, doc_type):
        return self.es.mget(
            index=index, doc_type=doc_type, body=body, _source=True)

    def get_bulk_docs(self, index, doc_type, doc_ids):
        from corehq.elastic import ESError
        docs = []
        results = self._mget(index=index, doc_type=doc_type, body={'ids': doc_ids})
        for doc_result in results['docs']:
            if 'error' in doc_result:
                raise ESError(doc_result['error'].get('reason', 'error doing bulk get'))
            if doc_result['found']:
                self._fix_hit(doc_result)
                docs.append(doc_result['_source'])
        return docs

    def create_doc(self, index, doc_type, doc_id, doc):
        self.es.create(index, doc_type, body=self._without_id_field(doc), id=doc_id)

    def update_doc(self, index, doc_type, doc_id, doc, params=None):
        self.es.index(index, doc_type, body=self._without_id_field(doc), id=doc_id,
                      params=params or {})

    def update_doc_fields(self, index, doc_type, doc_id, fields, params=None):
        self.es.update(index, doc_type, doc_id, body={"doc": self._without_id_field(fields)},
                       params=params or {})

    @staticmethod
    def _without_id_field(doc):
        # Field [_id] is a metadata field and cannot be added inside a document.
        # Use the index API request parameters.
        return {key: value for key, value in doc.items() if key != '_id'}

    def delete_doc(self, index, doc_type, doc_id):
        self.es.delete(index, doc_type, doc_id)

    def bulk_ops(self, actions, stats_only=False, **kwargs):
        for action in actions:
            if '_source' in action:
                action['_source'] = self._without_id_field(action['_source'])
        return bulk(self.es, actions, stats_only=stats_only, **kwargs)

    def search(self, index=None, doc_type=None, body=None, params=None, **kwargs):
        results = self.es.search(index=index, doc_type=doc_type, body=body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def scroll(self, scroll_id=None, body=None, params=None, **kwargs):
        results = self.es.scroll(scroll_id, body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    @staticmethod
    def _fix_hit(hit):
        if '_source' in hit:
            hit['_source']['_id'] = hit['_id']

    def _fix_hits_in_results(self, results):
        try:
            hits = results['hits']['hits']
        except KeyError:
            return results
        for hit in hits:
            self._fix_hit(hit)


class ElasticsearchInterface1(AbstractElasticsearchInterface):
    pass


class ElasticsearchInterface2(AbstractElasticsearchInterface):
    pass


class ElasticsearchInterface7(AbstractElasticsearchInterface):

    def search(self, index=None, doc_type=None, body=None, params=None, **kwargs):
        results = self.es.search(index=index, body=body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def put_mapping(self, doc_type, mapping, index):
        mapping = transform_for_es7(mapping)
        return self.es.indices.put_mapping(mapping, index=index)

    def create_doc(self, index, doc_type, doc_id, doc):
        self.es.create(index, body=self._without_id_field(doc), id=doc_id)

    def doc_exists(self, index, doc_id, doc_type):
        return self.es.exists(index, doc_id)

    def _get_source(self, index, doc_type, doc_id, source_includes=None):
        return self.es.get_source(index, doc_id, _source_includes=source_includes)

    def _mget(self, index, body, doc_type):
        return self.es.mget(
            index=index, body=body, _source=True)

    def update_doc(self, index, doc_type, doc_id, doc, params=None):
        self.es.index(index, body=self._without_id_field(doc), id=doc_id,
                      params=params or {})

    def update_doc_fields(self, index, doc_type, doc_id, fields, params=None):
        self.es.update(index, doc_id, body={"doc": self._without_id_field(fields)},
                       params=params or {})

    def delete_doc(self, index, doc_type, doc_id):
        self.es.delete(index, doc_id)


ElasticsearchInterface = {
    1: ElasticsearchInterface1,
    2: ElasticsearchInterface2,
    7: ElasticsearchInterface7,
}[settings.ELASTICSEARCH_MAJOR_VERSION]
