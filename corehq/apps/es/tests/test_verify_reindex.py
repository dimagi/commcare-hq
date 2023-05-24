from io import StringIO
from unittest import mock
from django.test import SimpleTestCase
from corehq.apps.es.management.commands.verify_reindex import Command as reindex_verify
from django.core.management import call_command


class TestVerifyReindex(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.error_log = "[2023-05-23 08:05:48,875][INFO][tasks] 25286904 finished with response ReindexResponse[took=1m,updated=0,created=0,batches=1,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[org.elasticsearch.action.bulk.BulkItemResponse$Failure@13ad032b, org.elasticsearch.action.bulk.BulkItemResponse$Failure@48125afb, org.elasticsearch.action.bulk.BulkItemResponse$Failure@6bf4625c],search_failures=[]]" # noqa E501

        cls.cancelled_log = "[2023-05-23 07:59:15,469][INFO ][tasks] 25286746 finished with response ReindexResponse[took=1m,updated=0,created=0,batches=1,versionConflicts=0,noops=0,retries=0,canceled=by user request,throttledUntil=0s,indexing_failures=[],search_failures=[]]" # noqa E501

        cls.success_log = "[2023-05-23 08:59:37,648][INFO ][tasks] 29216 finished with response ReindexResponse[took=1.8s,updated=0,created=1111,batches=2,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[],search_failures=[]]" # noqa E501

        return super().setUpClass()

    def test__parse_reindex_response_with_success_log(self):
        output = reindex_verify()._parse_reindex_response(self.success_log)
        expected_output = {'took': '1.8s', 'updated': '0', 'created': '1111', 'batches': '2', 'versionConflicts': '0', 'noops': '0', 'retries': '0', 'throttledUntil': '0s', 'indexing_failures': [], 'search_failures': []} # noqa E501

        self.assertEqual(output, expected_output)

    def test__parse_reindex_response_with_error_logs(self):
        output = reindex_verify()._parse_reindex_response(self.error_log)

        expected_output = {'took': '1m', 'updated': '0', 'created': '0', 'batches': '1', 'versionConflicts': '0', 'noops': '0', 'retries': '0', 'throttledUntil': '0s', 'indexing_failures': ['org.elasticsearch.action.bulk.BulkItemResponse$Failure@13ad032b', 'org.elasticsearch.action.bulk.BulkItemResponse$Failure@48125afb', 'org.elasticsearch.action.bulk.BulkItemResponse$Failure@6bf4625c'], 'search_failures': []} # noqa E501

        self.assertEqual(output, expected_output)

    def test_verify_reindex_command_with_error_log(self):
        output = StringIO()
        with mock.patch('sys.stdout', output):
            call_command('verify_reindex', '--eslog', self.error_log, stdout=output)

        expected_log = "Reindex Failed because of Indexing Failures - ['org.elasticsearch.action.bulk.BulkItemResponse$Failure@13ad032b', 'org.elasticsearch.action.bulk.BulkItemResponse$Failure@48125afb', 'org.elasticsearch.action.bulk.BulkItemResponse$Failure@6bf4625c']\n" # noqa E501

        self.assertEqual(output.getvalue(), expected_log)

    def test_verify_reindex_command_with_success_log(self):
        output = StringIO()
        with mock.patch('sys.stdout', output):
            call_command('verify_reindex', '--eslog', self.success_log, stdout=output)
        self.assertEqual(output.getvalue(), "Reindex Successful -\n")

    def test_verify_reindex_command_with_cancelled_log(self):
        output = StringIO()
        with mock.patch('sys.stdout', output):
            call_command('verify_reindex', '--eslog', self.cancelled_log, stdout=output)

        self.assertEqual(output.getvalue(), "Reindex cancelled becuase - by user request\n")

    def test_verify_reindex_command_with_invalid_log(self):
        log = "Some weird log entry"
        with self.assertRaises(ValueError):
            call_command('verify_reindex', '--eslog', log)
