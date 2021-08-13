from django.test import SimpleTestCase
from mock import ANY, patch

from corehq.apps.es.tests.utils import es_test
from corehq.elastic import SerializationError, get_es_new
from corehq.util.es.interface import ElasticsearchInterface


@es_test
class TestESInterface(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.es = get_es_new()

    def _validate_es_scan_search_params(self, scan_query, search_query):
        """Call ElasticsearchInterface.scan() and test that the resulting API
        search parameters match what we expect.

        Notably:
        - Search call does not include the `search_type='scan'`.
        - Calling `scan(..., query=scan_query, ...)` results in an API call
          where `body == search_query`.
        """
        interface = ElasticsearchInterface(self.es)
        skw = {
            "index": "et",
            "doc_type": "al",
            "request_timeout": ANY,
            "scroll": ANY,
            "size": ANY,
        }
        with patch.object(self.es, "search") as search:
            try:
                list(interface.scan(skw["index"], scan_query, skw["doc_type"]))
            except SerializationError:
                # fails to serialize the Mock object.
                pass
            search.assert_called_once_with(body=search_query, **skw)

    def test_scan_no_searchtype_scan(self):
        """Tests that search_type='scan' is not added to the search parameters"""
        self._validate_es_scan_search_params({}, {"sort": "_doc"})

    def test_scan_query_extended(self):
        """Tests that sort=_doc is added to an non-empty query"""
        self._validate_es_scan_search_params({"_id": "abc"},
                                             {"_id": "abc", "sort": "_doc"})

    def test_scan_query_sort_safe(self):
        """Tests that a provided a `sort` query will not be overwritten"""
        self._validate_es_scan_search_params({"sort": "_id"}, {"sort": "_id"})
