import json
import math
from contextlib import contextmanager
from copy import deepcopy

import uuid
from django.test import SimpleTestCase, override_settings
from nose.tools import nottest
from unittest.mock import patch

from corehq.util.es.elasticsearch import Elasticsearch, TransportError

from .utils import (
    TestDoc,
    TestDocumentAdapter,
    docs_from_result,
    docs_to_dict,
    es_test,
    temporary_index,
)
from ..client import (
    BulkActionItem,
    BaseAdapter,
    ElasticManageAdapter,
    get_client,
    _elastic_hosts,
    _client_default,
    _client_for_export,
)
from ..const import INDEX_CONF_REINDEX, INDEX_CONF_STANDARD
from ..exceptions import ESShardFailure, TaskError, TaskMissing


@override_settings(ELASTICSEARCH_HOSTS=["localhost"],
                   ELASTICSEARCH_PORT=9200)
@es_test
class TestClient(SimpleTestCase):

    def tearDown(self):
        # discard the memoized clients so other tests don't get the ones with
        # overridden settings from this test class.
        _client_default.reset_cache()
        _client_for_export.reset_cache()

    def test_elastic_host(self):
        expected = [{"host": "localhost", "port": 9200}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["localhost", "otherhost:9292"])
    def test_elastic_hosts(self):
        expected = [
            {"host": "localhost", "port": 9200},
            {"host": "otherhost", "port": 9292},
        ]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=[],
                       ELASTICSEARCH_HOST="otherhost:9292")
    def test_elastic_hosts_fall_back_to_host(self):
        expected = [{"host": "otherhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["somehost:9200"],
                       ELASTICSEARCH_HOST="ignored:9292")
    def test_elastic_host_is_ignored_if_hosts_present(self):
        expected = [{"host": "somehost", "port": 9200}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["somehost:badport"])
    def test_elastic_host_fails_non_int_port(self):
        with self.assertRaises(ValueError):
            _elastic_hosts()

    @override_settings(ELASTICSEARCH_HOSTS=["somehost:"])
    def test_elastic_host_fails_empty_port(self):
        with self.assertRaises(ValueError):
            _elastic_hosts()

    @override_settings(ELASTICSEARCH_PORT=9292)
    def test_elastic_hosts_alt_default_port(self):
        expected = [{"host": "localhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    @override_settings(ELASTICSEARCH_HOSTS=["otherhost:9292"])
    def test_elastic_hosts_alt_host_spec(self):
        expected = [{"host": "otherhost", "port": 9292}]
        self.assertEqual(expected, _elastic_hosts())

    def test_get_client(self):
        client = get_client()
        self.assertIsInstance(client, Elasticsearch)
        self.assertFalse(client.transport.retry_on_timeout)

    def test_get_client_for_export(self):
        export_client = get_client(for_export=True)
        self.assertIsInstance(export_client, Elasticsearch)
        self.assertTrue(export_client.transport.retry_on_timeout)
        self.assertEqual(export_client.transport.kwargs, {"timeout": 300})

    def test_get_client_is_memoized(self):
        client = get_client()
        client_exp = get_client(for_export=True)
        self.assertIs(client, get_client())
        self.assertIs(client_exp, get_client(for_export=True))
        self.assertIsNot(client, client_exp)


class AdapterTestCase(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.adapter = self.adapter_class()


@es_test
class TestBaseAdapter(AdapterTestCase):

    adapter_class = BaseAdapter

    def test_info(self):
        self.assertEqual(sorted(self.adapter.info()),
                         ["cluster_name", "cluster_uuid", "name", "tagline", "version"])

    def test_ping(self):
        self.assertTrue(self.adapter.ping())

    def test_ping_fail(self):
        # verify that the current (new or cached) client works
        self.assertTrue(BaseAdapter().ping())
        # discard cached client so we get a new one
        _client_default.reset_cache()
        with override_settings(ELASTICSEARCH_HOSTS=["localhost:65536"]):  # bad port
            ping_fail_adapter = BaseAdapter()
            self.assertFalse(ping_fail_adapter.ping())
        # discard again so later tests get a valid client
        _client_default.reset_cache()
        # verify that the cache clear was successful
        self.assertTrue(BaseAdapter().ping())


class AdapterWithIndexTestCase(AdapterTestCase):
    """Subclasses must set ``index`` class attribute."""

    def setUp(self):
        super().setUp()
        # clear in case it's still hanging around from other tests
        self._purge_test_index()

    def tearDown(self):
        self._purge_test_index()
        super().tearDown()

    @nottest
    def _purge_test_index(self):
        try:
            ElasticManageAdapter().index_delete(self.index)
        except TransportError:
            # TransportError(404, 'index_not_found_exception', 'no such index')
            pass


@es_test
class TestElasticManageAdapter(AdapterWithIndexTestCase):

    adapter_class = ElasticManageAdapter
    index = "test_manage-adapter"

    def test_index_exists(self):
        self.assertFalse(self.adapter.index_exists(self.index))
        self.adapter.index_create(self.index)
        self.adapter.indices_refresh([self.index])
        self.assertTrue(self.adapter.index_exists(self.index))

    def test_cluster_health(self):
        self.assertIn("status", self.adapter.cluster_health())

    def test_cluster_health_of_index(self):
        self.adapter.index_create(self.index)
        self.assertIn("status", self.adapter.cluster_health(self.index))

    def test_cluster_routing(self):
        # ensure it's something different first
        self.adapter.cluster_routing(enabled=False)
        # now set it and test
        self.adapter.cluster_routing(enabled=True)
        settings = self.adapter._es.cluster.get_settings(flat_settings=True)
        self.assertEqual(
            settings["transient"]["cluster.routing.allocation.enable"],
            "all",
        )
        self._clear_cluster_routing()

    def test_cluster_routing_disable(self):
        # ensure it's something different first
        self._clear_cluster_routing(verify=True)
        # now set it and test
        self.adapter.cluster_routing(enabled=False)
        settings = self.adapter._es.cluster.get_settings(flat_settings=True)
        self.assertEqual(
            settings["transient"]["cluster.routing.allocation.enable"],
            "none",
        )
        self._clear_cluster_routing()

    def _clear_cluster_routing(self, verify=False):
        """Attempt to "clear" the cluster setting. In v2.4 you can't clear
        a transient setting once its set without restarting the cluster, so we
        explicitly set the default value (`all`) instead.
        """
        self.adapter.cluster_routing(enabled=True)  # default value
        if verify:
            settings = self.adapter._es.cluster.get_settings(flat_settings=True)
            self.assertEqual(settings["transient"]["cluster.routing.allocation.enable"], "all")
        #
        # The code below is better. Use it instead when able Elastic v5+
        #
        #try:
        #    self.adapter._cluster_put_settings({"cluster.routing.allocation.enable": None})
        #except TransportError:
        #    # TransportError(400, 'action_request_validation_exception', 'Validation Failed: 1: no settings to update;')  # noqa: E501
        #    pass
        #if verify:
        #    settings = self.adapter._es.cluster.get_settings(flat_settings=True)
        #    self.assertIsNone(settings["transient"].get("cluster.routing.allocation.enable"))

    def test_get_node_info(self):
        info = self.adapter._es.nodes.info()
        node_id = list(info["nodes"])[0]
        node_name = info["nodes"][node_id]["name"]
        self.assertEqual(self.adapter.get_node_info(node_id, "name"), node_name)

    def test_get_task(self):
        with self._mock_single_task_response() as (task_id, patched):
            task = self.adapter.get_task(task_id)
            patched.assert_called_once_with(task_id=task_id, detailed=True)
            self.assertIn("running_time_in_nanos", task)

    @contextmanager
    def _mock_single_task_response(self):
        """A context manager that fetches a real list of all tasks from
        Elasticsearch and returns the tuple ``(task_id, patched)`` where:
        - ``task_id`` is the ID of a task present in the mock's ``return_value``
        - ``patched`` is the mock object returned by patching
          ``self.adapter._es.tasks.list`` and setting its ``return_value`` to
          the real list of tasks, pruned down to contain details for only
          ``task_id`` (to simulate the response returned for a single task by
          its ID)

        This function depends on the fact that at any given time, an
        Elasticsearch cluster will _always_ return at least one task (which is
        observed to be true in at least Elasticsearch 2.4).
        """
        response = self.adapter._es.tasks.list()
        parsed = self.adapter._parse_task_result(response, _return_one=False)
        task_id = list(parsed)[0]  # get the first task_id
        # prune the response of all tasks but one
        for node_name, info in response["nodes"].items():
            for t_id in list(info["tasks"]):
                if t_id != task_id:
                    info["tasks"].pop(t_id)
        with patch.object(self.adapter._es.tasks, "list", return_value=response) as patched:
            yield task_id, patched

    def test_get_task_missing(self):
        node_name = list(self.adapter._es.nodes.info()["nodes"])[0]
        hopefully_missing_task_id = f"{node_name}:0"
        with self.assertRaises(TaskMissing):
            self.adapter.get_task(hopefully_missing_task_id)

    def test_get_task_error(self):
        with self.assertRaises(TaskError):
            self.adapter.get_task("_:0")  # (hopefully) bad task (node) ID

    def test__parse_task_result_empty_valid_failure_and_cause(self):
        cause = {"type": "resource_not_found_exception"}
        result = {"nodes": {}, "node_failures": [{
            "type": "failed_node_exception",
            "caused_by": cause,
        }]}
        with self.assertRaises(TaskMissing) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(test.exception.tasks_result, cause)

    def test__parse_task_result_empty_unknown_reason(self):
        result = {"nodes": {}}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(result, test.exception.tasks_result)

    def test__parse_task_result_empty_unknown_fail_type(self):
        result = {"nodes": {}, "node_failures": [{"type": "bogus"}]}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(result, test.exception.tasks_result)

    def test__parse_task_result_empty_unknown_caused_by_type(self):
        result = {"nodes": {}, "node_failures": [{
            "type": "failed_node_exception",
            "caused_by": {"type": "bogus"},
        }]}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(result, test.exception.tasks_result)

    def test__parse_task_result_empty_missing_caused_by(self):
        result = {"nodes": {}, "node_failures": [{
            "type": "failed_node_exception"
        }]}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(result, test.exception.tasks_result)

    def test__parse_task_result_empty_multi_failures(self):
        result = {"nodes": {}, "node_failures": ["one", "two"]}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(test.exception.tasks_result, result)

    def test__parse_task_result_single_task_valid(self):
        details = "we're interested in this bit"
        result = {"nodes": {"node_0": {"tasks": {"node_0:1": details}}}}
        self.assertEqual(details, self.adapter._parse_task_result(result))

    def test__parse_task_result_multi_tasks_expected(self):
        result = {"nodes": {
            "node_0": {"tasks": {"node_0:1": {}, "node_0:2": {}}},
            "node_1": {"tasks": {"node_1:1": {}, "node_1:2": {}}},
        }}
        expected = {
            "node_0:1": {},
            "node_0:2": {},
            "node_1:1": {},
            "node_1:2": {},
        }
        self.assertEqual(
            expected,
            self.adapter._parse_task_result(result, _return_one=False),
        )

    def test__parse_task_result_multi_tasks_not_expected(self):
        result = {"nodes": {
            "node_0": {"tasks": {"node_0:1": {}, "node_0:2": {}}},
            "node_1": {"tasks": {"node_1:1": {}, "node_1:2": {}}},
        }}
        with self.assertRaises(TaskError) as test:
            self.adapter._parse_task_result(result)
        self.assertEqual(test.exception.tasks_result, result)

    def test_index_create(self):
        self.assertFalse(self.adapter.index_exists(self.index))
        self.adapter.index_create(self.index)
        self.assertTrue(self.adapter.index_exists(self.index))

    def test_index_delete(self):
        self.adapter.index_create(self.index)
        self.assertTrue(self.adapter.index_exists(self.index))
        self.adapter.index_delete(self.index)
        self.assertFalse(self.adapter.index_exists(self.index))

    def test_index_refresh(self):
        with patch.object(self.adapter, "indices_refresh") as patched:
            self.adapter.index_refresh(self.index)
            patched.assert_called_once_with([self.index])

    def test_indices_refresh(self):
        doc_adapter = TestDocumentAdapter()

        def get_search_hits():
            return doc_adapter.search({})["hits"]["hits"]

        with temporary_index(doc_adapter.index_name, doc_adapter.type, doc_adapter.mapping):
            # Disable auto-refresh to ensure the index doesn't refresh between our
            # index and search (which would cause this test to fail).
            self.adapter._index_put_settings(
                doc_adapter.index_name,
                {"index.refresh_interval": "-1"}
            )
            doc_adapter.index(TestDoc("1", "test"))
            self.assertEqual([], get_search_hits())
            self.adapter.indices_refresh([doc_adapter.index_name])
            docs = [h["_source"] for h in get_search_hits()]
        self.assertEqual([{"_id": "1", "entropy": 3, "value": "test"}], docs)

    def test_indices_refresh_requires_list_similar(self):
        self.adapter.indices_refresh([self.index])  # does not raise for list
        self.adapter.indices_refresh((self.index,))  # does not raise for tuple
        self.adapter.indices_refresh({self.index})  # does not raise for set
        with self.assertRaises(ValueError):
            self.adapter.indices_refresh(self.index)  # string is invalid

    def test_index_flush(self):
        self.adapter.index_create(self.index)
        flush_index = self.adapter._es.indices.flush  # keep a reference
        with patch.object(self.adapter._es.indices, "flush") as patched:
            self.adapter.index_flush(self.index)
            flush_index(self.index)  # also perform the actual Elastic request
            patched.assert_called_once_with(self.index, expand_wildcards="none")

    def test_index_close(self):
        doc_adapter = TestDocumentAdapter()
        with temporary_index(doc_adapter.index_name):
            doc_adapter.index(TestDoc("1", "test"))  # does not raise
            self.adapter.index_close(doc_adapter.index_name)
            with self.assertRaises(TransportError) as test:
                doc_adapter.index(TestDoc("2", "test"))
            self.assertEqual(test.exception.status_code, 403)
            self.assertEqual(test.exception.error, "index_closed_exception")

    def test_index_put_alias(self):
        alias = "test_alias"
        aliases = self.adapter.get_aliases()
        self.assertNotIn(alias, aliases)
        self.adapter.index_create(self.index)
        self.adapter.index_put_alias(self.index, alias)
        self._assert_alias_on_single_index(alias, self.index)

    def test_index_put_alias_flips_existing(self):
        alias = "test_alias"
        flip_to_index = f"{self.index}_alt"
        self.adapter.index_create(self.index)
        with temporary_index(flip_to_index):
            self.adapter.index_put_alias(self.index, alias)
            self._assert_alias_on_single_index(alias, self.index)
            self.adapter.index_put_alias(flip_to_index, alias)
            self._assert_alias_on_single_index(alias, flip_to_index)

    def _assert_alias_on_single_index(self, alias, index):
        aliases = self.adapter.get_aliases()
        self.assertIn(alias, aliases)
        self.assertEqual(aliases[alias], [index])

    def test_index_set_replicas(self):
        self.adapter.index_create(self.index)
        # initial value is 1
        self._verify_index_settings(self.index, {"index.number_of_replicas": 1})
        self.adapter.index_set_replicas(self.index, 0)
        self._verify_index_settings(self.index, {"index.number_of_replicas": 0})

    def test_index_configure_for_reindex(self):
        self.adapter.index_create(self.index)
        # change values to something else first
        self.adapter.index_configure_for_standard_ops(self.index)
        self._verify_index_settings(self.index, INDEX_CONF_STANDARD)
        # now change to the settings we want to test
        self.adapter.index_configure_for_reindex(self.index)
        self._verify_index_settings(self.index, INDEX_CONF_REINDEX)

    def test_index_configure_for_standard_ops(self):
        self.adapter.index_create(self.index)
        # change values to something else first
        self.adapter.index_configure_for_reindex(self.index)
        self._verify_index_settings(self.index, INDEX_CONF_REINDEX)
        # now change to the settings we want to test
        self.adapter.index_configure_for_standard_ops(self.index)
        self._verify_index_settings(self.index, INDEX_CONF_STANDARD)

    def test__index_put_settings(self):
        self.adapter.index_create(self.index)
        value = {"index.max_result_window": 100}
        self.adapter._index_put_settings(self.index, value)
        self._verify_index_settings(self.index, value)
        # update to a new value to verify we're actually changing it
        value["index.max_result_window"] = 13
        self.adapter._index_put_settings(self.index, value)
        self._verify_index_settings(self.index, value)

    def test__index_put_settings_nested(self):
        def get_flattened(mrw):
            return {"index.max_result_window": mrw}
        self.adapter.index_create(self.index)
        mrw = 100
        self.adapter._index_put_settings(self.index,
                                         {"index": {"max_result_window": mrw}})
        self._verify_index_settings(self.index, get_flattened(mrw))
        # update to a new value to verify we're actually changing it
        mrw = 13
        self.adapter._index_put_settings(self.index,
                                         {"index": {"max_result_window": mrw}})
        self._verify_index_settings(self.index, get_flattened(mrw))

    def _get_index_settings(self, index, setting_name=None):
        info = self.adapter._es.indices.get_settings(
            index,
            setting_name,
            flat_settings=True,
            # include_defaults=True,  # not supported in Elastic 2.4
        )[index]["settings"]
        return info if setting_name is None else info[setting_name]

    def _verify_index_settings(self, index, settings_flattened):
        fetched = self._get_index_settings(index)
        for key, value in settings_flattened.items():
            self.assertEqual(value, type(value)(fetched[key]))

    def test_index_put_mapping(self):
        type_ = "test_doc"
        mapping = {
            "properties": {
                "value": {"type": "string"}
            }
        }
        self.adapter.index_create(self.index)

        def get_mapping(index, type_):
            info = self.adapter._es.indices.get_mapping(index, type_)
            if info:
                return info[index]["mappings"][type_]
            return info

        self.assertEqual(get_mapping(self.index, type_), {})
        self.adapter.index_put_mapping(self.index, type_, mapping)
        self.assertEqual(get_mapping(self.index, type_), mapping)

    def test__validate_single_index(self):
        self.adapter._validate_single_index(self.index)  # does not raise

    def test__validate_single_index_fails_empty(self):
        with self.assertRaises(ValueError):
            self.adapter._validate_single_index("")

    def test__validate_single_index_fails_None(self):
        with self.assertRaises(ValueError):
            self.adapter._validate_single_index(None)

    def test__validate_single_index_fails__all(self):
        with self.assertRaises(ValueError):
            self.adapter._validate_single_index("_all")

    def test__validate_single_index_fails_multi_syntax(self):
        with self.assertRaises(ValueError):
            self.adapter._validate_single_index("index1,index2")

    def test__validate_single_index_fails_wildcard(self):
        with self.assertRaises(ValueError):
            self.adapter._validate_single_index("case*")


@nottest
class TestDocumentAdapterWithExtras(TestDocumentAdapter):
    """A special document adapter (has extra methods) specifically for reducing
    boilerplate on adapter tests where periodic management actions are needed.
    """

    def index_exists(self):
        return ElasticManageAdapter().index_exists(self.index_name)

    def create_index(self, settings=None):
        ElasticManageAdapter().index_create(self.index_name, settings)

    def delete_index(self):
        ElasticManageAdapter().index_delete(self.index_name)

    def refresh_index(self):
        ElasticManageAdapter().indices_refresh([self.index_name])


@es_test
class TestElasticDocumentAdapter(AdapterWithIndexTestCase):
    """Document adapter tests that require an existing index."""

    adapter_class = TestDocumentAdapterWithExtras
    index = TestDocumentAdapterWithExtras.index_name

    def setUp(self):
        super().setUp()
        # simply fail all the tests rather than spewing many huge tracebacks
        self.assertFalse(self.adapter.index_exists(),
                         f"index exists: {self.adapter.index_name}")
        self.adapter.create_index({"mappings": {self.adapter.type: self.adapter.mapping}})

    def test_exists(self):
        doc = self._index_new_doc()
        self.assertTrue(self.adapter.exists(doc["_id"]))

    def test_get(self):
        doc = self._index_new_doc()
        self.assertEqual(doc, self.adapter.get(doc["_id"]))

    def test_get_limit_fields(self):
        doc = self._index_new_doc()
        doc.pop("entropy")
        self.assertEqual(doc, self.adapter.get(doc["_id"], ["value"]))

    def test_count(self):
        docs = self._index_many_new_docs(2)
        self.assertEqual(docs_to_dict(docs), self._search_hits_dict({}))
        query = {"query": {"term": {"value": docs[0]["value"]}}}
        self.assertEqual(1, self.adapter.count(query))

    def test_get_docs(self):
        query_docs = self._index_many_new_docs(2)
        query_ids = [doc["_id"] for doc in query_docs]
        no_fetch = self._index_new_doc()
        fetched = docs_to_dict(self.adapter.get_docs(query_ids))
        self.assertNotIn(no_fetch["_id"], fetched)
        self.assertEqual(docs_to_dict(query_docs), fetched)

    # TODO: activate this test -- legacy Elastic code does not check for shard
    # failures on '.get_docs()' calls.
    #def test_get_docs_raises_on_shards_failure(self):
    #    doc = self._index_new_doc()
    #    doc_ids = [doc["_id"]]
    #    self.assertEqual([doc], self.adapter.get_docs(doc_ids))
    #    exc_args, wrapper = self._make_shards_fail({"failed": 1, "test": "val"},
    #                                               self.adapter._mget)
    #    with patch.object(self.adapter, "_mget", wrapper):
    #        with self.assertRaises(ESShardFailure) as test:
    #            self.adapter.get_docs(doc_ids)
    #        self.assertEqual(test.exception.args, exc_args)

    def test_iter_docs(self):
        query_docs = self._index_many_new_docs(4)
        no_fetch = query_docs.pop()
        query_ids = [doc["_id"] for doc in query_docs]
        fetched = self.adapter.iter_docs(query_ids, chunk_size=1)
        self.assertEqual(docs_to_dict(query_docs), docs_to_dict(fetched))
        self.assertNotIn(no_fetch["_id"], fetched)

    def test_iter_docs_chunks_requests(self):
        indexed = self._index_many_new_docs(7)
        query_ids = [doc["_id"] for doc in indexed]
        chunk_size = 2
        chunk_calls = math.ceil(len(indexed) / chunk_size)
        with patch.object(self.adapter, "get_docs", side_effect=self.adapter.get_docs) as patched:
            list(self.adapter.iter_docs(query_ids, chunk_size=chunk_size))
            self.assertEqual(patched.call_count, chunk_calls)

    def test_iter_docs_yields_same_as_get_docs(self):
        query_docs = self._index_many_new_docs(3)
        no_fetch = query_docs.pop()
        query_ids = [doc["_id"] for doc in query_docs]
        fetched = docs_to_dict(self.adapter.get_docs(query_ids))
        chunked = docs_to_dict(self.adapter.iter_docs(query_ids))
        self.assertNotIn(no_fetch["_id"], fetched)
        self.assertEqual(docs_to_dict(query_docs), fetched)
        self.assertEqual(fetched, chunked)

    def test__mget(self):
        one, two = self._index_many_new_docs(2)
        one_id = one.pop("_id")
        result = self.adapter._mget({"ids": [one_id]})
        result_docs_dict = {d["_id"]: d["_source"] for d in result["docs"]}
        self.assertEqual({one_id: one}, result_docs_dict)
        self.assertNotIn(two["_id"], result_docs_dict)

    def test_search(self):
        docs = self._index_many_new_docs(2)
        self.assertEqual(docs_to_dict(docs), self._search_hits_dict({}))

    def test_search_limited_results(self):
        docs = self._index_many_new_docs(2)
        no_fetch = docs.pop()
        query = {"query": {"term": {"value": docs[0]["value"]}}}
        expected = docs_to_dict(docs)
        self.assertEqual(expected, self._search_hits_dict(query))
        self.assertNotIn(no_fetch["_id"], expected)

    def test_search_raises_on_shards_failure(self):
        doc = self._index_new_doc()
        self.assertEqual(docs_to_dict([doc]), self._search_hits_dict({}))  # does not raise
        exc_args, wrapper = self._make_shards_fail({"failed": 1, "test": "val"},
                                                   self.adapter._search)
        with patch.object(self.adapter, "_search", wrapper):
            with self.assertRaises(ESShardFailure) as test:
                self.adapter.search({})
            self.assertEqual(test.exception.args, exc_args)

    def test__search(self):
        docs = self._index_many_new_docs(2)
        result = self.adapter._search({})
        self.assertEqual(set(result), {"took", "timed_out", "_shards", "hits"})
        self.assertEqual(set(result["hits"]), {"total", "max_score", "hits"})
        self.assertIsInstance(result["hits"]["total"], int)
        by_id = docs_to_dict(docs)
        for hit in result["hits"]["hits"]:
            hit.pop("_score")
            doc_id = hit["_id"]
            self.assertEqual(hit, {
                "_index": self.adapter.index_name,
                "_type": self.adapter.type,
                "_id": doc_id,
                "_source": by_id[doc_id],
            })

    def test_scroll(self):
        docs = self._index_many_new_docs(2)
        self.assertEqual(docs_to_dict(docs),
                         self._scroll_hits_dict({}, size=1))

    def test_scroll_yields_same_as_search(self):
        docs = self._index_many_new_docs(3)
        no_fetch = docs.pop()
        query = {"query": {"bool": {"must_not": {"term": {"value": no_fetch["value"]}}}}}
        searched = self._search_hits_dict(query)
        scrolled = self._scroll_hits_dict(query, size=1)
        self.assertNotIn(no_fetch["_id"], searched)
        self.assertEqual(docs_to_dict(docs), searched)
        self.assertEqual(searched, scrolled)

    def test_scroll_raises_on_shards_failure(self):
        docs = self._index_many_new_docs(3)
        self.assertEqual(docs_to_dict(docs), self._scroll_hits_dict({}, size=1))  # should not raise
        exc_args, wrapper = self._make_shards_fail({"failed": 1, "test": "val"},
                                                   self.adapter._es.scroll)
        with patch.object(self.adapter._es, "scroll", side_effect=wrapper) as patched:
            with self.assertRaises(ESShardFailure) as test:
                list(self.adapter.scroll({}, size=1))
            self.assertEqual(test.exception.args, exc_args)
            patched.assert_called_once()

    def test_scroll_cancels_after_exhaustion(self):
        docs = self._index_many_new_docs(3)
        with patch.object(self.adapter._es, "clear_scroll") as patched:
            self.assertEqual(docs_to_dict(docs),
                             self._scroll_hits_dict({}, size=1))
            patched.assert_called_once()

    def test_scroll_cancels_after_failure(self):
        class Bang(Exception):
            pass

        def crash(*args, **kw):
            raise Bang()

        self._index_many_new_docs(2)
        with patch.object(self.adapter._es, "scroll", side_effect=crash) as patched_scl, \
             patch.object(self.adapter._es, "clear_scroll") as patched_clr:
            with self.assertRaises(Bang):
                list(self.adapter.scroll({}, size=1))
            patched_scl.assert_called_once()
            patched_clr.assert_called_once()

    def test__scroll(self):
        docs = self._index_many_new_docs(5)
        top_level = {"_scroll_id", "took", "timed_out", "_shards", "hits"}
        is_first = True
        for result in self.adapter._scroll({}, size=2):
            self.assertEqual(set(result), top_level)
            if is_first:
                top_level.add("terminated_early")
                is_first = False
            self.assertEqual(set(result["hits"]), {"total", "max_score", "hits"})
            self.assertIsInstance(result["hits"]["total"], int)
            by_id = docs_to_dict(docs)
            for hit in result["hits"]["hits"]:
                hit.pop("_score")
                hit.pop("sort")
                doc_id = hit["_id"]
                self.assertEqual(hit, {
                    "_index": self.adapter.index_name,
                    "_type": self.adapter.type,
                    "_id": doc_id,
                    "_source": by_id[doc_id],
                })

    def test_scroll_no_searchtype_scan(self):
        """Tests that search_type='scan' is not added to the search parameters"""
        self._validate_scroll_search_params({}, {"sort": "_doc"})

    def test_scroll_query_extended(self):
        """Tests that sort=_doc is added to an non-empty query"""
        self._validate_scroll_search_params({"_id": "abc"},
                                            {"_id": "abc", "sort": "_doc"})

    def test_scroll_query_sort_safe(self):
        """Tests that a provided ``sort`` query will not be overwritten"""
        self._validate_scroll_search_params({"sort": "_id"}, {"sort": "_id"})

    def _validate_scroll_search_params(self, scroll_query, search_query):
        """Call adapter.scroll() and test that the resulting API search
        parameters match what we expect.

        Notably:
        - Search call does not include ``search_type='scan'``.
        - Calling ``scroll(query=scroll_query)`` results in an API call
          where ``body == search_query``.
        """
        scroll_kw = {
            "scroll": "1m",
            "size": 10,
        }
        with patch.object(self.adapter._es, "search", return_value={}) as search:
            list(self.adapter.scroll(scroll_query, **scroll_kw))
            search.assert_called_once_with(self.adapter.index_name,
                                           self.adapter.type, search_query,
                                           **scroll_kw)

    def test_scroll_ambiguous_size_raises(self):
        query = {"size": 1}
        with self.assertRaises(ValueError):
            list(self.adapter.scroll(query, size=1))

    def test_scroll_query_size_as_keyword(self):
        docs = self._index_many_new_docs(3)
        self._test_scroll_backend_calls({}, len(docs), size=1)

    def test_scroll_query_size_in_query(self):
        docs = self._index_many_new_docs(3)
        self._test_scroll_backend_calls({"size": 1}, len(docs))

    @patch("corehq.apps.es.client.SCROLL_SIZE", 1)
    def test_scroll_size_default(self):
        docs = self._index_many_new_docs(3)
        self._test_scroll_backend_calls({}, len(docs))

    def _test_scroll_backend_calls(self, query, call_count, **scroll_kw):
        _search = self.adapter._es.search
        _scroll = self.adapter._es.scroll
        with patch.object(self.adapter._es, "search", side_effect=_search) as search, \
             patch.object(self.adapter._es, "scroll", side_effect=_scroll) as scroll:
            list(self.adapter.scroll(query, **scroll_kw))
            # NOTE: scroll.call_count == call_count because the final
            # `client.scroll()`` call returns zero hits (ending the generator).
            # Call sequence (for 3 matched docs with size=1):
            # - len(client.search(...)["hits"]["hits"]) == 1
            # - len(client.scroll(...)["hits"]["hits"]) == 1
            # - len(client.scroll(...)["hits"]["hits"]) == 1
            # - len(client.scroll(...)["hits"]["hits"]) == 0
            search.assert_called_once()
            self.assertEqual(scroll.call_count, call_count)

    def test_scroll_returns_over_2x_size_docs(self):
        """Test that all results are returned for scroll queries."""
        scroll_size = 3  # fetch N docs per "scroll"
        total_docs = (scroll_size * 2) + 1
        docs = self._index_many_new_docs(total_docs)
        self.assertEqual(len(docs), total_docs)
        self.assertEqual(docs_to_dict(docs),
                         self._scroll_hits_dict({}, size=scroll_size))

    def test_index(self):
        doc = self._make_doc()
        self.assertEqual({}, self._search_hits_dict({}))
        self.adapter.index(doc, refresh=True)
        self.assertEqual([self.adapter.to_json(doc)],
                         docs_from_result(self.adapter.search({})))

    def test_index_fails_with_invalid_id(self):
        doc = self._make_doc()
        doc.id = None
        with self.assertRaises(ValueError):
            self.adapter.index(doc, refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_index_fails_with_invalid_source(self):
        doc = self._make_doc()
        bad_source = self.adapter.to_json(doc)
        invalid = (doc.id, bad_source)
        with patch.object(self.adapter, "from_python", return_value=invalid):
            with self.assertRaises(ValueError):
                self.adapter.index(doc, refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_index_succeeds_if_exists(self):
        doc = self._make_doc()
        self.adapter.index(doc, refresh=True)
        self.assertEqual([self.adapter.to_json(doc)],
                         docs_from_result(self.adapter.search({})))
        self.adapter.index(doc, refresh=True)  # does not raise

    def test_index_with_change_succeeds_if_exists(self):
        doc = self._make_doc()
        doc_id = doc.id
        self.adapter.index(doc, refresh=True)
        self.assertEqual([self.adapter.to_json(doc)],
                         docs_from_result(self.adapter.search({})))
        doc.value = self._make_doc().value  # modify the doc
        self.assertEqual(doc.id, doc_id)  # confirm it has the same ID
        self.adapter.index(doc, refresh=True)  # does not raise
        self.assertEqual([self.adapter.to_json(doc)],
                         docs_from_result(self.adapter.search({})))

    def test_update(self):
        doc = self._index_new_doc()
        self.assertEqual([doc], docs_from_result(self.adapter.search({})))
        doc["value"] = self._make_doc().value  # modify the doc
        self.adapter.update(doc["_id"], {"value": doc["value"]}, refresh=True)
        self.assertEqual([doc], docs_from_result(self.adapter.search({})))

    def test_update_tolerates_id_in_fields(self):
        doc = self._index_new_doc()
        doc["value"] = self._make_doc().value  # modify the doc
        self.adapter.update(doc["_id"], doc, refresh=True)  # does not raise
        self.assertEqual([doc], docs_from_result(self.adapter.search({})))

    def test_update_fails_ambiguous_id_values(self):
        doc = self._make_doc()
        with self.assertRaises(ValueError):
            self.adapter.update(doc.id, {"_id": f"{doc.id}x", "value": "test"},
                                refresh=True)
        self.assertEqual([], docs_from_result(self.adapter.search({})))

    def test_update_fails_if_missing(self):
        self.assertEqual([], docs_from_result(self.adapter.search({})))
        doc = self._make_doc()
        with self.assertRaises(TransportError) as test:
            self.adapter.update(doc.id, {"value": "test"}, refresh=True)
        self.assertEqual(test.exception.status_code, 404)
        self.assertEqual(test.exception.error, "document_missing_exception")
        self.assertEqual([], docs_from_result(self.adapter.search({})))

    def test_delete(self):
        doc = self._index_new_doc()
        self.assertEqual([doc], docs_from_result(self.adapter.search({})))
        self.adapter.delete(doc["_id"], refresh=True)
        self.assertEqual([], docs_from_result(self.adapter.search({})))

    def test_delete_fails_if_missing(self):
        missing_id = self._make_doc().id
        self.assertEqual([], docs_from_result(self.adapter.search({})))
        with self.assertRaises(TransportError) as test:
            self.adapter.delete(missing_id)
        self.assertEqual(test.exception.status_code, 404)
        error_info = test.exception.info
        error_info.pop("_version")
        error_info.pop("_shards")
        self.assertEqual(error_info, {
            "found": False,
            "_index": self.adapter.index_name,
            "_type": self.adapter.type,
            "_id": missing_id,
        })

    def test_bulk(self):
        def tform_to_dict(docs):
            return docs_to_dict(self.adapter.to_json(doc) for doc in docs)
        self.assertEqual({}, self._search_hits_dict({}))
        docs = [self._make_doc() for x in range(2)]
        self.adapter.bulk([BulkActionItem.index(doc) for doc in docs], refresh=True)
        self.assertEqual(tform_to_dict(docs), self._search_hits_dict({}))
        self.adapter.bulk([BulkActionItem.delete(doc) for doc in docs], refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_bulk_iterates_actions_only_once(self):
        """Ensure the ``bulk()`` method supports generators and does not attempt
        to iterate over its ``actions`` argument more than once.
        """
        doc = self._make_doc()
        actions = OneshotIterable([BulkActionItem.index(doc)])
        self.adapter.bulk(actions)  # does not raise IterableExhaustedError

    def test_bulk_index_iterates_docs_only_once(self):
        """Ensure the ``bulk_index()`` method supports generators and does not
        attempt to iterate over its ``docs`` argument more than once.
        """
        doc = self._make_doc()
        docs = OneshotIterable([doc])
        self.adapter.bulk_index(docs)  # does not raise IterableExhaustedError

    def test_bulk_delete_iterates_doc_ids_only_once(self):
        """Ensure the ``bulk_delete()`` method supports generators and does not
        attempt to iterate over its ``doc_ids`` argument more than once.
        """
        doc = self._index_new_doc()
        doc_ids = OneshotIterable([doc["_id"]])
        self.adapter.bulk_delete(doc_ids)  # does not raise IterableExhaustedError

    def test_bulk_index_and_delete(self):
        def tform_to_dict(docs):
            return docs_to_dict(self.adapter.to_json(doc) for doc in docs)
        docs = [self._make_doc() for x in range(2)]
        self.adapter.bulk_index(docs, refresh=True)
        self.assertEqual(tform_to_dict(docs), self._search_hits_dict({}))
        docs.append(self._make_doc())
        actions = [
            BulkActionItem.delete(docs.pop(0)),  # delete first
            BulkActionItem.index(docs[-1]),  # index new
        ]
        self.adapter.bulk(actions, refresh=True)
        self.assertEqual(tform_to_dict(docs), self._search_hits_dict({}))

    def test_bulk_index(self):
        docs = []
        serialized = []
        for x in range(3):
            doc = self._make_doc()
            docs.append(doc)
            serialized.append(self.adapter.to_json(doc))
        self.assertEqual({}, self._search_hits_dict({}))
        self.adapter.bulk_index(docs, refresh=True)
        self.assertEqual(docs_to_dict(serialized), self._search_hits_dict({}))

    def test_bulk_index_fails_with_invalid_id(self):
        docs = [self._make_doc() for x in range(2)]
        docs[0].id = None
        with self.assertRaises(ValueError):
            self.adapter.bulk_index(docs, refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_bulk_index_fails_with_invalid_source(self):
        doc = self._make_doc()
        bad_source = self.adapter.to_json(doc)
        invalid = (doc.id, bad_source)
        with patch.object(self.adapter, "from_python", return_value=invalid):
            with self.assertRaises(ValueError):
                self.adapter.bulk_index([doc], refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_bulk_delete(self):
        docs = self._index_many_new_docs(3)
        self.assertEqual(docs_to_dict(docs), self._search_hits_dict({}))
        self.adapter.bulk_delete([d["_id"] for d in docs], refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test_bulk_delete_fails_with_invalid_id(self):
        with self.assertRaises(ValueError):
            self.adapter.bulk_delete(["1", ""], refresh=True)
        self.assertEqual({}, self._search_hits_dict({}))

    def test__report_and_fail_on_shard_failures(self):
        result = self.adapter._search({})
        # in case this test search actually had a shard failure...
        result["_shards"] = {"failed": 0}
        self.adapter._report_and_fail_on_shard_failures(result)  # does not raise

    def test__report_and_fail_on_shard_failures_raises_on_shard_failure(self):
        shard_result = {"failed": 5, "test": True}
        shard_exc_args = (f"_shards: {json.dumps(shard_result)}",)
        result = self.adapter._search({})
        result["_shards"] = shard_result
        with self.assertRaises(ESShardFailure) as test:
            self.adapter._report_and_fail_on_shard_failures(result)
        self.assertEqual(test.exception.args, shard_exc_args)

    def test__report_and_fail_on_shard_failures_with_invalid_result_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.adapter._report_and_fail_on_shard_failures([])

    def _index_many_new_docs(self, count, refresh=True):
        docs = []
        for x in range(count):
            docs.append(self._index_new_doc(refresh=False))
        if refresh:
            self.adapter.refresh_index()
        return docs

    def _index_new_doc(self, refresh=True):
        doc = self._make_doc()
        self.adapter.index(doc, refresh=refresh)
        return self.adapter.to_json(doc)

    def _make_doc(self, value=None):
        if value is None:
            if not hasattr(self, "_doc_value_history"):
                self._doc_value_history = 0
            value = f"test doc {self._doc_value_history:04}"
            self._doc_value_history += 1
        return TestDoc(uuid.uuid4().hex, value)

    def _search_hits_dict(self, query):
        """Convenience method for getting a ``dict`` of search results.

        :param query: ``dict`` search query (default: ``{}``)
        :returns: ``{<doc_id>: <doc_sans_id>, ...}`` dict
        """
        return docs_to_dict(docs_from_result(self.adapter.search(query)))

    def _scroll_hits_dict(self, query, **kw):
        def do_scroll():
            for doc in self.adapter.scroll(query, **kw):
                yield doc["_source"]
        return docs_to_dict(do_scroll())

    @staticmethod
    def _make_shards_fail(shards_obj, result_getter):
        def wrapper(*args, **kw):
            result = result_getter(*args, **kw)
            result["_shards"] = shards_obj
            return result
        exc_args = (f"_shards: {json.dumps(shards_obj)}",)
        return exc_args, wrapper


@es_test
class TestElasticDocumentAdapterWithoutRequests(AdapterTestCase):
    """Document adapter tests that don't need to hit the Elastic backend."""

    adapter_class = TestDocumentAdapterWithExtras

    def test_from_python(self):
        doc = TestDoc("1", "test")
        from_python = (doc.id, {"value": doc.value, "entropy": doc.entropy})
        self.assertEqual(from_python, self.adapter.from_python(doc))

    def test_to_json(self):
        doc = TestDoc("1", "test")
        as_json = {"_id": doc.id, "value": doc.value, "entropy": doc.entropy}
        self.assertEqual(as_json, self.adapter.to_json(doc))

    def test_to_json_id_null(self):
        doc = TestDoc(None, "test")
        as_json = {"value": doc.value, "entropy": doc.entropy}
        self.assertEqual(as_json, self.adapter.to_json(doc))

    def test__prepare_count_query(self):
        query = {k: "remove" for k in ["size", "sort", "from", "to", "_source"]}
        query["key"] = "keep"
        self.assertEqual({"key": "keep"}, self.adapter._prepare_count_query(query))

    def test__render_bulk_action_index(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.index(doc)
        doc_id, source = self.adapter.from_python(doc)
        expected = {
            "_index": self.adapter.index_name,
            "_type": self.adapter.type,
            "_op_type": "index",
            "_id": doc_id,
            "_source": source,
        }
        self.assertEqual(expected, self.adapter._render_bulk_action(action))

    def test__render_bulk_action_delete(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.delete(doc)
        expected = {
            "_index": self.adapter.index_name,
            "_type": self.adapter.type,
            "_op_type": "delete",
            "_id": doc.id,
        }
        self.assertEqual(expected, self.adapter._render_bulk_action(action))

    def test__render_bulk_action_delete_id(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.delete_id(doc.id)
        expected = {
            "_index": self.adapter.index_name,
            "_type": self.adapter.type,
            "_op_type": "delete",
            "_id": doc.id,
        }
        self.assertEqual(expected, self.adapter._render_bulk_action(action))

    def test__render_bulk_action_fails_unsupported_action(self):
        from enum import Enum

        class SpecialBulkActionItem(BulkActionItem):

            OpType = Enum("OpType", "index delete create")

            @classmethod
            def create(cls, doc):
                return cls(cls.OpType.create, doc=doc)

        action = SpecialBulkActionItem.create(TestDoc("1", "test"))
        with self.assertRaises(ValueError) as test:
            self.adapter._render_bulk_action(action)
        self.assertIn("unsupported action type", str(test.exception))

    def test__render_bulk_action_fails_invalid_ids(self):
        bad = TestDoc(id="")
        with self.assertRaises(ValueError):
            self.adapter._render_bulk_action(BulkActionItem.delete(bad))
        with self.assertRaises(ValueError):
            self.adapter._render_bulk_action(BulkActionItem.delete_id(bad.id))
        with self.assertRaises(ValueError):
            self.adapter._render_bulk_action(BulkActionItem.index(bad))

    def test__verify_doc_id(self):
        self.adapter._verify_doc_id("abc")  # should not raise

    def test__verify_doc_id_fails_empty_string(self):
        with self.assertRaises(ValueError):
            self.adapter._verify_doc_id("")

    def test__verify_doc_id_fails_non_strings(self):
        for invalid in [None, True, False, 123, 1.23]:
            with self.assertRaises(ValueError):
                self.adapter._verify_doc_id(invalid)

    def test__verify_doc_source(self):
        # does not raise
        self.adapter._verify_doc_source({"value": "test", "entropy": 3})

    def test__verify_doc_source_fails_if_not_dict(self):
        with self.assertRaises(ValueError):
            self.adapter._verify_doc_source(["1"])

    def test__verify_doc_source_fails_if_id_present(self):
        with self.assertRaises(ValueError):
            self.adapter._verify_doc_source({"_id": "1", "value": "test"})

    def test__fix_hit(self):
        doc_id = "abc"
        hit = {"_id": doc_id, "_source": {"test": True}}
        expected = deepcopy(hit)
        expected["_source"]["_id"] = doc_id
        self.adapter._fix_hit(hit)
        self.assertEqual(expected, hit)

    def test__fix_hits_in_result(self):
        ids = ["abc", "def"]
        result = {"hits": {"hits": [
            {"_id": ids[0], "_source": {"test": True}},
            {"_id": ids[1], "_source": {"test": True}},
        ]}}
        expected = deepcopy(result)
        expected["hits"]["hits"][0]["_source"]["_id"] = ids[0]
        expected["hits"]["hits"][1]["_source"]["_id"] = ids[1]
        self.adapter._fix_hits_in_result(result)
        self.assertEqual(expected, result)


@es_test
class TestBulkActionItem(SimpleTestCase):

    def test_delete(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.delete(doc)
        self.assertIs(action.op_type, BulkActionItem.OpType.delete)
        self.assertIs(action.doc, doc)
        self.assertIsNone(action.doc_id)
        self.assertTrue(action.is_delete)
        self.assertFalse(action.is_index)

    def test_delete_id(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.delete_id(doc.id)
        self.assertIs(action.op_type, BulkActionItem.OpType.delete)
        self.assertIsNone(action.doc)
        self.assertEqual(action.doc_id, doc.id)
        self.assertTrue(action.is_delete)
        self.assertFalse(action.is_index)

    def test_index(self):
        doc = TestDoc("1", "test")
        action = BulkActionItem.index(doc)
        self.assertIs(action.op_type, BulkActionItem.OpType.index)
        self.assertIs(action.doc, doc)
        self.assertIsNone(action.doc_id)
        self.assertFalse(action.is_delete)
        self.assertTrue(action.is_index)

    def test_create_fails_with_invalid_action(self):
        doc = TestDoc("1", "test")
        with self.assertRaises(ValueError):
            BulkActionItem("index", doc=doc)

    def test_create_fails_without_doc_params(self):
        with self.assertRaises(ValueError):
            BulkActionItem(BulkActionItem.OpType.delete)
        with self.assertRaises(ValueError):
            BulkActionItem(BulkActionItem.OpType.index)

    def test_create_fails_with_multiple_doc_params(self):
        doc = TestDoc("1", "test")
        with self.assertRaises(ValueError):
            BulkActionItem(BulkActionItem.OpType.delete, doc=doc, doc_id=doc.id)

    def test_create_fails_with_doc_id_for_index(self):
        with self.assertRaises(ValueError):
            BulkActionItem(BulkActionItem.OpType.index, doc_id="1")

    def test_index___eq__(self):
        doc = TestDoc("1", "test")
        self.assertEqual(
            BulkActionItem.index(doc),
            BulkActionItem.index(doc),
        )
        self.assertNotEqual(
            BulkActionItem.index(doc),
            BulkActionItem.index(TestDoc("2", "test")),
        )

    def test_delete___eq__(self):
        doc = TestDoc("1", "test")
        self.assertEqual(
            BulkActionItem.delete(doc),
            BulkActionItem.delete(doc),
        )
        self.assertNotEqual(
            BulkActionItem.delete(doc),
            BulkActionItem.delete(TestDoc("2", "test")),
        )

    def test_delete_id___eq__(self):
        doc_id = "1"
        self.assertEqual(
            BulkActionItem.delete_id(doc_id),
            BulkActionItem.delete_id(doc_id),
        )
        self.assertNotEqual(
            BulkActionItem.delete_id(doc_id),
            BulkActionItem.delete_id("2"),
        )

    def test_delete_delete_and_delete_id_not_equal(self):
        """Bulk delete items are not equal when instantiated via different args
        because the BulkActionItem cannot know that an ID belongs to a specifc
        document (the ID alone does not carry sufficient information to make
        this connection).
        """
        doc = TestDoc("1", "test")
        self.assertNotEqual(
            BulkActionItem.delete(doc),
            BulkActionItem.delete_id(doc.id),
        )


class OneshotIterable:

    def __init__(self, items):
        self.items = items
        self.exhausted = False

    def __iter__(self):
        if self.exhausted:
            raise IterableExhaustedError("cannot iterate items more than once")
        yield from self.items
        self.exhausted = True


class IterableExhaustedError(Exception):
    pass
