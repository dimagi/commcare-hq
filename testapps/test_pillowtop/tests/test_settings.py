import os
from django.conf import settings
from django.test import TestCase, override_settings
import json

from corehq.util.test_utils import TestFileMixin
from pillowtop.utils import get_all_pillow_configs
from testapps.test_pillowtop.utils import real_pillow_settings


@override_settings(DEBUG=True)
class PillowtopSettingsTest(TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)
    maxDiff = None

    def setUp(self):
        self.settings_context = real_pillow_settings()
        self.settings_context.__enter__()

    def tearDown(self):
        self.settings_context.__exit__(None, None, None)

    def test_instantiate_all(self):
        all_pillow_configs = list(get_all_pillow_configs())
        expected_meta = self.get_expected_meta()

        self.assertEqual(len(all_pillow_configs), len(expected_meta))
        for pillow_config in all_pillow_configs:
            self.assertEqual(expected_meta[pillow_config.name], _pillow_meta_from_config(pillow_config))

    def get_expected_meta(self):
        expected_meta = self.get_json('all-pillow-meta')
        for pillow, meta in expected_meta.items():
            if meta.get('couchdb_uri') is not None:
                meta['couchdb_uri'] = meta['couchdb_uri'].format(COUCH_SERVER_ROOT=settings.COUCH_SERVER_ROOT)
        return expected_meta

    def _rewrite_file(self, pillow_configs):
        # utility that should only be called manually
        with open(self.get_path('all-pillow-meta', 'json'), 'w', encoding='utf-8') as f:
            f.write(
                json.dumps({config.name: _pillow_meta_from_config(config) for config in pillow_configs},
                           indent=4, sort_keys=True)
            )


def _pillow_meta_from_config(pillow_config):
    pillow_class = pillow_config.get_class()
    if pillow_config.instance_generator is None:
        pillow_instance = pillow_class()
    else:
        # if we have a custom instance generator just use it
        pillow_instance = pillow_config.get_instance()
    props = {
        'name': pillow_instance.pillow_id,
        'advertised_name': pillow_instance.get_name(),
        'full_class_name': pillow_config.class_name,
        'checkpoint_id': pillow_instance.checkpoint.checkpoint_id,
        'change_feed_type': type(pillow_instance.get_change_feed()).__name__,
    }
    return props
