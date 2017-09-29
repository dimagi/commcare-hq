from django.test import TestCase

from ..models import SerialIdBucket


class SerialIDTest(TestCase):
    domain = 'serial_id_tests'

    def tearDown(self):
        SerialIdBucket.objects.all().delete()

    def test_basic_usage(self):
        self.assertEqual(0, SerialId.get_next(self.domain, 'testbucket'))
        self.assertEqual(0, SerialId.get_next(self.domain, 'other_bucket'))
        self.assertEqual(1, SerialId.get_next(self.domain, 'testbucket'))
        self.assertEqual(2, SerialId.get_next(self.domain, 'testbucket'))
        self.assertEqual(1, SerialId.get_next(self.domain, 'other_bucket'))
