from mock import patch, Mock

from django.test import SimpleTestCase
from django.conf import settings

from ..s3 import ObjectStore


class ObjectStoreTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @patch('boto3.resource')
    def test_initialize_object_store(self, resource_mock):
        resource = Mock()
        resource_mock.return_value = resource

        ObjectStore()
        self.assertEqual('s3', resource_mock.call_args[0][0])

    @patch('boto3.resource')
    def test_bucket_name(self, _):
        object_store = ObjectStore()
        name = object_store.bucket_name
        self.assertEqual(name, settings.RIAKCS_DEFAULT_BUCKET)

        object_store = ObjectStore(domain='ben')
        name = object_store.bucket_name
        self.assertEqual(name, 'ben')
