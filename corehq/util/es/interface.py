import abc

from django.conf import settings

from corehq.util.es.elasticsearch import bulk


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def update_index_settings(self, index, settings_dict):
        assert set(settings_dict.keys()) == {'index'}, settings_dict.keys()
        settings_dict = {
            "index": {
                key: value for key, value in settings_dict['index'].items()
                if key not in self._disallowed_index_settings
            }
        }
        return self.es.indices.put_settings(settings_dict, index=index)

    def get_doc(self, index, doc_type, doc_id):
        doc = self.es.get_source(index, doc_type, doc_id)
        doc['_id'] = doc_id
        return doc

    def get_bulk_docs(self, index, doc_type, doc_ids):
        docs = []
        results = self.es.mget(
            index=index, doc_type=doc_type, body={'ids': doc_ids}, _source=True)
        for doc_result in results['docs']:
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

    def doc_exists(self, index, doc_type, doc_id):
        return self.es.exists(index, doc_type, doc_id)

    def delete_doc(self, index, doc_type, doc_id):
        self.es.delete(index, doc_type, doc_id)

    def bulk_ops(self, actions, stats_only=False, **kwargs):
        for action in actions:
            if '_source' in action:
                action['_source'] = self._without_id_field(action['_source'])
        return bulk(self.es, actions, stats_only=stats_only, **kwargs)

    def search(self, index=None, doc_type=None, body=None, params=None, **kwargs):
        results = self.es.search(index, doc_type, body=body, params=params or {}, **kwargs)
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
    _disallowed_index_settings = (
        'max_result_window',
    )


class ElasticsearchInterface2(AbstractElasticsearchInterface):
    _disallowed_index_settings = (
        'merge.policy.merge_factor',
        'store.throttle.max_bytes_per_sec',
        'store.throttle.type',
    )


ElasticsearchInterface = {
    1: ElasticsearchInterface1,
    2: ElasticsearchInterface2,
}[settings.ELASTICSEARCH_MAJOR_VERSION]
