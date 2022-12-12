from django.test import SimpleTestCase
from unittest.mock import patch

from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test

from ..service_checks import check_elasticsearch


@es_test(requires=[group_adapter])
class TestCheckElasticsearch(SimpleTestCase):

    class Fail(Exception):
        pass

    def test_check_elasticsearch(self):
        status = check_elasticsearch()
        self.assertTrue(status.success)
        self.assertEqual(status.msg, "Successfully sent a doc to ES and read it back")
        self.assertIsNone(status.exception)

    def test_check_elasticsearch_passes_for_cluster_yellow(self):
        with patch("corehq.apps.hqadmin.service_checks.check_es_cluster_health", return_value="yellow") as mock:
            from corehq.apps.hqadmin.service_checks import check_es_cluster_health
            self.assertEqual("yellow", check_es_cluster_health())
            mock.reset_mock()
            self.assertTrue(check_elasticsearch().success)
        mock.assert_called_once()

    def test_check_elasticsearch_fails_for_cluster_red(self):
        with patch("corehq.apps.hqadmin.service_checks.check_es_cluster_health", return_value="red"):
            status = check_elasticsearch()
        self.assertFalse(status.success)
        self.assertEqual(status.msg, "Cluster health at red")
        self.assertIsNone(status.exception)

    def test_check_elasticsearch_fails_with_exc_if_group_doc_index_raises(self):
        with patch.object(group_adapter, "index", side_effect=self.Fail) as mock:
            status = check_elasticsearch()
        mock.assert_called_once()
        self.assertFalse(status.success)
        self.assertEqual(status.msg, "Something went wrong sending a doc to ES")
        self.assertIsInstance(status.exception, self.Fail)

    def test_check_elasticsearch_fails_with_exc_if_group_doc_delete_raises(self):
        with patch.object(group_adapter, "delete", side_effect=self.Fail) as mock:
            status = check_elasticsearch()
        mock.assert_called_once()
        self.assertFalse(status.success)
        self.assertEqual(status.msg, "Something went wrong sending a doc to ES")
        self.assertIsInstance(status.exception, self.Fail)

    def test_check_elasticsearch_fails_if_indexed_doc_is_missing(self):
        with patch.object(group_adapter, "index", return_value=None) as mock:
            status = check_elasticsearch()
        mock.assert_called_once()
        self.assertFalse(status.success)
        self.assertEqual(status.msg, "Something went wrong sending a doc to ES")
        self.assertRegex(
            str(status.exception),
            r"^Indexed doc not found: elasticsearch-service-check-",
        )
