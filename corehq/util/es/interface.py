import abc
import logging
import traceback

from django.conf import settings

from corehq.util.es.elasticsearch import bulk


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def _verify_is_alias(self, index_or_alias):
        from corehq.elastic import ES_META
        if settings.ENABLE_ES_INTERFACE_LOGGING:
            logger = logging.getLogger('es_interface')
            all_es_aliases = [index_info.alias for index_info in ES_META.values()]
            if index_or_alias not in all_es_aliases:
                logger.info("Found a use case where an index is queried instead of alias")
                logger.info(traceback.format_stack())

    def update_index_settings(self, index, settings_dict):
        assert set(settings_dict.keys()) == {'index'}, settings_dict.keys()
        return self.es.indices.put_settings(settings_dict, index=index)

    def get_doc(self, index_alias, doc_type, doc_id):
        self._verify_is_alias(index_alias)
        doc = self.es.get_source(index_alias, doc_type, doc_id)
        doc['_id'] = doc_id
        return doc

    def get_bulk_docs(self, index_alias, doc_type, doc_ids):
        from corehq.elastic import ESError
        self._verify_is_alias(index_alias)
        docs = []
        results = self.es.mget(
            index=index_alias, doc_type=doc_type, body={'ids': doc_ids}, _source=True)
        for doc_result in results['docs']:
            if 'error' in doc_result:
                raise ESError(doc_result['error'].get('reason', 'error doing bulk get'))
            if doc_result['found']:
                self._fix_hit(doc_result)
                docs.append(doc_result['_source'])
        return docs

    def create_doc(self, index_alias, doc_type, doc_id, doc):
        self._verify_is_alias(index_alias)
        self.es.create(index_alias, doc_type, body=self._without_id_field(doc), id=doc_id)

    def update_doc(self, index_alias, doc_type, doc_id, doc, params=None):
        self._verify_is_alias(index_alias)
        self.es.index(index_alias, doc_type, body=self._without_id_field(doc), id=doc_id,
                      params=params or {})

    def update_doc_fields(self, index_alias, doc_type, doc_id, fields, params=None):
        self._verify_is_alias(index_alias)
        self.es.update(index_alias, doc_type, doc_id, body={"doc": self._without_id_field(fields)},
                       params=params or {})

    @staticmethod
    def _without_id_field(doc):
        # Field [_id] is a metadata field and cannot be added inside a document.
        # Use the index API request parameters.
        return {key: value for key, value in doc.items() if key != '_id'}

    def delete_doc(self, index_alias, doc_type, doc_id):
        self._verify_is_alias(index_alias)
        self.es.delete(index_alias, doc_type, doc_id)

    def bulk_ops(self, actions, stats_only=False, **kwargs):
        for action in actions:
            if '_source' in action:
                action['_source'] = self._without_id_field(action['_source'])
        ret = bulk(self.es, actions, stats_only=stats_only, **kwargs)
        return ret

    def search(self, index_alias=None, doc_type=None, body=None, params=None, **kwargs):
        self._verify_is_alias(index_alias)
        results = self.es.search(index_alias, doc_type, body=body, params=params or {}, **kwargs)
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


ElasticsearchInterface = {
    1: ElasticsearchInterface1,
    2: ElasticsearchInterface2,
}[settings.ELASTICSEARCH_MAJOR_VERSION]
