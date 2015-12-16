import os
from django.conf import settings
from django.test import TestCase, override_settings
import json
from corehq.util.test_utils import TestFileMixin
from pillowtop.listener import AliasedElasticPillow, BasicPillow
from pillowtop.utils import get_all_pillow_configs


@override_settings(DEBUG=True)
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
        all_pillow_configs = list(get_all_pillow_configs())
        expected_meta = self.get_json('all-pillow-meta')

        self.assertEqual(len(all_pillow_configs), len(expected_meta))
        for pillow_config in all_pillow_configs:
            self.assertEqual(expected_meta[pillow_config.name], _pillow_meta_from_config(pillow_config))

    def _rewrite_file(self, pillow_configs):
        # utility that should only be called manually
        with open(self.get_path('all-pillow-meta', 'json'), 'w') as f:
            f.write(
                json.dumps({config.name: _pillow_meta_from_config(config) for config in pillow_configs},
                           indent=4, sort_keys=True)
            )


def _pillow_meta_from_config(pillow_config):
    pillow_class = pillow_config.get_class()
    is_elastic = issubclass(pillow_class, AliasedElasticPillow)
    if pillow_config.instance_generator == pillow_config.class_name:
        kwargs = {'online': False} if is_elastic else {}
        pillow_instance = pillow_class(**kwargs)
    else:
        # if we have a custom instance generator just use it
        pillow_instance = pillow_config.get_instance()
    props = {
        'name': pillow_config.name,
        'advertised_name': pillow_instance.get_name(),
        'full_class_name': pillow_config.class_name,
        'checkpoint_id': pillow_instance.checkpoint.checkpoint_id,
        'change_feed_type': type(pillow_instance.get_change_feed()).__name__,
    }
    if issubclass(pillow_class, BasicPillow):
        couchdb = pillow_instance.get_couch_db()
        props.update({
            'document_class': pillow_instance.document_class.__name__ if pillow_instance.document_class else None,
            'couch_filter': getattr(pillow_instance, 'couch_filter'),
            'include_docs': getattr(pillow_instance, 'include_docs'),
            'extra_args': getattr(pillow_instance, 'extra_args'),
            'couchdb_type': type(couchdb).__name__,
            'couchdb_uri': couchdb.uri if couchdb else None
        })
    if is_elastic:
        props.update({
            'es_alias': pillow_instance.es_alias,
            'es_type': pillow_instance.es_type,
            'es_index': pillow_instance.es_index,
            'unique_id': pillow_instance.get_unique_id(),
        })
    return props
