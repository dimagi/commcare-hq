import os
from django.conf import settings
from django.test import TestCase
import json
from corehq.util.test_utils import TestFileMixin
from pillowtop import get_all_pillow_classes
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

    def test_instantiate_all(self):
        all_pillow_classes = get_all_pillow_classes()
        expected_meta = self.get_json('all-pillow-meta')

        for pillow_class in all_pillow_classes:
            self.assertEqual(expected_meta[pillow_class.__name__], _pillow_meta_from_class(pillow_class))

    def _rewrite_file(self, pillow_classes):
        # utility that should only be called manually
        with open(self.get_path('all-pillow-meta', 'json'), 'w') as f:
            f.write(
                json.dumps({cls.__name__: _pillow_meta_from_class(cls) for cls in pillow_classes},
                           indent=4)
            )


def _pillow_meta_from_class(pillow_class):
    is_elastic = issubclass(pillow_class, AliasedElasticPillow)
    kwargs = {'create_index': False, 'online': False} if is_elastic else {}
    pillow_instance = pillow_class(**kwargs)
    props = {
        'class_name': pillow_instance.__class__.__name__,
        'document_class': pillow_instance.document_class.__name__ if pillow_instance.document_class else None,
        'couch_filter': pillow_instance.couch_filter,
        'include_docs': pillow_instance.include_docs,
        'extra_args': pillow_instance.extra_args,
    }
    if is_elastic:
        props.update({
            'es_alias': pillow_instance.es_alias,
            'es_type': pillow_instance.es_type,
            'es_index': pillow_instance.es_index,
            'unique_id': pillow_instance.get_unique_id(),
        })
    return props
