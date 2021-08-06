import abc
import logging
import traceback

from django.conf import settings

from corehq.util.es.elasticsearch import bulk, scan


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):
    def __init__(self, es):
        self.es = es

    def get_aliases(self):
        return self.es.indices.get_aliases()

    def put_mapping(self, doc_type, mapping, index):
        return self.es.indices.put_mapping(doc_type, {doc_type: mapping}, index=index)

    def _verify_is_alias(self, index_or_alias):
        from corehq.elastic import ES_META, ESError
        from pillowtop.tests.utils import TEST_ES_ALIAS
        all_es_aliases = [index_info.alias for index_info in ES_META.values()] + [TEST_ES_ALIAS]
        if index_or_alias not in all_es_aliases:
            raise ESError(
                f"{index_or_alias} is an unknown alias, query target must be one of {all_es_aliases}")

    def update_index_settings(self, index, settings_dict):
        assert set(settings_dict.keys()) == {'index'}, settings_dict.keys()
        return self.es.indices.put_settings(settings_dict, index=index)

    def _get_source(self, index_alias, doc_type, doc_id, source_includes=None):
        kwargs = {"_source_include": source_includes} if source_includes else {}
        return self.es.get_source(index_alias, doc_type, doc_id, **kwargs)

    def doc_exists(self, index_alias, doc_id, doc_type):
        return self.es.exists(index_alias, doc_type, doc_id)

    def _mget(self, index_alias, body, doc_type):
        return self.es.mget(
            index=index_alias, doc_type=doc_type, body=body, _source=True)

    def get_doc(self, index_alias, doc_type, doc_id, source_includes=None, verify_alias=True):
        if verify_alias:
            self._verify_is_alias(index_alias)
        doc = self._get_source(index_alias, doc_type, doc_id, source_includes=source_includes)
        doc['_id'] = doc_id
        return doc

    def get_bulk_docs(self, index_alias, doc_type, doc_ids, verify_alias=True):
        from corehq.elastic import ESError
        if verify_alias:
            self._verify_is_alias(index_alias)
        docs = []
        results = self._mget(index_alias=index_alias, doc_type=doc_type, body={'ids': doc_ids})
        for doc_result in results['docs']:
            if 'error' in doc_result:
                raise ESError(doc_result['error'].get('reason', 'error doing bulk get'))
            if doc_result['found']:
                self._fix_hit(doc_result)
                docs.append(doc_result['_source'])
        return docs

    def index_doc(self, index_alias, doc_type, doc_id, doc, params=None, verify_alias=True):
        if verify_alias:
            self._verify_is_alias(index_alias)
        self.es.index(index_alias, doc_type, body=self._without_id_field(doc), id=doc_id,
                      params=params or {})

    def update_doc_fields(self, index_alias, doc_type, doc_id, fields, params=None, verify_alias=True):
        if verify_alias:
            self._verify_is_alias(index_alias)
        self.es.update(index_alias, doc_type, doc_id, body={"doc": self._without_id_field(fields)},
                       params=params or {})

    def _prepare_count_query(self, query):
        # pagination params are not required and not supported in ES count API
        query = query.copy()
        for extra in ['size', 'sort', 'from', 'to', '_source']:
            query.pop(extra, None)
        return query

    def count(self, index_alias, doc_type, query):
        query = self._prepare_count_query(query)
        return self.es.count(index=index_alias, doc_type=doc_type, body=query).get('count')

    @staticmethod
    def _without_id_field(doc):
        # Field [_id] is a metadata field and cannot be added inside a document.
        # Use the index API request parameters.
        return {key: value for key, value in doc.items() if key != '_id'}

    def delete_doc(self, index_alias, doc_type, doc_id):
        self.es.delete(index_alias, doc_type, doc_id)

    def bulk_ops(self, actions, stats_only=False, **kwargs):
        for action in actions:
            if '_source' in action:
                action['_source'] = self._without_id_field(action['_source'])
        ret = bulk(self.es, actions, stats_only=stats_only, **kwargs)
        return ret

    def search(self, index_alias=None, doc_type=None, body=None, params=None, verify_alias=True, **kwargs):
        if verify_alias:
            self._verify_is_alias(index_alias)
        results = self.es.search(index=index_alias, doc_type=doc_type, body=body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def scroll(self, scroll_id=None, body=None, params=None, **kwargs):
        results = self.es.scroll(scroll_id, body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def scan(self, index_alias, query, doc_type):
        return scan(self.es, query=query, index=index_alias, doc_type=doc_type,
                    preserve_order=True)

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

        total = results['hits']['total']
        # In ES7 total is a dict
        if isinstance(total, dict):
            results['hits']['total'] = total.get('value', 0)



class ElasticsearchInterfaceDefault(AbstractElasticsearchInterface):
    pass


ElasticsearchInterface = ElasticsearchInterfaceDefault
