import abc

from corehq.util.es.elasticsearch import bulk


class AbstractElasticsearchInterface(metaclass=abc.ABCMeta):

    # Default scroll parameters (same values hard-coded in elasticsearch-py's
    # `scan()` helper).
    SCROLL_KEEPALIVE = '5m'
    SCROLL_SIZE = 1000

    def __init__(self, es):
        self.es = es

    def get_aliases(self):
        return self.es.indices.get_aliases()

    def put_mapping(self, doc_type, mapping, index):
        return self.es.indices.put_mapping(doc_type, {doc_type: mapping}, index=index)

    def _verify_is_alias(self, alias):
        """Verify that an alias is one of a registered index"""
        from corehq.apps.es.registry import verify_alias
        verify_alias(alias)

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

    def get_doc(self, index_alias, doc_type, doc_id, source_includes=None):
        self._verify_is_alias(index_alias)
        doc = self._get_source(index_alias, doc_type, doc_id, source_includes=source_includes)
        doc['_id'] = doc_id
        return doc

    def get_bulk_docs(self, index_alias, doc_type, doc_ids):
        from corehq.elastic import ESError
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

    def index_doc(self, index_alias, doc_type, doc_id, doc, params=None):
        self._verify_is_alias(index_alias)
        self.es.index(index_alias, doc_type, body=self._without_id_field(doc), id=doc_id,
                      params=params or {})

    def update_doc_fields(self, index_alias, doc_type, doc_id, fields, params=None):
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
            # Set a large scroll size if one is not already is configured.
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
