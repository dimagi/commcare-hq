from __future__ import absolute_import
from __future__ import unicode_literals
from unittest import expectedFailure
from django.test import SimpleTestCase
from elasticsearch import Elasticsearch
from .utils import require_elasticsearch


class RequireElasticsearchTest(SimpleTestCase):

    def test_fail_on_assert_errors(self):
        @expectedFailure
        @require_elasticsearch
        def fail_hard():
            self.fail('This should fail')
        fail_hard()

    def test_fail_on_random_errors(self):
        @require_elasticsearch
        def raise_error():
            raise Exception('Fail!')
        with self.assertRaises(Exception):
            raise_error()

    def test_no_fail_on_elasticsearch_errors(self):
        @require_elasticsearch
        def elasticsearch_fail():
            es = Elasticsearch([{'host': 'example.com', 'port': 9999}], timeout=0.1)
            es.info()
        elasticsearch_fail()
