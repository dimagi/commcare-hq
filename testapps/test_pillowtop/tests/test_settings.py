import os
from django.conf import settings
from django.test import TestCase, SimpleTestCase
import json
from pillowtop import get_all_pillow_instances
from pillowtop.listener import AliasedElasticPillow


class PillowtopSettingsTest(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    @classmethod
    def tearDownClass(cls):
        settings.PILLOWTOPS = cls._PILLOWTOPS

    def test_instantiate_all(self):
        all_pillows = get_all_pillow_instances()
        # todo: switch to TestFileMixin
        with open(os.path.join(os.path.dirname(__file__), 'data', 'all-pillow-meta.json')) as f:
            expected_meta = json.loads(f.read())
        for pillow in all_pillows:
            self.assertEqual(expected_meta[pillow.__class__.__name__], _pillow_meta_from_instance(pillow))


def _pillow_meta_from_instance(pillow_instance):
    props = {
        'class_name': pillow_instance.__class__.__name__,
        'db_name': pillow_instance.couch_db.dbname,
        'document_class': pillow_instance.document_class.__name__ if pillow_instance.document_class else None,
        'couch_filter': pillow_instance.couch_filter,
        'include_docs': pillow_instance.include_docs,
        'extra_args': pillow_instance.extra_args,
    }
    if isinstance(pillow_instance, AliasedElasticPillow):
        props.update({
            'es_alias': pillow_instance.es_alias,
            'es_type': pillow_instance.es_type,
            'es_index': pillow_instance.es_index,
            'unique_id': pillow_instance.get_unique_id(),
        })
    return props
