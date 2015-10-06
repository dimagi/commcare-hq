import os
from unittest import skip
from django.conf import settings
from django.test import TestCase
import json
from corehq.util.test_utils import TestFileMixin
from pillowtop import get_all_pillow_instances
from pillowtop.listener import AliasedElasticPillow


class PillowtopSettingsTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)
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

    @skip('this test depends on elasticsearch because pillows depend on elasticsearch')
    def test_instantiate_all(self):
        all_pillows = get_all_pillow_instances()
        expected_meta = self.get_json('all-pillow-meta')

        for pillow in all_pillows:
            self.assertEqual(expected_meta[pillow.__class__.__name__], _pillow_meta_from_instance(pillow))

    def _rewrite_file(self, pillows):
        # utility that should only be called manually
        with open(self.get_path('all-pillow-meta', 'json'), 'w') as f:
            f.write(json.dumps({p.__class__.__name__: _pillow_meta_from_instance(p) for p in pillows}, indent=4))


def _pillow_meta_from_instance(pillow_instance):
    props = {
        'class_name': pillow_instance.__class__.__name__,
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
