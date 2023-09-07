import uuid
from unittest import mock

from django.test import SimpleTestCase

from pillowtop.processors.elastic import send_to_elasticsearch

from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.util.es.elasticsearch import ConnectionError, RequestError
from corehq.util.test_utils import capture_log_output

from .utils import get_pillow_doc_adapter


@es_test(requires=[get_pillow_doc_adapter()])
class TestSendToElasticsearch(SimpleTestCase):

    def setUp(self):
        self.adapter = get_pillow_doc_adapter()

    def test_create_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)
        res = self.adapter.get(doc['_id'])
        self.assertEqual(res, doc)

    def _send_to_es_and_check(self, doc, update=False, es_merge_update=False,
                              delete=False, esgetter=None):
        if update and es_merge_update:
            old_doc = self.adapter.get(doc['_id'])

        self._send_to_es(doc, es_merge_update=es_merge_update, delete=delete)

        manager.index_refresh(self.adapter.index_name)

        if not delete:
            self.assertEqual(1, self.adapter.count({}))
            es_doc = self.adapter.get(doc['_id'])
            if es_merge_update:
                old_doc.update(es_doc)
                for prop in doc:
                    self.assertEqual(doc[prop], old_doc[prop])
            else:
                for prop in doc:
                    self.assertEqual(doc[prop], es_doc[prop])
                self.assertTrue(all(prop in doc for prop in es_doc))
        else:
            self.assertEqual(0, self.adapter.count({}))

    def _send_to_es(self, doc, es_merge_update=False, delete=False):
        send_to_elasticsearch(
            adapter=self.adapter,
            doc_id=doc['_id'],
            name='test',
            data=doc,
            es_merge_update=es_merge_update,
            delete=delete
        )

    def test_update_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        doc['property'] = 'bazz'
        self._send_to_es_and_check(doc, update=True)

    def test_replace_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        del doc['property']
        self._send_to_es_and_check(doc, update=True)

    def test_merge_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        update = doc.copy()
        del update['property']
        update['new_prop'] = 'new_val'
        # merging should still keep old 'property'
        self._send_to_es_and_check(update, update=True, es_merge_update=True)

    def test_delete_doc(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc)

        self._send_to_es_and_check(doc, delete=True)

    def test_missing_delete(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        self._send_to_es_and_check(doc, delete=True)

    def test_missing_merge(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}
        send_to_elasticsearch(self.adapter, doc['_id'], 'test', data=doc, es_merge_update=True)
        self.assertEqual(0, self.adapter.count({}))

    def test_connection_failure_no_error(self):
        logs = self._send_to_es_mock_errors(ConnectionError("test", "test", "test"), 2)
        self.assertIn("put_robust error", logs)
        self.assertIn("Max retry error", logs)

    def test_request_error(self):
        logs = self._send_to_es_mock_errors(RequestError("test", "test", "test"), 1)
        self.assertIn("put_robust error", logs)

    def _send_to_es_mock_errors(self, exception, retries):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        with mock.patch("pillowtop.processors.elastic._propagate_failure", return_value=False), \
             mock.patch("pillowtop.processors.elastic._retries", return_value=retries), \
             mock.patch("pillowtop.processors.elastic._sleep_between_retries"), \
             mock.patch.object(self.adapter, 'index') as doc_adapter, \
             capture_log_output("pillowtop") as log:
            doc_adapter.side_effect = exception
            send_to_elasticsearch(self.adapter, doc['_id'], name='test', data=doc)
        return log.get_output()

    def test_not_found(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'bar'}

        self._send_to_es_and_check(doc, delete=True)

    def test_conflict(self):
        doc = {'_id': uuid.uuid4().hex, 'doc_type': 'MyCoolDoc', 'property': 'foo'}
        self._send_to_es_and_check(doc)

        # attempt to create the same doc twice shouldn't fail
        self._send_to_es_and_check(doc)
