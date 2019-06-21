from __future__ import absolute_import
from __future__ import unicode_literals
import os
import yaml
from collections import defaultdict
from django.conf import settings
from django.test import SimpleTestCase
from corehq.apps.app_manager.commcare_settings import (
    get_custom_commcare_settings,
    get_commcare_settings_lookup,
    check_condition,
    circular_dependencies,
    parse_condition_string,
    PROFILE_SETTINGS_TO_TRANSLATE,
    LAYOUT_SETTINGS_TO_TRANSLATE,
)
from corehq.apps.app_manager.static_strings import STATICALLY_ANALYZABLE_TRANSLATIONS
from corehq.apps.app_manager.models import Application
import six
from six.moves import range
from io import open


class CommCareSettingsTest(SimpleTestCase):

    def set_up_apps(self, how_many):
        apps = []
        for _ in range(how_many):
            app = Application()
            app.profile["features"], app.profile["properties"] = {}, {}
            apps.append(app)
        return tuple(apps)

    def test_parse_condition(self):
        str1 = "{features.sense}='true'"
        cond1 = parse_condition_string(str1)
        self.assertEqual(cond1, {"type": "features", "id": "sense", "equals": "true"})
        str2 = "{features.sense}=true"
        cond2 = parse_condition_string(str2)
        self.assertEqual(cond2, {"type": "features", "id": "sense", "equals": True})
        str3 = "{properties.server-tether}='sync'"
        cond3 = parse_condition_string(str3)
        self.assertEqual(cond3, {"type": "properties", "id": "server-tether", "equals": "sync"})

    def test_check_condition(self):
        sense_condition = "{features.sense}='true'"
        server_tether_condition = "{properties.server-tether}='sync'"

        test_app1, test_app2, test_app3, test_app4 = self.set_up_apps(4)
        test_app1.profile["features"]["sense"] = True
        test_app2.profile["features"]["sense"] = False
        test_app3.profile["features"]["sense"] = 'true'
        test_app4.profile["properties"]["server-tether"] = 'sync'

        self.assertTrue(check_condition(test_app1, sense_condition))
        self.assertFalse(check_condition(test_app2, sense_condition))
        self.assertTrue(check_condition(test_app3, sense_condition))
        self.assertTrue(check_condition(test_app4, server_tether_condition))

    def test_circular_dependencies(self):
        def generate_lookup(settings):
            lookup = defaultdict(lambda: defaultdict(dict))
            for setting in settings:
                lookup[setting['type']][setting['id']] = setting
            return lookup

        settings1 = [
            {
                'contingent_default': [
                    {'condition': "{features.notsense}='true'", 'value': 'Yes'},
                    {'condition': "{features.sense}='true'", 'value': 'Yes'},
                ],
                'id': 'cc-login-images',
                'type': 'properties',
            },
            {
                'contingent_default': [{'condition': "{properties.server-tether}='true'", 'value': 'Yes'}],
                'id': 'sense',
                'type': 'features',
            },
            {
                'contingent_default': [{'condition': "{properties.cc-login-images}='true'", 'value': 'Yes'}],
                'id': 'server-tether',
                'type': 'properties',
            },
        ]

        self.assertTrue(circular_dependencies(settings1, generate_lookup(settings1)))
        self.assertFalse(circular_dependencies(get_custom_commcare_settings(), get_commcare_settings_lookup()))

    def test_get_profile_setting(self):
        test_app1, test_app2, test_app3 = self.set_up_apps(3)
        test_app1.profile["properties"]["unsent-time-limit"] = "30"
        test_app2.profile["properties"]["server-tether"] = "sync"

        self.assertEqual(test_app1.get_profile_setting("properties", "unsent-time-limit"), "30")
        self.assertEqual(test_app2.get_profile_setting("properties", "unsent-time-limit"), "5")

    def test_translated_strings(self):
        '''
        Ensures all yaml strings are translated. To auto generate these strings,
        see scripts/yaml_static_strings.py
        '''
        base_path = os.path.join(
            settings.BASE_DIR, 'corehq', 'apps', 'app_manager', 'static', 'app_manager', 'json'
        )

        files_and_keys_to_translate = [
            ('commcare-profile-settings.yaml', PROFILE_SETTINGS_TO_TRANSLATE),
            ('commcare-app-settings.yaml', PROFILE_SETTINGS_TO_TRANSLATE),
            ('commcare-settings-layout.yaml', LAYOUT_SETTINGS_TO_TRANSLATE),
        ]

        static_strings = set(STATICALLY_ANALYZABLE_TRANSLATIONS)

        for filepath, keys_to_translate in files_and_keys_to_translate:
            with open(os.path.join(base_path, filepath), encoding='utf-8') as f:
                cc_settings = yaml.safe_load(f)
                for setting in cc_settings:
                    for key in keys_to_translate:
                        value = setting.get(key)
                        if not value:
                            continue
                        if not isinstance(value, six.string_types):
                            for v in value:
                                self.assertIn(
                                    v,
                                    static_strings,
                                    'You need to add "{}" to static_strings.py'.format(v)
                                )
                        else:
                            self.assertIn(
                                value,
                                static_strings,
                                'You need to add "{}" to static_strings.py'.format(value)
                            )
