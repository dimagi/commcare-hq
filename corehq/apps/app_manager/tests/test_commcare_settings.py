from collections import defaultdict
from django.test import SimpleTestCase as TestCase
from corehq.apps.app_manager.commcare_settings import parse_condition_string, check_condition, circular_dependencies, SETTINGS, SETTINGS_LOOKUP
from corehq.apps.app_manager.models import Application


class CommCareSettingsTest(TestCase):
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
        self.assertFalse(circular_dependencies(SETTINGS, SETTINGS_LOOKUP))

    def test_get_profile_setting(self):
        test_app1, test_app2, test_app3 = self.set_up_apps(3)
        test_app1.profile["properties"]["unsent-time-limit"] = "30"
        test_app2.profile["properties"]["server-tether"] = "push-only"
        test_app3.profile["properties"]["server-tether"] = "sync"

        self.assertEqual(test_app1.get_profile_setting("properties", "unsent-time-limit"), "30")
        self.assertEqual(test_app2.get_profile_setting("properties", "unsent-time-limit"), "-1")
        self.assertEqual(test_app3.get_profile_setting("properties", "unsent-time-limit"), "5")
