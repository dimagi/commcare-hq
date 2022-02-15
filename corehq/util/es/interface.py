from functools import cached_property

from corehq.apps.es.client import ElasticManageAdapter
from corehq.apps.es.const import SCROLL_KEEPALIVE, SCROLL_SIZE
from corehq.apps.es.transient_util import doc_adapter_from_alias
from corehq.util.es.elasticsearch import bulk


class ElasticsearchInterface:

    SCROLL_KEEPALIVE = SCROLL_KEEPALIVE
    SCROLL_SIZE = SCROLL_SIZE

    def __init__(self, es):
        # TODO: verify that the `es` arg came from the client module and is not
        #       a real client (would indicate the caller is not compliant).
        self.es = es

    @cached_property
    def manager(self):
        # lazy-load the manage adapter only if needed
        return ElasticManageAdapter()

    def get_aliases(self):
        return self.manager.get_aliases()

    def put_mapping(self, doc_type, mapping, index):
        return self.manager.index_put_mapping(index, doc_type, mapping)

    def _verify_is_alias(self, alias):
        """Verify that an alias is one of a registered index"""
        from corehq.apps.es.registry import verify_alias
        verify_alias(alias)

    def update_index_settings_reindex(self, index):
        self.manager.index_configure_for_reindex(index)

    def update_index_settings_standard(self, index):
        self.manager.index_configure_for_standard_ops(index)

    def doc_exists(self, index_alias, doc_id, doc_type):
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        return doc_adapter.exists(doc_id)

    def get_doc(self, index_alias, doc_type, doc_id, source_includes=None):
        self._verify_is_alias(index_alias)
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        if source_includes is None:
            source_includes = []
        return doc_adapter.fetch(doc_id, source_includes=source_includes)

    def get_bulk_docs(self, index_alias, doc_type, doc_ids):
        self._verify_is_alias(index_alias)
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        return doc_adapter.fetch_many(doc_ids)

    def index_doc(self, index_alias, doc_type, doc_id, doc, params=None):
        self._verify_is_alias(index_alias)
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        if doc.get("_id", object()) != doc_id:
            doc["_id"] = doc_id
        kw = {} if params is None else params
        doc_adapter.upsert(doc, **kw)

    def update_doc_fields(self, index_alias, doc_type, doc_id, fields, params=None):
        self._verify_is_alias(index_alias)
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        kw = {} if params is None else params
        doc_adapter.update(doc_id, fields, **kw)

    def count(self, index_alias, doc_type, query):
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        return doc_adapter.count(query)

    @staticmethod
    def _without_id_field(doc):
        # Field [_id] is a metadata field and cannot be added inside a document.
        # Use the index API request parameters.
        return {key: value for key, value in doc.items() if key != '_id'}

    def delete_doc(self, index_alias, doc_type, doc_id):
        doc_adapter = self._get_doc_adapter(index_alias, doc_type)
        doc_adapter.delete(doc_id)

    def bulk_ops(self, actions, stats_only=False, **kwargs):
        for action in actions:
            if '_source' in action:
                action['_source'] = self._without_id_field(action['_source'])
        ret = bulk(self.es, actions, stats_only=stats_only, **kwargs)
        return ret

    def search(self, index_alias=None, doc_type=None, body=None, params=None, **kwargs):
        self._verify_is_alias(index_alias)
        results = self.es.search(index=index_alias, doc_type=doc_type, body=body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def scroll(self, scroll_id=None, body=None, params=None, **kwargs):
        results = self.es.scroll(scroll_id, body, params=params or {}, **kwargs)
        self._fix_hits_in_results(results)
        return results

    def iter_scroll(self, index_alias=None, doc_type=None, body=None,
                    scroll=SCROLL_KEEPALIVE, **kwargs):
        """Perform one or more scroll requests to completely exhaust a scrolling
        search context.

        Providing a query with `size` specified as well as the `size` keyword
        argument is ambiguous, and Elastic docs do not say what happens when
        `size` is provided both as a GET parameter _as well as_ part of the
        query body. Real-world observations show that the GET parameter wins,
        but to avoid ambiguity, specifying both in this function will raise a
        ValueError.

        Read before using:
        - Scroll queries are not designed for real-time user requests.
        - Using aggregations with scroll queries may yield non-aggregated
          results.
        - The most efficient way to perform a scroll request is to sort by
          `_doc`.
        - Scroll request results reflect the state of the index at the time the
          initial `search` is requested. Changes to the index after that time
          will not be reflected for the duration of the search context.
        - Open scroll search contexts can keep old index segments alive longer,
          which may require more disk space and file descriptor limits.
        - An Elasticsearch cluster has a limited number of allowed concurrent
          search contexts. Versions 2.4 and 5.6 do not specify what the default
          maximum limit is, or how to configure it. Version 7.14 specifies the
          default is 500 concurrent search contexts.
        - See: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-request-scroll.html
        """
        body = body.copy() if body else {}
        body.setdefault("sort", "_doc")  # configure for efficiency if able
        # validate size
        size_qy = body.get("size")
        size_kw = kwargs.get("size")
        if size_kw is None and size_qy is None:
            # Set a large scroll size if one is not already configured.
            # Observations on Elastic v2.4 show default (when not specified)
            # scroll size of 10.
            kwargs["size"] = self.SCROLL_SIZE
        elif not (size_kw is None or size_qy is None):
            raise ValueError(f"size cannot be specified in both query and keyword "
                             f"arguments (query: {size_qy}, kw: {size_kw})")
        results = self.search(index_alias, doc_type, body, scroll=scroll, **kwargs)
        scroll_id = results.get('_scroll_id')
        if scroll_id is None:
            return
        try:
            yield results
            while True:
                # Failure to add the `scroll` parameter here will cause the
                # scroll context to terminate immediately after this request,
                # resulting in this method fetching a maximum `size * 2`
                # documents.
                # see: https://stackoverflow.com/a/63911571
                results = self.scroll(scroll_id, params={"scroll": scroll})
                scroll_id = results.get('_scroll_id')
                yield results
                if scroll_id is None or not results['hits']['hits']:
                    break
        finally:
            if scroll_id:
                self.es.clear_scroll(body={'scroll_id': [scroll_id]}, ignore=(404,))

    def _get_doc_adapter(self, index_alias, doc_type):
        doc_adapter = doc_adapter_from_alias(index_alias)
        if doc_adapter.type != doc_type:
            raise ValueError(f"wrong type ({doc_type}) for adapter: {doc_adapter}")
        return doc_adapter

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
