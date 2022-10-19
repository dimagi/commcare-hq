"""HQ Elasticsearch client logic (adapters)."""
import copy
import json
import logging
from enum import Enum
from functools import cached_property

from django.db.backends.base.creation import TEST_DATABASE_PREFIX
from django.conf import settings
from django.utils.functional import classproperty

from memoized import memoized

from dimagi.utils.chunked import chunked

from corehq.util.es.elasticsearch import (
    Elasticsearch,
    ElasticsearchException,
    NotFoundError,
    bulk,
)
from corehq.util.metrics import metrics_counter

from .app_config import register_document_adapter
from .const import (
    INDEX_CONF_REINDEX,
    INDEX_CONF_STANDARD,
    SCROLL_KEEPALIVE,
    SCROLL_SIZE,
)
from .exceptions import ESError, ESShardFailure, TaskError, TaskMissing
from .utils import ElasticJSONSerializer

log = logging.getLogger(__name__)


class BaseAdapter:
    """Base adapter that includes methods common to all adapters."""

    def __init__(self):
        self._es = get_client()

    def info(self):
        """Return the Elasticsearch server info."""
        try:
            return self._es.info()
        except ElasticsearchException as exc:
            raise ESError("Elasticsearch is unavailable") from exc

    def ping(self):
        """Ping the Elasticsearch service."""
        try:
            return self._es.ping()
        except ElasticsearchException as exc:
            raise ESError("Elasticsearch is unavailable") from exc

    @property
    def elastic_major_version(self):
        return self.elastic_version[0]

    @cached_property
    def elastic_version(self):
        cluster_info = self.info()
        try:
            version = tuple(int(v) for v in cluster_info["version"]["number"].split("."))
        except (KeyError, ValueError):
            version = ()
        if version:
            return version
        raise ESError(f"invalid elasticsearch info: {cluster_info!r}")


class ElasticManageAdapter(BaseAdapter):

    def index_exists(self, index):
        """Check if ``index`` refers to a valid index identifier (index name or
        alias).

        :param name: ``str`` index name or alias
        :returns: ``bool``
        """
        self._validate_single_index(index)
        try:
            if self._es.indices.get(index, feature="_aliases",
                                    expand_wildcards="none"):
                return True
        except NotFoundError:
            pass
        return False

    def get_indices(self, full_info=False):
        """Return the cluster index information.

        :param full_info: ``bool`` whether to return the full index info
                          (default ``False``)
        :returns: ``dict``
        """
        feature = "" if full_info else "_aliases,_settings"
        return self._es.indices.get("_all", feature=feature)

    def get_aliases(self):
        """Return the cluster aliases information.

        :returns: ``dict`` with format ``{<alias>: [<index>, ...], ...}``
        """
        aliases = {}
        for index, alias_info in self._es.indices.get_aliases().items():
            for alias in alias_info.get("aliases", {}):
                aliases.setdefault(alias, []).append(index)
        return aliases

    def cluster_health(self, index=None):
        """Return the Elasticsearch cluster health."""
        if index is not None:
            self._validate_single_index(index)
        return self._es.cluster.health(index)

    def cluster_routing(self, *, enabled):
        """Enable or disable cluster routing.

        :param enabled: ``bool`` whether to enable or disable routing
        """
        value = "all" if enabled else "none"
        self._cluster_put_settings({"cluster.routing.allocation.enable": value})

    def _cluster_put_settings(self, settings, transient=True, is_flat=True):
        set_type = "transient" if transient else "persistent"
        self._es.cluster.put_settings({set_type: settings}, flat_settings=is_flat)

    def get_node_info(self, node_id, metric):
        """Return a specific metric from the node info for an Elasticsearch node.

        :param node_id: ``str`` ID of the node
        :param metric: ``str`` name of the metric to fetch
        :returns: deserialized JSON (``dict``, ``list``, ``str``, etc)
        """
        return self._es.nodes.info(node_id, metric)["nodes"][node_id][metric]

    def get_task(self, task_id):
        """Return the details for an active task

        :param task_id: ``str`` ID of the task
        :returns: ``dict`` of task details
        :raises: ``TaskError`` or ``TaskMissing`` (subclass of ``TaskError``)
        """
        # NOTE: elasticsearch5 python library doesn't support `task_id` as a
        # kwarg for the `tasks.list()` method, and uses `tasks.get()` for that
        # instead.
        return self._parse_task_result(self._es.tasks.list(task_id=task_id,
                                                           detailed=True))

    @staticmethod
    def _parse_task_result(result, *, _return_one=True):
        """Parse the ``tasks.list()`` output and return a dictionary of task
        details.

        :param result: Elasticsearch ``/_tasks`` response
        :param _return_one: ``bool`` (default ``True``) verify that there is
                            only one task result and return the details for that
                            task only.  Setting to ``False`` changes the return
                            value, returning a dictionary of one or more tasks,
                            keyed by their ``task_id`` (used for tests, but is
                            not necessarily a "for testing only" feature).
        :returns: ``dict``
        :raises: ``TaskError`` or ``TaskMissing`` (subclass of ``TaskError``)
        """
        tasks = {}
        for node_name, info in result.get("nodes", {}).items():
            for task_id, details in info.get("tasks", {}).items():
                tasks[task_id] = details
        if tasks:
            if not _return_one:
                return tasks
            if len(tasks) == 1:
                return list(tasks.values()).pop()
        try:
            failures = result["node_failures"]
            failure = failures.pop()
            if not failures and failure["type"] == "failed_node_exception":
                cause = failure["caused_by"]
                if cause["type"] == "resource_not_found_exception":
                    raise TaskMissing(cause)
        except (KeyError, IndexError):
            # task info format is not what we expected
            pass
        raise TaskError(result)

    def index_create(self, index, settings=None):
        """Create a new index.

        :param index: ``str`` index name
        :param settings: ``dict`` of index settings
        """
        self._validate_single_index(index)
        self._es.indices.create(index, settings)

    def index_delete(self, index):
        """Delete an existing index.

        :param index: ``str`` index name
        """
        self._validate_single_index(index)
        self._es.indices.delete(index)

    def index_refresh(self, index):
        """Convenience method for refreshing a single index."""
        self.indices_refresh([index])

    def indices_refresh(self, indices):
        """Refresh a list of indices.

        :param indices: iterable of index names or aliases
        """
        if not isinstance(indices, (list, tuple, set)):
            raise ValueError(f"invalid list of indices: {indices}")
        for index in indices:
            self._validate_single_index(index)
        self._es.indices.refresh(",".join(indices), expand_wildcards="none")

    def index_flush(self, index):
        """Flush an index.

        :param index: ``str`` index name
        """
        self._validate_single_index(index)
        self._es.indices.flush(index, expand_wildcards="none")

    def index_close(self, index):
        """Close an index.

        :param index: ``str`` index name
        """
        self._validate_single_index(index)
        self._es.indices.close(index, expand_wildcards="none")

    def index_put_alias(self, index, name):
        """Assign an alias to an existing index. This uses the
        ``Elasticsearch.update_aliases()`` method to perform both 'remove' and
        'add' actions simultaneously, which is atomic on the server-side. This
        ensures that the alias is **only** assigned to one index at a time, and
        that (if present) an existing alias does not vanish momentarily.

        See: https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html

        :param index: ``str`` name of the index to be aliased
        :param name: ``str`` name of the alias to assign to ``index``
        """
        self._validate_single_index(index)
        self._validate_single_index(name)
        # remove the alias (if assigned) and (re)assign it in a single request
        self._es.indices.update_aliases({"actions": [
            {"remove": {"index": "_all", "alias": name}},
            {"add": {"index": index, "alias": name}},
        ]})

    def index_set_replicas(self, index, replicas):
        """Set the number of replicas for an index.

        :param index: ``str`` index for which to change the replicas
        :param replicas: ``int`` number of replicas
        """
        self._validate_single_index(index)
        settings = {"index.number_of_replicas": replicas}
        self._index_put_settings(index, settings)

    def index_configure_for_reindex(self, index):
        """Update an index with settings optimized for reindexing.

        :param index: ``str`` index for which to change the settings
        """
        self._validate_single_index(index)
        return self._index_put_settings(index, INDEX_CONF_REINDEX)

    def index_configure_for_standard_ops(self, index):
        """Update an index with settings optimized standard HQ performance.

        :param index: ``str`` index for which to change the settings
        """
        return self._index_put_settings(index, INDEX_CONF_STANDARD)

    def _index_put_settings(self, index, settings):
        self._validate_single_index(index)
        if not (list(settings) == ["index"]
                or all(key.startswith("index.") for key in settings)):
            raise ValueError(f"Invalid index settings: {settings}")
        return self._es.indices.put_settings(settings, index)

    def index_put_mapping(self, index, type_, mapping):
        """Update the mapping for a doc type on an index.

        :param index: ``str`` index where the mapping should be updated
        :param type_: ``str`` doc type to update on the index
        :param mapping: ``dict`` mapping for the provided doc type
        """
        self._validate_single_index(index)
        return self._es.indices.put_mapping(type_, {type_: mapping}, index,
                                            expand_wildcards="none")

    @staticmethod
    def _validate_single_index(index):
        """Verify that the provided index is a valid, single index

        - is non-zero
        - is not ``_all``
        - does not contain commas (``,``)
        - does not contain wildcards (i.e. asterisks, ``*``).

        See: https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-get-index.html#get-index-api-path-params  # noqa: E501

        :param index: index name or alias
        """
        if not index:
            raise ValueError(f"invalid index: {index}")
        elif index == "_all":
            raise ValueError("refusing to operate on all indices")
        elif "," in index:
            raise ValueError(f"refusing to operate on multiple indices: {index}")
        elif "*" in index:
            raise ValueError(f"refusing to operate with index wildcards: {index}")


class ElasticDocumentAdapter(BaseAdapter):
    """Base for subclassing document-specific adapters.

    Subclasses must define the following:

    - ``mapping``: attribute (``dict``)
    - ``from_python(...)``: classmethod for converting models into Elastic format
    """

    def __init__(self, index_name, type_):
        """A document adapter for a single index.

        :param index_name: the name of the index that this adapter interacts with
        :param type_: the index ``_type`` for the mapping
        """
        super().__init__()
        self.index_name = index_name
        self.type = type_

    def export_adapter(self):
        """Get an instance of this document adapter configured for "export"
        queries (i.e. the low-level Elasticsearch client object is configured
        with longer request timeouts, etc).
        """
        adapter = copy.copy(self)
        adapter._es = get_client(for_export=True)
        return adapter

    @classproperty
    def settings(cls):
        return settings.ELASTIC_ADAPTER_SETTINGS.get(cls.__name__, {})

    @classmethod
    def from_python(cls, doc):
        """Transform a Python model object into the json-serializable (``dict``)
        format suitable for indexing in Elasticsearch.

        :param doc: document (instance of a Python model)
        :returns: ``tuple`` of ``(doc_id, source_dict)`` suitable for being
                  indexed/updated/deleted in Elasticsearch
        """
        raise NotImplementedError(f"{cls.__name__} is abstract")

    @classmethod
    def to_json(cls, doc):
        """Convenience method that returns the full "from python" document
        (including the ``_id`` key, if present) as it would be returned by an
        adapter ``search`` result.

        This method is not used by the adapter itself, and is only present for
        other code which wishes to work with documents in a couch-like format.

        :param doc: document (instance of a Python model)
        """
        _id, source = cls.from_python(doc)
        if _id is not None:
            source["_id"] = _id
        return source

    def exists(self, doc_id):
        """Check if a document exists for the provided ``doc_id``

        Equivalent to the legacy ``ElasticsearchInterface.doc_exists(...)``
        method.

        :param doc_id: ``str`` ID of the document to be checked
        :returns: ``bool``
        """
        return self._es.exists(self.index_name, self.type, doc_id)

    def get(self, doc_id, source_includes=None):
        """Return the document for the provided ``doc_id``

        Equivalent to the legacy ``ElasticsearchInterface.get_doc(...)`` method.

        :param doc_id: ``str`` ID of the document to be fetched
        :param source_includes: a list of fields to extract and return. If
                                ``None`` (the default), the entire document is
                                returned.
        :returns: ``dict``
        """
        kw = {"_source_include": source_includes} if source_includes else {}
        doc = self._es.get_source(self.index_name, self.type, doc_id, **kw)
        # TODO: standardize all result collections returned by this class.
        doc["_id"] = doc_id
        return doc

    def count(self, query):
        """Return the number of documents matched by the ``query``

        :param query: ``dict`` query body
        :returns: ``int``
        """
        query = self._prepare_count_query(query)
        return self._es.count(self.index_name, self.type, query).get("count")

    def _prepare_count_query(self, query):
        """TODO: move this logic to the calling class (the low-level adapter
        should not be performing this type of manipulation).
        """
        # pagination params are not required and not supported in ES count API
        query = query.copy()
        for extra in ["size", "sort", "from", "to", "_source"]:
            query.pop(extra, None)
        return query

    def get_docs(self, doc_ids):
        """Return multiple docs for the provided ``doc_ids``

        Equivalent to the legacy ``ElasticsearchInterface.get_bulk_docs(...)``
        method.

        :param doc_ids: iterable of document IDs (``str``'s)
        :returns: ``dict``
        """
        docs = []
        result = self._mget({"ids": doc_ids})
        # TODO: check for shard failures
        for doc_result in result["docs"]:
            if "error" in doc_result:
                raise ESError(doc_result["error"].get("reason", "multi-get error"))
            if doc_result["found"]:
                # TODO: standardize all result collections returned by this class.
                self._fix_hit(doc_result)
                docs.append(doc_result["_source"])
        return docs

    def iter_docs(self, doc_ids, chunk_size=100):
        """Return a generator which fetches documents in chunks.

        :param doc_ids: iterable of document IDs (``str``s)
        :param chunk_size: ``int`` number of documents to fetch per query
        :yields: ``dict`` documents
        """
        # TODO: standardize all result collections returned by this class.
        for ids_chunk in chunked(doc_ids, chunk_size):
            yield from self.get_docs(ids_chunk)

    def _mget(self, query):
        """Perform an ``mget`` request and return the result.

        :param query: ``dict`` mget query
        """
        return self._es.mget(query, self.index_name, self.type, _source=True)

    def search(self, query, **kw):
        """Perform a query (search) and return the result.

        :param query: ``dict`` search query to execute
        :param **kw: extra parameters passed directly to the
                     underlying ``elasticsearch.Elasticsearch.search()`` method.
        :returns: ``dict``
        """
        # TODO:
        # - standardize all result collections returned by this class.
        # - remove **kw and standardize which arguments HQ uses
        try:
            result = self._search(query, **kw)
            self._fix_hits_in_result(result)
            self._report_and_fail_on_shard_failures(result)
        except ElasticsearchException as exc:
            raise ESError(exc)
        return result

    def _search(self, query, **kw):
        """Perform a "low-level" search and return the raw result. This is
        split into a separate method for ease of testing the result format.
        """
        return self._es.search(self.index_name, self.type, query, **kw)

    def scroll(self, query, scroll=SCROLL_KEEPALIVE, size=None):
        """Perfrom a scrolling search, yielding each doc until the entire context
        is exhausted.

        :param query: ``dict`` raw search query.
        :param scroll: ``str`` time value specifying how long the Elastic
                       cluster should keep the search context alive.
        :param size: ``int`` scroll size (number of documents per "scroll" page)
                     When set to ``None`` (the default), the default scroll size
                     is used.
        :yields: ``dict`` documents
        """
        # TODO: standardize all result collections returned by this class.
        try:
            for result in self._scroll(query, scroll, size):
                self._report_and_fail_on_shard_failures(result)
                self._fix_hits_in_result(result)
                for hit in result["hits"]["hits"]:
                    yield hit
        except ElasticsearchException as e:
            raise ESError(e)

    def _scroll(self, query, scroll, size):
        """Perform one or more scroll requests to completely exhaust a scrolling
        search context.

        :param query: ``dict`` search query to execute
        :param scroll: ``str`` duration to keep scroll context alive
        :param size: ``int`` scroll size (number of documents per "scroll" page)
        :yields: ``dict``s of Elasticsearch result objects

        Providing a query with ``size`` specified as well as the ``size``
        keyword argument is ambiguous, and Elastic docs do not say what happens
        when ``size`` is provided both as a GET parameter _as well as_ part of
        the query body. Real-world observations show that the GET parameter
        wins, but to avoid ambiguity, specifying both in this function will
        raise a ``ValueError``.

        Read before using:
        - Scroll queries are not designed for real-time user requests.
        - Using aggregations with scroll queries may yield non-aggregated
          results.
        - The most efficient way to perform a scroll request is to sort by
          ``_doc``.
        - Scroll request results reflect the state of the index at the time the
          initial ``search`` is requested. Changes to the index after that time
          will not be reflected for the duration of the search context.
        - Open scroll search contexts can keep old index segments alive longer,
          which may require more disk space and file descriptor limits.
        - An Elasticsearch cluster has a limited number of allowed concurrent
          search contexts. Versions 2.4 and 5.6 do not specify what the default
          maximum limit is, or how to configure it. Version 7.14 specifies the
          default is 500 concurrent search contexts.
        - See: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-request-scroll.html
        """
        query = query.copy()
        query.setdefault("sort", "_doc")  # configure for efficiency if able
        kwargs = {"scroll": scroll}
        # validate/set default size
        size_qy = query.get("size")
        if size_qy is None:
            # Set a large scroll size if one is not already configured.
            # Observations on Elastic v2.4 show default (when not specified)
            # scroll size of 10.
            kwargs["size"] = SCROLL_SIZE if size is None else size
        elif size is not None:
            raise ValueError(f"ambiguous scroll size (specified in both query "
                             f"and arguments): query={size_qy}, arg={size}")
        result = self._search(query, **kwargs)
        scroll_id = result.get("_scroll_id")
        if scroll_id is None:
            return
        try:
            yield result
            while True:
                # Failure to add the `scroll` parameter here will cause the
                # scroll context to terminate immediately after this request,
                # resulting in this method fetching a maximum `size * 2`
                # documents.
                # see: https://stackoverflow.com/a/63911571
                result = self._es.scroll(scroll_id, scroll=scroll)
                scroll_id = result.get("_scroll_id")
                yield result
                if scroll_id is None or not result["hits"]["hits"]:
                    break
        finally:
            if scroll_id:
                self._es.clear_scroll(body={"scroll_id": [scroll_id]}, ignore=(404,))

    def index(self, doc, refresh=False, **kw):
        """Index (send) a new document in (to) Elasticsearch

        Equivalent to the legacy
        ``ElasticsearchInterface.index_doc(...)`` method.

        :param doc: the (Python model) document to index
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        :param **kw: extra parameters passed directly to the underlying
                     ``elasticsearch.Elasticsearch.index()`` method.
        """
        # TODO: remove **kw and standardize which arguments HQ uses
        doc_id, source = self.from_python(doc)
        self._verify_doc_id(doc_id)
        self._verify_doc_source(source)
        self._index(doc_id, source, refresh, **kw)

    def _index(self, doc_id, source, refresh, **kw):
        """Perform the low-level (3rd party library) index operation."""
        self._es.index(self.index_name, self.type, source, doc_id,
                       refresh=self._refresh_value(refresh), **kw)

    def update(self, doc_id, fields, return_doc=False, refresh=False,
               _upsert=False, retry_on_conflict=None):
        """Update an existing document in Elasticsearch

        Equivalent to the legacy
        ``ElasticsearchInterface.update_doc_fields(...)`` method.

        :param doc_id: ``str`` ID of the document to update
        :param fields: ``dict`` of name/values to update on the existing Elastic
                       doc
        :param return_doc: ``bool`` return the full updated doc. When ``False``
                           (the default), ``None`` is returned.
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        :param _upsert: ``bool``. Only needed for multiplexing, use the
                        `index()` method instead. Create a new document if one
                        doesn't already exist. When ``False`` (the default),
                        performing an update request for a missing document will
                        raise an exception.
        :param retry_on_conflict: ``int`` number of times to retry the update if
                                  there is a conflict. Ignored if ``None`` (the
                                  default). Otherwise, the value it is passed
                                  directly to the low-level `update()` method.
        :returns: ``dict`` or ``None``
        """
        if "_id" in fields:
            if doc_id != fields["_id"]:
                raise ValueError(f"ambiguous doc_id: ({doc_id!r} != {fields['_id']!r})")
            fields = {key: fields[key] for key in fields if key != "_id"}
        self._verify_doc_source(fields)
        kw = {"refresh": self._refresh_value(refresh)}
        if retry_on_conflict is not None:
            kw["retry_on_conflict"] = retry_on_conflict
        return self._update(doc_id, fields, return_doc, _upsert, **kw)

    def _update(self, doc_id, fields, return_doc, _upsert, **kw):
        """Perform the low-level (3rd party library) update operation."""
        if return_doc:
            major_version = self.elastic_major_version
            assert major_version in {2, 5, 6, 7, 8}, self.elastic_version
            if major_version == 2:
                kw["fields"] = "_source"
            elif major_version in {5, 6, 7}:
                # this changed in elasticsearch-py v5.x
                kw["_source"] = "true"
            else:
                # this changes again in elasticsearch-py v8.x
                kw["source"] = True
        payload = {"doc": fields}
        if _upsert:
            payload["doc_as_upsert"] = True
        response = self._es.update(self.index_name, self.type, doc_id, payload, **kw)
        return response.get("get", {}).get("_source")

    def delete(self, doc_id, refresh=False):
        """Delete an existing document from Elasticsearch

        Equivalent to the legacy ``ElasticsearchInterface.delete_doc(...)``
        method.

        :param doc_id: ``str`` ID of the document to delete
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        """
        self._es.delete(self.index_name, self.type, doc_id,
                        refresh=self._refresh_value(refresh))

    @staticmethod
    def _refresh_value(refresh):
        """Translate a boolean ``refresh`` argument value into a string value
        expected by Elasticsearch.

        :param refresh: ``bool``
        :returns: ``str`` (one of ``'true'`` or ``'false'``)
        """
        # valid Elasticsearch values are ["true", "false", "wait_for"]
        if refresh not in {True, False}:
            raise ValueError(f"Invalid 'refresh' value, expected bool, got {refresh!r}")
        return "true" if refresh else "false"

    def bulk(self, actions, refresh=False, **kw):
        """Use the Elasticsearch library's ``bulk()`` helper function to process
        documents en masse.

        Equivalent to the legacy ``ElasticsearchInterface.bulk_ops(...)``
        method.

        :param actions: iterable of ``BulkActionItem`` instances
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        :param **kw: extra parameters passed directly to the underlying
                     ``elasticsearch.helpers.bulk()`` function.
        """
        # TODO: remove **kw and standardize which arguments HQ uses
        payload = [self._render_bulk_action(action) for action in actions]
        return bulk(self._es, payload, refresh=self._refresh_value(refresh), **kw)

    def bulk_index(self, docs, refresh=False, **kw):
        """Convenience method for bulk indexing many documents without the
        BulkActionItem boilerplate.

        :param docs: iterable of (Python model) documents to be indexed
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        :param **kw: extra parameters passed directly to the underlying
                     ``elasticsearch.helpers.bulk()`` function.
        """
        # TODO: remove **kw and standardize which arguments HQ uses
        action_gen = (BulkActionItem.index(doc) for doc in docs)
        return self.bulk(action_gen, refresh, **kw)

    def bulk_delete(self, doc_ids, refresh=False, **kw):
        """Convenience method for bulk deleting many documents by ID without the
        BulkActionItem boilerplate.

        :param doc_ids: iterable of document IDs to be deleted
        :param refresh: ``bool`` refresh the effected shards to make this
                        operation visible to search
        :param **kw: extra parameters passed directly to the underlying
                     ``elasticsearch.helpers.bulk()`` function.
        """
        # TODO: remove **kw and standardize which arguments HQ uses
        action_gen = (BulkActionItem.delete_id(doc_id) for doc_id in doc_ids)
        return self.bulk(action_gen, refresh, **kw)

    def _render_bulk_action(self, action):
        """Return a "raw" action object in the format required by the
        Elasticsearch ``bulk()`` helper function.

        :param action: a ``BulkActionItem`` instance
        :returns: ``dict``
        """
        for_elastic = {
            "_index": self.index_name,
            "_type": self.type,
        }
        if action.is_delete:
            for_elastic["_op_type"] = "delete"
            if action.doc is None:
                doc_id = action.doc_id
            else:
                doc_id = self.from_python(action.doc)[0]
        elif action.is_index:
            for_elastic["_op_type"] = "index"
            doc_id, source = self.from_python(action.doc)
            self._verify_doc_source(source)
            for_elastic["_source"] = source
        else:
            raise ValueError(f"unsupported action type: {action!r}")
        self._verify_doc_id(doc_id)
        for_elastic["_id"] = doc_id
        return for_elastic

    @staticmethod
    def _verify_doc_id(doc_id):
        """Check whether or not the provided ``doc_id`` is a valid value to
        use as the ``_id`` for an Elasticsearch document.

        :param doc_id: value to check
        :raises: ``ValueError``
        """
        if not (isinstance(doc_id, str) and doc_id):
            raise ValueError(f"invalid Elastic _id value: {doc_id!r}")

    @staticmethod
    def _verify_doc_source(source):
        """Check whether or the not the provided ``source`` is valid for
        passing to Elasticseach (does not contain any illegal meta properties).

        :param source: ``dict`` of document properties to check
        :raises: ``ValueError``
        """
        if not isinstance(source, dict) or "_id" in source:
            raise ValueError(f"invalid Elastic _source value: {source}")
        if Tombstone.PROPERTY_NAME in source:
            raise ValueError(f"property {Tombstone.PROPERTY_NAME} is reserved")

    @staticmethod
    def _fix_hit(hit):
        """Modify the ``hit`` dict that is passed to this method.

        :param hit: ``dict`` Elasticsearch result
        :returns: ``None``
        """
        # TODO: standardize all result collections returned by this class.
        if "_source" in hit:
            hit["_source"]["_id"] = hit["_id"]

    def _fix_hits_in_result(self, result):
        """Munge the ``result`` dict, conditionally modifying it.

        :param result: ``dict`` of Elasticsearch result hits (or possibly
                        something else)
        :returns: ``None``
        """
        # TODO: standardize all result collections returned by this class.
        try:
            hits = result["hits"]["hits"]
        except KeyError:
            return
        for hit in hits:
            self._fix_hit(hit)

    @staticmethod
    def _report_and_fail_on_shard_failures(result):
        """
        Raise an ESShardFailure if there are shard failures in a search result
        (JSON) and report to datadog.
        The ``commcare.es.partial_results`` metric counts 1 per Elastic request
        with any shard failure.

        :param result: Elasticsearch ``search`` or ``scroll`` result object
        :raises: ``ESShardFailure``, ``ValueError``
        """
        if not isinstance(result, dict):
            raise ValueError(f"invalid Elastic result object: {result}")
        if result.get("_shards", {}).get("failed"):
            metrics_counter("commcare.es.partial_results")
            # Example message:
            #   "_shards: {"successful": 4, "failed": 1, "total": 5}"
            shard_info = json.dumps(result["_shards"])
            raise ESShardFailure(f"_shards: {shard_info}")

    def __repr__(self):
        return f"<{self.__class__.__name__} index={self.index_name!r}, type={self.type!r}>"


class BulkActionItem:
    """A wrapper for documents to be processed via Elasticsearch's Bulk API.
    Collections of these objects can be passed to an ElasticDocumentAdapter's
    ``.bulk()`` method for processing.

    Instances of this class are meant to be acquired via one of the factory
    methods rather than instantiating directly (via ``__init__()``).
    """

    OpType = Enum("OpType", "index delete")

    def __init__(self, op_type, doc=None, doc_id=None):
        if not (isinstance(op_type, self.OpType) and op_type in self.OpType):
            raise ValueError(f"invalid operations type: {op_type!r}")
        if doc is None and doc_id is None:
            raise ValueError("at least one of 'doc' or 'doc_id' are required")
        elif not (doc is None or doc_id is None):
            raise ValueError("'doc' and 'doc_id' are mutually exclusive")
        elif doc is None and op_type is not self.OpType.delete:
            raise ValueError("'doc_id' can only be used for delete operations")
        self.doc = doc
        self.doc_id = doc_id
        self.op_type = op_type

    @classmethod
    def delete(cls, doc):
        """Factory method for a document delete action"""
        return cls(cls.OpType.delete, doc=doc)

    @classmethod
    def delete_id(cls, doc_id):
        """Factory method for a document delete action providing only the ID"""
        return cls(cls.OpType.delete, doc_id=doc_id)

    @classmethod
    def index(cls, doc):
        """Factory method for a document index action"""
        return cls(cls.OpType.index, doc=doc)

    @property
    def is_delete(self):
        """``True`` if this is a delete action, otherwise ``False``."""
        return self.op_type is self.OpType.delete

    @property
    def is_index(self):
        """``True`` if this is an index action, otherwise ``False``."""
        return self.op_type is self.OpType.index

    def __eq__(self, other):
        if not isinstance(other, BulkActionItem):
            return NotImplemented
        return (self.op_type, self.doc, self.doc_id) == (other.op_type, other.doc, other.doc_id)

    def __repr__(self):
        if self.doc_id is not None:
            doc_info = f"_id={self.doc_id!r}"
        else:
            doc_info = f"doc={self.doc!r}"
        return f"<{self.__class__.__name__} op_type={self.op_type.name}, {doc_info}>"


class ElasticMultiplexAdapter(BaseAdapter):

    def __init__(self, primary_adapter, secondary_adapter):
        super().__init__()
        self.index_name = primary_adapter.index_name
        self.type = primary_adapter.type
        self.mapping = primary_adapter.mapping

        self.primary = primary_adapter
        self.secondary = secondary_adapter
        # TODO document this better
        self.secondary.from_python = self.from_python

    def export_adapter(self):
        adapter = copy.copy(self)
        adapter.primary = adapter.primary.export_adapter()
        return adapter

    def from_python(self, doc):
        # TODO: this is a classmethod on the the document adapter, but should
        # be converted to an instance method
        if isinstance(doc, Tombstone):
            return doc.id, Tombstone.create_document()
        return self.primary.from_python(doc)

    # meta methods and Elastic index read methods (pass-through on the primary
    # adapter)
    @property
    def settings(self):
        # TODO: this is a classproperty on the the document adapter, but should
        # be converted to a property
        return self.primary.settings

    def to_json(self, doc):
        # TODO: this is a classmethod on the the document adapter, but should
        # be converted to an instance method
        return self.primary.to_json(doc)

    def count(self, *args, **kw):
        return self.primary.count(*args, **kw)

    def exists(self, *args, **kw):
        return self.primary.exists(*args, **kw)

    def get(self, *args, **kw):
        return self.primary.get(*args, **kw)

    def get_docs(self, *args, **kw):
        return self.primary.get_docs(*args, **kw)

    def iter_docs(self, *args, **kw):
        return self.primary.iter_docs(*args, **kw)

    def scroll(self, *args, **kw):
        return self.primary.scroll(*args, **kw)

    def search(self, *args, **kw):
        return self.primary.search(*args, **kw)

    # Elastic index write methods (multiplexed between both adapters)
    def bulk(self, actions, refresh=False, **kw):
        """Pass actions verbatim to primary. Convert delete actions to
        'index tombstone' actions and send to secondary."""
        primary_actions = []
        secondary_actions = []
        for action in actions:
            primary_actions.append(action)
            if action.is_delete:
                # This logic belongs in the BulkActionItem class, but that class
                # has no concept of 'to_python(doc)'
                if action.doc_id is None:
                    doc_id = self.from_python(action.doc)[0]
                else:
                    doc_id = action.doc_id
                action = BulkActionItem.index(Tombstone(doc_id))
            secondary_actions.append(action)
        self.primary.bulk(primary_actions, refresh, **kw)
        # don't refresh the secondary because we never read from it
        self.secondary.bulk(secondary_actions, **kw)

    def delete(self, doc_id, refresh=False):
        """Delete on primary, index tombstone on secondary."""
        self.primary.delete(doc_id, refresh)
        # don't refresh the secondary because we never read from it
        self.secondary._index(doc_id, Tombstone.create_document())

    def index(self, doc, refresh=False, **kw):
        """Index on both adapters"""
        self.primary.index(doc, refresh, **kw)
        # don't refresh the secondary because we never read from it
        self.secondary.index(doc, **kw)

    def update(self, doc_id, fields, return_doc=False, refresh=False,
               _upsert=False, **kw):
        """Update on the primary adapter, fetching the full doc; then upsert the
        secondary adapter.
        """
        full_doc = self.primary.update(doc_id, fields, return_doc=True,
                                       refresh=refresh, _upsert=_upsert, **kw)
        # don't refresh the secondary because we never read from it
        self.secondary.update(doc_id, full_doc, _upsert=True, **kw)
        if return_doc:
            return full_doc
        return None


class Tombstone:

    PROPERTY_NAME = "__is_tombstone__"

    def __init__(self, doc_id):
        self.id = doc_id

    @classmethod
    def create_document(cls):
        return {cls.PROPERTY_NAME: True}


def get_client(for_export=False):
    """Get an elasticsearch client instance.

    :param for_export: (optional ``bool``) specifies whether the returned
                          client should be optimized for slow export queries.
    :returns: `elasticsearch.Elasticsearch` instance.
    """
    if for_export:
        return _client_for_export()
    return _client_default()


@memoized
def _client_default():
    """Get a configured elasticsearch client instance."""
    return _client()


@memoized
def _client_for_export():
    """Get an elasticsearch client with settings more tolerant of slow queries
    (better suited for large exports).
    """
    return _client(
        retry_on_timeout=True,
        max_retries=3,
        timeout=300,  # query timeout in seconds
    )


def _client(**override_kw):
    """Configure an elasticsearch.Elasticsearch instance."""
    hosts = _elastic_hosts()
    client_kw = {
        "timeout": settings.ES_SEARCH_TIMEOUT,
        "serializer": ElasticJSONSerializer(),
    }
    client_kw.update(override_kw)
    return Elasticsearch(hosts, **client_kw)


def _elastic_hosts():
    """Render the host list for passing to an elasticsearch-py client."""
    parse_hosts = getattr(settings, 'ELASTICSEARCH_HOSTS', [])
    if not parse_hosts:
        parse_hosts.append(settings.ELASTICSEARCH_HOST)
    hosts = []
    for hostspec in parse_hosts:
        host, delim, port = hostspec.partition(":")
        if delim:
            port = int(port)
        else:
            port = settings.ELASTICSEARCH_PORT
        hosts.append({"host": host, "port": port})
    return hosts


def create_document_adapter(cls, index_name, type_, *, secondary=None):
    """Creates, registers and returns a document adapter instance for the
    parameters provided.

    :param cls: an ``ElasticDocumentAdapter`` subclass
    :param index_name: the name of the index that the adapter interacts with
    :param type_: the index ``_type`` for the adapter's mapping.
    :param secondary: the name of the secondary index in a multiplexing
        configuration. If an index name is provided, the returned adapter will
        be an instance of ``ElasticMultiplexAdapter``.  If ``None`` (the
        default), the returned adapter will be an instance of ``cls``.
    :returns: a document adapter instance.
    """
    def runtime_name(name):
        # transform the name if testing
        return f"{TEST_DATABASE_PREFIX}{name}" if settings.UNIT_TESTING else name

    doc_adapter = cls(runtime_name(index_name), type_)
    if secondary is not None:
        secondary_adapter = cls(runtime_name(secondary), type_)
        doc_adapter = ElasticMultiplexAdapter(doc_adapter, secondary_adapter)

    register_document_adapter(doc_adapter)
    return doc_adapter


manager = ElasticManageAdapter()
