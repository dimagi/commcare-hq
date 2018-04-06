from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TransactionTestCase

from ..models import SerialIdBucket


# The standard TestCase wraps everything in a transaction, which can obscure
# issues related to atomicity.  Enter TransactionTestCase.
class SerialIDTest(TransactionTestCase):
    domain = 'serial_id_tests'

    def tearDown(self):
        SerialIdBucket.objects.all().delete()

    def get_next(self, bucket_id, session_id=None):
        """Light wrapper that handles wiping the cache at the end of the test"""
        self.addCleanup(lambda: SerialIdBucket._get_next_cached.clear(
            SerialIdBucket, self.domain, bucket_id, session_id))
        return SerialIdBucket.get_next(self.domain, bucket_id, session_id)

    def test_basic_usage(self):
        self.assertEqual(0, self.get_next('testbucket'))
        self.assertEqual(0, self.get_next('other_bucket'))
        self.assertEqual(1, self.get_next('testbucket'))
        self.assertEqual(2, self.get_next('testbucket'))
        self.assertEqual(1, self.get_next('other_bucket'))

    def test_session_caching(self):
        self.assertEqual(0, self.get_next('testbucket', 'session1'))
        self.assertEqual(1, self.get_next('testbucket', 'session2'))
        self.assertEqual(0, self.get_next('testbucket', 'session1'))
        self.assertEqual(2, self.get_next('testbucket'))
