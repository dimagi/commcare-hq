
import six
import uuid

from django.conf import settings
from django.test import TestCase
from mock import MagicMock

from pillow_retry.models import PillowError
from pillowtop import get_all_pillow_configs
from pillowtop.dao.exceptions import DocumentMissingError
from pillowtop.feed.interface import Change


class ExceptionA(Exception):
    pass


class PillowtopRetryAllPillowsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(PillowtopRetryAllPillowsTests, cls).setUpClass()
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS
        super(PillowtopRetryAllPillowsTests, cls).tearDownClass()

    def tearDown(self):
        PillowError.objects.all().delete()

    def test_all_pillows_handle_errors(self):
        all_pillow_configs = list(get_all_pillow_configs())
        for pillow_config in all_pillow_configs:
            self._test_error_logging_for_pillow(pillow_config)

    def _test_error_logging_for_pillow(self, pillow_config):
        pillow = _pillow_instance_from_config_with_mock_process_change(pillow_config)
        if pillow.retry_errors:
            exc_class = Exception
            if six.PY3:
                exc_class_string = 'builtins.Exception'
            else:
                exc_class_string = 'exceptions.Exception'
        else:
            exc_class = DocumentMissingError
            exc_class_string = 'pillowtop.dao.exceptions.DocumentMissingError'

        pillow.process_change = MagicMock(side_effect=exc_class(pillow.pillow_id))
        doc = self._get_random_doc()
        pillow.process_with_error_handling(
            Change(id=doc['id'], sequence_id='3', document=doc),
        )

        errors = PillowError.objects.filter(pillow=pillow.pillow_id).all()
        self.assertEqual(1, len(errors), pillow_config)
        error = errors[0]
        self.assertEqual(error.doc_id, doc['id'], pillow_config)
        self.assertEqual(exc_class_string, error.error_type)
        self.assertIn(pillow.pillow_id, error.error_traceback)

    def _get_random_doc(self):
        return {
            'id': uuid.uuid4().hex,
            'doc_type': 'CommCareCase',
            'type': 'mother',
            'domain': 'pillow-retry-domain',
        }


def _pillow_instance_from_config_with_mock_process_change(pillow_config):
    pillow_class = pillow_config.get_class()
    if pillow_config.instance_generator is None:
        instance = pillow_class()
    else:
        instance = pillow_config.get_instance()

    return instance
